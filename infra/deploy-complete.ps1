# Complete script for deployment and testing of the new architecture
param(
    [string] $Region = "us-east-1",
    [string] $Account = "544547773663",
    [switch] $SkipECR,
    [switch] $SkipDeploy,
    [switch] $TestOnly,
    [switch] $SkipTest,
    [switch] $IncludeAdmin,
    [string] $AdminDomain,
    [string] $AdminCertArn,
    [switch] $NoCache
)

$ErrorActionPreference = "Stop"

Write-Host "Complete deployment of dynamic MIP architecture" -ForegroundColor Green
Write-Host "Region: $Region, Account: $Account" -ForegroundColor Yellow


# Return to project root
Push-Location (Join-Path $PSScriptRoot "..")

# Move to infra folder for CDK commands
Push-Location $PSScriptRoot

try {
    if (-not $TestOnly) {
        # 1. ECR e build immagini
        if (-not $SkipECR) {
            Write-Host "1. Preparing ECR repositories..." -ForegroundColor Cyan
            & "$PSScriptRoot\ecr\create-ecr-repos.ps1" -Region $Region -Account $Account
            # if ($LASTEXITCODE -ne 0) { throw "ECR creation failed" }

            Write-Host "Building and pushing images..." -ForegroundColor Cyan
            & "$PSScriptRoot\ecr\push-algos.ps1" -Region $Region -Account $Account
            if ($LASTEXITCODE -ne 0) { throw "Image push failed" }

            Write-Host "Pushing PACS API..." -ForegroundColor Cyan
            & "$PSScriptRoot\ecr\push-pacs.ps1" -Region $Region -Account $Account
            if ($LASTEXITCODE -ne 0) { throw "PACS push failed" }

            # Build and push admin portal if requested (before CDK deploy for initial setup)
            if ($IncludeAdmin) {
                Write-Host "Building and pushing Admin Portal (initial)..." -ForegroundColor Cyan
                if ($NoCache) {
                    & "$PSScriptRoot\ecr\push-admin.ps1" -Region $Region -Account $Account -NoCache
                } else {
                    & "$PSScriptRoot\ecr\push-admin.ps1" -Region $Region -Account $Account
                }
                if ($LASTEXITCODE -ne 0) { throw "Admin portal push failed" }
            }
        }

        # 2. Deploy CDK
        if (-not $SkipDeploy) {
            $env:AWS_REGION = $Region
            $env:AWS_ACCOUNT = $Account
            Write-Host "Setting AWS region to $env:AWS_REGION and account to $env:AWS_ACCOUNT" -ForegroundColor Yellow

            Write-Host "2. Deploying CDK stacks..." -ForegroundColor Cyan
            

            Write-Host "Deploying Imports stack..." -ForegroundColor Yellow
            cdk deploy Imports --require-approval never
            if ($LASTEXITCODE -ne 0) { throw "Imports deploy failed" }

            Write-Host "Deploying PacsApi stack..." -ForegroundColor Yellow
            cdk deploy PacsApi --require-approval never
            if ($LASTEXITCODE -ne 0) { throw "PacsApi deploy failed" }

            Write-Host "Deploying ImgPipeline stack..." -ForegroundColor Yellow
            cdk deploy ImgPipeline --require-approval never
            if ($LASTEXITCODE -ne 0) { throw "ImgPipeline deploy failed" }

            # Deploy Admin Stack if requested
            if ($IncludeAdmin) {
                Write-Host "Deploying AdminStack..." -ForegroundColor Yellow
                
                # Set admin domain configuration if provided
                if ($AdminDomain) {
                    $env:ADMIN_DOMAIN_NAME = $AdminDomain
                }
                if ($AdminCertArn) {
                    $env:ADMIN_CERTIFICATE_ARN = $AdminCertArn
                }
                
                cdk deploy AdminStack --require-approval never
                if ($LASTEXITCODE -ne 0) { throw "AdminStack deploy failed" }
                
                # Rebuild and push admin portal with correct Cognito configuration
                Write-Host "Rebuilding Admin Portal with Cognito configuration..." -ForegroundColor Cyan
                
                # Get AdminStack outputs
                $adminStackOutputs = aws cloudformation describe-stacks --region $Region --stack-name AdminStack --query "Stacks[0].Outputs" | ConvertFrom-Json
                $userPoolId = ($adminStackOutputs | Where-Object { $_.OutputKey -eq "UserPoolId" }).OutputValue
                $userPoolClientId = ($adminStackOutputs | Where-Object { $_.OutputKey -eq "UserPoolClientId" }).OutputValue
                
                # Get ImgPipeline API URL
                $imgStackOutputs = aws cloudformation describe-stacks --region $Region --stack-name ImgPipeline --query "Stacks[0].Outputs" | ConvertFrom-Json
                $apiBaseUrl = ($imgStackOutputs | Where-Object { $_.OutputKey -eq "ProcessingApiEndpoint" }).OutputValue
                
                if ($userPoolId -and $userPoolClientId -and $apiBaseUrl) {
                    # Set environment variables for admin portal build
                    $env:REACT_APP_USER_POOL_ID = $userPoolId
                    $env:REACT_APP_USER_POOL_CLIENT_ID = $userPoolClientId
                    $env:REACT_APP_AWS_REGION = $Region
                    $env:REACT_APP_API_BASE_URL = $apiBaseUrl
                    
                    Write-Host "Cognito configuration:" -ForegroundColor Yellow
                    Write-Host "  User Pool ID: $userPoolId" -ForegroundColor White
                    Write-Host "  Client ID: $userPoolClientId" -ForegroundColor White
                    Write-Host "  Region: $Region" -ForegroundColor White
                    Write-Host "  API Base URL: $apiBaseUrl" -ForegroundColor White
                    
                    if ($NoCache) {
                        & "$PSScriptRoot\ecr\push-admin.ps1" -Region $Region -Account $Account -Tag "cognito-configured" -NoCache
                    } else {
                        & "$PSScriptRoot\ecr\push-admin.ps1" -Region $Region -Account $Account -Tag "cognito-configured"
                    }
                    if ($LASTEXITCODE -ne 0) { throw "Admin portal rebuild failed" }
                    
                    # Update ECS service to use new image
                    Write-Host "Updating ECS service with new image..." -ForegroundColor Cyan
                    $adminClusterName = ($adminStackOutputs | Where-Object { $_.OutputKey -eq "AdminClusterName" }).OutputValue
                    if ($adminClusterName) {
                        # Get the actual service name from ECS
                        $servicesJson = aws ecs list-services --region $Region --cluster $adminClusterName
                        if ($LASTEXITCODE -eq 0) {
                            $services = $servicesJson | ConvertFrom-Json
                            if ($services.serviceArns -and $services.serviceArns.Count -gt 0) {
                                $serviceArn = $services.serviceArns[0]
                                $serviceName = $serviceArn.Split('/')[-1]
                                
                                Write-Host "Found service: $serviceName" -ForegroundColor Cyan
                                aws ecs update-service --region $Region --cluster $adminClusterName --service $serviceName --force-new-deployment > $null
                                if ($LASTEXITCODE -eq 0) {
                                    Write-Host "ECS service update initiated" -ForegroundColor Green
                                    
                                    # Invalidate CloudFront cache to ensure new version is served
                                    $cloudFrontDistributionId = ($adminStackOutputs | Where-Object { $_.OutputKey -eq "AdminCloudFrontDistributionId" }).OutputValue
                                    if ($cloudFrontDistributionId) {
                                        Write-Host "Invalidating CloudFront cache..." -ForegroundColor Cyan
                                        aws cloudfront create-invalidation --region $Region --distribution-id $cloudFrontDistributionId --paths "/*" > $null
                                        if ($LASTEXITCODE -eq 0) {
                                            Write-Host "CloudFront cache invalidation initiated" -ForegroundColor Green
                                        } else {
                                            Write-Warning "Failed to invalidate CloudFront cache, but service was updated"
                                        }
                                    } else {
                                        Write-Warning "CloudFront distribution ID not found in outputs"
                                    }
                                } else {
                                    Write-Warning "Failed to update ECS service, but image was rebuilt successfully"
                                }
                            } else {
                                Write-Warning "No services found in cluster $adminClusterName"
                            }
                        } else {
                            Write-Warning "Failed to list services in cluster $adminClusterName"
                        }
                    }
                } else {
                    Write-Warning "Could not retrieve required configuration from stack outputs"
                    Write-Warning "UserPoolId: $userPoolId, ClientId: $userPoolClientId, ApiUrl: $apiBaseUrl"
                }
            }

            # Torna alla root dopo il deploy CDK
            Pop-Location

            Write-Host "All stacks deployed successfully!" -ForegroundColor Green
        }

        # 3. Generate environment variables
        Write-Host "3. Generating environment variables..." -ForegroundColor Cyan
        & "$PSScriptRoot\gen_env\gen_env.ps1" -ImgStack "ImgPipeline" -PacsStack "PacsApi"
        if ($LASTEXITCODE -ne 0) { throw "Environment generation failed" }

        # Import variables
        . "$PSScriptRoot\gen_env\env.ps1"
        Write-Host "Environment variables loaded." -ForegroundColor Green
    }

    if (-not $SkipTest) {
        # 4. User Management and Testing:
        Write-Host "4. User Management and Testing:" -ForegroundColor Cyan
        Write-Host "Create users with different roles:" -ForegroundColor Yellow
        Write-Host "  Admin user:    .\scripts\create-admin-user.ps1 -Username 'admin@company.com' -Password 'AdminPass123!' -Role 'Administrators'" -ForegroundColor White
        Write-Host "  Regular user:  .\scripts\create-admin-user.ps1 -Username 'user@company.com' -Password 'UserPass123!' -Role 'Users'" -ForegroundColor White
        Write-Host "Or setup example users: .\scripts\setup-example-users.ps1" -ForegroundColor White
        Write-Host "`nTest API with roles:" -ForegroundColor Yellow
        Write-Host "  .\test\test-admin-api.ps1 -Username 'admin@company.com' -Password 'AdminPass123!'" -ForegroundColor White

        Write-Host "Waiting for provisioning to complete..." -ForegroundColor Cyan
        Start-Sleep -Seconds 60

        # 5. Test API amministrazione
        Write-Host "5. Testing administration API..." -ForegroundColor Cyan

        if (-not $env:API_BASE) {
            Write-Host "Loading environment variables..." -ForegroundColor Yellow
            if (Test-Path "$PSScriptRoot\gen_env\env.ps1") {
                . "$PSScriptRoot\gen_env\env.ps1"
            } else {
                throw "Environment file not found. Run without -TestOnly first."
            }
        }

        # Note: Admin API testing now requires Cognito authentication
        Write-Host "5. Admin API authentication info:" -ForegroundColor Cyan
        Write-Host "To test admin API, create a user in Cognito and use:" -ForegroundColor Yellow
        Write-Host ".\test\test-admin-api.ps1 -Username 'user@example.com' -Password 'Password123!'" -ForegroundColor White

        # 6. Test end-to-end processing
        Write-Host "6. Testing end-to-end processing..." -ForegroundColor Cyan
        
        $testJob = @{
            job_id = "e2e-test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            client_id = "test-client-e2e"
            pacs    = @{
                study_id  = "liver1/phantomx_abdomen_pelvis_dataset/D55-01"
                series_id = "300/AiCE_BODY-SHARP_300_172938.900"
                image_id  = "IM-0135-0095.dcm"
                scope     = "image"
            }
        } | ConvertTo-Json -Depth 4 -Compress

        try {
            Write-Host "Sending test job to processing_1..." -ForegroundColor Yellow
            $response = Invoke-RestMethod -Uri "$env:API_BASE/process/processing_1" -Method POST -Headers @{
                'Content-Type' = 'application/json'
            } -Body ($testJob | ConvertTo-Json -Depth 10)
            
            Write-Host "Job submitted successfully!" -ForegroundColor Green
            $response | ConvertTo-Json -Depth 10 | Write-Host
            
        } catch {
            Write-Host "Job submission failed: $($_.Exception.Message)" -ForegroundColor Red
            if ($_.Exception.Response) {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $errorBody = $reader.ReadToEnd()
                Write-Host "Response: $errorBody" -ForegroundColor Red
            }
        }
    }

    Write-Host "\nDeploy and test completed!" -ForegroundColor Green
    Write-Host "\nNext steps:" -ForegroundColor Yellow
    Write-Host "1. Check CloudWatch logs for Lambda functions" -ForegroundColor White
    Write-Host "2. Monitor ECS services in the console" -ForegroundColor White
    Write-Host "3. Test with the React frontend" -ForegroundColor White
    Write-Host "\nAPI Endpoints:" -ForegroundColor Yellow
    Write-Host "- Processing: $($env:API_BASE)/process/{algo_id}" -ForegroundColor White
    Write-Host "- Admin: $($env:API_BASE)/admin/algorithms" -ForegroundColor White
    Write-Host "- Admin Key: $($env:ADMIN_KEY)" -ForegroundColor White
    Write-Host "- WebSocket: $($env:WS_ENDPOINT)" -ForegroundColor White
    
    if ($IncludeAdmin) {
        Write-Host "\nAdmin Portal:" -ForegroundColor Yellow
        if ($AdminDomain) {
            Write-Host "- Portal URL: https://$AdminDomain" -ForegroundColor White
        } else {
            Write-Host "- Check CDK outputs for CloudFront URL" -ForegroundColor White
        }
        Write-Host "- Admin login: Use 'Administrators' group users" -ForegroundColor White
        Write-Host "- User login: Use 'Users' group users for read-only access" -ForegroundColor White
    }
}
catch {
    Write-Host "\nError: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
