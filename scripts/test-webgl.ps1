$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $projectRoot '.cache\playwright'
Push-Location (Join-Path $projectRoot 'web')
try {
    npx.cmd playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Test browser installation failed' }
    node tests/webgl-acceptance.mjs
    if ($LASTEXITCODE -ne 0) { throw 'WebGL acceptance failed. See artifacts/webgl-acceptance.json.' }
    $env:CELL_LIFECYCLE_ONLY = '1'
    try {
        node tests/webgl-acceptance.mjs
        if ($LASTEXITCODE -ne 0) { throw 'WebGL recovery acceptance failed. See artifacts/webgl-lifecycle.json.' }
    } finally { Remove-Item Env:CELL_LIFECYCLE_ONLY -ErrorAction SilentlyContinue }
} finally { Pop-Location }
