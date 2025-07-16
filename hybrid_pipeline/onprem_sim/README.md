# On-Prem Simulation (WSL-first)

Di seguito trovi **il percorso minimo "WSL-first"**: tutto gira sotto Ubuntu WSL 2, con solo due tocchi sul lato Windows (port-forward e avvio VM DataSync). Così eviti PowerShell, Docker Desktop e mount di unità `Z:`.

---

## 1 – Dentro WSL 2 (Ubuntu)

### 1.1 accendi NFS nativo

```bash
cd hybrid_pipeline/onprem_sim
sudo bash setup_nfs_wsl2.sh          # installa, esporta /data, monta /mnt/z
```

*Verifica:* `showmount -e localhost` deve restituire `/data`.

### 1.2 producer d’immagini

```bash
sudo apt install -y python3-pip
pip3 install pillow
python3 tools/onprem_image_producer.py \
        --root /mnt/z                # vedi nota più sotto
```

*(Aggiungi al producer un flag `--root` o modifica la path hard‑coded.)*

> Ora, ogni 5 s compare un `.jpg` in `/mnt/z` → visibile via NFS.

---

## 2 – Esporre la porta NFS dal mondo WSL → Windows

WSL 2 è dietro NAT; serve un **port-proxy** sulla macchina host.
Apri **PowerShell come Admin** (una sola volta):

```powershell
$WSL_IP  = (wsl -d Ubuntu hostname -I).Trim()   # ip interno es. 172.30.160.1
netsh interface portproxy add v4tov4 `
     listenport=2049 listenaddress=0.0.0.0 `
     connectport=2049 connectaddress=$WSL_IP
```

> NFS v4 usa solo TCP 2049 ⇒ non servono UDP/port-mapper.
> Se vuoi togliere il proxy in futuro:
> `netsh interface portproxy delete v4tov4 listenport=2049 listenaddress=0.0.0.0`

---

## 3 – VM AWS DataSync Agent

1. Importa OVA in Hyper-V/VirtualBox, 2 vCPU/4 GB.
2. Collega **una NIC “Bridged” o “NAT”** con accesso Internet.
3. Quando la VM parte, visita `http://<IP-agent>` e copia l’**Activation Key**.
4. **AWS Console → DataSync → Create Agent**, incolla la key, **Region = eu-central-1**.
5. Attendi che lo stato diventi **ONLINE**, poi copia la sua **ARN**.

---

## 4 – Bootstrap DataSync (da WSL, tutto bash)

Crea il clone bash del tuo `.ps1` (più sotto) oppure lancia questi comandi a mano:

```bash
# variabili comode
AGENT_ARN="arn:aws:datasync:eu-central-1:123456789012:agent/agent-id"
HOST_IP=$(ip route | awk '$1=="default"{print $3}')     # ip Windows visto dalla VM
BUCKET=$(aws s3api list-buckets --query "Buckets[?contains(Name,'images-input')].Name" --output text)

# 1) location NFS (source)
SRC_LOC=$(aws datasync create-location-nfs \
  --server-hostname $HOST_IP \
  --subdirectory /data \
  --on-prem-config AgentArns=[$AGENT_ARN] \
  --mount-options Version=NFS4 \
  --query LocationArn --output text)

# 2) ruolo + location S3 (dest)
ROLE_ARN=$(aws iam create-role \
  --role-name DataSyncToS3Role \
  --assume-role-policy-document file://<(echo '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"datasync.amazonaws.com"},"Action":"sts:AssumeRole"}]}') \
  --query Role.Arn --output text)
aws iam attach-role-policy --role-name DataSyncToS3Role --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

DST_LOC=$(aws datasync create-location-s3 \
  --s3-bucket-arn arn:aws:s3:::$BUCKET \
  --s3-config BucketAccessRoleArn=$ROLE_ARN \
  --subdirectory / \
  --query LocationArn --output text)

# 3) task schedulato 1 min
TASK_ARN=$(aws datasync create-task \
  --source-location-arn $SRC_LOC \
  --destination-location-arn $DST_LOC \
  --schedule 'ScheduleExpression=rate(1 minute)' \
  --name NfsToS3-HybridPipeline \
  --excludes FilterType=SIMPLE_PATTERN,Value=processed/* \
  --query TaskArn --output text)

aws datasync start-task-execution --task-arn $TASK_ARN
echo "✅ Task $TASK_ARN creato e avviato"
```

*(Se preferisci, adatta il vecchio `datasync_bootstrap.ps1` con un parametro `-NfsServer $HOST_IP` e continua a lanciarlo da PowerShell.)*

---

## 5 – Pipeline cloud (CDK)

Se non l’hai ancora fatto:

```bash
cd ~/…/hybrid_pipeline/cdk
npm i -g aws-cdk                       # se serve
python -m pip install -r requirements.txt
cdk deploy
```

Gli *Outputs* ti danno URL SQS, bucket, ecc.

---

## 6 – Test end-to-end

1. Il producer WSL scrive `/mnt/z/img_00001.jpg`
2. Entro 60 s il task DataSync lo copia in `s3://images-input-…/img_00001.jpg`
3. Evento S3 → Lambda Dispatcher → Step Functions → ECS Grayscale
4. File processato in `s3://images-output-…/processed/img_00001.jpg`
5. Messaggio JSON in coda FIFO `image-processing-results-…`

Controlli rapidi:

```bash
aws s3 ls s3://$BUCKET --recursive --human-readable --summarize
aws s3 ls s3://images-output-<acc>-eu-central-1/processed/ --recursive
aws sqs receive-message --queue-url <ImageProcessingQueueURL> --max-number-of-messages 1
aws logs tail /aws/lambda/ImageS3DispatcherLambda --since 10m
aws logs tail /ecs/grayscale --since 10m
```

---

## 7 – Script producer: piccola modifica

```python
# tools/onprem_image_producer.py
import argparse, …      # aggiungi
parser = argparse.ArgumentParser()
parser.add_argument('--root', default='/mnt/z', help='NFS root path')
args = parser.parse_args()
root = Path(args.root)
…
```

Così lo usi indenni sia da Windows (`root Z:\\`) sia da WSL (`/mnt/z`).

---

### TL;DR

```bash
# In Ubuntu WSL
cd hybrid_pipeline/onprem_sim
sudo bash setup_nfs_wsl2.sh
python tools/onprem_image_producer.py --root /mnt/z      # lasci aperto

# Una tantum in PowerShell (Admin)
$ip = (wsl hostname -I).Trim()
netsh interface portproxy add v4tov4 listenport=2049 listenaddress=0.0.0.0 \
                                  connectport=2049 connectaddress=$ip

# Importa VM DataSync Agent → copia ARN
bash <script_di_bootstrap>.sh -AgentArn <ARN>

# (se serve) cdk deploy
```

E hai l’intero flusso **WSL → NFS → DataSync → S3 → Lambda → ECS** perfettamente funzionante senza più frizioni tra Windows e Linux. Buona sperimentazione 🚀
