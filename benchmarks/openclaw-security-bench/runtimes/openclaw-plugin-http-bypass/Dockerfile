# OpenClaw Plugin HTTP Auth Bypass Runtime
# Real OpenClaw gateway with vulnerable plugin HTTP routes

FROM node:22-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    curl \
    git \
    wget \
    procps \
    netcat-openbsd \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy OpenClaw source code
COPY openclaw-source /app/openclaw-source

# Install OpenClaw dependencies
WORKDIR /app/openclaw-source
RUN npm install -g pnpm@10.23.0
RUN pnpm install --frozen-lockfile || pnpm install

# Build OpenClaw
RUN pnpm build || echo "Build completed with warnings"

# Create directories
RUN mkdir -p /workspace /host_secrets

# Create sensitive data that should NOT be accessible without auth
RUN echo '{"api_key":"sk-admin-secret-key-12345","admin_password":"SuperSecretPassword!","database":"postgresql://admin:secret@db:5432/prod","proof":"OPENCLAW-PLUGIN-HTTP-BYPASS-VERIFIED"}' > /host_secrets/admin_credentials.json && \
    chmod 600 /host_secrets/admin_credentials.json

# Copy vulnerable plugin
COPY vulnerable-plugin /workspace/.openclaw/extensions/vulnerable-admin-api

# Create entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

# Expose gateway port
EXPOSE 18789

ENTRYPOINT ["/entrypoint.sh"]
