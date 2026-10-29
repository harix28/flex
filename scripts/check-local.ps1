param([ValidateRange(1,65535)][int]$Port)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Create the Python 3.12 virtual environment first.' }
    & $python -m sentinel.check
    if ($LASTEXITCODE -ne 0) { throw 'Model/data verification failed. Existing data was preserved.' }
    $replayArgs = @('-m', 'sentinel.replay', '--request', '.runtime/replay-engine1.json')
    if ($PSBoundParameters.ContainsKey('Port')) { $replayArgs += @('--port', "$Port") }
    & $python @replayArgs
    if ($LASTEXITCODE -ne 0) { throw 'Replay failed. Check the server terminal and port.' }
} finally {
    Pop-Location
}
