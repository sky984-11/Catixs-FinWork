FROM node:20-alpine AS web-build

WORKDIR /app/web

RUN npm install -g pnpm@9.15.9 --registry=https://registry.npmmirror.com \
    && pnpm config set registry https://registry.npmmirror.com

COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm run build


FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

COPY app ./app
COPY scripts ./scripts
COPY deploy ./deploy
COPY pyproject.toml run.py ./
COPY --from=web-build /app/web/dist ./web/dist

RUN mkdir -p migrations uploads/tickets app/logs \
    && rm -f /etc/nginx/sites-enabled/default \
    && cp deploy/web.conf /etc/nginx/sites-available/web.conf \
    && ln -s /etc/nginx/sites-available/web.conf /etc/nginx/sites-enabled/web.conf \
    && chmod +x deploy/entrypoint.sh

EXPOSE 80

ENTRYPOINT ["sh", "deploy/entrypoint.sh"]
