"""Evaluation REST API Routes"""
from fastapi import APIRouter
from app.evaluation.cases import EVALUATION_CASES
from app.evaluation.runner import run_evaluation_suite

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])

@router.get("/cases")
async def get_all_evaluation_cases():
    """Retrieve all 10 standardized adversarial and legitimate benchmark cases."""
    return {"cases": EVALUATION_CASES}

@router.post("/run")
async def trigger_full_evaluation():
    """
    Execute the automated 10-case evaluation matrix and return physical execution results.
    """
    return {"report": run_evaluation_suite()}
