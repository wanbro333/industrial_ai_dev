$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot 'runtime\processes.json'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'No project process record.'; exit 0 }
$run = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
$expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
foreach ($processId in @($run.controller,$run.server)) {
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$processId) -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    $isController = $process.CommandLine -like ('*controller.main*--session*' + $run.session + '*')
    $isServer = $process.CommandLine -like ('*' + (Join-Path $projectRoot 'scripts\serve.py') + '*')
    if ($process.ExecutablePath -eq $expectedPython -and ($isController -or $isServer)) {
        Stop-Process -Id $processId
        Write-Output ('Stopped project process ' + $processId)
    } else { Write-Warning ('PID no longer matches this project; left untouched: ' + $processId) }
}
Remove-Item -LiteralPath $pidFile
