# Create user in Cognito User Pool with role assignment
param(
    [Parameter(Mandatory=$true)]
    [string]$Username,
    
    [Parameter(Mandatory=$true)]
    [string]$Password,
    
    [Parameter(Mandatory=$false)]
    [string]$Email = $Username,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("Administrators", "Users")]
    [string]$Role = "Users",
    
    [Parameter(Mandatory=$false)]
    [string]$UserPoolId = $env:USER_POOL_ID
)

if (-not $UserPoolId) {
    Write-Error "USER_POOL_ID environment variable not set"
    Write-Host "Load environment first: . .\gen_env\env.ps1"
    exit 1
}

Write-Host "Creating user in Cognito User Pool..." -ForegroundColor Green
Write-Host "User Pool ID: $UserPoolId" -ForegroundColor Cyan
Write-Host "Username: $Username" -ForegroundColor Cyan
Write-Host "Email: $Email" -ForegroundColor Cyan
Write-Host "Role: $Role" -ForegroundColor Cyan

try {
    # Create user
    Write-Host "`nCreating user..." -ForegroundColor Yellow
    $createResult = aws cognito-idp admin-create-user `
        --user-pool-id $UserPoolId `
        --username $Username `
        --user-attributes Name=email,Value=$Email Name=email_verified,Value=true `
        --temporary-password $Password `
        --message-action SUPPRESS `
        --output json
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create user"
    }
    
    Write-Host "User created successfully!" -ForegroundColor Green
    
    # Set permanent password
    Write-Host "`nSetting permanent password..." -ForegroundColor Yellow
    $passwordResult = aws cognito-idp admin-set-user-password `
        --user-pool-id $UserPoolId `
        --username $Username `
        --password $Password `
        --permanent
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set permanent password"
    }
    
    Write-Host "Password set successfully!" -ForegroundColor Green
    
    # Confirm user status
    Write-Host "`nConfirming user..." -ForegroundColor Yellow
    $confirmResult = aws cognito-idp admin-confirm-sign-up `
        --user-pool-id $UserPoolId `
        --username $Username
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "User confirmation may have failed, but user might still be usable"
    } else {
        Write-Host "User confirmed successfully!" -ForegroundColor Green
    }
    
    # Add user to appropriate group
    Write-Host "`nAdding user to $Role group..." -ForegroundColor Yellow
    $groupResult = aws cognito-idp admin-add-user-to-group `
        --user-pool-id $UserPoolId `
        --username $Username `
        --group-name $Role
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to add user to group, but user is still created"
    } else {
        Write-Host "User added to $Role group successfully!" -ForegroundColor Green
    }
    
    Write-Host "`n✅ User created and ready to use!" -ForegroundColor Green
    Write-Host "`nUser details:" -ForegroundColor Yellow
    Write-Host "- Username: $Username" -ForegroundColor White
    Write-Host "- Role: $Role" -ForegroundColor White
    Write-Host "- Permissions: $(if ($Role -eq 'Administrators') { 'Full CRUD access' } else { 'Read-only access' })" -ForegroundColor White
    Write-Host "`nYou can now test with:" -ForegroundColor Yellow
    Write-Host ".\test\test-admin-api.ps1 -Username '$Username' -Password '$Password'" -ForegroundColor White
    
} catch {
    Write-Error "Failed to create admin user: $_"
    
    # Try to get more info about existing user
    Write-Host "`nChecking if user already exists..." -ForegroundColor Yellow
    try {
        $userInfo = aws cognito-idp admin-get-user `
            --user-pool-id $UserPoolId `
            --username $Username `
            --output json 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "User already exists!" -ForegroundColor Yellow
            $user = $userInfo | ConvertFrom-Json
            Write-Host "Status: $($user.UserStatus)" -ForegroundColor Cyan
            
            # Try to update password
            Write-Host "Updating password for existing user..." -ForegroundColor Yellow
            aws cognito-idp admin-set-user-password `
                --user-pool-id $UserPoolId `
                --username $Username `
                --password $Password `
                --permanent
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Password updated for existing user!" -ForegroundColor Green
                
                # Try to add to group
                Write-Host "Adding user to $Role group..." -ForegroundColor Yellow
                aws cognito-idp admin-add-user-to-group `
                    --user-pool-id $UserPoolId `
                    --username $Username `
                    --group-name $Role 2>$null
                
                Write-Host "You can now test with: .\test\test-admin-api.ps1 -Username '$Username' -Password '$Password'" -ForegroundColor White
            }
        }
    } catch {
        Write-Host "User does not exist and creation failed" -ForegroundColor Red
    }
    
    exit 1
}
