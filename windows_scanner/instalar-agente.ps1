param(
    [string]$OrigenSistema = ""
)

$ErrorActionPreference = "Stop"
$TaskName = "Instituto Scanner Agent"
$InstallDir = Join-Path $env:LOCALAPPDATA "Instituto\ScannerAgent"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($OrigenSistema)) {
    $OrigenSistema = Read-Host "Direccion del sistema (ejemplo: https://instituto.ejemplo.com)"
}

try {
    $SystemUri = [Uri]$OrigenSistema
} catch {
    throw "La direccion del sistema no es valida. Debe incluir http:// o https://"
}
if ($SystemUri.Scheme -notin @("http", "https") -or [string]::IsNullOrWhiteSpace($SystemUri.Host)) {
    throw "La direccion del sistema debe comenzar con http:// o https://"
}
$NormalizedOrigin = $SystemUri.GetLeftPart([UriPartial]::Authority).TrimEnd("/")

if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) {
    throw "No se encontro el lanzador de Python. Instala Python 3 desde python.org y activa la opcion Add Python to PATH."
}
$PythonExe = (& py -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    throw "No se encontro Python 3. Instalalo desde python.org y vuelve a ejecutar el instalador."
}
$PythonwExe = Join-Path (Split-Path -Parent $PythonExe) "pythonw.exe"
if (-not (Test-Path $PythonwExe)) {
    throw "No se encontro pythonw.exe junto a Python 3."
}

$Naps2Candidates = @(
    (Join-Path $env:ProgramFiles "NAPS2\NAPS2.Console.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\NAPS2\NAPS2.Console.exe")
)
if (${env:ProgramFiles(x86)}) {
    $Naps2Candidates += Join-Path ${env:ProgramFiles(x86)} "NAPS2\NAPS2.Console.exe"
}
$Naps2Candidates = $Naps2Candidates | Where-Object { Test-Path $_ }
$Naps2Console = $Naps2Candidates | Select-Object -First 1
if (-not $Naps2Console) {
    throw "No se encontro NAPS2. Instalalo, crea el perfil Instituto ES-60W y vuelve a intentar."
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item (Join-Path $SourceDir "agent.py") (Join-Path $InstallDir "agent.py") -Force

$Config = [ordered]@{
    allowed_origins = (@($NormalizedOrigin, "http://localhost:8000", "http://127.0.0.1:8000") | Select-Object -Unique)
    naps2_console = $Naps2Console
    profile = "Instituto ES-60W"
    page_delay_ms = 10000
    scan_timeout_seconds = 300
    max_pages = 20
}
$Config | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $InstallDir "scanner-agent.json") -Encoding UTF8

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonwExe `
    -Argument ('"' + (Join-Path $InstallDir "agent.py") + '"') `
    -WorkingDirectory $InstallDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "Agente local para escanear fichas desde el sistema del Instituto" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2

try {
    $Health = Invoke-RestMethod "http://127.0.0.1:17654/health" -TimeoutSec 5
    if ($Health.status -ne "ready") {
        throw "El agente inicio, pero NAPS2 requiere configuracion."
    }
} catch {
    throw "El agente fue instalado pero no respondio correctamente. Revisa $InstallDir\scanner-agent.log"
}

Write-Host ""
Write-Host "Instalacion completada." -ForegroundColor Green
Write-Host "El agente se iniciara automaticamente y funcionara sin ventana visible."
Write-Host "Origen autorizado: $NormalizedOrigin"
Write-Host "Diagnostico: http://127.0.0.1:17654/health"
Read-Host "Presiona Enter para cerrar"
