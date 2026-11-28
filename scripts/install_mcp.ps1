param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$environment = Join-Path $root "results\step45\venv"
$interpreter = Join-Path $environment "Scripts\python.exe"
if (!(Test-Path -LiteralPath $interpreter)) {
    & $Python -m venv $environment
    if ($LASTEXITCODE) { throw "Could not create the isolated Python environment." }
}
& $interpreter -m pip install --disable-pip-version-check -r (Join-Path $root "requirements-mcp.txt")
if ($LASTEXITCODE) { throw "MCP dependency installation failed." }
Write-Output "Interpreter: $interpreter"
Write-Output "Server: $(Join-Path $PSScriptRoot 'serve_mcp.py')"
