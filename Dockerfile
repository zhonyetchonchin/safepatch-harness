FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SAFEPATCH_HOST=0.0.0.0
ENV SAFEPATCH_PORT=8000
ENV SAFEPATCH_DATA_DIR=/data/safepatch

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "safepatch", "--demo", "--public-demo", "--host", "0.0.0.0"]
