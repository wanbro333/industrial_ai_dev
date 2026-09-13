$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed' }
    }
    & .venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
    Push-Location web
    try {
        npm.cmd ci --ignore-scripts --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Web template build failed' }
    } finally { Pop-Location }
} finally { Pop-Location }
