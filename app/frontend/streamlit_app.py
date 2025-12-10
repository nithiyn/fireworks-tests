"""Streamlit frontend for the loan underwriting demo."""

import streamlit as st
import requests
from typing import Any

# Backend API URL
API_BASE_URL = "http://localhost:8000"

# Required documents for completeness check
REQUIRED_DOCS = {"PAYSTUB", "BANK_STATEMENT", "ID"}

# Sample application data (matches backend SAMPLE_APPLICATION)
SAMPLE_APPLICATION = {
    "income": 8000,
    "debts": [2000, 400, 200],  # mortgage, car, cards
    "loan_amount": 400000,
    "property_value": 500000,
    "fico": 710,
    "uploaded_docs": ["PAYSTUB", "ID"],  # Missing BANK_STATEMENT
    "product": "Standard Mortgage"
}


def init_session_state():
    """Initialize session state variables."""
    if "app_data" not in st.session_state:
        st.session_state.app_data = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "processing" not in st.session_state:
        st.session_state.processing = False


def load_sample_application():
    """Load the sample application data into session state."""
    st.session_state.app_data = SAMPLE_APPLICATION.copy()


def call_orchestrator(message: str, app_data: dict[str, Any]) -> dict[str, Any]:
    """Call the orchestrator API endpoint."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/orchestrator",
            json={"message": message, "app_data": app_data},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "response": f"Error calling API: {str(e)}"}


def render_document_status(uploaded_docs: list[str]):
    """Render document status with checkmarks/X marks."""
    uploaded_set = set(doc.upper() for doc in uploaded_docs)
    
    for doc in REQUIRED_DOCS:
        if doc in uploaded_set:
            st.markdown(f"✅ {doc}")
        else:
            st.markdown(f"❌ {doc} *(missing)*")


def render_left_panel():
    """Render the left panel with application data."""
    st.header("📋 Application Data")
    
    # Load Sample Application button
    if st.button("📥 Load Sample Application", use_container_width=True):
        load_sample_application()
        st.rerun()
    
    if st.session_state.app_data is None:
        st.info("Click 'Load Sample Application' to populate the form with sample data.")
        return
    
    app_data = st.session_state.app_data
    
    st.divider()
    
    # Income
    st.subheader("💰 Income")
    st.metric("Monthly Income", f"${app_data['income']:,.0f}")
    
    # Debts
    st.subheader("💳 Monthly Debts")
    debt_labels = ["Mortgage/Rent", "Car Payment", "Credit Cards"]
    for i, debt in enumerate(app_data["debts"]):
        label = debt_labels[i] if i < len(debt_labels) else f"Debt {i+1}"
        st.text(f"  {label}: ${debt:,.0f}")
    total_debt = sum(app_data["debts"])
    st.metric("Total Monthly Debts", f"${total_debt:,.0f}")
    
    # Loan Details
    st.subheader("🏠 Loan Details")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Loan Amount", f"${app_data['loan_amount']:,.0f}")
    with col2:
        st.metric("Property Value", f"${app_data['property_value']:,.0f}")
    
    # FICO Score
    st.subheader("📊 Credit Score")
    st.metric("FICO Score", app_data["fico"])
    
    # Product Type
    st.subheader("📄 Product Type")
    st.text(app_data.get("product", "Standard Mortgage"))
    
    # Document Status
    st.subheader("📁 Document Status")
    render_document_status(app_data["uploaded_docs"])


def render_right_panel():
    """Render the right panel with chat interface."""
    st.header("💬 Loan Validation Chat")
    
    # Chat history display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").markdown(msg["content"])
    
    # Show loading state if processing
    if st.session_state.processing:
        with st.chat_message("assistant"):
            st.markdown("⏳ **Processing your request...**")
            with st.spinner("🤖 Orchestrator Agent is coordinating sub-agents..."):
                # Process the pending message
                process_pending_message()
        return
    
    # Quick action button
    col1, col2 = st.columns([1, 3])
    with col1:
        run_validation = st.button(
            "🚀 Run Validation",
            disabled=st.session_state.app_data is None or st.session_state.processing,
            use_container_width=True
        )
    
    # Chat input
    user_input = st.chat_input(
        "Ask about the loan application...",
        disabled=st.session_state.app_data is None or st.session_state.processing
    )
    
    # Handle Run Validation button
    if run_validation:
        user_input = "Please validate this loan application and provide a summary for the underwriter."
    
    # Process user input
    if user_input and st.session_state.app_data is not None:
        process_user_message(user_input)


def format_tool_calls(tool_calls: list[dict[str, Any]]) -> str:
    """Format tool calls for display in chat."""
    if not tool_calls:
        return ""
    
    lines = ["**🔧 Agent Tool Calls:**"]
    for i, tc in enumerate(tool_calls, 1):
        tool_name = tc.get("name", tc.get("function", {}).get("name", "unknown"))
        # Map tool names to friendly descriptions
        tool_descriptions = {
            "run_verification_agent": "📊 Verification Agent (DTI, LTV, Doc Check)",
            "run_policy_agent": "📋 Policy Agent (Compliance Check)",
            "summarize_for_underwriter": "📝 Generate Underwriter Summary",
            "compute_dti": "🧮 Compute DTI Ratio",
            "compute_ltv": "🧮 Compute LTV Ratio",
            "check_doc_completeness": "📁 Check Document Completeness",
            "get_policy_snippet": "📖 Retrieve Policy Rules",
        }
        friendly_name = tool_descriptions.get(tool_name, f"🔹 {tool_name}")
        lines.append(f"  {i}. {friendly_name} ✅")
    
    return "\n".join(lines)


def process_user_message(message: str):
    """Process a user message and get orchestrator response."""
    # Add user message to history
    st.session_state.chat_history.append({"role": "user", "content": message})
    
    # Show processing state
    st.session_state.processing = True
    st.rerun()


def process_pending_message():
    """Process any pending message (called while showing spinner)."""
    if not st.session_state.processing:
        return
    
    # Get the last user message
    user_messages = [m for m in st.session_state.chat_history if m["role"] == "user"]
    if not user_messages:
        st.session_state.processing = False
        return
    
    message = user_messages[-1]["content"]
    
    # Call orchestrator API
    result = call_orchestrator(message, st.session_state.app_data)
    
    # Format response with tool call progress
    if "error" in result and result.get("response", "").startswith("Error"):
        response_text = f"⚠️ {result['response']}"
    else:
        response_text = result.get("response", "No response received.")
        
        # Add tool call progress if available
        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            tool_call_text = format_tool_calls(tool_calls)
            response_text = f"{tool_call_text}\n\n---\n\n{response_text}"
    
    # Add assistant response to history
    st.session_state.chat_history.append({"role": "assistant", "content": response_text})
    
    st.session_state.processing = False
    st.rerun()


def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="Loan Underwriting Demo",
        page_icon="🏦",
        layout="wide"
    )
    
    # Initialize session state
    init_session_state()
    
    # App title
    st.title("🏦 Multi-Agent Loan Underwriting Demo")
    st.caption("Powered by Fireworks AI")
    
    # Two-column layout
    left_col, right_col = st.columns([1, 2])
    
    with left_col:
        render_left_panel()
    
    with right_col:
        render_right_panel()


if __name__ == "__main__":
    main()
