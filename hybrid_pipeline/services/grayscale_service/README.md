# Test Locale del Servizio Grayscale

Questo servizio può essere testato localmente utilizzando il file `test_message.json`.

## Prerequisiti

- Assicurati che `test_message.json` sia presente nella cartella corrente.
- Docker installato sul tuo sistema.
- Il servizio deve essere buildato come immagine Docker. Esegui il comando:

```bash
docker build -f Dockerfile_aws -t grayscale_test:latest .
```

## Esecuzione del Test

Esegui il seguente comando per avviare il container Docker e testare il servizio:

```bash
docker run --rm -it ^
    -v "${PWD}\test_message.json:/app/test_message.json" ^
    grayscale_test:latest ^
    python app.py /app/test_message.json
```

> **Nota:** Su Linux/MacOS sostituisci `^` con `\` e usa `${PWD}` invece di `${PWD}\`.

## Risultati

Al termine dell'esecuzione, il servizio elaborerà il file `test_message.json` e mostrerà l'output direttamente nel terminale.
