#  Multi-Agent Loan Underwriting Demo

A demonstration of agentic architecture for mortgage loan underwriting using Fireworks AI. The system features an Orchestrator Agent that coordinates Verification and Policy sub-agents via tool-calling to validate loan applications.

## Features

- **Multi-Agent Architecture**: Orchestrator coordinates specialized sub-agents
- **Deterministic Tools**: DTI, LTV calculations and document completeness checks
- **Simulated RAG**: Policy evaluation against configurable rule snippets
- **Interactive UI**: Two-panel Streamlit interface with chat-based interaction

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │  Application Data   │  │      Chat Interface         │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Orchestrator Agent                      │    │
│  │    ┌──────────────────┐  ┌──────────────────┐       │    │
│  │    │ Verification     │  │ Policy Agent     │       │    │
│  │    │ Agent            │  │                  │       │    │
│  │    └──────────────────┘  └──────────────────┘       │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌───────────────────────────┴───────────────────────────┐  │
│  │  Tools: compute_dti, compute_ltv, check_doc_complete  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Fireworks AI   │
                    │  (LLM API)      │
                    └─────────────────┘
```

## Prerequisites

- Python 3.10+
- Fireworks AI API key ([Get one here](https://fireworks.ai/))

## Setup

### 1. Clone and navigate to the project

```bash
cd loan-underwriting-demo
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and replace `your_api_key_here` with your Fireworks API key:

```
FIREWORKS_API_KEY=your_actual_api_key
FIREWORKS_MODEL=accounts/fireworks/models/llama-v3p1-70b-instruct
```

## Running the Application

You need to run both the backend and frontend in separate terminals.

### Terminal 1: Start the Backend (FastAPI)

```bash
uvicorn app.backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Terminal 2: Start the Frontend (Streamlit)

```bash
streamlit run app/frontend/streamlit_app.py
```

The UI will open automatically at `http://localhost:8501`

## Demo Walkthrough

Follow these steps to demonstrate the multi-agent loan underwriting system:

### Step 1: Load Sample Application

1. Open the Streamlit UI in your browser (`http://localhost:8501`)
2. Click the **"📥 Load Sample Application"** button in the left panel
3. Observe the pre-populated application data:
   - Monthly Income: $8,000
   - Monthly Debts: $2,600 total (mortgage, car, credit cards)
   - Loan Amount: $400,000
   - Property Value: $500,000
   - FICO Score: 710
   - Documents: Note that **BANK_STATEMENT is missing** (shown with ❌)

### Step 2: Run Validation

1. Click the **"🚀 Run Validation"** button in the chat panel
2. Watch as the Orchestrator Agent:
   - Acknowledges the request
   - Calls the Verification Agent to compute DTI and LTV ratios
   - Calls the Policy Agent to check compliance against policy rules
   - Generates a formatted underwriter summary

### Step 3: Review Results

The response will include:
- **DTI Calculation**: ~32.5% (below 43% threshold ✅)
- **LTV Calculation**: 80% (at threshold ⚠️)
- **FICO Check**: 710 (above 680 minimum ✅)
- **Document Status**: Missing BANK_STATEMENT ❌
- **Policy Decision**: Details on pass/fail with reason codes

### Step 4: Ask Follow-up Questions

Try asking questions in the chat:
- "What documents are missing?"
- "Would this application qualify for an FHA loan?"
- "What is the maximum loan amount this applicant could qualify for?"

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/sample-application` | GET | Get sample application data |
| `/orchestrator` | POST | Run orchestrator agent |

### Example API Call

```bash
curl -X POST http://localhost:8000/orchestrator \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Please validate this loan application",
    "app_data": {
      "income": 8000,
      "debts": [2000, 400, 200],
      "loan_amount": 400000,
      "property_value": 500000,
      "fico": 710,
      "uploaded_docs": ["PAYSTUB", "ID"],
      "product": "Standard Mortgage"
    }
  }'
```

## Project Structure

```
├── app/
│   ├── frontend/
│   │   └── streamlit_app.py      # Streamlit UI
│   └── backend/
│       ├── main.py               # FastAPI app
│       ├── models.py             # Pydantic models
│       ├── fireworks_client.py   # Fireworks SDK wrapper
│       ├── agents/
│       │   ├── orchestrator.py   # Orchestrator Agent
│       │   ├── verification.py   # Verification Agent
│       │   └── policy.py         # Policy Agent
│       └── tools/
│           ├── calculations.py   # DTI, LTV, doc check
│           └── policy.py         # Policy snippet retrieval
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration Options

### Model Selection

You can change the LLM model in `.env`:

```
FIREWORKS_MODEL=accounts/fireworks/models/llama-v3p1-70b-instruct
```

Recommended models for tool calling:
- `llama-v3p1-70b-instruct` - Good balance of capability and speed
- `llama-v3p1-405b-instruct` - Maximum capability
- `mixtral-8x22b-instruct` - Fast alternative

## Troubleshooting

### "FIREWORKS_API_KEY not configured"
Ensure your `.env` file exists and contains a valid API key.

### Backend not responding
Check that uvicorn is running on port 8000 and there are no firewall issues.

### Streamlit can't connect to backend
Verify the backend is running before starting the frontend. The frontend expects the API at `http://localhost:8000`.

## License

This is a demonstration project for educational purposes.
