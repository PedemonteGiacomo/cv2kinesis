#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root or with sudo" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"

mkdir -p "$DATA_DIR"

if ! dpkg -s nfs-kernel-server >/dev/null 2>&1; then
    apt-get update
    apt-get install -y nfs-kernel-server
fi

echo "$DATA_DIR *(rw,sync,no_subtree_check,no_root_squash)" > /etc/exports.d/onprem_sim.exports
exportfs -ra

mkdir -p /mnt/z
if ! mountpoint -q /mnt/z; then
    mount localhost:"$DATA_DIR" /mnt/z
fi

echo "✅ NFS exported from $DATA_DIR and mounted on /mnt/z"
