FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tools ./tools

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host ${RPI3_METEO_HOST:-0.0.0.0} --port ${RPI3_METEO_PORT:-8000}"]
