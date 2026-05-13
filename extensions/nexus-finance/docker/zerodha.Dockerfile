FROM python:3.12-slim

RUN groupadd -r mcp && useradd -r -g mcp mcp

WORKDIR /app

RUN pip install --no-cache-dir kiteconnect~=5.0 mcp~=1.26

COPY zerodha_mcp.py .

USER mcp

EXPOSE 8001

ENTRYPOINT ["python", "zerodha_mcp.py"]
