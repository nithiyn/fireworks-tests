"""Data models for the loan underwriting demo."""

from pydantic import BaseModel
from typing import Optional


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class ToolExecutionError(AgentError):
    """Error during tool execution."""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class FireworksAPIError(AgentError):
    """Error during Fireworks API call."""
    def __init__(self, message: str, retries: int = 0):
        self.retries = retries
        super().__init__(f"Fireworks API error after {retries} retries: {message}")


class ValidationError(AgentError):
    """Error during argument validation."""
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error for '{field}': {message}")


class ApplicationData(BaseModel):
    """Loan application data structure."""
    income: float  # Monthly income
    debts: list[float]  # List of monthly debt payments
    loan_amount: float
    property_value: float
    fico: int
    uploaded_docs: list[str]
    product: str = "Standard Mortgage"


class VerificationResult(BaseModel):
    """Results from the Verification Agent."""
    dti_percent: float
    ltv_percent: float
    missing_docs: list[str]
    notes: Optional[str] = None


class PolicyResult(BaseModel):
    """Results from the Policy Agent."""
    decision: str  # "PASS" or "FAIL"
    reason_codes: list[str]
    explanation: str


class UnderwriterSummary(BaseModel):
    """Formatted summary for underwriter review."""
    dti_summary: str
    ltv_summary: str
    fico_summary: str
    doc_conditions: list[str]
    policy_decision: str
    underwriter_note: str


# Sample application with intentionally missing BANK_STATEMENT
# to demonstrate the doc-check functionality (Requirement 1.3)
SAMPLE_APPLICATION = ApplicationData(
    income=8000,
    debts=[2000, 400, 200],  # mortgage, car, cards
    loan_amount=400000,
    property_value=500000,
    fico=710,
    uploaded_docs=["PAYSTUB", "ID"],  # Missing BANK_STATEMENT
    product="Standard Mortgage"
)
