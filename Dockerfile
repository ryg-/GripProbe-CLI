FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    nodejs \
    npm \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY pyproject.toml README.md /work/
COPY gripprobe /work/gripprobe

RUN pip install --upgrade pip && pip install -e .[dev]

# Optional shell adapters used by the benchmark matrix.
RUN npm install -g @continuedev/cli
RUN npm install -g opencode-ai
RUN python3 -m venv /opt/venvs/gptme \
    && /opt/venvs/gptme/bin/pip install --upgrade pip \
    && /opt/venvs/gptme/bin/pip install gptme \
    && ln -sf /opt/venvs/gptme/bin/gptme /usr/local/bin/gptme
RUN python3 -m venv /opt/venvs/aider \
    && /opt/venvs/aider/bin/pip install --upgrade pip \
    && /opt/venvs/aider/bin/pip install aider-chat \
    && ln -sf /opt/venvs/aider/bin/aider /usr/local/bin/aider

CMD ["python3", "-m", "gripprobe.cli", "--root", ".", "validate"]
