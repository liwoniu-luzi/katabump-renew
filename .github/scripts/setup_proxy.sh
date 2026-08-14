#!/bin/bash
# setup_proxy.sh - Setup Hysteria 1 proxy for GitHub Actions
# If proxy setup fails, fall back to direct connection

# Read node link from environment
NODE_LINK=${NODE_LINK:-}

if [ -z "$NODE_LINK" ]; then
  echo "[INFO] No proxy configured, using direct connection"
  echo "IS_PROXY=false" >> $GITHUB_ENV
  echo "PROXY_SERVER=" >> $GITHUB_ENV
  exit 0
fi

# Check protocol (should be hysteria://)
PROTO=$(echo "$NODE_LINK" | cut -d':' -f1)
if [ "$PROTO" != "hysteria" ]; then
  echo "[WARN] Unsupported protocol: $PROTO (only hysteria:// is supported)"
  echo "[WARN] Falling back to direct connection"
  echo "IS_PROXY=false" >> $GITHUB_ENV
  echo "PROXY_SERVER=" >> $GITHUB_ENV
  exit 0
fi

echo "[INFO] Protocol: hysteria"

# Install jq if missing
if ! command -v jq &> /dev/null; then
  echo "[INFO] Installing jq..."
  sudo apt-get update >/dev/null 2>&1 && sudo apt-get install -y jq >/dev/null 2>&1 || {
    echo "[WARN] Failed to install jq, falling back to direct connection"
    echo "IS_PROXY=false" >> $GITHUB_ENV
    echo "PROXY_SERVER=" >> $GITHUB_ENV
    exit 0
  }
fi

# Determine architecture
ARCH_RAW=$(uname -m)
case "$ARCH_RAW" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) 
    echo "[WARN] Unsupported architecture: $ARCH_RAW, falling back to direct connection"
    echo "IS_PROXY=false" >> $GITHUB_ENV
    echo "PROXY_SERVER=" >> $GITHUB_ENV
    exit 0
    ;;
esac

# Hysteria 1 version
HY_VERSION="1.3.5"

# Download Hysteria client
echo "[INFO] Downloading Hysteria v${HY_VERSION} for ${ARCH}..."
DOWNLOAD_URL="https://github.com/apernet/hysteria/releases/download/v${HY_VERSION}/hysteria-linux-${ARCH}"
if ! curl -L -o hysteria "$DOWNLOAD_URL" --connect-timeout 15 --max-time 60; then
  echo "[WARN] Failed to download Hysteria client, falling back to direct connection"
  echo "IS_PROXY=false" >> $GITHUB_ENV
  echo "PROXY_SERVER=" >> $GITHUB_ENV
  exit 0
fi
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
  echo "[WARN] Failed to parse server address, falling back to direct connection"
  echo "IS_PROXY=false" >> $GITHUB_ENV
  echo "PROXY_SERVER=" >> $GITHUB_ENV
  exit 0
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

# Parse query parameters (inline function without local keyword)
if [ -n "$QUERY" ]; then
  # protocol
  TEMP_VAL=$(echo "$QUERY" | grep -o 'protocol=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && PROTOCOL="$TEMP_VAL"
  
  # upmbps
  TEMP_VAL=$(echo "$QUERY" | grep -o 'upmbps=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && UP_MBPS="$TEMP_VAL"
  
  # downmbps
  TEMP_VAL=$(echo "$QUERY" | grep -o 'downmbps=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && DOWN_MBPS="$TEMP_VAL"
  
  # obfs
  TEMP_VAL=$(echo "$QUERY" | grep -o 'obfs=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && OBFS="$TEMP_VAL"
  
  # obfsParam
  TEMP_VAL=$(echo "$QUERY" | grep -o 'obfsParam=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && OBFS_PARAM="$TEMP_VAL"
  
  # peer
  TEMP_VAL=$(echo "$QUERY" | grep -o 'peer=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && PEER="$TEMP_VAL"
  
  # insecure
  TEMP_VAL=$(echo "$QUERY" | grep -o 'insecure=[^&]*' | cut -d= -f2)
  [ -n "$TEMP_VAL" ] && INSECURE="$TEMP_VAL"
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
  echo "[WARN] Proxy connection failed, falling back to direct connection"
  echo "---- Hysteria log (last 20 lines) ----"
  tail -20 hysteria.log 2>/dev/null || true
  echo "IS_PROXY=false" >> $GITHUB_ENV
  echo "PROXY_SERVER=" >> $GITHUB_ENV
  # Kill hysteria process
  pkill -f hysteria 2>/dev/null || true
fi
