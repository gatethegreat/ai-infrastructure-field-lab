[CmdletBinding()]
param(
    [string]$StackName = 'agentcore-policy-field-lab',
    [string]$RateLimitStackName = 'agentcore-policy-field-lab-rate-limit',
    [string]$Region = '<approved-region>',
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

if (-not $Apply) {
    Write-Host "TEARDOWN PLAN ONLY for stack $StackName in $Region"
    Write-Host "Order: capture exact resource IDs; delete rate-limit stack $RateLimitStackName; delete main stack $StackName; verify every captured resource is absent."
    Write-Host 'No AWS resource was changed. Re-run with -Apply after explicit teardown approval.'
    exit 0
}
if ($Region -eq '<approved-region>') { throw 'Supply the approved AWS Region before teardown.' }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { throw 'AWS CLI is required for teardown.' }

function Invoke-AwsCapture {
    param([Parameter(Mandatory)][string[]]$AwsArguments)
    $text = (& aws @AwsArguments 2>&1 | Out-String).Trim()
    [pscustomobject]@{ ExitCode = $LASTEXITCODE; Text = $text }
}

function Invoke-AwsChecked {
    param([Parameter(Mandatory)][string[]]$AwsArguments)
    $result = Invoke-AwsCapture $AwsArguments
    if ($result.ExitCode -ne 0) {
        throw "AWS CLI command failed: aws $($AwsArguments[0]) $($AwsArguments[1]). $($result.Text)"
    }
    $result.Text
}

function Assert-AwsNotFound {
    param([Parameter(Mandatory)][string]$Label, [Parameter(Mandatory)][string[]]$AwsArguments)
    $result = Invoke-AwsCapture $AwsArguments
    if ($result.ExitCode -eq 0) { throw "$Label still exists after teardown." }
    if ($result.Text -notmatch '(?i)ResourceNotFound|NoSuchEntity|does not exist|not found') {
        throw "$Label absence could not be proven; AWS returned: $($result.Text)"
    }
    Write-Host "Verified absent: $Label"
}

$mainRead = Invoke-AwsCapture @(
    'cloudformation', 'describe-stacks', '--stack-name', $StackName,
    '--region', $Region, '--query', 'Stacks[0]', '--output', 'json'
)
$mainExists = $mainRead.ExitCode -eq 0
if (-not $mainExists -and $mainRead.Text -notmatch '(?i)does not exist|not found') {
    throw "Could not read the main stack before teardown: $($mainRead.Text)"
}

$captured = @{}
if ($mainExists) {
    $stack = $mainRead.Text | ConvertFrom-Json
    foreach ($output in @($stack.Outputs)) {
        if (-not [string]::IsNullOrWhiteSpace($output.OutputValue)) {
            $captured[$output.OutputKey] = $output.OutputValue
        }
    }
    $resourceRead = Invoke-AwsCapture @(
        'cloudformation', 'describe-stack-resources', '--stack-name', $StackName,
        '--region', $Region, '--query', 'StackResources', '--output', 'json'
    )
    if ($resourceRead.ExitCode -eq 0) {
        $logicalToCaptureKey = @{
            SyntheticGateway = 'GatewayIdentifier'
            PolicyEngine = 'PolicyEngineId'
            SyntheticToolsFunction = 'SyntheticToolsFunctionName'
            SyntheticToolsLogGroup = 'SyntheticToolsLogGroupName'
            OperationTable = 'OperationTableName'
            SyntheticToolRole = 'SyntheticToolRoleName'
            GatewayExecutionRole = 'GatewayExecutionRoleName'
            PrimaryCallerRole = 'PrimaryCallerRoleName'
            SecondaryCallerRole = 'SecondaryCallerRoleName'
        }
        foreach ($resource in ($resourceRead.Text | ConvertFrom-Json)) {
            $captureKey = $logicalToCaptureKey[$resource.LogicalResourceId]
            if ($captureKey -and -not [string]::IsNullOrWhiteSpace($resource.PhysicalResourceId)) {
                $captured[$captureKey] = $resource.PhysicalResourceId
            }
        }
    } else {
        Write-Warning 'Stack resources could not be enumerated; teardown will verify only IDs available from outputs.'
    }
    if ($captured.ContainsKey('PolicyEngineId') -and $captured.PolicyEngineId -match '^arn:') {
        $captured.PolicyEngineId = ([string]$captured.PolicyEngineId).Split('/')[-1]
    }
    Write-Host "Captured $($captured.Count) available resource identifiers from stack state $($stack.StackStatus)."
} else {
    Write-Host 'Main stack is already absent; no resource IDs are available to delete.'
}

$rateRead = Invoke-AwsCapture @('cloudformation', 'describe-stacks', '--stack-name', $RateLimitStackName, '--region', $Region)
if ($rateRead.ExitCode -eq 0) {
    Invoke-AwsChecked @('cloudformation', 'delete-stack', '--stack-name', $RateLimitStackName, '--region', $Region) | Out-Null
    Invoke-AwsChecked @('cloudformation', 'wait', 'stack-delete-complete', '--stack-name', $RateLimitStackName, '--region', $Region) | Out-Null
} elseif ($rateRead.Text -match '(?i)does not exist|not found') {
    Write-Host 'Separate rate-limit stack is absent; continuing with main stack teardown.'
} else {
    throw "Could not verify whether the rate-limit stack exists: $($rateRead.Text)"
}
Assert-AwsNotFound 'rate-limit CloudFormation stack' @('cloudformation', 'describe-stacks', '--stack-name', $RateLimitStackName, '--region', $Region)

if ($mainExists) {
    Invoke-AwsChecked @('cloudformation', 'delete-stack', '--stack-name', $StackName, '--region', $Region) | Out-Null
    Invoke-AwsChecked @('cloudformation', 'wait', 'stack-delete-complete', '--stack-name', $StackName, '--region', $Region) | Out-Null
}
Assert-AwsNotFound 'main CloudFormation stack' @('cloudformation', 'describe-stacks', '--stack-name', $StackName, '--region', $Region)

if ($mainExists) {
    if ($captured.ContainsKey('GatewayIdentifier')) {
        Assert-AwsNotFound 'AgentCore gateway' @('bedrock-agentcore-control', 'get-gateway', '--gateway-identifier', $captured.GatewayIdentifier, '--region', $Region)
    }
    if ($captured.ContainsKey('PolicyEngineId')) {
        Assert-AwsNotFound 'AgentCore policy engine' @('bedrock-agentcore-control', 'get-policy-engine', '--policy-engine-id', $captured.PolicyEngineId, '--region', $Region)
    }
    if ($captured.ContainsKey('SyntheticToolsFunctionName')) {
        Assert-AwsNotFound 'Lambda function' @('lambda', 'get-function', '--function-name', $captured.SyntheticToolsFunctionName, '--region', $Region)
    }
    if ($captured.ContainsKey('OperationTableName')) {
        Assert-AwsNotFound 'DynamoDB table' @('dynamodb', 'describe-table', '--table-name', $captured.OperationTableName, '--region', $Region)
    }
    foreach ($roleKey in @('SyntheticToolRoleName', 'GatewayExecutionRoleName', 'PrimaryCallerRoleName', 'SecondaryCallerRoleName')) {
        if ($captured.ContainsKey($roleKey)) {
            Assert-AwsNotFound "IAM role $($captured[$roleKey])" @('iam', 'get-role', '--role-name', $captured[$roleKey])
        }
    }
    if ($captured.ContainsKey('SyntheticToolsLogGroupName')) {
        $logGroups = Invoke-AwsChecked @(
            'logs', 'describe-log-groups', '--log-group-name-prefix', $captured.SyntheticToolsLogGroupName,
            '--region', $Region, '--query', 'logGroups[].logGroupName', '--output', 'json'
        ) | ConvertFrom-Json
        if ($logGroups -contains $captured.SyntheticToolsLogGroupName) {
            throw "Lambda log group still exists after teardown: $($captured.SyntheticToolsLogGroupName)"
        }
        Write-Host 'Verified absent: Lambda log group'
    }
}

Write-Host 'Teardown completed and every captured resource was verified absent.'
