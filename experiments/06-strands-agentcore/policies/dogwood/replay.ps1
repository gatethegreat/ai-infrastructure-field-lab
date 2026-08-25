[CmdletBinding()]
param(
    [string]$Image = "ai-field-lab-dogwood:1.0.0-c6237c8"
)

$ErrorActionPreference = "Stop"
$policyDirectory = Split-Path -Parent $PSCommandPath
$traces = Get-ChildItem -LiteralPath (Join-Path $policyDirectory "traces") -Filter "*.log" | Sort-Object Name

foreach ($trace in $traces) {
    Write-Host "Replaying $($trace.Name)"
    docker run --rm `
        --volume "${policyDirectory}:/lab:ro" `
        $Image replay /lab/policies.dw `
        --policy-schema /lab/schema.cedarschema `
        --event-schema /lab/events.dwschema `
        --trace "/lab/traces/$($trace.Name)" `
        --format json

    if ($LASTEXITCODE -ne 0) {
        throw "Dogwood replay failed for $($trace.Name) with exit code $LASTEXITCODE"
    }
}
