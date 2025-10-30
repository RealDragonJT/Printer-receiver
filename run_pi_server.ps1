$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $projectDir 'venv\Scripts\Activate.ps1'
if (Test-Path $venv) { . $venv }

$python = Join-Path $projectDir 'venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

& $python (Join-Path $projectDir 'run_pi_server.py')



