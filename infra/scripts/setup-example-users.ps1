# Setup example users for different roles
param(
    [Parameter(Mandatory=$false)]
    [string]$UserPoolId = $env:USER_POOL_ID
)

if (-not $UserPoolId) {
    Write-Error "USER_POOL_ID environment variable not set"
    Write-Host "Load environment first: . .\gen_env\env.ps1"
    exit 1
}

Write-Host "Setting up example users for MIP system..." -ForegroundColor Green
Write-Host "User Pool ID: $UserPoolId" -ForegroundColor Cyan

try {
    # Create admin user
    Write-Host "`n=== Creating Administrator User ===" -ForegroundColor Yellow
    & "$PSScriptRoot\create-admin-user.ps1" `
        -Username "admin@mip-system.com" `
        -Password "AdminPass123!" `
        -Role "Administrators"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to create admin user, but continuing..."
    }
    
    # Create regular user
    Write-Host "`n=== Creating Regular User ===" -ForegroundColor Yellow
    & "$PSScriptRoot\create-admin-user.ps1" `
        -Username "user@mip-system.com" `
        -Password "UserPass123!" `
        -Role "Users"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to create regular user, but continuing..."
    }
    
    Write-Host "`n✅ User setup completed!" -ForegroundColor Green
    Write-Host "`nExample users created:" -ForegroundColor Yellow
    
    Write-Host "`n🔑 Administrator (Full Access):" -ForegroundColor Cyan
    Write-Host "  Username: admin@mip-system.com" -ForegroundColor White
    Write-Host "  Password: AdminPass123!" -ForegroundColor White
    Write-Host "  Permissions: Create, Read, Update, Delete algorithms" -ForegroundColor White
    Write-Host "  Portal: Admin Portal (react-admin)" -ForegroundColor White
    
    Write-Host "`n👤 Regular User (Read-Only):" -ForegroundColor Cyan
    Write-Host "  Username: user@mip-system.com" -ForegroundColor White
    Write-Host "  Password: UserPass123!" -ForegroundColor White
    Write-Host "  Permissions: View algorithms only" -ForegroundColor White
    Write-Host "  Portal: User Portal (react-app)" -ForegroundColor White
    
    Write-Host "`nTesting:" -ForegroundColor Yellow
    Write-Host "  Admin API: .\test\test-admin-api.ps1 -Username 'admin@mip-system.com' -Password 'AdminPass123!'" -ForegroundColor White
    Write-Host "  User API:  .\test\test-admin-api.ps1 -Username 'user@mip-system.com' -Password 'UserPass123!'" -ForegroundColor White
    
    Write-Host "`nPortals (after deploy):" -ForegroundColor Yellow
    Write-Host "  Admin Portal: Check AdminStack CloudFront URL in CDK outputs" -ForegroundColor White
    Write-Host "  User Portal:  Check UserAppStack CloudFront URL in CDK outputs" -ForegroundColor White
    
} catch {
    Write-Error "Setup failed: $_"
    exit 1
}
