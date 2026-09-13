param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'web\dist\index.html'))) { throw 'Run scripts/build-webgl.ps1 first. No WebGL build is available.' }
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run scripts/setup.ps1 first.' }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw ('Port already occupied: ' + $Port) }
$runtimeDir = Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$pidFile = Join-Path $runtimeDir 'processes.json'
if (Test-Path -LiteralPath $pidFile) {
    $previousRun = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    foreach ($previousId in @($previousRun.controller,$previousRun.server)) {
        $previousProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$previousId) -ErrorAction SilentlyContinue
        if ($previousProcess -and $previousProcess.ExecutablePath -eq $pythonExe) { throw 'A previous project process is still running. Run scripts/stop.ps1 first.' }
    }
}
$session = [Guid]::NewGuid().ToString('N').Substring(0,16)
$serverScript = Join-Path $projectRoot 'scripts\serve.py'
$server = Start-Process -FilePath $pythonExe -ArgumentList @('-u',('"' + $serverScript + '"'),'--port',$Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'server.log') -RedirectStandardError (Join-Path $runtimeDir 'server-error.log')
try {
    $controller = Start-Process -FilePath $pythonExe -ArgumentList @('-u','-m','controller.main','--session',$session,'--web-port',$Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'controller.log') -RedirectStandardError (Join-Path $runtimeDir 'controller-error.log')
} catch { Stop-Process -Id $server.Id -ErrorAction SilentlyContinue; throw }
@{controller=$controller.Id;server=$server.Id;session=$session;port=$Port;python=$pythonExe} | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8
$url = 'http://localhost:' + $Port + '/?session=' + $session
Write-Output ('Session: ' + $session)
Write-Output ('Open: ' + $url)
Start-Process $url
