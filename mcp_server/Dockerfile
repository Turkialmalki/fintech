# Separately deployable MCP server (shares the domain package with the API).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/app /srv/app
COPY backend/rip_mcp /srv/rip_mcp
ENV PYTHONPATH=/srv
RUN useradd --uid 10001 rip
USER 10001
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=3s CMD curl -fsS http://localhost:8765/healthz || exit 1
CMD ["python", "-m", "rip_mcp", "--transport", "streamable-http", "--port", "8765"]
