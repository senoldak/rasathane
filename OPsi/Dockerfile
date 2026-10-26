FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY static/ ./static/

RUN pip install --no-cache-dir . uvicorn && \
    mkdir -p data && \
    useradd -m -u 10001 opsi && \
    chown -R opsi:opsi /app

USER opsi

EXPOSE 8000

# Nightly scan: docker run --rm -v opsi-data:/app/data opsi nightly
# Service:     docker run -p 8000:8000 -v opsi-data:/app/data opsi serve
ENTRYPOINT ["python", "-m", "opsi.cli"]
CMD ["serve"]
