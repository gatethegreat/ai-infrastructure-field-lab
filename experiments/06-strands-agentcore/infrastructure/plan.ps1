[CmdletBinding()]
param(
    [string]$TemplatePath = '',
    [string]$RateLimitTemplatePath = '',
    [string]$Region = '<approved-region>',
    [switch]$ValidateWithAws
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TemplatePath)) {
    $TemplatePath = Join-Path $PSScriptRoot 'agentcore-policy-lab.yaml'
}
if ([string]::IsNullOrWhiteSpace($RateLimitTemplatePath)) {
    $RateLimitTemplatePath = Join-Path $PSScriptRoot 'agentcore-rate-limit.yaml'
}

foreach ($path in @($TemplatePath, $RateLimitTemplatePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Template not found: $path"
    }
}

$template = Get-Content -LiteralPath $TemplatePath -Raw
$requiredResources = @(
    'AWS::BedrockAgentCore::Gateway',
    'AWS::BedrockAgentCore::GatewayTarget',
    'AWS::BedrockAgentCore::PolicyEngine',
    'AWS::BedrockAgentCore::Policy',
    'AWS::Lambda::Function'
)
foreach ($resource in $requiredResources) {
    if (-not $template.Contains($resource)) {
        throw "Template is missing required resource type: $resource"
    }
}
$rateLimitTemplate = Get-Content -LiteralPath $RateLimitTemplatePath -Raw
if (-not $rateLimitTemplate.Contains('AWS::BedrockAgentCore::GatewayRateLimit')) {
    throw 'Rate-limit template is missing AWS::BedrockAgentCore::GatewayRateLimit.'
}
if (($template + $rateLimitTemplate) -match '(?i)(access[_-]?key|secret[_-]?access[_-]?key)\s*[:=]\s*[^<\s]') {
    throw 'Template appears to contain a credential-like value.'
}

Write-Host 'Local template checks passed.'
Write-Host 'No AWS resource was created or changed.'
Write-Host "Planned template: $TemplatePath"
Write-Host "Planned separate rate-limit template: $RateLimitTemplatePath"
Write-Host "Planned Region: $Region"

if (-not $ValidateWithAws) {
    Write-Host 'AWS validation was not requested. Re-run with -ValidateWithAws for a read-only service validation.'
    exit 0
}
if ($Region -eq '<approved-region>') {
    throw 'Supply an approved AWS Region before AWS validation.'
}
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw 'AWS CLI is required for service-side validation.'
}

aws cloudformation validate-template `
    --region $Region `
    --template-body "file://$TemplatePath"
if ($LASTEXITCODE -ne 0) {
    throw 'Main CloudFormation template service validation failed.'
}
aws cloudformation validate-template `
    --region $Region `
    --template-body "file://$RateLimitTemplatePath"
if ($LASTEXITCODE -ne 0) {
    throw 'Rate-limit CloudFormation template service validation failed.'
}
