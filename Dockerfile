# Container image for the regulations.gov MCP server, hosted by the Obot MCP gateway
# as a `containerized` server. It serves MCP over streamable HTTP at :8080/mcp with a
# /health readiness endpoint (see src/regulations_gov/app.py + routes.py).
#
# Mirrors the pattern used by the other GSA MCP servers (e.g. mcp-server-fema-nfhl):
# a plain pip install from a uv-exported requirements.txt, PYTHONPATH=/app/src,
# and PORT=8080 selecting the HTTP transport. No BuildKit-only features, so it
# builds cleanly under `docker buildx --platform linux/amd64`.
#

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PORT=8080

WORKDIR /app

COPY requirements.txt .
COPY pyproject.toml .
COPY README.md .
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

# PORT=8080 selects the HTTP transport at /mcp (see app.py transport selection).
CMD ["sh", "-c", "PORT=8080 python -m regulations_gov.app"]
