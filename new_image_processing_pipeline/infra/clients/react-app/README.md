# Frontend React di test per provisioning e processing

## Setup

1. Installa le dipendenze:
   ```bash
   npm ci --prefix infra/clients/react-app
   ```
2. Avvia il frontend:
   ```bash
   npm start --prefix infra/clients/react-app
   ```
3. Imposta la variabile `API_BASE` in `src/index.jsx` con l'endpoint del tuo API Gateway (es: `https://xyz.execute-api.eu-central-1.amazonaws.com/prod`).
4. Apri [http://localhost:3000](http://localhost:3000) nel browser.

## Flusso end-to-end

1. **Provisiona la coda**: Clicca "Provisiona coda" per creare dinamicamente una coda SQS e la subscription SNS per il tuo client. Ricevi `client_id` e `queue_url`.
2. **Invia job**: Clicca "Avvia processing" per inviare un job di processing con `{ callback: { client_id } }`.
3. **Ricevi risultati**: Il frontend pollerà la coda via HTTP chiamando `/proxy-sqs?queue=<queue_url>` e mostrerà il risultato appena disponibile.

### Esempio polling React
```js
async function pollResult(jid) {
  while(true) {
    const sqsRes = await fetch(
      `${API_BASE}/proxy-sqs?queue=${encodeURIComponent(queueUrl)}`
    );
    const msgs = await sqsRes.json();
    const found = msgs.find(m=>m.job_id===jid);
    if(found) {
      setResult(found);
      setStatus('done');
      return;
    }
    await new Promise(r=>setTimeout(r,2000));
  }
}
```

**Nota:** Tutto il flusso è HTTP puro, nessuna credenziale AWS nel browser.
