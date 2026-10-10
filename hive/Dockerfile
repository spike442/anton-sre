FROM node:22-alpine AS ui-build

WORKDIR /ui
ARG ANTON_API_URL=https://anton.timcasa.me
ARG SENSEI_API_URL=https://sensei.timcasa.me
ARG HIVE_API_URL=https://hive.timcasa.me
ARG HIVE_VERSION
ENV VITE_ANTON_API_URL=${ANTON_API_URL} \
    VITE_SENSEI_API_URL=${SENSEI_API_URL} \
    VITE_HIVE_API_URL=${HIVE_API_URL} \
    VITE_HIVE_VERSION=${HIVE_VERSION}

COPY hive/ui/package.json hive/ui/package-lock.json ./
RUN npm ci
COPY hive/ui ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY packages/hive-common /tmp/hive-common
COPY hive/pyproject.toml ./
COPY hive/src ./src
COPY hive/infra/config /etc/hive
COPY --from=ui-build /ui/dist ./ui/dist
RUN pip install --no-cache-dir /tmp/hive-common . \
    && useradd --uid 65532 --create-home --shell /usr/sbin/nologin hive

USER 65532:65532
EXPOSE 8070
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8070"]
