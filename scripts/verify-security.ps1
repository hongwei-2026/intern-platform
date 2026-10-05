#Requires -Version 5.1
# Wrapper: run python verifier (encoding-safe).
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py (Join-Path $Root "scripts\verify_security.py") @args
exit $LASTEXITCODE
