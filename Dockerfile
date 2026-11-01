FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
COPY fixtures/ ./fixtures/
RUN pip install --no-cache-dir .
CMD ["python", "-m", "cloud_warehouse", "--source", "fixture", "--sink", "local"]
