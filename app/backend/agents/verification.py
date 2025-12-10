"""Verification Agent for computing DTI, LTV, and checking document completeness."""

import json
from typing import Any

from ..fireworks_client import call_with_tools
from ..models import (
    VerificationResult, 
    ToolExecutionError, 
    ValidationError,
    FireworksAPIError,
    AgentError
)
from ..tools.calculations import compute_dti, compute_ltv, check_doc_completeness


VERIFICATION_SYSTEM_PROMPT = """You are the Verification Agent. Given loan application data, use your tools to:
1. Compute DTI ratio using compute_dti
2. Compute LTV ratio using compute_ltv  
3. Check document completeness using check_doc_completeness

Return all results in a structured format. Do not invent or estimate numbers - only use values from tool results."""


VERIFICATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "compute_dti",
            "description": "Calculate debt-to-income ratio",
            "parameters": {
                "type": "object",
                "properties": {
                    "income": {"type": "number", "description": "Monthly income in dollars"},
                    "debts": {"type": "array", "items": {"type": "number"}, "description": "List of monthly debt payments"}
                },
                "required": ["income", "debts"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_ltv",
            "description": "Calculate loan-to-value ratio",
            "parameters": {
                "type": "object",
                "properties": {
                    "loan_amount": {"type": "number", "description": "Requested loan amount"},
                    "property_value": {"type": "number", "description": "Property value"}
                },
                "required": ["loan_amount", "property_value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_doc_completeness",
            "description": "Check which required documents are missing",
            "parameters": {
                "type": "object",
                "properties": {
                    "uploaded_docs": {"type": "array", "items": {"type": "string"}, "description": "List of uploaded document types"}
                },
                "required": ["uploaded_docs"]
            }
        }
    }
]


# Map tool names to their implementations
TOOL_IMPLEMENTATIONS = {
    "compute_dti": compute_dti,
    "compute_ltv": compute_ltv,
    "check_doc_completeness": check_doc_completeness,
}

# Required arguments for each tool
TOOL_REQUIRED_ARGS = {
    "compute_dti": ["income", "debts"],
    "compute_ltv": ["loan_amount", "property_value"],
    "check_doc_completeness": ["uploaded_docs"],
}


def validate_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    """
    Validate tool arguments before execution.
    
    Args:
        tool_name: Name of the tool to validate for
        arguments: Arguments to validate
        
    Raises:
        ValidationError: If required arguments are missing or invalid
    """
    if tool_name not in TOOL_REQUIRED_ARGS:
        raise ToolExecutionError(tool_name, f"Unknown tool: {tool_name}")
    
    required = TOOL_REQUIRED_ARGS[tool_name]
    for arg in required:
        if arg not in arguments:
            raise ValidationError(arg, f"Required argument '{arg}' missing for tool '{tool_name}'")
        if arguments[arg] is None:
            raise ValidationError(arg, f"Argument '{arg}' cannot be None")


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a tool by name with given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool
        
    Returns:
        Tool execution result
        
    Raises:
        ToolExecutionError: If tool execution fails
        ValidationError: If arguments are invalid
    """
    # Validate arguments first
    validate_tool_arguments(tool_name, arguments)
    
    if tool_name not in TOOL_IMPLEMENTATIONS:
        raise ToolExecutionError(tool_name, f"Unknown tool: {tool_name}")
    
    try:
        return TOOL_IMPLEMENTATIONS[tool_name](**arguments)
    except (ValidationError, ToolExecutionError):
        raise
    except Exception as e:
        raise ToolExecutionError(tool_name, str(e))


def run_verification_agent(app_data: dict[str, Any]) -> VerificationResult:
    """
    Run the Verification Agent to compute DTI, LTV, and check documents.
    
    Args:
        app_data: Application data containing income, debts, loan_amount, 
                  property_value, and uploaded_docs
                  
    Returns:
        VerificationResult with dti_percent, ltv_percent, and missing_docs
        
    Raises:
        AgentError: If a critical error occurs during verification
    """
    # Build the user message with application data
    user_message = f"""Please verify the following loan application:
- Monthly Income: ${app_data['income']:,.2f}
- Monthly Debts: {app_data['debts']}
- Loan Amount: ${app_data['loan_amount']:,.2f}
- Property Value: ${app_data['property_value']:,.2f}
- Uploaded Documents: {app_data['uploaded_docs']}

Use your tools to compute DTI, LTV, and check document completeness."""

    messages = [
        {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    # Track results from tool executions
    dti_result = None
    ltv_result = None
    doc_result = None
    errors = []
    
    # Agent loop - continue until all tools are called or no more tool calls
    max_iterations = 5
    response = None
    
    try:
        for _ in range(max_iterations):
            response = call_with_tools(messages, VERIFICATION_TOOLS)
            
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
                    result = execute_tool(tool_name, arguments)
                    
                    # Store results by tool type
                    if tool_name == "compute_dti":
                        dti_result = result
                    elif tool_name == "compute_ltv":
                        ltv_result = result
                    elif tool_name == "check_doc_completeness":
                        doc_result = result
                    
                    tool_results.append({
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "result": result
                    })
                except (ValidationError, ToolExecutionError) as e:
                    # Log the error but continue with other tools
                    errors.append(str(e))
                    tool_results.append({
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "result": {"error": str(e)}
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
                            "arguments": json.dumps(response["tool_calls"][i]["arguments"])
                        }
                    }
                    for i, tc in enumerate(tool_results)
                ]
            })
            
            # Add tool results
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": json.dumps(tr["result"])
                })
            
            # Check if we have all results
            if dti_result and ltv_result and doc_result:
                break
                
    except FireworksAPIError as e:
        # API error - include in notes but return partial results
        errors.append(str(e))
    
    # Build notes including any errors
    notes = response.get("content") if response else None
    if errors:
        error_note = "Errors encountered: " + "; ".join(errors)
        notes = f"{notes}\n\n{error_note}" if notes else error_note
    
    # Build the verification result with whatever we have
    return VerificationResult(
        dti_percent=dti_result["dti_percent"] if dti_result else 0.0,
        ltv_percent=ltv_result["ltv_percent"] if ltv_result else 0.0,
        missing_docs=doc_result["missing_docs"] if doc_result else [],
        notes=notes
    )
