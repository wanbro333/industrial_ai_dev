param([string]$UnityEditor = 'D:\UnityEditors\6000.3.24f1\Editor\Unity.exe')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $UnityEditor)) { throw 'Unity Editor missing. Install 6000.3.24f1 with Web Build Support, or pass -UnityEditor with the executable path.' }
Push-Location (Join-Path $projectRoot 'web')
try {
    npm.cmd ci --ignore-scripts --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Web bridge build failed' }
} finally { Pop-Location }
$logDir = Join-Path $projectRoot 'artifacts'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$unityProject = Join-Path $projectRoot 'unity'
$buildLog = Join-Path $logDir 'unity-build.log'
$buildArgs = @('-batchmode','-nographics','-quit','-projectPath',('"' + $unityProject + '"'),'-buildTarget','WebGL','-executeMethod','BuildCell.WebGL','-logFile',('"' + $buildLog + '"'))
$process = Start-Process -FilePath $UnityEditor -ArgumentList $buildArgs -WindowStyle Hidden -PassThru
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw ('Unity build failed. See ' + $buildLog) }
Write-Output ('WebGL ready: ' + (Join-Path $projectRoot 'web\dist\index.html'))
