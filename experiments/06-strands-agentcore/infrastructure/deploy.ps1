[CmdletBinding()]
param(
    [string]$StackName = 'agentcore-policy-field-lab',
    [string]$RateLimitStackName = 'agentcore-policy-field-lab-rate-limit',
    [string]$Region = '<approved-region>',
    [string]$CallerPrincipalArn = '',
    [ValidateSet('LOG_ONLY', 'ENFORCE')]
    [string]$PolicyEngineMode = 'LOG_ONLY',
    [ValidateSet('LOG_ONLY', 'ACTIVE')]
    [string]$PolicyEnforcementMode = 'LOG_ONLY',
    [int]$SessionWriteLimit = 3,
    [int]$RetryLimit = 3,
    [int]$RequestsPerSecond = 5,
    [switch]$Apply,
    [switch]$ApplyRateLimit
)

$ErrorActionPreference = 'Stop'
$templatePath = Join-Path $PSScriptRoot 'agentcore-policy-lab.yaml'
$rateLimitTemplatePath = Join-Path $PSScriptRoot 'agentcore-rate-limit.yaml'

& (Join-Path $PSScriptRoot 'plan.ps1') `
    -TemplatePath $templatePath `
    -RateLimitTemplatePath $rateLimitTemplatePath `
    -Region $Region

if (-not $Apply -and -not $ApplyRateLimit) {
    Write-Host 'PLAN ONLY: no AWS mutation requested.'
    Write-Host 'Use -Apply for the CloudFormation stack or -ApplyRateLimit for the separate throttle.'
    exit 0
}
if ($Region -eq '<approved-region>') {
    throw 'Supply an approved AWS Region before applying changes.'
}
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw 'AWS CLI is required to apply changes.'
}

if ($Apply) {
    if ($CallerPrincipalArn -notmatch '^arn:aws(-[a-z0-9-]+)?:iam::[0-9]{12}:(role|user)/.+$') {
        throw 'Supply the approved operator IAM role or user ARN in -CallerPrincipalArn.'
    }
    Write-Host "Applying CloudFormation stack $StackName in $Region."
    aws cloudformation deploy `
        --stack-name $StackName `
        --region $Region `
        --template-file $templatePath `
        --capabilities CAPABILITY_IAM `
        --no-fail-on-empty-changeset `
        --parameter-overrides `
            "CallerPrincipalArn=$CallerPrincipalArn" `
            "PolicyEngineMode=$PolicyEngineMode" `
            "PolicyEnforcementMode=$PolicyEnforcementMode" `
            "SessionWriteLimit=$SessionWriteLimit" `
            "RetryLimit=$RetryLimit"
    if ($LASTEXITCODE -ne 0) {
        throw 'CloudFormation deployment failed.'
    }
}

if ($ApplyRateLimit) {
    $gatewayId = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query "Stacks[0].Outputs[?OutputKey=='GatewayIdentifier'].OutputValue | [0]" `
        --output text
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gatewayId) -or $gatewayId -eq 'None') {
        throw 'Could not resolve GatewayIdentifier from the deployed stack.'
    }
    Write-Host "Applying separate rate-limit stack $RateLimitStackName. This is not authorization evidence."
    aws cloudformation deploy `
        --stack-name $RateLimitStackName `
        --region $Region `
        --template-file $rateLimitTemplatePath `
        --no-fail-on-empty-changeset `
        --parameter-overrides `
            "GatewayIdentifier=$gatewayId" `
            "RequestsPerSecond=$RequestsPerSecond"
    if ($LASTEXITCODE -ne 0) {
        throw 'Gateway rate-limit CloudFormation deployment failed.'
    }
}
