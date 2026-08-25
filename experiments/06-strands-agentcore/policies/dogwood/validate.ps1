[CmdletBinding()]
param(
    [string]$Image = "ai-field-lab-dogwood:1.0.0-c6237c8"
)

$ErrorActionPreference = "Stop"
$policyDirectory = Split-Path -Parent $PSCommandPath

docker run --rm `
    --volume "${policyDirectory}:/lab:ro" `
    $Image validate /lab/policies.dw `
    --policy-schema /lab/schema.cedarschema `
    --event-schema /lab/events.dwschema `
    --format json

if ($LASTEXITCODE -ne 0) {
    throw "Dogwood policy validation failed with exit code $LASTEXITCODE"
}
