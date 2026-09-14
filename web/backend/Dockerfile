# Build context is the repo root (see fly.toml) -- this image needs both
# the passthebot engine package (src/passthebot) and the web backend (app/).
FROM python:3.11-slim

WORKDIR /srv

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY web/backend/pyproject.toml ./web/backend/pyproject.toml
COPY web/backend/app ./web/backend/app
RUN pip install --no-cache-dir ./web/backend

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--app-dir", "web/backend", "--host", "0.0.0.0", "--port", "8080"]
