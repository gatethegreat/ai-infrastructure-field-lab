[CmdletBinding()]
param(
    [string]$Image = "ai-field-lab-dogwood:1.0.0-c6237c8"
)

$ErrorActionPreference = "Stop"
$policyDirectory = Split-Path -Parent $PSCommandPath

docker run --rm `
    --volume "${policyDirectory}:/lab" `
    $Image schema mcp --manifest /lab/tools.json -o /lab/schema.cedarschema

if ($LASTEXITCODE -ne 0) {
    throw "Dogwood schema generation failed with exit code $LASTEXITCODE"
}

# MCP describes tool inputs/outputs but has no policy-session field. Add the
# local reference interpreter's request context field deterministically.
$schemaPath = Join-Path $policyDirectory "schema.cedarschema"
$schema = Get-Content -LiteralPath $schemaPath -Raw

# Dogwood's MCP converter emits nested JSON objects as Cedar entities. That
# makes `...inputs(A)` expose only `input.change` and prevents temporal
# correlation on the object's leaves. This deterministic correction preserves
# the manifest's JSON-object semantics as a Cedar record alias, allowing the
# event schema to derive `input.change.approval_id` and `.change_id`.
$recordCorrected = $schema -replace '(?m)^  entity execute_write_Input_change = \{', '  type execute_write_Input_change = {'
if ($recordCorrected -eq $schema) {
    throw "Generated schema did not contain the expected nested change entity"
}
$schema = $recordCorrected

$replacement = '$1sessionId: String,' + "`n" + '$1system: SystemContext'
$augmented = $schema -replace "(?m)^(\s+)system: SystemContext$", $replacement
if ($augmented -eq $schema) {
    throw "Generated schema did not contain the expected SystemContext fields"
}
[System.IO.File]::WriteAllText($schemaPath, $augmented, [System.Text.UTF8Encoding]::new($false))
