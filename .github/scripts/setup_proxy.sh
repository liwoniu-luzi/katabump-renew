#!/bin/bash
# setup_proxy.sh - Setup Hysteria 1 proxy for GitHub Actions
set -e

# Read node link from environment
NODE_LINK=${NODE_LINK:-}

if [ -z "$NODE_LINK" ]; then
  echo "[INFO] No proxy configured, using direct connection"
  echo "IS_PROXY=false" >> $GITHUB_ENV
  exit 0
fi

# Check protocol (should be hysteria://)
PROTO=$(echo "$NODE_LINK" | cut -d':' -f1)
if [ "$PROTO" != "hysteria" ]; then
  echo "[ERROR] Unsupported protocol: $PROTO (only hysteria:// is supported)"
  exit 1
fi

echo "[INFO] Protocol: hysteria"

# Install jq if missing
if ! command -v jq &> /dev/null; then
  echo "[INFO] Installing jq..."
  sudo apt-get update >/dev/null && sudo apt-get install -y jq >/dev/null
fi

# Determine architecture
ARCH_RAW=$(uname -m)
case "$ARCH_RAW" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "[ERROR] Unsupported architecture: $ARCH_RAW"; exit 1 ;;
esac

# Hysteria 1 latest stable version (adjust if needed)
HY_VERSION="1.3.5"

# Download Hysteria client
echo "[INFO] Downloading Hysteria v${HY_VERSION} for ${ARCH}..."
DOWNLOAD_URL="https://github.com/apernet/hysteria/releases/download/v${HY_VERSION}/hysteria-linux-${ARCH}"
curl -L -o hysteria "$DOWNLOAD_URL"
chmod +x hysteria

# Parse hysteria:// link
# Format: hysteria://password@host:port/?protocol=udp&upmbps=100&downmbps=100&obfs=xplus&obfsParam=xxx&peer=example.com&insecure=1#Name
CONTENT="${NODE_LINK#hysteria://}"
CONTENT="${CONTENT%%#*}"   # remove fragment

# Split auth and host_port
AUTH=""
HOST_PORT=""
if [[ "$CONTENT" == *"@"* ]]; then
  AUTH="${CONTENT%%@*}"
  HOST_PORT="${CONTENT#*@}"
else
  # Some links may use query param 'auth'
  HOST_PORT="$CONTENT"
fi

# Split host_port and query
QUERY=""
if [[ "$HOST_PORT" == *"?"* ]]; then
  HOST="${HOST_PORT%%\?*}"
  QUERY="${HOST_PORT#*\?}"
else
  HOST="$HOST_PORT"
fi

# Extract server and port
SERVER="${HOST%:*}"
PORT="${HOST#*:}"
if [ -z "$SERVER" ] || [ -z "$PORT" ]; then
  echo "[ERROR] Failed to parse server address"
  exit 1
fi

# If auth not in URL, try to get from query 'auth'
if [ -z "$AUTH" ]; then
  AUTH=$(echo "$QUERY" | grep -o 'auth=[^&]*' | cut -d= -f2)
fi

# Default values
PROTOCOL="udp"
UP_MBPS=100
DOWN_MBPS=100
OBFS=""
OBFS_PARAM=""
PEER=""
INSECURE=0

# Parse query parameters
parse_query() {
  local key="$1"
  local value=$(echo "$QUERY" | grep -o "${key}=[^&]*" | cut -d= -f2)
  echo "$value"
}

if [ -n "$QUERY" ]; then
  PROTOCOL=$(parse_query "protocol" || echo "udp")
  [ -z "$PROTOCOL" ] && PROTOCOL="udp"
  UP_MBPS=$(parse_query "upmbps" || echo "100")
  [ -z "$UP_MBPS" ] && UP_MBPS=100
  DOWN_MBPS=$(parse_query "downmbps" || echo "100")
  [ -z "$DOWN_MBPS" ] && DOWN_MBPS=100
  OBFS=$(parse_query "obfs" || echo "")
  OBFS_PARAM=$(parse_query "obfsParam" || echo "")
  PEER=$(parse_query "peer" || echo "")
  INSECURE=$(parse_query "insecure" || echo "0")
fi

# If peer is empty, use server
[ -z "$PEER" ] && PEER="$SERVER"

# Generate Hysteria client JSON config
CONFIG_FILE="hysteria-client.json"
cat > "$CONFIG_FILE" <<EOF
{
  "server": "${SERVER}:${PORT}",
  "protocol": "${PROTOCOL}",
  "up_mbps": ${UP_MBPS},
  "down_mbps": ${DOWN_MBPS},
  "socks5": {
    "listen": "127.0.0.1:1080"
  },
  "auth_str": "${AUTH}",
  "insecure": $([ "$INSECURE" = "1" ] || [ "$INSECURE" = "true" ] && echo true || echo false),
  "obfs": "${OBFS}",
  "obfs_param": "${OBFS_PARAM}",
  "peer": "${PEER}"
}
EOF

# Start Hysteria client
echo "[INFO] Starting Hysteria client..."
nohup ./hysteria -c "$CONFIG_FILE" client > hysteria.log 2>&1 &
sleep 5

# Test proxy
echo "[INFO] Testing SOCKS5 proxy at 127.0.0.1:1080..."
if curl -x socks5h://127.0.0.1:1080 -s --max-time 15 https://api.ipify.org > /dev/null 2>&1; then
  echo "[INFO] Proxy connection successful"
  echo "IS_PROXY=true" >> $GITHUB_ENV
  echo "PROXY_SERVER=socks5://127.0.0.1:1080" >> $GITHUB_ENV
else
  echo "[ERROR] Proxy connection failed"
  echo "---- Hysteria log ----"
  cat hysteria.log
  exit 1
fi
