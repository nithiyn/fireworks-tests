"""Orchestrator Agent that coordinates Verification and Policy sub-agents."""

import json
from typing import Any

from ..fireworks_client import call_with_tools
from ..models import (
    ApplicationData, 
    VerificationResult, 
    PolicyResult, 
    UnderwriterSummary,
    FireworksAPIError,
    ToolExecutionError,
    ValidationError,
    AgentError
)
from .verification import run_verification_agent
from .policy import run_policy_agent


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Loan Orchestrator Agent. You help users validate mortgage loan applications.

When a user asks to validate an application:
1. Call run_verification_agent to compute DTI, LTV, and check documents
2. Call run_policy_agent with the verification results to check policy compliance
3. Call summarize_for_underwriter to generate the final summary

Always explain what you're doing and present results clearly."""


ORCHESTRATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_verification_agent",
            "description": "Run the Verification Agent to compute DTI, LTV ratios and check document completeness",
            "parameters": {
                "type": "object",
                "properties": {
                    "income": {"type": "number", "description": "Monthly income in dollars"},
                    "debts": {"type": "array", "items": {"type": "number"}, "description": "List of monthly debt payments"},
                    "loan_amount": {"type": "number", "description": "Requested loan amount"},
                    "property_value": {"type": "number", "description": "Property value"},
                    "uploaded_docs": {"type": "array", "items": {"type": "string"}, "description": "List of uploaded document types"}
                },
                "required": ["income", "debts", "loan_amount", "property_value", "uploaded_docs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_policy_agent",
            "description": "Run the Policy Agent to check if metrics meet policy requirements",
            "parameters": {
                "type": "object",
                "properties": {
                    "dti_percent": {"type": "number", "description": "Debt-to-income ratio as percentage"},
                    "ltv_percent": {"type": "number", "description": "Loan-to-value ratio as percentage"},
                    "fico": {"type": "integer", "description": "FICO credit score"},
                    "product": {"type": "string", "description": "Loan product type", "default": "Standard Mortgage"}
                },
                "required": ["dti_percent", "ltv_percent", "fico"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_for_underwriter",
            "description": "Generate a formatted summary for the underwriter",
            "parameters": {
                "type": "object",
                "properties": {
                    "verification_result": {
                        "type": "object",
                        "description": "Results from verification agent",
                        "properties": {
                            "dti_percent": {"type": "number"},
                            "ltv_percent": {"type": "number"},
                            "missing_docs": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    "policy_result": {
                        "type": "object",
                        "description": "Results from policy agent",
                        "properties": {
                            "decision": {"type": "string"},
                            "reason_codes": {"type": "array", "items": {"type": "string"}},
                            "explanation": {"type": "string"}
                        }
                    },
                    "fico": {"type": "integer", "description": "FICO credit score"}
                },
                "required": ["verification_result", "policy_result", "fico"]
            }
        }
    }
]


def summarize_for_underwriter(
    verification_result: dict[str, Any],
    policy_result: dict[str, Any],
    fico: int
) -> UnderwriterSummary:
    """
    Generate a formatted summary for underwriter review.
    
    Args:
        verification_result: Results from verification agent
        policy_result: Results from policy agent
        fico: FICO credit score
        
    Returns:
        UnderwriterSummary with formatted results
    """
    dti = verification_result.get("dti_percent", 0)
    ltv = verification_result.get("ltv_percent", 0)
    missing_docs = verification_result.get("missing_docs", [])
    
    # Standard thresholds
    max_dti = 43.0
    max_ltv = 80.0
    min_fico = 680
    
    # Build summaries with threshold comparisons
    dti_status = "✓ PASS" if dti <= max_dti else "✗ FAIL"
    dti_summary = f"DTI: {dti}% (max {max_dti}%) - {dti_status}"
    
    ltv_status = "✓ PASS" if ltv <= max_ltv else "✗ FAIL"
    ltv_summary = f"LTV: {ltv}% (max {max_ltv}%) - {ltv_status}"
    
    fico_status = "✓ PASS" if fico >= min_fico else "✗ FAIL"
    fico_summary = f"FICO: {fico} (min {min_fico}) - {fico_status}"
    
    # Document conditions
    doc_conditions = []
    if missing_docs:
        for doc in missing_docs:
            doc_conditions.append(f"Missing: {doc}")
    else:
        doc_conditions.append("All required documents present")
    
    # Policy decision
    decision = policy_result.get("decision", "UNKNOWN")
    explanation = policy_result.get("explanation", "")
    
    # Generate underwriter note
    if decision == "PASS" and not missing_docs:
        underwriter_note = "Application meets all policy criteria. Recommend approval pending standard verification."
    elif decision == "PASS" and missing_docs:
        underwriter_note = f"Application meets financial criteria but requires additional documentation: {', '.join(missing_docs)}. Conditional approval recommended."
    else:
        reason_codes = policy_result.get("reason_codes", [])
        underwriter_note = f"Application does not meet policy criteria. Issues: {', '.join(reason_codes)}. Manual review required."
    
    return UnderwriterSummary(
        dti_summary=dti_summary,
        ltv_summary=ltv_summary,
        fico_summary=fico_summary,
        doc_conditions=doc_conditions,
        policy_decision=f"{decision}: {explanation}",
        underwriter_note=underwriter_note
    )


def validate_orchestrator_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    """
    Validate arguments for orchestrator tools.
    
    Raises:
        ValidationError: If required arguments are missing or invalid
    """
    if tool_name == "run_verification_agent":
        required = ["income", "debts", "loan_amount", "property_value", "uploaded_docs"]
        for arg in required:
            if arg not in arguments:
                raise ValidationError(arg, f"Required argument '{arg}' missing")
                
    elif tool_name == "run_policy_agent":
        required = ["dti_percent", "ltv_percent", "fico"]
        for arg in required:
            if arg not in arguments:
                raise ValidationError(arg, f"Required argument '{arg}' missing")
                
    elif tool_name == "summarize_for_underwriter":
        required = ["verification_result", "policy_result", "fico"]
        for arg in required:
            if arg not in arguments:
                raise ValidationError(arg, f"Required argument '{arg}' missing")


def execute_orchestrator_tool(
    tool_name: str, 
    arguments: dict[str, Any],
    app_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute an orchestrator tool by name.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments for the tool
        app_data: Application data context
        
    Returns:
        Tool execution result as dict
        
    Raises:
        ToolExecutionError: If tool execution fails
        ValidationError: If arguments are invalid
    """
    # Validate arguments first
    try:
        validate_orchestrator_arguments(tool_name, arguments)
    except ValidationError as e:
        raise ToolExecutionError(tool_name, str(e))
    
    try:
        if tool_name == "run_verification_agent":
            result = run_verification_agent(arguments)
            return result.model_dump()
        
        elif tool_name == "run_policy_agent":
            result = run_policy_agent(
                dti_percent=arguments["dti_percent"],
                ltv_percent=arguments["ltv_percent"],
                fico=arguments["fico"],
                product=arguments.get("product", "Standard Mortgage")
            )
            return result.model_dump()
        
        elif tool_name == "summarize_for_underwriter":
            result = summarize_for_underwriter(
                verification_result=arguments["verification_result"],
                policy_result=arguments["policy_result"],
                fico=arguments["fico"]
            )
            return result.model_dump()
        
        else:
            raise ToolExecutionError(tool_name, f"Unknown tool: {tool_name}")
            
    except (ValidationError, ToolExecutionError, AgentError):
        raise
    except Exception as e:
        raise ToolExecutionError(tool_name, str(e))


def run_orchestrator(
    user_message: str,
    app_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Run the Orchestrator Agent to coordinate loan validation.
    
    Args:
        user_message: User's request message
        app_data: Application data dict
        
    Returns:
        Dict with response text and tool_calls trace
    """
    # Build context message with application data
    context = f"""Current loan application data:
- Monthly Income: ${app_data['income']:,.2f}
- Monthly Debts: {app_data['debts']} (total: ${sum(app_data['debts']):,.2f})
- Loan Amount: ${app_data['loan_amount']:,.2f}
- Property Value: ${app_data['property_value']:,.2f}
- FICO Score: {app_data['fico']}
- Uploaded Documents: {app_data['uploaded_docs']}
- Product Type: {app_data.get('product', 'Standard Mortgage')}"""

    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\nUser request: {user_message}"}
    ]
    
    tool_calls_trace = []
    verification_result = None
    policy_result = None
    final_summary = None
    errors = []
    response = None
    
    # Agent loop with error handling
    max_iterations = 10
    try:
        for _ in range(max_iterations):
            response = call_with_tools(messages, ORCHESTRATOR_TOOLS)
            
            # If no tool calls, we're done
            if not response["tool_calls"]:
                break
            
            # Process each tool call
            tool_results = []
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["name"]
                arguments = tool_call["arguments"]
                
                # Execute the tool with error handling
                try:
                    result = execute_orchestrator_tool(tool_name, arguments, app_data)
                    
                    # Track results
                    if tool_name == "run_verification_agent":
                        verification_result = result
                    elif tool_name == "run_policy_agent":
                        policy_result = result
                    elif tool_name == "summarize_for_underwriter":
                        final_summary = result
                        
                except (ToolExecutionError, ValidationError, AgentError) as e:
                    # Log error but continue
                    errors.append(str(e))
                    result = {"error": str(e)}
                
                tool_results.append({
                    "tool_call_id": tool_call["id"],
                    "name": tool_name,
                    "arguments": arguments,
                    "result": result
                })
                
                tool_calls_trace.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                })
            
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": response["content"],
                "tool_calls": [
                    {
                        "id": tc["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"])
                        }
                    }
                    for tc in tool_results
                ]
            })
            
            # Add tool results
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": json.dumps(tr["result"])
                })
                
    except FireworksAPIError as e:
        errors.append(str(e))
    
    # Format final response
    final_response = response.get("content", "") if response else ""
    
    # If we have a summary, format it nicely
    if final_summary:
        formatted_summary = format_summary(final_summary)
        if not final_response:
            final_response = formatted_summary
    
    # Append errors to response if any
    if errors:
        error_msg = "\n\n⚠️ Errors encountered during processing:\n" + "\n".join(f"• {e}" for e in errors)
        final_response = final_response + error_msg if final_response else error_msg
    
    return {
        "response": final_response,
        "tool_calls": tool_calls_trace,
        "verification_result": verification_result,
        "policy_result": policy_result,
        "summary": final_summary,
        "errors": errors if errors else None
    }


def format_summary(summary: dict[str, Any]) -> str:
    """Format the underwriter summary for display."""
    lines = [
        "=" * 50,
        "UNDERWRITER SUMMARY",
        "=" * 50,
        "",
        "FINANCIAL METRICS:",
        f"  • {summary['dti_summary']}",
        f"  • {summary['ltv_summary']}",
        f"  • {summary['fico_summary']}",
        "",
        "DOCUMENTATION STATUS:",
    ]
    
    for condition in summary.get("doc_conditions", []):
        lines.append(f"  • {condition}")
    
    lines.extend([
        "",
        "POLICY DECISION:",
        f"  {summary['policy_decision']}",
        "",
        "UNDERWRITER NOTE:",
        f"  {summary['underwriter_note']}",
        "=" * 50
    ])
    
    return "\n".join(lines)
