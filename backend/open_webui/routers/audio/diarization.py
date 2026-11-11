
"""
Open WebUI 0.13.3 - Speaker Diarization API
Pyannote API integration (Phase 1)
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import aiohttp
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from open_webui.models.config import Config
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_permission

router = APIRouter()

PYANNOTE_API_URL = os.getenv(
    "PYANNOTE_API_URL",
    "http://host.docker.internal:8001"
)

MAX_AUDIO_BYTES = 20 * 1024 * 1024


def normalize_audio(src: Path, dst: Path):
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error",
            "-y", "-i", str(src),
            "-map", "0:a:0",
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(dst),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )


async def request_pyannote(wav_path: Path):
    timeout = aiohttp.ClientTimeout(total=600)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:
        with wav_path.open("rb") as audio:
            form = aiohttp.FormData()
            form.add_field(
                "file",
                audio,
                filename="audio.wav",
                content_type="audio/wav",
            )

            async with session.post(
                f"{PYANNOTE_API_URL}/diarize",
                data=form,
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=502,
                        detail="Pyannote processing failed",
                    )

                return await response.json()


@router.post("/diarize")
async def diarize_audio(
    request: Request,
    file: UploadFile = File(...),
    language: str | None = Form(None),
    user=Depends(get_verified_user),
):
    # Follow the existing Open WebUI STT permission.
    if user.role != "admin":
        permissions = await Config.get(
            "user.permissions"
        )
        permitted = await has_permission(
            user.id, "chat.stt", permissions
        )
        if not permitted:
            raise HTTPException(
                status_code=403,
                detail="STT permission denied",
            )

    allowed_extensions = await Config.get(
        "audio.stt.allowed_extensions", []
    )
    filename = os.path.basename(file.filename or "")
    extension = Path(filename).suffix.lower().lstrip(".")

    if allowed_extensions and extension not in allowed_extensions:
        raise HTTPException(400, "Unsupported audio extension")

    with tempfile.TemporaryDirectory(
        prefix="openwebui_diarize_"
    ) as tmp:
        workdir = Path(tmp)
        source = workdir / f"input.{extension or 'bin'}"
        wav_path = workdir / "audio_16k.wav"

        size = 0
        try:
            with source.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_AUDIO_BYTES:
                        raise HTTPException(
                            413, "Audio file too large"
                        )
                    output.write(chunk)

            if not size:
                raise HTTPException(400, "Empty audio file")

            try:
                await asyncio.to_thread(
                    normalize_audio, source, wav_path
                )
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ):
                raise HTTPException(
                    400, "Audio conversion failed"
                )

            result = await request_pyannote(wav_path)

            return {
                "filename": filename,
                "language": language,
                "speakers": result.get("speakers", []),
                "num_speakers": result.get("num_speakers", 0),
                "segments": result.get("segments", []),
            }

        finally:
            await file.close()
