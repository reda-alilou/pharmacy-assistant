FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOME=/tmp \
    MEDID_CATALOG_PATH=/app/data/metadata/ammps_medications_enriched.jsonl \
    MEDID_MODEL_DIR=/models \
    MEDID_LOG_FILE=/tmp/medid.log

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /models /app/data/metadata \
    && chown -R app:app /models /app/data

COPY services/image/requirements.txt ./requirements.txt
# CPU-only PyTorch avoids multi-gigabyte CUDA wheels in this demo image.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install --no-cache-dir -r requirements.txt

COPY services/image/medid ./medid
COPY data/imports/ammps_medications_enriched.jsonl ./data/metadata/ammps_medications_enriched.jsonl

USER 10001:10001
EXPOSE 8002
CMD ["uvicorn", "medid.api:app", "--host", "0.0.0.0", "--port", "8002", "--no-access-log"]
