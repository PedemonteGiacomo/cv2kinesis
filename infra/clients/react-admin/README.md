# MIP Admin Portal

A React application for managing medical image processing algorithms.

## Features

- 🔐 **Secure Authentication** with AWS Cognito
- 📊 **Dashboard** to view all algorithms
- ➕ **Algorithm Creation** with guided form
- ✏️ **Edit Algorithms** existing ones
- 🗑️ **Safe Deletion** of algorithms
- 🚀 **Automatic Deploy** on AWS Fargate + CloudFront
- 📱 **Responsive Design** with Material-UI

## Architettura

```
[CloudFront] → [ALB] → [Fargate] → [React App]
                                        ↓
                                  [API Gateway] → [Lambda]
                                        ↓
                                   [DynamoDB]
```

## Technology Stack

- **Frontend**: React 18, Material-UI, AWS Amplify
- **Authentication**: AWS Cognito
- **Containerization**: Docker + nginx
- **Deploy**: AWS Fargate, CloudFront, ALB
- **API**: AWS API Gateway, Lambda

## Local Setup

### Prerequisites

- Node.js 18+
- Docker
- AWS CLI configured

### Installation

```bash
# Clone and install dependencies
cd infra/clients/react-admin
npm install

# Copy and configure environment variables
cp .env.example .env.local
# Edit .env.local with your values
```

### `.env.local` Configuration

```env
REACT_APP_AWS_REGION=us-east-1
REACT_APP_USER_POOL_ID=us-east-1_XXXXXXXXX
REACT_APP_USER_POOL_CLIENT_ID=your-cognito-client-id
REACT_APP_API_BASE_URL=https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod
REACT_APP_ADMIN_KEY=your-admin-key-here
```

### Development Start

```bash
# Start development server
npm start

# App will be available at http://localhost:3000
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

### First Access

1. After deployment, go to CloudFront URL shown in outputs
2. Click "Create Account" to create first user
3. Verify email received from Cognito
4. Login

### Algorithm Management

#### Create New Algorithm

1. Click "New Algorithm"
2. Fill required fields:
   - **Name**: Algorithm identifier
   - **Version**: Semantic version (ex: 1.0.0)
   - **Docker Image**: Full image URI
   - **CPU/Memory**: Required resources
3. Configure advanced options if needed:
   - Environment variables
   - Startup commands
   - Exposed ports
4. Click "Create"

#### Edit Algorithm

1. Click "Edit" on algorithm card
2. Update necessary fields
3. Click "Update"

#### Delete Algorithm

1. Click "Delete" on algorithm card
2. Confirm deletion

### Algorithm States

- **🟢 Active**: Algorithm running and ready to receive requests
- **🔴 Inactive**: Algorithm stopped or unavailable
- **🟡 Pending**: Algorithm starting up or updating

## Project Structure

```
react-admin/
├── public/
│   └── index.html          # HTML template
├── src/
│   ├── components/
│   │   ├── AlgorithmManager.js    # Main component
│   │   └── AlgorithmForm.js       # Algorithm form
│   ├── services/
│   │   └── apiService.js          # API Gateway client
│   ├── App.js              # Root component with Cognito
│   ├── App.css             # Global styles
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
