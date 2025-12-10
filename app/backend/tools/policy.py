"""Policy tools for loan evaluation (simulated RAG)."""

# Simulated RAG - hardcoded policy snippets for demo
POLICY_SNIPPETS = {
    "Standard Mortgage": """
STANDARD MORTGAGE POLICY GUIDELINES:
- Maximum DTI: 43%
- Maximum LTV: 80%
- Minimum FICO: 680
- Required Documents: Paystub (last 30 days), Bank Statement (last 2 months), Government ID
""",
    "FHA Loan": """
FHA LOAN POLICY GUIDELINES:
- Maximum DTI: 50%
- Maximum LTV: 96.5%
- Minimum FICO: 580
- Required Documents: Paystub, Bank Statement, ID, Tax Returns (2 years)
"""
}


def get_policy_snippet(product: str) -> dict:
    """Retrieve policy rules for a product (simulated RAG).
    
    Args:
        product: Loan product type (e.g., "Standard Mortgage", "FHA Loan")
        
    Returns:
        Dictionary with product name and policy_text
    """
    snippet = POLICY_SNIPPETS.get(product, POLICY_SNIPPETS["Standard Mortgage"])
    return {
        "product": product,
        "policy_text": snippet
    }
