# GEAP Harness Eval — single image: engine + dashboard + 5 harness CLIs + task toolchains.
# Build on linux/amd64 (Cloud Build) — Apple-Silicon local builds produce arm64 images Cloud Run rejects.

# ---------------------------------------------------------------- dashboard
FROM node:24.20.0-bookworm-slim AS web
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# ---------------------------------------------------------------- runtime
FROM debian:bookworm-slim
ARG NODE_VERSION=24.20.0
ARG GO_VERSION=1.24.3
ARG RUST_VERSION=1.94.1
ARG LITESTREAM_VERSION=0.5.17
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

# toolchains the 36 tasks need (offline, stdlib-only) + harness/runtime deps; ca-certificates matters (TLS to GCS)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils unzip tini procps build-essential python3 python3-venv \
      clang make sqlite3 zstd openssl fd-find openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz \
      | tar -xJ -C /usr/local --strip-components=1 \
    && curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz | tar -xz -C /usr/local \
    && curl -fsSL https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-x86_64.tar.gz \
      | tar -xz -C /usr/local/bin litestream
ENV PATH=/usr/local/go/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /usr/local/bin/

# non-root: Claude Code refuses --dangerously-skip-permissions as root
RUN useradd -m -u 1000 -s /bin/bash eval && mkdir -p /app /data /var/tmp/geap-eval-work && chown -R eval:eval /app /data /var/tmp/geap-eval-work
USER eval
ENV HOME=/home/eval CARGO_HOME=/home/eval/.cargo RUSTUP_HOME=/home/eval/.rustup
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain ${RUST_VERSION}
ENV PATH=/home/eval/.cargo/bin:$PATH

WORKDIR /app
COPY --chown=eval:eval pyproject.toml uv.lock README.md ./
COPY --chown=eval:eval src/ src/
RUN uv sync --frozen --no-dev --python 3.13
ENV PATH=/app/.venv/bin:$PATH

USER root
RUN /app/.venv/bin/playwright install-deps chromium
USER eval
RUN playwright install chromium

COPY --chown=eval:eval tasks/ tasks/
COPY --chown=eval:eval pricing/ pricing/
COPY --chown=eval:eval configs/ configs/
COPY --chown=eval:eval scripts/ scripts/
COPY --chown=eval:eval docs/ docs/
COPY --chown=eval:eval --from=web /web/dist web/dist
COPY --chown=eval:eval deploy/entrypoint.sh deploy/litestream.yml /app/deploy/

# harness CLIs at build time (fast first run); every run still upgrades to the latest release and freezes it in lock.json
RUN mkdir -p tools/pi/cache && cp /usr/bin/fdfind tools/pi/cache/fd \
    && geap-eval install

ENV GEAP_HOST=0.0.0.0 PORT=8080 \
    GEAP_RUNS_DIR=/data/runs GEAP_DB_PATH=/data/db/geap-eval.db GEAP_WORK_ROOT=/var/tmp/geap-eval-work \
    GEAP_IDENTITY_MODE=service_account GEAP_PUBLIC_READONLY=1 GEAP_CHROMIUM_NO_SANDBOX=1
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/entrypoint.sh"]
