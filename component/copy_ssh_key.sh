#!/bin/bash
set -e

# -------------------------------
# Configuration
# -------------------------------
DEFAULT_KEY="$HOME/.ssh/id_ed25519"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# -------------------------------
# Arguments
# -------------------------------
if [ -z "$1" ]; then
    error "Usage: $0 user@host [public_key_path]"
fi

REMOTE="$1"
PUB_KEY="${2:-$DEFAULT_KEY.pub}"
PRIV_KEY="${PUB_KEY%.pub}"

info "Remote host: $REMOTE"
info "Public key:  $PUB_KEY"

# -------------------------------
# Step 1: Generate SSH key if needed
# -------------------------------
if [ ! -f "$PUB_KEY" ]; then
    warn "SSH key not found, generating new ed25519 key..."

    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"

    ssh-keygen -t ed25519 -f "$PRIV_KEY" -N "" -C "$(whoami)@$(hostname)"

    info "SSH key generated:"
    info "  $PRIV_KEY"
    info "  $PUB_KEY"
else
    info "Existing SSH key found"
fi

# -------------------------------
# Step 2: Start ssh-agent if needed
# -------------------------------
if ! ssh-add -l >/dev/null 2>&1; then
    info "Starting ssh-agent"
    eval "$(ssh-agent -s)"
    ssh-add "$PRIV_KEY"
fi

# -------------------------------
# Step 3: Copy key to remote
# -------------------------------
if command -v ssh-copy-id >/dev/null 2>&1; then
    info "Copying key using ssh-copy-id"
    ssh-copy-id -i "$PUB_KEY" "$REMOTE"
else
    warn "ssh-copy-id not found, using manual method"

    SSH_KEY_CONTENT=$(cat "$PUB_KEY")

    ssh "$REMOTE" "mkdir -p ~/.ssh && chmod 700 ~/.ssh"
    echo "$SSH_KEY_CONTENT" | ssh "$REMOTE" \
        "cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

    ssh "$REMOTE" "sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys"
fi

# -------------------------------
# Step 4: Verify passwordless login
# -------------------------------
info "Testing passwordless SSH connection..."

if ssh -o BatchMode=yes -o ConnectTimeout=5 "$REMOTE" "echo OK" >/dev/null 2>&1; then
    info "✓ Passwordless SSH is working"
    info "You can now log in with: ssh $REMOTE"
else
    warn "Key copied, but passwordless login failed"
    warn "Check sshd_config, permissions, or firewall on remote host"
fi

