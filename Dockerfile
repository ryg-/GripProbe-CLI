FROM python:3.12-slim AS core

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV NODE_VERSION=22.19.0
ENV TMPDIR=/work/.tmp
ENV TMP=/work/.tmp
ENV TEMP=/work/.tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 \
    curl \
    git \
    openssh-client \
    patch \
    procps \
    ripgrep \
    strace \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
        amd64) node_arch="x64" ;; \
        arm64) node_arch="arm64" ;; \
        *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm -f /tmp/node.tar.xz \
    && node --version \
    && npm --version

WORKDIR /work

RUN mkdir -p /work/.tmp

COPY pyproject.toml README.md /work/
COPY gripprobe /work/gripprobe

RUN pip install --upgrade pip && pip install -e .[dev]

CMD ["python3", "-m", "gripprobe.cli", "--root", ".", "validate"]


FROM core AS continue-cli

RUN npm install -g @continuedev/cli \
    && npm cache clean --force


FROM core AS opencode

RUN npm install -g opencode-ai \
    && npm cache clean --force


FROM core AS codex

RUN npm install -g @openai/codex \
    && npm cache clean --force


FROM core AS aider

RUN python3 -m venv /opt/venvs/aider \
    && TMPDIR=/work/.tmp TMP=/work/.tmp TEMP=/work/.tmp /opt/venvs/aider/bin/pip install --upgrade pip \
    && TMPDIR=/work/.tmp TMP=/work/.tmp TEMP=/work/.tmp /opt/venvs/aider/bin/pip install --no-compile aider-chat \
    && ln -sf /opt/venvs/aider/bin/aider /usr/local/bin/aider


FROM core AS hermes

RUN python3 -m venv /opt/venvs/hermes \
    && TMPDIR=/work/.tmp TMP=/work/.tmp TEMP=/work/.tmp /opt/venvs/hermes/bin/pip install --upgrade pip \
    && TMPDIR=/work/.tmp TMP=/work/.tmp TEMP=/work/.tmp /opt/venvs/hermes/bin/pip install --no-compile hermes-agent \
    && ln -sf /opt/venvs/hermes/bin/hermes /usr/local/bin/hermes


FROM core AS gptme

RUN mkdir -p /work/.tmp \
    && echo "TMPDIR=$TMPDIR TMP=$TMP TEMP=$TEMP" \
    && df -h / /tmp /work /work/.tmp \
    && echo "Contents of /tmp before gptme install:" \
    && ls -lah /tmp \
    && echo "Contents of /work/.tmp before gptme install:" \
    && ls -lah /work/.tmp \
    && python3 -c 'import os, tempfile; print("python tempfile.gettempdir() =", tempfile.gettempdir()); print("TMPDIR =", os.environ.get("TMPDIR")); print("TMP =", os.environ.get("TMP")); print("TEMP =", os.environ.get("TEMP"))' \
    && python3 -m venv /opt/venvs/gptme \
    && TMPDIR=/work/.tmp TMP=/work/.tmp TEMP=/work/.tmp /opt/venvs/gptme/bin/pip install --upgrade pip \
    && TMPDIR=/work/.tmp TMP=/work/.tmp TEMP=/work/.tmp /opt/venvs/gptme/bin/pip install --no-compile gptme \
    && echo "Contents of /tmp after gptme install:" \
    && ls -lah /tmp \
    && echo "Contents of /work/.tmp after gptme install:" \
    && ls -lah /work/.tmp \
    && ln -sf /opt/venvs/gptme/bin/gptme /usr/local/bin/gptme


FROM core AS pi

RUN npm install -g @earendil-works/pi-coding-agent \
    && npm cache clean --force


FROM core AS goose

RUN curl -fsSL -o /tmp/goose.tar.bz2 https://github.com/aaif-goose/goose/releases/download/stable/goose-x86_64-unknown-linux-gnu.tar.bz2 \
    && mkdir -p /tmp/goose \
    && tar -xjf /tmp/goose.tar.bz2 -C /tmp/goose \
    && install "$(find /tmp/goose -type f -name goose | head -n 1)" /usr/local/bin/goose \
    && rm -rf /tmp/goose /tmp/goose.tar.bz2
