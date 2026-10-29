[CmdletBinding()]
param([switch]$Dev, [switch]$Down, [switch]$Rebuild, [switch]$Logs,
      [string]$EnvFile = '.env.production')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE). Deployment not verified." }
}
Invoke-Docker info --format '{{.ServerVersion}}'
Invoke-Docker compose version
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw 'Create a private env file from .env.container.example with generated secrets first.'
}
$compose = @('compose', '--env-file', $EnvFile, '-f', 'docker-compose.yml')
if ($Dev) { $compose += @('-f', 'docker-compose.dev.yml') }
Invoke-Docker @compose config --quiet
if ($Down) { Invoke-Docker @compose down; exit 0 }
$up = @('up', '-d', '--wait', '--wait-timeout', '180')
if ($Rebuild) { $up += '--build' }
Invoke-Docker @compose @up
Write-Host 'Container health checks passed. Verify authenticated browser login before release.'
if ($Logs) { Invoke-Docker @compose logs -f }
