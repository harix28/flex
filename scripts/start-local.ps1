param([ValidateRange(1,65535)][int]$Port)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Create the Python 3.12 .venv and install requirements.txt first.'
    }
    & $python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'The local virtual environment must use Python 3.12.' }
    & $python -m sentinel.local_setup
    if ($LASTEXITCODE -ne 0) { throw 'Local configuration setup failed.' }
    $serveArgs = @('-m', 'sentinel.serve')
    if ($PSBoundParameters.ContainsKey('Port')) { $serveArgs += @('--port', "$Port") }
    Write-Host 'Keep this terminal open. Use scripts/check-local.ps1 in a second terminal. Stop with Ctrl+C.'
    & $python @serveArgs
    if ($LASTEXITCODE -ne 0) { throw 'API server exited with an error.' }
} finally {
    Pop-Location
}
