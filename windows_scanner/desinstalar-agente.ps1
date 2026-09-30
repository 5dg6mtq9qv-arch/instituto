$ErrorActionPreference = "Stop"
$TaskName = "Instituto Scanner Agent"
$InstallDir = Join-Path $env:LOCALAPPDATA "Instituto\ScannerAgent"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

Write-Host "El agente de escaneo fue desinstalado." -ForegroundColor Green
Read-Host "Presiona Enter para cerrar"
