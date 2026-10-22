# The Mimir API: catalogue, discovery, accounts and community. Applies migrations and loads the seed (both
# idempotent) on start, then serves on $PORT.
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "python -m mde setup && exec uvicorn mde.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
