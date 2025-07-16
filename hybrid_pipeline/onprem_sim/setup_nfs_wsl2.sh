#!/usr/bin/env bash
set -euo pipefail
DATA_DIR="/data"
MOUNT_PT="/mnt/z"

# 1. installa server se manca
if ! dpkg -s nfs-kernel-server >/dev/null 2>&1; then
   sudo apt update && sudo apt install -y nfs-kernel-server
fi

# 2. crea dir export solo se non c’è
sudo mkdir -p "$DATA_DIR"
sudo chown nobody:nogroup "$DATA_DIR"

# 3. aggiungi export solo se non già presente
grep -q "^$DATA_DIR " /etc/exports 2>/dev/null || \
  echo "$DATA_DIR *(rw,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports
sudo exportfs -ra

# 4. avvia/riavvia servizio
sudo systemctl enable --now nfs-server

# 5. mount locale se non esiste
sudo mkdir -p "$MOUNT_PT"
mountpoint -q "$MOUNT_PT" || sudo mount -t nfs -o vers=4 localhost:$DATA_DIR "$MOUNT_PT"

echo "✅ NFS pronto: export $DATA_DIR montato su $MOUNT_PT"
