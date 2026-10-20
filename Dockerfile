FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/api
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api ./apps/api
COPY fixtures/tongyu ./fixtures/tongyu
COPY --from=web /web/dist ./apps/web/dist

RUN mkdir -p /app/data
WORKDIR /app/apps/api
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

