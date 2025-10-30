$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venvPython = Join-Path $projectDir 'venv\Scripts\python.exe'
$runScriptPs1 = Join-Path $projectDir 'run_pi_server.ps1'

if (-not (Test-Path $venvPython)) {
  Write-Error "Python venv not found at $venvPython. Create it and install deps first."
}

# Create wrapper to run server via venv
@"
powershell -NoProfile -ExecutionPolicy Bypass -File `"$runScriptPs1`"
"@ | Out-Null

$taskName = 'DiscordPrinterReceiver'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runScriptPs1`""
$trigger1 = New-ScheduledTaskTrigger -AtLogOn
$trigger2 = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId $env:UserName -LogonType Interactive -RunLevel Highest

try {
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger1, $trigger2 -Principal $principal -Force | Out-Null
  Write-Host "Installed Task Scheduler task: $taskName"
  Write-Host "It will start at login and at startup. You can start it now from Task Scheduler."
}
catch {
  Write-Error $_
}



