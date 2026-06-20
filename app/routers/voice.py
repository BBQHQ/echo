"""Voice transcription endpoints."""

from fastapi import APIRouter, UploadFile, File, Query
from app.services.whisper import transcribe, get_status, warm_up
from app.services import voice_log

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe an uploaded audio file with the local whisper.cpp server."""
    audio_bytes = await file.read()
    result = await transcribe(audio_bytes, filename=file.filename or "audio.wav")

    if "text" in result and result["text"]:
        source = "upload" if file.filename and file.filename != "recording.webm" else "recording"
        await voice_log.log_transcription(
            text=result["text"],
            duration_ms=result.get("duration_ms"),
            source=source,
        )

    return result


@router.get("/history")
async def voice_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return voice transcription history, newest first."""
    items = await voice_log.get_history(limit=limit, offset=offset)
    total = await voice_log.get_count()
    return {"items": items, "total": total}


@router.delete("/history/{entry_id}")
async def delete_voice_entry(entry_id: int):
    """Delete a voice log entry."""
    ok = await voice_log.delete_entry(entry_id)
    return {"deleted": ok}


@router.post("/warmup")
async def whisper_warmup():
    """Start whisper server in the background so it's ready when recording ends."""
    return await warm_up()


@router.get("/status")
async def whisper_status():
    """Current transcription backend status."""
    return await get_status()
