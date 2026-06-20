"""Whisper model manager endpoints — list, download, select, delete."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import model_store, whisper
from app.services.state import set_state

router = APIRouter(prefix="/models", tags=["models"])


class ModelRequest(BaseModel):
    filename: str


@router.get("")
async def list_models():
    """Catalog + which are on disk + the active one + any download in progress."""
    # Report the *effective* model whisper actually uses (which falls back to a
    # downloaded model when the stored/default choice isn't on disk), so the UI
    # never marks a missing model as active.
    active = await whisper.get_active_model()
    return {
        "catalog": model_store.CATALOG,
        "downloaded": model_store.list_downloaded(),
        "active": active,
        "downloading": model_store.current_download(),
    }


@router.post("/download")
async def download_model(req: ModelRequest):
    """Start a background download of a model from HuggingFace."""
    result = await model_store.start_download(req.filename)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Download failed"))
    return result


@router.post("/select")
async def select_model(req: ModelRequest):
    """Switch the active model. Must already be downloaded."""
    if not model_store.is_valid_filename(req.filename):
        raise HTTPException(status_code=400, detail="Invalid model filename")
    if req.filename not in model_store.list_downloaded():
        raise HTTPException(status_code=400, detail="Model not downloaded yet")
    await set_state("active_model", req.filename)
    # Stop the running server so the next transcription reloads the new model.
    await whisper.restart_for_model_change()
    return {"ok": True, "active": req.filename}


@router.delete("/{filename}")
async def delete_model(filename: str):
    """Delete a downloaded model file (refused if it's the active one)."""
    active = await whisper.get_active_model()
    if filename == active:
        raise HTTPException(status_code=400, detail="Cannot delete the active model. Select another first.")
    result = model_store.delete_model(filename)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Delete failed"))
    return result
