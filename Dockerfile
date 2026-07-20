FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/heiman/pyproject.toml backend/heiman/setup.py* ./backend/heiman/
COPY cli/pyproject.toml ./cli/

WORKDIR /app/backend/heiman
RUN pip install --no-cache-dir -e .

WORKDIR /app/cli
RUN pip install --no-cache-dir -e .

FROM python:3.12-slim as frontend-builder

WORKDIR /app/web

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://get.pnpm.io/install.sh | sh -

ENV PATH="/root/.local/share/pnpm:${PATH}"

COPY web/package.json web/pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

COPY web/ .

RUN pnpm build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/heiman-backend /usr/local/bin/heiman-backend
COPY --from=builder /usr/local/bin/heiman /usr/local/bin/heiman

COPY --from=frontend-builder /app/web/dist/ /app/static/

COPY backend/heiman/src/ /app/src/
COPY backend/heiman/.env.example /app/.env.example

EXPOSE 8000

VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["heiman-backend"]
