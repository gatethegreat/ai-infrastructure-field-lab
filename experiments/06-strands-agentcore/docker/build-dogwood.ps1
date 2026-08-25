[CmdletBinding()]
param(
    [string]$Image = "ai-field-lab-dogwood:1.0.0-c6237c8"
)

$ErrorActionPreference = "Stop"
$dockerDirectory = Split-Path -Parent $PSCommandPath

docker build `
    --file (Join-Path $dockerDirectory "Dockerfile.dogwood") `
    --tag $Image `
    $dockerDirectory

if ($LASTEXITCODE -ne 0) {
    throw "Dogwood image build failed with exit code $LASTEXITCODE"
}

docker image inspect $Image --format '{{json .RepoDigests}} {{.Id}}'
if ($LASTEXITCODE -ne 0) {
    throw "Dogwood image inspection failed with exit code $LASTEXITCODE"
}
