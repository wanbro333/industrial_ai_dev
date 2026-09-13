$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    dotnet build tests/device_harness/DeviceHarness.csproj -c Release --nologo
    if ($LASTEXITCODE -ne 0) { throw 'C# device harness build failed' }
    & .venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Controller or closed-loop tests failed' }
    Push-Location web
    try { npm.cmd test; if ($LASTEXITCODE -ne 0) { throw 'Browser protocol tests failed' } }
    finally { Pop-Location }
} finally { Pop-Location }
