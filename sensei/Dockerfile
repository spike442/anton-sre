FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GIT_TERMINAL_PROMPT=0
ARG TARGETARCH=amd64
ARG KUBECTL_VERSION=v1.37.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git openssh-client \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
    && chmod 0755 /usr/local/bin/kubectl \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/hive-common /tmp/hive-common
COPY sensei/pyproject.toml ./
COPY sensei/src ./src
COPY sensei/infra/config /etc/sensei
RUN pip install --no-cache-dir /tmp/hive-common . \
    && useradd --uid 65532 --create-home --shell /usr/sbin/nologin reviewer \
    && mkdir -p /tmp/sensei \
    && chown -R 65532:65532 /tmp/sensei

USER 65532:65532
EXPOSE 8090
CMD ["uvicorn", "sensei.server:app", "--host", "0.0.0.0", "--port", "8090"]
