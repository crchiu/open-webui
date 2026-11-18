
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/models/huggingface

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Install the verified CUDA 12.1 PyTorch version.
RUN python -m pip install --no-cache-dir \
    torch==2.5.1 \
    torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu121

#COPY speaker_diarization/requirements-docker.txt \
#     /app/requirements.txt
#
#RUN python -m pip install --no-cache-dir \
#    -r /app/requirements.txt && \
#    python -m pip check

COPY speaker_diarization/requirements-docker.txt \
     /app/requirements.txt

COPY speaker_diarization/constraints.txt \
     /app/constraints.txt

RUN python -m pip install --no-cache-dir \
    -c /app/constraints.txt \
    -r /app/requirements.txt && \
    python -m pip check


COPY speaker_diarization/service.py \
     /app/speaker_diarization/service.py

RUN touch /app/speaker_diarization/__init__.py

EXPOSE 8001

CMD ["python", "-m", "uvicorn", \
     "speaker_diarization.service:app", \
     "--host", "0.0.0.0", \
     "--port", "8001"]

RUN python -c "\
import torch, torchaudio, pyannote.audio; \
assert torch.__version__.startswith('2.5.1'); \
assert torchaudio.__version__.startswith('2.5.1'); \
assert pyannote.audio.__version__ == '3.4.0'; \
print('Pyannote dependency check passed')"
