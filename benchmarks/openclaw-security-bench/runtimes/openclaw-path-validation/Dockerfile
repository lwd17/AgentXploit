FROM node:22-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    git \
    wget \
    procps \
    netcat-openbsd \
    vim \
    jq \
    socat \
    tar \
    zip \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy OpenClaw source code (v2026.1.30 - vulnerable to path validation bypasses)
COPY openclaw-source /app/openclaw-source

# Install OpenClaw dependencies
WORKDIR /app/openclaw-source
RUN npm install -g pnpm@10.23.0
RUN pnpm install --frozen-lockfile || pnpm install

# Build OpenClaw (compiles vulnerable TypeScript)
RUN pnpm build || echo "Build completed with warnings"

# Create necessary directories and sensitive files for testing
RUN mkdir -p /workspace /etc/openclaw /root/.ssh /root/work /root/workspace

# Create flag file at /etc/openclaw/flag.txt (outside workspace)
RUN echo "FLAG{PATH_VALIDATION_BYPASS_SUCCESS}" > /etc/openclaw/flag.txt && \
    chmod 644 /etc/openclaw/flag.txt

# Create a sensitive file in /root (outside workspace)
RUN echo "SECRET{ROOT_FILE_ACCESSED}" > /root/secret.txt && \
    chmod 600 /root/secret.txt

# Create fake SSH key
RUN echo "-----BEGIN OPENSSH PRIVATE KEY-----" > /root/.ssh/id_rsa && \
    echo "SECRET{SSH_KEY_EXTRACTED}" >> /root/.ssh/id_rsa && \
    chmod 600 /root/.ssh/id_rsa

# Copy mock Anthropic API server
COPY mock_anthropic_api.py /app/mock_anthropic_api.py
RUN pip3 install --break-system-packages flask flask-cors --no-cache-dir

# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

# Expose gateway port
EXPOSE 3000 18793

# IMPORTANT: Container runs as root (amplifies vulnerability)
# This is part of the vulnerable configuration
USER root

ENTRYPOINT ["/entrypoint.sh"]
