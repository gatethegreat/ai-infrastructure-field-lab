[CmdletBinding()]
param(
    [string]$Image = "ai-field-lab-dogwood:1.0.0-c6237c8"
)

$ErrorActionPreference = "Stop"
$policyDirectory = Split-Path -Parent $PSCommandPath
$expected = Get-Content -LiteralPath (Join-Path $policyDirectory "expected_verdicts.json") -Raw | ConvertFrom-Json -AsHashtable

& (Join-Path $policyDirectory "validate.ps1") -Image $Image

foreach ($entry in $expected.GetEnumerator() | Sort-Object Key) {
    $json = docker run --rm `
        --volume "${policyDirectory}:/lab:ro" `
        $Image replay /lab/policies.dw `
        --policy-schema /lab/schema.cedarschema `
        --event-schema /lab/events.dwschema `
        --trace "/lab/traces/$($entry.Key)" `
        --format json | Out-String

    if ($LASTEXITCODE -ne 0) {
        throw "Dogwood replay failed for $($entry.Key) with exit code $LASTEXITCODE"
    }

    $actual = @(($json | ConvertFrom-Json).verdicts | ForEach-Object { $_.verdict })
    $wanted = @($entry.Value)
    if (Compare-Object -ReferenceObject $wanted -DifferenceObject $actual -SyncWindow 0) {
        throw "Verdict mismatch for $($entry.Key): expected $($wanted -join ','), got $($actual -join ',')"
    }
    Write-Host "PASS $($entry.Key): $($actual -join ',')"
}
