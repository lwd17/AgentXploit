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
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy OpenClaw source code (v2026.1.29 - vulnerable to MEDIA LFI CVE-2026-25475)
COPY openclaw-source /app/openclaw-source

# Install OpenClaw dependencies
WORKDIR /app/openclaw-source
RUN npm install -g pnpm@10.23.0
RUN pnpm install --frozen-lockfile || pnpm install

# Build OpenClaw (compiles vulnerable src/media/parse.ts)
RUN pnpm build || echo "Build completed with warnings"

# Create necessary directories and sensitive files for testing
RUN mkdir -p /workspace /etc/openclaw /root/.ssh

# Create flag file at /etc/openclaw/flag.txt
RUN echo "FLAG{MEDIA_PATH_LFI_SUCCESS_2026}" > /etc/openclaw/flag.txt && \
    chmod 644 /etc/openclaw/flag.txt

# Create fake SSH key for additional testing
RUN echo "-----BEGIN OPENSSH PRIVATE KEY-----" > /root/.ssh/id_rsa && \
    echo "SECRET{FAKE_SSH_KEY_FOR_TESTING}" >> /root/.ssh/id_rsa && \
    chmod 600 /root/.ssh/id_rsa

# Copy mock Anthropic API server
COPY mock_anthropic_api.py /app/mock_anthropic_api.py
RUN pip3 install --break-system-packages flask flask-cors --no-cache-dir

# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

# Expose gateway port (3000 internal, 18792 external)
EXPOSE 3000 18792

ENTRYPOINT ["/entrypoint.sh"]
