"""Policy Agent for evaluating loan applications against policy rules."""

import json
from typing import Any

from ..fireworks_client import call_with_tools
from ..models import PolicyResult, FireworksAPIError, ToolExecutionError, ValidationError
from ..tools.policy import get_policy_snippet


POLICY_SYSTEM_PROMPT = """You are the Policy Agent. You evaluate loan applications against policy rules.

When given DTI, LTV, FICO, and a product type:
1. Call get_policy_snippet to retrieve the policy rules
2. Compare the metrics against the policy thresholds
3. Return PASS or FAIL with specific reason codes and explanation

Base your decision ONLY on the policy text provided. Do not use external knowledge.

After evaluating, respond with a JSON object in this exact format:
{
    "decision": "PASS" or "FAIL",
    "reason_codes": ["list", "of", "codes"],
    "explanation": "detailed explanation"
}

Reason codes should be like: "DTI_EXCEEDED", "LTV_EXCEEDED", "FICO_BELOW_MIN", "ALL_CRITERIA_MET"."""


POLICY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_policy_snippet",
            "description": "Retrieve policy rules for a loan product",
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {"type": "string", "description": "Loan product type (e.g., 'Standard Mortgage', 'FHA Loan')"}
                },
                "required": ["product"]
            }
        }
    }
]


def validate_policy_arguments(
    dti_percent: float, 
    ltv_percent: float, 
    fico: int
) -> None:
    """
    Validate policy agent input arguments.
    
    Raises:
        ValidationError: If arguments are invalid
    """
    if dti_percent is None:
        raise ValidationError("dti_percent", "DTI percentage cannot be None")
    if not isinstance(dti_percent, (int, float)):
        raise ValidationError("dti_percent", f"Expected number, got {type(dti_percent).__name__}")
    if dti_percent < 0:
        raise ValidationError("dti_percent", f"DTI cannot be negative, got {dti_percent}")
        
    if ltv_percent is None:
        raise ValidationError("ltv_percent", "LTV percentage cannot be None")
    if not isinstance(ltv_percent, (int, float)):
        raise ValidationError("ltv_percent", f"Expected number, got {type(ltv_percent).__name__}")
    if ltv_percent < 0:
        raise ValidationError("ltv_percent", f"LTV cannot be negative, got {ltv_percent}")
        
    if fico is None:
        raise ValidationError("fico", "FICO score cannot be None")
    if not isinstance(fico, (int, float)):
        raise ValidationError("fico", f"Expected number, got {type(fico).__name__}")
    if fico < 300 or fico > 850:
        raise ValidationError("fico", f"FICO score must be between 300-850, got {fico}")


def run_policy_agent(
    dti_percent: float, 
    ltv_percent: float, 
    fico: int, 
    product: str = "Standard Mortgage"
) -> PolicyResult:
    """
    Run the Policy Agent to evaluate loan metrics against policy rules.
    
    Args:
        dti_percent: Debt-to-income ratio as percentage
        ltv_percent: Loan-to-value ratio as percentage
        fico: FICO credit score
        product: Loan product type
        
    Returns:
        PolicyResult with decision, reason_codes, and explanation
    """
    # Validate input arguments
    try:
        validate_policy_arguments(dti_percent, ltv_percent, fico)
    except ValidationError as e:
        # Return a FAIL result with validation error
        return PolicyResult(
            decision="FAIL",
            reason_codes=["VALIDATION_ERROR"],
            explanation=str(e)
        )
    
    user_message = f"""Please evaluate the following loan metrics against policy rules:
- DTI: {dti_percent}%
- LTV: {ltv_percent}%
- FICO Score: {fico}
- Product Type: {product}

First retrieve the policy rules using get_policy_snippet, then evaluate the metrics and provide your decision."""

    messages = [
        {"role": "system", "content": POLICY_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    
    policy_text = None
    response = None
    
    # Agent loop with error handling
    max_iterations = 3
    try:
        for _ in range(max_iterations):
            response = call_with_tools(messages, POLICY_TOOLS)
            
            # Process tool calls if any
            if response["tool_calls"]:
                tool_results = []
                for tool_call in response["tool_calls"]:
                    if tool_call["name"] == "get_policy_snippet":
                        try:
                            result = get_policy_snippet(tool_call["arguments"].get("product", product))
                            policy_text = result["policy_text"]
                        except Exception as e:
                            result = {"error": str(e), "policy_text": ""}
                        
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "name": tool_call["name"],
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
            else:
                # No more tool calls - parse the final response
                break
                
    except FireworksAPIError as e:
        # API error - fall back to deterministic evaluation
        return parse_policy_response(None, dti_percent, ltv_percent, fico, policy_text)
    
    # Parse the final response to extract decision
    content = response["content"] if response else None
    return parse_policy_response(content, dti_percent, ltv_percent, fico, policy_text)


def parse_policy_response(
    content: str | None, 
    dti_percent: float, 
    ltv_percent: float, 
    fico: int,
    policy_text: str | None
) -> PolicyResult:
    """
    Parse the LLM response to extract policy decision.
    Falls back to deterministic evaluation if parsing fails.
    """
    # Try to parse JSON from response
    if content:
        try:
            # Look for JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)
                return PolicyResult(
                    decision=data.get("decision", "FAIL"),
                    reason_codes=data.get("reason_codes", []),
                    explanation=data.get("explanation", content)
                )
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Fallback: deterministic evaluation based on standard thresholds
    reason_codes = []
    explanations = []
    
    # Standard Mortgage thresholds
    max_dti = 43.0
    max_ltv = 80.0
    min_fico = 680
    
    if dti_percent > max_dti:
        reason_codes.append("DTI_EXCEEDED")
        explanations.append(f"DTI of {dti_percent}% exceeds maximum of {max_dti}%")
    
    if ltv_percent > max_ltv:
        reason_codes.append("LTV_EXCEEDED")
        explanations.append(f"LTV of {ltv_percent}% exceeds maximum of {max_ltv}%")
    
    if fico < min_fico:
        reason_codes.append("FICO_BELOW_MIN")
        explanations.append(f"FICO score of {fico} is below minimum of {min_fico}")
    
    if not reason_codes:
        reason_codes.append("ALL_CRITERIA_MET")
        decision = "PASS"
        explanation = f"All criteria met: DTI {dti_percent}% <= {max_dti}%, LTV {ltv_percent}% <= {max_ltv}%, FICO {fico} >= {min_fico}"
    else:
        decision = "FAIL"
        explanation = "; ".join(explanations)
    
    return PolicyResult(
        decision=decision,
        reason_codes=reason_codes,
        explanation=explanation
    )
