[CmdletBinding()]
param(
    [string]$InputDirectory = '',
    [string]$OutputDirectory = '',
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$experimentRoot = Split-Path $PSScriptRoot -Parent
if ([string]::IsNullOrWhiteSpace($InputDirectory)) {
    $InputDirectory = Join-Path $experimentRoot 'evidence\cloud\private'
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $experimentRoot 'evidence\cloud\redacted-candidate'
}
$rulesPath = Join-Path $PSScriptRoot 'redaction-rules.json'
$rules = Get-Content -LiteralPath $rulesPath -Raw | ConvertFrom-Json

if (-not (Test-Path -LiteralPath $InputDirectory -PathType Container)) {
    Write-Host "No private evidence directory exists: $InputDirectory"
    Write-Host 'No file was written.'
    exit 0
}

$files = Get-ChildItem -LiteralPath $InputDirectory -File -Recurse
Write-Host "Redaction candidate files: $($files.Count)"
if (-not $Apply) {
    Write-Host "PREVIEW ONLY: would write redacted copies under $OutputDirectory"
    exit 0
}

$inputRoot = [System.IO.Path]::GetFullPath($InputDirectory)
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
if ($inputRoot -eq $outputRoot) {
    throw 'Input and output directories must differ.'
}

foreach ($file in $files) {
    $relative = [System.IO.Path]::GetRelativePath($inputRoot, $file.FullName)
    $destination = Join-Path $outputRoot $relative
    $destinationParent = Split-Path $destination -Parent
    New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    $content = Get-Content -LiteralPath $file.FullName -Raw
    foreach ($rule in $rules.patterns) {
        $replacement = if ($null -ne $rule.replacement) { $rule.replacement } else { $rules.replacement }
        $content = [regex]::Replace($content, $rule.regex, $replacement)
    }
    [System.IO.File]::WriteAllText($destination, $content, $utf8NoBom)
}

Write-Host 'Redacted copies written. Manually inspect them before committing; automated redaction is not proof of safety.'
