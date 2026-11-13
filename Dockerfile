# Multi-stage Dockerfile for AetherGuard Unified AgentOps Control Plane
# Stage 1: Build the frontend
FROM node:24-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend & Runtime
FROM python:3.12-slim AS runner
WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST_PATH=/frontend/dist \
    AETHERGUARD_DB_PATH=/data/sandbox.db \
    PORT=8000

# Install dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY backend/app ./app
COPY backend/pytest.ini ./

# Copy built frontend assets from stage 1
COPY --from=frontend-builder /build/frontend/dist /frontend/dist

RUN useradd --system --uid 10001 --create-home aetherguard \
    && mkdir -p /data \
    && chown aetherguard:aetherguard /data
USER aetherguard

# Expose HTTP port
EXPOSE 8000

# Run FastAPI backend via Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
