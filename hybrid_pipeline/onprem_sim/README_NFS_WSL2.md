# NFS server nativo in WSL2 (Ubuntu)

Questo setup consente di simulare un NAS NFS locale su Windows tramite WSL2, senza Docker.

## Passi automatici (script `setup_nfs_wsl2.sh`)

1. Installa il server NFS:
   - `sudo apt update && sudo apt install -y nfs-kernel-server`
2. Prepara la directory da esportare:
   - `sudo mkdir -p /data && sudo chown nobody:nogroup /data`
3. Configura l'export:
   - `/data *(rw,sync,no_subtree_check,no_root_squash)` in `/etc/exports`
   - `sudo exportfs -ra`
4. Avvia il server NFS:
   - `sudo systemctl start nfs-server`
5. Monta la share NFS:
   - `sudo mkdir -p /mnt/z && sudo mount -t nfs -o vers=4 localhost:/data /mnt/z`

## Utilizzo

- Esegui lo script in WSL2:
  ```bash
  bash setup_nfs_wsl2.sh
  ```
- La share `/data` sarà accessibile e montata su `/mnt/z`.
- Puoi usarla come NAS locale per test, producer, pipeline, ecc.

## Note
- Non serve Docker Desktop.
- Funziona solo in ambiente WSL2 (Ubuntu).
- Per disattivare il server NFS:
  ```bash
  sudo systemctl stop nfs-server
  ```
