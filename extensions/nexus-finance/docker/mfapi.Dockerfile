FROM python:3.12-slim

RUN groupadd -r mcp && useradd -r -g mcp mcp

WORKDIR /app

RUN pip install --no-cache-dir httpx~=0.28 mcp~=1.26

COPY mfapi_mcp.py .

USER mcp

EXPOSE 8002

ENTRYPOINT ["python", "mfapi_mcp.py"]
