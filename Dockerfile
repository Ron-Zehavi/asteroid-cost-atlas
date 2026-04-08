FROM node:22-slim AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY configs/ configs/
COPY data/processed/ data/processed/

RUN pip install --no-cache-dir ".[web]"

COPY --from=frontend /build/dist web/dist/

RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "asteroid_cost_atlas.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
