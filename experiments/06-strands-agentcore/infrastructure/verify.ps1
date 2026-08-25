[CmdletBinding()]
param(
    [string]$StackName = 'agentcore-policy-field-lab',
    [string]$RateLimitStackName = 'agentcore-policy-field-lab-rate-limit',
    [string]$Region = '<approved-region>',
    [switch]$IncludeRateLimit,
    [switch]$QueryAws
)

$ErrorActionPreference = 'Stop'

if (-not $QueryAws) {
    Write-Host 'VERIFY PLAN ONLY: no AWS query was requested.'
    Write-Host 'With -QueryAws, this script reads stack outputs and policy state.'
    Write-Host 'Add -IncludeRateLimit to verify the separate rate-limit stack through CloudFormation.'
    exit 0
}
if ($Region -eq '<approved-region>') {
    throw 'Supply the approved AWS Region.'
}
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw 'AWS CLI is required for verification.'
}

function Invoke-AwsChecked {
    param([Parameter(Mandatory)][string[]]$AwsArguments)
    $result = & aws @AwsArguments
    if ($LASTEXITCODE -ne 0) {
        throw "AWS CLI command failed: aws $($AwsArguments[0]) $($AwsArguments[1])"
    }
    return $result
}

$outputs = Invoke-AwsChecked @(
    'cloudformation', 'describe-stacks',
    '--stack-name', $StackName,
    '--region', $Region,
    '--query', 'Stacks[0].Outputs',
    '--output', 'json'
) | ConvertFrom-Json

$gatewayId = ($outputs | Where-Object OutputKey -eq 'GatewayIdentifier').OutputValue
$engineId = ($outputs | Where-Object OutputKey -eq 'PolicyEngineId').OutputValue
if ([string]::IsNullOrWhiteSpace($gatewayId) -or [string]::IsNullOrWhiteSpace($engineId)) {
    throw 'Required GatewayIdentifier or PolicyEngineId output is missing.'
}

Invoke-AwsChecked @('bedrock-agentcore-control', 'get-gateway', '--gateway-identifier', $gatewayId, '--region', $Region)
Invoke-AwsChecked @('bedrock-agentcore-control', 'get-policy-engine', '--policy-engine-id', $engineId, '--region', $Region)
Invoke-AwsChecked @('bedrock-agentcore-control', 'list-policies', '--policy-engine-id', $engineId, '--region', $Region)
Invoke-AwsChecked @('cloudformation', 'describe-stack-resources', '--stack-name', $StackName, '--region', $Region)

if ($IncludeRateLimit) {
    Invoke-AwsChecked @('cloudformation', 'describe-stacks', '--stack-name', $RateLimitStackName, '--region', $Region)
    Invoke-AwsChecked @('cloudformation', 'describe-stack-resources', '--stack-name', $RateLimitStackName, '--region', $Region)
}

Write-Host 'Verification was read-only. Save raw output only under ignored private evidence storage.'
