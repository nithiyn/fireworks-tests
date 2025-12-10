"""FastAPI backend for the loan underwriting demo."""

import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents.orchestrator import run_orchestrator
from .models import ApplicationData, SAMPLE_APPLICATION

# Load environment variables
load_dotenv()


# Request/Response schemas
class OrchestratorRequest(BaseModel):
    """Request schema for the orchestrator endpoint."""
    message: str
    app_data: dict[str, Any]


class OrchestratorResponse(BaseModel):
    """Response schema for the orchestrator endpoint."""
    response: str
    tool_calls: list[dict[str, Any]]
    verification_result: Optional[dict[str, Any]] = None
    policy_result: Optional[dict[str, Any]] = None
    summary: Optional[dict[str, Any]] = None


# Create FastAPI app
app = FastAPI(
    title="Loan Underwriting Demo API",
    description="Multi-agent loan underwriting demo using Fireworks AI",
    version="1.0.0"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for demo purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Loan Underwriting Demo API"}


@app.get("/sample-application")
async def get_sample_application():
    """Return the sample application data."""
    return SAMPLE_APPLICATION.model_dump()


@app.post("/orchestrator", response_model=OrchestratorResponse)
async def orchestrator_endpoint(request: OrchestratorRequest) -> OrchestratorResponse:
    """
    Invoke the Orchestrator Agent to validate a loan application.
    
    The orchestrator coordinates Verification and Policy sub-agents
    to compute metrics and check policy compliance.
    
    Requirements: 2.1, 2.5
    """
    # Validate API key is configured
    if not os.environ.get("FIREWORKS_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="FIREWORKS_API_KEY environment variable not configured"
        )
    
    try:
        # Run the orchestrator agent
        result = run_orchestrator(
            user_message=request.message,
            app_data=request.app_data
        )
        
        return OrchestratorResponse(
            response=result.get("response", ""),
            tool_calls=result.get("tool_calls", []),
            verification_result=result.get("verification_result"),
            policy_result=result.get("policy_result"),
            summary=result.get("summary")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator error: {str(e)}"
        )
