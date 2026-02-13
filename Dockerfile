# ---- Frontend build ----
FROM node:20-alpine AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci || npm install
COPY web/ ./
RUN npm run build

# ---- Backend ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY removarr ./removarr
# copy built SPA into backend static dir
COPY --from=webbuild /web/dist ./removarr/static

EXPOSE 8765
CMD ["uvicorn", "removarr.main:app", "--host", "0.0.0.0", "--port", "8765"]
