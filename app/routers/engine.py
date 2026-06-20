"""Engine (whisper.cpp binary) management — GPU detection + CPU/CUDA install."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import engine

router = APIRouter(prefix="/engine", tags=["engine"])


class EngineRequest(BaseModel):
    variant: str  # "cpu" | "cuda"


@router.get("")
async def engine_status():
    """GPU info + which engine is installed + any install in progress."""
    return await engine.current()


@router.post("/install")
async def install_engine(req: EngineRequest):
    """Download + install a prebuilt engine (CPU or CUDA) and switch to it."""
    result = await engine.start_install(req.variant)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Install failed"))
    return result
