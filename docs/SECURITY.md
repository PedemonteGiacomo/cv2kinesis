# Security and Authentication

The Medical Image Processing system uses AWS Cognito for secure authentication with **role-based authorization** through Cognito Groups.

## Security Architecture

```
[Client] → [Cognito Authentication] → [JWT Token with Groups] → [API Gateway] → [Lambda with Role-based Authorization]
```

### Roles and Permissions

#### **Administrators Group**
- **Permissions**: Full CRUD on algorithms (Create, Read, Update, Delete)
- **Portal**: Admin Portal (react-admin)
- **API Access**: All `/admin/algorithms/*` endpoints

#### **Users Group** 
- **Permissions**: Read-only algorithms
- **Portal**: User Portal (react-app)  
- **API Access**: Only GET `/admin/algorithms` and `/admin/algorithms/{id}`

### Authentication Flow

1. **Login**: User authenticates with Cognito using email/password
2. **JWT Token**: Cognito returns a valid JWT access token
3. **API Request**: Client sends token in `Authorization: Bearer <token>` header
4. **Validation**: Admin Lambda validates JWT token using Cognito public keys
5. **Access**: If valid, user can access administration APIs

## Cognito Setup

### 1. After Deployment

AdminStack deployment automatically creates:
- User Pool for admin users
- User Pool Client for the application
- JWT configuration for Lambda

### 2. Create Users with Roles

#### Administrator User
```powershell
.\scripts\create-admin-user.ps1 `
    -Username "admin@yourcompany.com" `
    -Password "AdminPassword123!" `
    -Role "Administrators"
```

#### Regular User (Read-Only)
```powershell
.\scripts\create-admin-user.ps1 `
    -Username "user@yourcompany.com" `
    -Password "UserPassword123!" `
    -Role "Users"
```

#### Quick Setup with Example Users
```powershell
.\scripts\setup-example-users.ps1
```

### 3. API Testing

```powershell
# Test with admin user (full access)
.\test\test-admin-api.ps1 -Username "admin@yourcompany.com" -Password "AdminPassword123!"

# Test with regular user (read-only)
.\test\test-admin-api.ps1 -Username "user@yourcompany.com" -Password "UserPassword123!"
```

## JWT Token Management

### In React Frontend

#### Admin Portal (react-admin)
- Full access for users in "Administrators" group
- Complete CRUD interface for algorithm management
- Permission validation on client and server side

#### User Portal (react-app)
- Read-only access for users in "Users" group
- Algorithm catalog view
- Simplified interface without edit functions

### Token Validation

The admin Lambda validates tokens by checking:
- **Signature**: Using Cognito public keys
- **Issuer**: Verifies token comes from correct User Pool
- **Expiration**: Checks token is not expired
- **Token Use**: Verifies it's an access token
- **Groups**: Checks Cognito groups for authorization (`cognito:groups`)

### Role-Based Authorization

```javascript
// Example authorization logic in Lambda
const userGroups = payload.get('cognito:groups', []);

const permissions = {
  'read': ['Administrators', 'Users'],   // Both can read
  'write': ['Administrators'],           // Only admin can write
  'admin': ['Administrators']            // Only admin for admin operations
};
```

## API Security

### Required Headers

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

### "Authentication failed" Error

1. Verify user exists in User Pool
2. Check password is correct
3. Verify user is confirmed (status CONFIRMED)

### "Token verification failed" Error

1. Check token is not expired
2. Verify USER_POOL_ID is correct in Lambda
3. Check connectivity for JWKS key download

### Password Reset

```powershell
# Reset password via CLI
aws cognito-idp admin-set-user-password `
    --user-pool-id $env:USER_POOL_ID `
    --username "admin@yourcompany.com" `
    --password "NewPassword123!" `
    --permanent
```

## Monitoring

### CloudWatch Logs

- `/aws/lambda/ImgPipeline-AdminAlgosFn*`: Admin Lambda logs
- Search "Token verification" for authentication debugging

### Cognito Metrics

- User sign-ins
- Authentication failures
- Token requests

## Best Practices

1. **Password Rotation**: Change admin passwords periodically
2. **Token Expiry**: Tokens automatically expire after 24h
3. **HTTPS Only**: Always use HTTPS to protect tokens
4. **Principle of Least Privilege**: Each user should have only necessary permissions

## Admin Key Migration

If migrating from old system with `x-admin-key`:

1. **Deploy new system** with Cognito
2. **Create admin users** with new script
3. **Update clients** to use Bearer token instead of x-admin-key
4. **Remove references** to old hardcoded admin keys
