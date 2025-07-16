#!/bin/bash
# Script per configurare NFS server nativo in WSL2 (Ubuntu)
set -e

# 1. Installa il server NFS
sudo apt update
sudo apt install -y nfs-kernel-server

# 2. Prepara la directory da esportare
sudo mkdir -p /data
sudo chown nobody:nogroup /data

# 3. Configura l'export
echo "/data *(rw,sync,no_subtree_check,no_root_squash)" | sudo tee /etc/exports
sudo exportfs -ra

# 4. Avvia il server NFS
sudo systemctl start nfs-server

# 5. Monta la share NFS (da WSL2 o altro client Linux)
sudo mkdir -p /mnt/z
sudo mount -t nfs -o vers=4 localhost:/data /mnt/z

echo "✅ NFS server attivo su WSL2. Share /data montata su /mnt/z."
