"""
FastAPI HTTP application for the GridWise Smart Campus Energy Optimizer.
Exposes required endpoints: GET /health and POST /optimize-energy.
"""
import time
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder

from app.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HealthResponse
)
from app.llm_interpreter import interpret_operator_notes
from app.optimizer import solve_energy_schedule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gridwise.api")

app = FastAPI(
    title="GridWise Smart Campus Energy Optimization API",
    description="LLM-Assisted Operator Directive Interpretation & Mathematical Energy Scheduling",
    version="1.0.0"
)

# Enable CORS for external judge harness access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return controlled HTTP 400 for malformed or structurally invalid JSON requests."""
    logger.warning(f"Malformed request on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({
            "detail": "Malformed JSON or structurally invalid request.",
            "errors": exc.errors()
        })
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Return controlled HTTP 400 for value and constraint validation errors."""
    logger.warning(f"Validation error on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": f"Validation error: {str(exc)}"
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Pass through standard HTTPExceptions cleanly without triggering 500 handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Return controlled HTTP 500 without leaking secrets, tokens, or raw stack traces."""
    logger.error(f"Controlled server error during request on {request.url.path}: {str(exc)}", exc_info=False)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "A controlled internal error occurred while processing the energy schedule."
        }
    )

# --- API Endpoints ---

@app.get("/health", response_model=HealthResponse, tags=["Readiness"])
async def health_check():
    """
    Readiness endpoint for the judging harness.
    Must return HTTP 200 with status 'ok'.
    """
    return HealthResponse(status="ok")

@app.post("/optimize-energy", response_model=OptimizeEnergyResponse, tags=["Optimization"])
async def optimize_energy(payload: OptimizeEnergyRequest):
    """
    Main endpoint:
    1. Interprets 1-3 operator notes via LLM with deterministic guardrails.
    2. Optimizes 24-hour campus energy schedule via SciPy HiGHS LP solver.
    3. Replays schedule and returns complete verified plan with recalculated metrics.
    """
    start_time = time.perf_counter()
    logger.info(f"Processing scenario '{payload.scenario_id}' with {len(payload.operator_notes)} notes...")

    # Step 1: Interpret operator notes through LLM & Guardrails
    directives = await interpret_operator_notes(
        operator_notes=payload.operator_notes,
        battery=payload.battery
    )

    # Step 2: Solve 24-hour optimization problem
    response = solve_energy_schedule(
        scenario_id=payload.scenario_id,
        hours=payload.hours,
        battery=payload.battery,
        directives=directives
    )

    elapsed = time.perf_counter() - start_time
    logger.info(f"Scenario '{payload.scenario_id}' completed in {elapsed:.3f}s. Cost: {response.total_cost_bdt:.2f} BDT")
    return response

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
