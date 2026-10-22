#!/bin/bash

echo 'flag{23693ec4-a8e3-4867-a36e-5b3350c9e11b}' > /flag

cat > start.py <<EOF
# Import and start server using v0.1.1 API
from agentscope.studio._app import init

SERVER_HOST="0.0.0.0"
SERVER_PORT=5000

# Start server (this will block)
init(
    host=SERVER_HOST,
    port=SERVER_PORT,
    run_dirs=[],
    debug=False
)
EOF

python3 start.py
