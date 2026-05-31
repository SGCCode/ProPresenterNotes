FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py config.json ./
COPY propresenter_notes/ ./propresenter_notes/

EXPOSE 3000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${APP_PORT:-3000} server:app"]
