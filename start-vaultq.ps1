$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

if (-not $env:VAULTQ_ROOT) {
    $env:VAULTQ_ROOT = $projectRoot
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonExecutable = if (Test-Path $venvPython) { $venvPython } else { "python" }
$api = Start-Process $pythonExecutable -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru

try {
    Set-Location (Join-Path $projectRoot "frontend")
    npm run dev
}
finally {
    if (-not $api.HasExited) {
        Stop-Process -Id $api.Id
    }
    Set-Location $projectRoot
}
