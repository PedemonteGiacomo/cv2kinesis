# Sicurezza e Autenticazione

Il sistema Medical Image Processing utilizza AWS Cognito per l'autenticazione sicura con **autorizzazione basata sui ruoli** attraverso Cognito Groups.

## Architettura di Sicurezza

```
[Client] → [Cognito Authentication] → [JWT Token with Groups] → [API Gateway] → [Lambda with Role-based Authorization]
```

### Ruoli e Permessi

#### **Administrators Group**
- **Permessi**: CRUD completo su algoritmi (Create, Read, Update, Delete)
- **Portal**: Admin Portal (react-admin)
- **API Access**: Tutti gli endpoint `/admin/algorithms/*`

#### **Users Group** 
- **Permessi**: Solo lettura algoritmi (Read-only)
- **Portal**: User Portal (react-app)  
- **API Access**: Solo GET `/admin/algorithms` e `/admin/algorithms/{id}`

### Flusso di Autenticazione

1. **Login**: L'utente si autentica con Cognito usando email/password
2. **Token JWT**: Cognito restituisce un access token JWT valido
3. **API Request**: Il client invia il token nell'header `Authorization: Bearer <token>`
4. **Validation**: La Lambda admin valida il token JWT usando le chiavi pubbliche di Cognito
5. **Access**: Se valido, l'utente può accedere alle API di amministrazione

## Setup Cognito

### 1. Dopo il Deploy

Il deploy dell'AdminStack crea automaticamente:
- User Pool per gli utenti admin
- User Pool Client per l'applicazione
- Configurazione JWT per la Lambda

### 2. Creare Utenti con Ruoli

#### Utente Amministratore
```powershell
.\scripts\create-admin-user.ps1 `
    -Username "admin@tuazienda.com" `
    -Password "AdminPassword123!" `
    -Role "Administrators"
```

#### Utente Normale (Solo Lettura)
```powershell
.\scripts\create-admin-user.ps1 `
    -Username "user@tuazienda.com" `
    -Password "UserPassword123!" `
    -Role "Users"
```

#### Setup Rapido con Utenti di Esempio
```powershell
.\scripts\setup-example-users.ps1
```

### 3. Test delle API

```powershell
# Test con utente admin (accesso completo)
.\test\test-admin-api.ps1 -Username "admin@tuazienda.com" -Password "AdminPassword123!"

# Test con utente normale (solo lettura)
.\test\test-admin-api.ps1 -Username "user@tuazienda.com" -Password "UserPassword123!"
```

## Gestione Token JWT

### Nel Frontend React

#### Admin Portal (react-admin)
- Accesso completo per utenti in gruppo "Administrators"
- Interfaccia CRUD completa per gestione algoritmi
- Validazione permessi lato client e server

#### User Portal (react-app)
- Accesso read-only per utenti in gruppo "Users"
- Visualizzazione catalogo algoritmi
- Interfaccia semplificata senza funzioni di modifica

### Token Validation

La Lambda admin valida i token controllando:
- **Signature**: Usando le chiavi pubbliche di Cognito
- **Issuer**: Verifica che il token venga dal User Pool corretto
- **Expiration**: Controlla che il token non sia scaduto
- **Token Use**: Verifica che sia un access token
- **Groups**: Controlla i gruppi Cognito per autorizzazione (`cognito:groups`)

### Autorizzazione Basata sui Ruoli

```javascript
// Esempio logica autorizzazione nella Lambda
const userGroups = payload.get('cognito:groups', []);

const permissions = {
  'read': ['Administrators', 'Users'],   // Entrambi possono leggere
  'write': ['Administrators'],           // Solo admin possono scrivere
  'admin': ['Administrators']            // Solo admin per operazioni admin
};
```

## Sicurezza API

### Headers Richiesti

```http
Authorization: Bearer <cognito-jwt-token>
Content-Type: application/json
```

### CORS Configuration

```javascript
{
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type,Authorization",
  "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"
}
```

## Troubleshooting

### Errore "Authentication failed"

1. Verificare che l'utente esista nel User Pool
2. Controllare che la password sia corretta
3. Verificare che l'utente sia confermato (status CONFIRMED)

### Errore "Token verification failed"

1. Controllare che il token non sia scaduto
2. Verificare che l'USER_POOL_ID sia corretto nella Lambda
3. Controllare la connettività per il download delle chiavi JWKS

### Reset Password

```powershell
# Reset password via CLI
aws cognito-idp admin-set-user-password `
    --user-pool-id $env:USER_POOL_ID `
    --username "admin@tuazienda.com" `
    --password "NuovaPassword123!" `
    --permanent
```

## Monitoraggio

### CloudWatch Logs

- `/aws/lambda/ImgPipeline-AdminAlgosFn*`: Log della Lambda admin
- Cercare "Token verification" per debug autenticazione

### Metriche Cognito

- User sign-ins
- Authentication failures
- Token requests

## Best Practices

1. **Rotazione Password**: Cambiare periodicamente le password admin
2. **Token Expiry**: I token scadono automaticamente dopo 24h
3. **HTTPS Only**: Usare sempre HTTPS per proteggere i token
4. **Principio del Minimo Privilegio**: Ogni utente dovrebbe avere solo i permessi necessari

## Migrazione da Admin Key

Se stai migrando dal vecchio sistema con `x-admin-key`:

1. **Deploy nuovo sistema** con Cognito
2. **Creare utenti admin** con il nuovo script
3. **Aggiornare client** per usare Bearer token invece di x-admin-key
4. **Rimuovere riferimenti** alle vecchie chiavi admin hardcoded
