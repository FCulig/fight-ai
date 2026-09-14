from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models.eval_run import EvalRunCreate, EvalRunResponse, EvalRunSummary, FixtureSummary
from app.services import eval_run_service

router = APIRouter()


@router.get("/fixtures", response_model=List[FixtureSummary])
def get_fixtures():
    return eval_run_service.list_fixtures()


@router.get("/", response_model=List[EvalRunSummary])
def get_runs(reference_fight_id: int, scored_fight_id: Optional[int] = None):
    return eval_run_service.list_runs(reference_fight_id, scored_fight_id)


@router.get("/{run_id}", response_model=EvalRunResponse)
def get_run(run_id: int):
    run = eval_run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return run


@router.post("/", response_model=EvalRunResponse, status_code=201)
def create_run(payload: EvalRunCreate):
    try:
        return eval_run_service.create_run(
            payload.reference_fight_id, payload.scored_fight_id, payload.tolerance_secs,
        )
    except eval_run_service.InvalidPairing as e:
        raise HTTPException(status_code=400, detail=str(e))
