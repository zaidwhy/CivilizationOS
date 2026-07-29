# CivilizationOS backend (FastAPI). The 3D city frontend (web/) deploys
# separately to Vercel - this image serves the API + WebSocket only.
FROM python:3.12-slim
WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/ api/

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
