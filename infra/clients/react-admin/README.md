# MIP Admin Portal

Un'applicazione React per la gestione degli algoritmi di elaborazione delle immagini mediche.

## Caratteristiche

- 🔐 **Autenticazione sicura** con AWS Cognito
- 📊 **Dashboard** per visualizzare tutti gli algoritmi
- ➕ **Creazione algoritmi** con form guidato
- ✏️ **Modifica algoritmi** esistenti
- 🗑️ **Eliminazione** sicura degli algoritmi
- 🚀 **Deploy automatico** su AWS Fargate + CloudFront
- 📱 **Responsive design** con Material-UI

## Architettura

```
[CloudFront] → [ALB] → [Fargate] → [React App]
                                        ↓
                                  [API Gateway] → [Lambda]
                                        ↓
                                   [DynamoDB]
```

## Tecnologie

- **Frontend**: React 18, Material-UI, AWS Amplify
- **Autenticazione**: AWS Cognito
- **Containerizzazione**: Docker + nginx
- **Deploy**: AWS Fargate, CloudFront, ALB
- **API**: AWS API Gateway, Lambda

## Setup Locale

### Prerequisiti

- Node.js 18+
- Docker
- AWS CLI configurato

### Installazione

```bash
# Clona e installa dipendenze
cd infra/clients/react-admin
npm install

# Copia e configura le variabili di ambiente
cp .env.example .env.local
# Modifica .env.local con i tuoi valori
```

### Configurazione `.env.local`

```env
REACT_APP_AWS_REGION=us-east-1
REACT_APP_USER_POOL_ID=us-east-1_XXXXXXXXX
REACT_APP_USER_POOL_CLIENT_ID=your-cognito-client-id
REACT_APP_API_BASE_URL=https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod
REACT_APP_ADMIN_KEY=your-admin-key-here
```

### Avvio Sviluppo

```bash
# Avvia il server di sviluppo
npm start

# L'app sarà disponibile su http://localhost:3000
```

### Build

```bash
# Build per produzione
npm run build

# Test build locale
npx serve -s build
```

## Deploy su AWS

### 1. Build e Push dell'Immagine

```powershell
# Da PowerShell, nella directory infra/ecr
.\push-admin.ps1
```

### 2. Deploy dell'Infrastruttura

```powershell
# Da PowerShell, nella directory infra
cd ..
cdk deploy AdminStack
```

### 3. Configurazione Opzionale del Dominio

Per usare un dominio personalizzato, imposta le variabili di ambiente:

```powershell
$env:ADMIN_DOMAIN_NAME = "admin.tuodominio.com"
$env:ADMIN_CERTIFICATE_ARN = "arn:aws:acm:us-east-1:123456789012:certificate/..."
cdk deploy AdminStack
```

## Utilizzo

### Primo Accesso

1. Dopo il deploy, vai all'URL di CloudFront mostrato negli output
2. Clicca su "Create Account" per creare il primo utente
3. Verifica l'email ricevuta da Cognito
4. Effettua il login

### Gestione Algoritmi

#### Creare un Nuovo Algoritmo

1. Clicca su "Nuovo Algoritmo"
2. Compila i campi obbligatori:
   - **Nome**: Identificativo dell'algoritmo
   - **Versione**: Versione semantica (es: 1.0.0)
   - **Immagine Docker**: URI completo dell'immagine
   - **CPU/Memoria**: Risorse richieste
3. Configura le opzioni avanzate se necessario:
   - Variabili di ambiente
   - Comandi di avvio
   - Porte esposte
4. Clicca "Crea"

#### Modificare un Algoritmo

1. Clicca "Modifica" sulla card dell'algoritmo
2. Aggiorna i campi necessari
3. Clicca "Aggiorna"

#### Eliminare un Algoritmo

1. Clicca "Elimina" sulla card dell'algoritmo
2. Conferma l'eliminazione

### Stati degli Algoritmi

- **🟢 Attivo**: Algoritmo in esecuzione e pronto a ricevere richieste
- **🔴 Inattivo**: Algoritmo fermato o non disponibile
- **🟡 In attesa**: Algoritmo in fase di avvio o aggiornamento

## Struttura del Progetto

```
react-admin/
├── public/
│   └── index.html          # Template HTML
├── src/
│   ├── components/
│   │   ├── AlgorithmManager.js    # Componente principale
│   │   └── AlgorithmForm.js       # Form per algoritmi
│   ├── services/
│   │   └── apiService.js          # Client per API Gateway
│   ├── App.js              # Componente root con Cognito
│   ├── App.css             # Stili globali
│   └── index.js            # Entry point
├── Dockerfile              # Container per produzione
├── nginx.conf              # Configurazione nginx
├── package.json            # Dipendenze Node.js
└── .env.example           # Template variabili ambiente
```

## Sicurezza

- **Autenticazione**: Cognito con JWT tokens
- **Autorizzazione**: Admin key per API access
- **HTTPS**: Forzato tramite CloudFront
- **Headers di sicurezza**: Configurati in nginx
- **CORS**: Configurato su API Gateway

## Monitoraggio

### CloudWatch Logs

```bash
# Visualizza i log del container
aws logs tail /aws/ecs/mip-admin-portal --follow
```

### Metriche

- CPU/Memory utilization su ECS
- Request count su ALB
- Error rate su CloudFront

## Troubleshooting

### Errori Comuni

#### "Missing Cognito configuration"

- Verifica che `REACT_APP_USER_POOL_ID` e `REACT_APP_USER_POOL_CLIENT_ID` siano impostati
- Controlla che l'AdminStack sia stato deployato correttamente

#### "Errore di connessione: impossibile raggiungere il server"

- Verifica che `REACT_APP_API_BASE_URL` sia corretto
- Controlla che l'ImgPipeline stack sia attivo
- Verifica la configurazione CORS su API Gateway

#### "Unauthorized"

- Controlla che `REACT_APP_ADMIN_KEY` sia corretto
- Verifica che l'utente sia autenticato correttamente

### Debug

Per abilitare il debug:

```javascript
// In src/services/apiService.js
console.log('API Request:', url, requestOptions);
```

## Sviluppo

### Aggiungere Nuove Funzionalità

1. **Componenti**: Aggiungi in `src/components/`
2. **Servizi**: Estendi `src/services/apiService.js`
3. **Stili**: Usa Material-UI themes o `App.css`

### Test

```bash
# Run tests (da implementare)
npm test

# Type checking (se si migra a TypeScript)
npm run type-check
```

## Licenza

Proprietario - Medical Image Processing System
