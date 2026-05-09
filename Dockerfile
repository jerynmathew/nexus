FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

COPY src/ src/
COPY personas/ personas/
RUN uv pip install --no-cache-dir .

FROM python:3.12-slim

RUN groupadd -r nexus && useradd -r -g nexus -d /app nexus

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY personas/ /app/personas/
COPY config.example.yaml /app/config.example.yaml

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/data && chown -R nexus:nexus /app

USER nexus

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import nexus" || exit 1

ENTRYPOINT ["python", "-m", "nexus"]
CMD ["run", "--config", "/app/config.yaml"]
