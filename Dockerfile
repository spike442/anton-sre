FROM node:22-alpine AS frontend-build

WORKDIR /frontend
ARG ANTON_VERSION
ENV VITE_ANTON_VERSION=${ANTON_VERSION}
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
ENV PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    TERM=dumb \
    GIT_TERMINAL_PROMPT=0
ARG TARGETARCH=amd64
ARG KUBECTL_VERSION=v1.37.0
ARG FLUX_VERSION=2.4.0
ARG HELM_VERSION=3.22.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git jq openssh-client passwd \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
    && chmod 0755 /usr/local/bin/kubectl \
    && curl -fsSL "https://github.com/fluxcd/flux2/releases/download/v${FLUX_VERSION}/flux_${FLUX_VERSION}_linux_${TARGETARCH}.tar.gz" | tar -xz -C /usr/local/bin flux \
    && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" | tar -xz --strip-components=1 -C /usr/local/bin "linux-${TARGETARCH}/helm" \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY infra/config /etc/anton/config
COPY src ./src
COPY --from=frontend-build /frontend/dist ./static
RUN groupadd --gid 65532 anton \
    && useradd --uid 65532 --gid 65532 --home-dir /home/anton --create-home --shell /usr/sbin/nologin anton \
    && pip install --no-cache-dir . \
    && mkdir -p /home/anton \
    && chown -R 65532:65532 /home/anton

USER 65532:65532
CMD ["uvicorn", "server:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
