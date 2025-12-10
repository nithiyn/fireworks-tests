"""Deterministic calculation tools for loan verification."""

from ..models import ToolExecutionError, ValidationError


def validate_positive_number(value: float, field_name: str) -> None:
    """Validate that a number is positive and non-zero for division."""
    if value is None:
        raise ValidationError(field_name, "Value cannot be None")
    if not isinstance(value, (int, float)):
        raise ValidationError(field_name, f"Expected number, got {type(value).__name__}")
    if value <= 0:
        raise ValidationError(field_name, f"Value must be positive, got {value}")


def compute_dti(income: float, debts: list[float]) -> dict:
    """Calculate debt-to-income ratio.
    
    Args:
        income: Monthly income in dollars
        debts: List of monthly debt payments
        
    Returns:
        Dictionary with dti_ratio and dti_percent
        
    Raises:
        ValidationError: If income is zero or negative
        ToolExecutionError: If calculation fails
    """
    try:
        # Validate income to prevent division by zero
        validate_positive_number(income, "income")
        
        if debts is None:
            debts = []
        
        total_debt = sum(debts)
        ratio = total_debt / income
        return {
            "dti_ratio": ratio,
            "dti_percent": round(100 * ratio, 1)
        }
    except ValidationError:
        raise
    except Exception as e:
        raise ToolExecutionError("compute_dti", str(e))


def compute_ltv(loan_amount: float, property_value: float) -> dict:
    """Calculate loan-to-value ratio.
    
    Args:
        loan_amount: Requested loan amount
        property_value: Property value
        
    Returns:
        Dictionary with ltv_ratio and ltv_percent
        
    Raises:
        ValidationError: If property_value is zero or negative
        ToolExecutionError: If calculation fails
    """
    try:
        # Validate property_value to prevent division by zero
        validate_positive_number(property_value, "property_value")
        
        if loan_amount is None or loan_amount < 0:
            raise ValidationError("loan_amount", f"Loan amount must be non-negative, got {loan_amount}")
        
        ratio = loan_amount / property_value
        return {
            "ltv_ratio": ratio,
            "ltv_percent": round(100 * ratio, 1)
        }
    except ValidationError:
        raise
    except Exception as e:
        raise ToolExecutionError("compute_ltv", str(e))


def check_doc_completeness(uploaded_docs: list[str]) -> dict:
    """Check for missing required documents.
    
    Args:
        uploaded_docs: List of uploaded document types
        
    Returns:
        Dictionary with missing_docs list and complete boolean
    """
    required = {"PAYSTUB", "BANK_STATEMENT", "ID"}
    uploaded_set = set(doc.upper() for doc in uploaded_docs)
    missing = list(required - uploaded_set)
    return {
        "missing_docs": missing,
        "complete": len(missing) == 0
    }
