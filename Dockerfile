FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS test

COPY server.py config.json ./
COPY propresenter_notes/ ./propresenter_notes/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]

FROM base AS runtime

COPY server.py config.json ./
COPY propresenter_notes/ ./propresenter_notes/

EXPOSE 3000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${APP_PORT:-3000} server:app"]
