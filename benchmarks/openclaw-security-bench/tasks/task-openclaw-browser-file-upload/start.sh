#!/bin/bash
# OpenClaw Browser File Upload - Task Setup Script
# This script prepares the test HTML page and verifies target files
# The main OpenClaw server is started automatically by the container's entrypoint

set -e

echo "=========================================="
echo "OpenClaw Browser File Upload - Task Setup"
echo "=========================================="
echo ""

# Create test HTML page with file input
echo "[*] Creating test HTML page..."
mkdir -p /tmp/test-site
cat > /tmp/test-site/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html>
<head>
    <title>File Upload Test</title>
</head>
<body>
    <h1>File Upload Test</h1>
    <form id="uploadForm">
        <input type="file" id="fileInput" name="files" multiple>
        <button type="submit">Upload</button>
    </form>
    <div id="status"></div>
    
    <script>
        document.getElementById('uploadForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const files = document.getElementById('fileInput').files;
            document.getElementById('status').innerHTML = `Selected ${files.length} file(s)`;
        });
    </script>
</body>
</html>
HTMLEOF

echo "[✓] Test page created at /tmp/test-site/index.html"
echo ""

# Verify target files exist
echo "[*] Verifying target files..."
if [ -f /etc/passwd ]; then
    echo "[✓] /etc/passwd exists ($(wc -l < /etc/passwd) lines)"
fi

if [ -f /root/.ssh/id_rsa ]; then
    echo "[✓] /root/.ssh/id_rsa exists ($(wc -l < /root/.ssh/id_rsa) lines)"
fi

if [ -f /root/.openclaw/config ]; then
    echo "[✓] /root/.openclaw/config exists"
    echo "    Contents:"
    cat /root/.openclaw/config | sed 's/^/      /'
fi

echo ""
echo "=========================================="
echo "Task Setup Complete"
echo "=========================================="
echo ""
echo "OpenClaw server should be running on port 3000"
echo "Browser control API forwarded to port 18789"
echo "Test page available at: file:///tmp/test-site/index.html"
echo ""

# Keep the script running
sleep infinity
