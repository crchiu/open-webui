
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



async def transcribe_with_word_timestamps(
    request: Request,
    wav_path: Path,
    language: str | None = None,
):
    from open_webui.config import (
        WHISPER_LANGUAGE,
        WHISPER_MULTILINGUAL,
        WHISPER_VAD_FILTER,
    )
    from open_webui.routers.audio import set_faster_whisper_model

    # Reuse the same model instance as Open WebUI STT.
    if request.app.state.faster_whisper_model is None:
        model_name = await Config.get("audio.stt.whisper_model")

        request.app.state.faster_whisper_model = (
            await asyncio.to_thread(
                set_faster_whisper_model,
                model_name,
            )
        )

    model = request.app.state.faster_whisper_model

    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Local Faster-Whisper model is not configured",
        )

    selected_language = WHISPER_LANGUAGE or language

    def run_whisper():
        segments, info = model.transcribe(
            str(wav_path),
            beam_size=5,
            vad_filter=WHISPER_VAD_FILTER,
            language=selected_language,
            multilingual=WHISPER_MULTILINGUAL,
            word_timestamps=True,
        )

        words = []
        full_text = []

        for segment in segments:
            full_text.append(segment.text)

            for word in segment.words or []:
                words.append({
                    "start": float(word.start),
                    "end": float(word.end),
                    "text": word.word,
                })

        return {
            "text": "".join(full_text).strip(),
            "language": info.language,
            "words": words,
        }

    return await asyncio.to_thread(run_whisper)


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


            # result = await request_pyannote(wav_path)

            # return {
            #    "filename": filename,
            #    "language": language,
            #    "speakers": result.get("speakers", []),
            #    "num_speakers": result.get("num_speakers", 0),
            #    "segments": result.get("segments", []),
            #}


            # 1. Speaker diarization
            result = await request_pyannote(wav_path)

            # 2. Word-level Whisper transcription
            whisper_result = await transcribe_with_word_timestamps(
                request,
                wav_path,
                language,
            )

            # 3. Align words with speaker turns
            from open_webui.routers.audio.alignment import align_words

            aligned = align_words(
                whisper_result["words"],
                result.get("segments", []),
            )

            return {
                "filename": filename,
                "language": whisper_result["language"],
                "text": whisper_result["text"],
                "speakers": result.get("speakers", []),
                "num_speakers": result.get("num_speakers", 0),
                "segments": result.get("segments", []),
                "diarization": aligned,
            }

        finally:
            await file.close()


async def analyze_saved_audio(
    request: Request,
    audio_path: str | Path,
    filename: str,
    language: str | None = None,
):
    """
    Analyze an existing uploaded audio file using
    Faster-Whisper + Pyannote speaker diarization.
    """
    from open_webui.routers.audio.alignment import align_words

    source = Path(audio_path)

    if not source.is_file():
        raise FileNotFoundError(
            f"Audio file not found: {source}"
        )

    if source.stat().st_size > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Audio file too large for diarization",
        )

    with tempfile.TemporaryDirectory(
        prefix="openwebui_diarize_file_"
    ) as tmp:
        wav_path = Path(tmp) / "audio_16k.wav"

        # 1. Convert audio into 16kHz mono WAV.
        await asyncio.to_thread(
            normalize_audio,
            source,
            wav_path,
        )

        # 2. Run Pyannote speaker diarization.
        speaker_result = await request_pyannote(wav_path)

        # 3. Run Faster-Whisper with word timestamps.
        whisper_result = await transcribe_with_word_timestamps(
            request,
            wav_path,
            language,
        )

        # 4. Align recognized words with speaker segments.
        aligned = align_words(
            whisper_result["words"],
            speaker_result.get("segments", []),
        )

        return {
            "filename": filename,
            "language": whisper_result["language"],
            "text": whisper_result["text"],
            "speakers": speaker_result.get("speakers", []),
            "num_speakers": speaker_result.get(
                "num_speakers", 0
            ),
            "segments": speaker_result.get("segments", []),
            "diarization": aligned,
        }
