
"""
Pyannote Speaker Diarization API
Open WebUI 0.13.3 Integration
Based on dev-v0.6.34
"""

import os
import subprocess
import tempfile
import threading
from pathlib import Path

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from pyannote.audio import Pipeline

MODEL_ID = "pyannote/speaker-diarization-3.1"
MAX_UPLOAD_BYTES = int(
    os.getenv("MAX_DIARIZATION_UPLOAD_MB", "500")
) * 1024 * 1024


app = FastAPI(
    title="Pyannote Diarization API",
    version="0.1.0",
)

pipeline = None
inference_lock = threading.Lock()


@app.on_event("startup")
def load_model():
    global pipeline

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not configured")

    pipeline = Pipeline.from_pretrained(
        MODEL_ID,
        use_auth_token=token,
    )

    if pipeline is None:
        raise RuntimeError("Failed to load Pyannote pipeline")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    pipeline.to(device)

    print(f"Pyannote loaded on {device}", flush=True)


@app.get("/health")
def health():
    return {
        "status": "ok" if pipeline is not None else "loading",
        "model": MODEL_ID,
        "cuda": torch.cuda.is_available(),
    }


def run_diarization(audio_path: Path):
    # Serialize GPU inference for the initial implementation.
    with inference_lock:
        result = pipeline(str(audio_path))

    segments = []
    speakers = set()

    for turn, _, speaker in result.itertracks(
        yield_label=True
    ):
        speakers.add(speaker)
        segments.append({
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "speaker": speaker,
        })

    return {
        "speakers": sorted(speakers),
        "num_speakers": len(speakers),
        "segments": segments,
    }


@app.post("/diarize")
async def diarize(file: UploadFile = File(...)):
    if pipeline is None:
        raise HTTPException(503, "Model not loaded")

    with tempfile.TemporaryDirectory(
        prefix="pyannote_"
    ) as tmp:
        workdir = Path(tmp)
        input_path = workdir / "input_audio"
        wav_path = workdir / "audio_16k.wav"

        size = 0

        try:
            with input_path.open("wb") as f:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            413, "Audio file too large"
                        )
                    f.write(chunk)

            if size == 0:
                raise HTTPException(400, "Empty audio file")

            # Normalize all audio to 16kHz mono PCM WAV.
            command = [
                "ffmpeg", "-nostdin", "-v", "error",
                "-y", "-i", str(input_path),
                "-map", "0:a:0",
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                str(wav_path),
            ]

            subprocess.run(
                command,
                check=True,
                capture_output=True,
                timeout=120,
            )

            if not wav_path.exists():
                raise HTTPException(
                    400, "Audio conversion failed"
                )

            import asyncio
            result = await asyncio.to_thread(
                run_diarization, wav_path
            )
            return result

        except subprocess.TimeoutExpired:
            raise HTTPException(
                408, "Audio conversion timed out"
            )
        except subprocess.CalledProcessError:
            raise HTTPException(
                400, "Invalid or unsupported audio"
            )
        finally:
            await file.close()
