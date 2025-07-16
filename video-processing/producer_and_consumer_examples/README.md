# 🎥 Simple Real-time Object Detection Pipeline

Pipeline semplificata per object detection in tempo reale usando:
- **Webcam locale** → **AWS Kinesis** → **YOLO Detection**

## 🚀 Setup Rapido

### 1. Installa le dipendenze
```bash
pip install -r requirements.txt
```

### 2. Configura AWS
Copia il file di esempio e inserisci le tue credenziali:
```bash
# Copia il file di esempio
copy .env.example .env

# Modifica .env con le tue credenziali AWS reali
# AWS_ACCESS_KEY_ID=your_access_key_here
# AWS_SECRET_ACCESS_KEY=your_secret_key_here
# AWS_REGION=eu-central-1
```

### 3. Crea lo stream Kinesis
```bash
aws kinesis create-stream --stream-name testcam --shard-count 1 --region eu-central-1
```

## 🎯 Utilizzo

### Producer (Terminal 1)
```bash
python producer.py
```
- 🎥 Apre la webcam e mostra la finestra video
- 📤 Invia frames a Kinesis in tempo reale
- ⌨️ Premi 'q' per uscire

### Consumer (Terminal 2)
```bash
python consumer.py
```
- 📥 Legge frames da Kinesis
- 🤖 Fa object detection con YOLO
- 📊 Mostra log dettagliati delle detection

## 🎯 Oggetti Rilevabili

Il sistema rileva automaticamente:
- `bottle` (bottiglie)
- `cup` (tazze/bicchieri)
- `laptop` (computer portatili)
- `cell phone` (telefoni)
- `person` (persone)
- `book` (libri)
- `chair` (sedie)

**Soglia di confidenza**: 80%

## 📝 Log Example

**Producer:**
```
🎥 Avvio Producer: webcam=0 → Kinesis=testcam
✅ Webcam aperta con successo
📤 Frame 30 inviato a Kinesis
```

**Consumer:**
```
🎯 DETECTED in frame 15: person (95%), laptop (88%)
🎯 DETECTED in frame 23: bottle (92%)
```

## ⚙️ Configurazione

Modifica `settings.py` per:
- Cambiare oggetti da rilevare: `YOLO_CLASSES_TO_DETECT`
- Modificare soglia confidenza: `THRESHOLD`
- Cambiare risoluzione video: `WIDTH`

## 🛑 Per Fermare

- **Producer**: Premi 'q' nella finestra video o Ctrl+C
- **Consumer**: Ctrl+C nel terminale

---

✨ **Pipeline completa funzionante in 2 terminali!** ✨
