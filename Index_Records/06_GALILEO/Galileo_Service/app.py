from fastapi import FastAPI
from pydantic import BaseModel

# Import your engines
from engines.galileo import run_clarity_cycle

# Import your new multi-user routes
from routes.login import router as login_router
from routes.markoff import router as markoff_router


app = FastAPI(title="GALILEO Clarity Engine")


# -----------------------------
# Request/Response Models
# -----------------------------
class ClarityRequest(BaseModel):
    input: str
    mode: str | None = "conversational"
    goal: str | None = None

class ClarityResponse(BaseModel):
    output: str
    mode: str
    diagnostics: dict


# -----------------------------
# GALILEO Clarify Endpoint
# -----------------------------
@app.post("/galileo/clarify", response_model=ClarityResponse)
async def clarify(req: ClarityRequest):
    result = await run_clarity_cycle(req.input, req.mode, req.goal)
    return ClarityResponse(**result)


# -----------------------------
# Multi-User Routes
# -----------------------------
app.include_router(login_router)
app.include_router(markoff_router)
