param(
  [int]$Port = 8000,
  [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$ProjectRootPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$ProjectRootPathForWsl = $ProjectRootPath -replace "\\", "/"
$WslProjectRoot = (& wsl.exe wslpath -a "$ProjectRootPathForWsl").Trim()

if (-not $WslProjectRoot) {
  throw "Failed to resolve WSL project path from $ProjectRootPath"
}

$EscapedWslProjectRoot = $WslProjectRoot.Replace("'", "'\''")
$ReloadArg = if ($NoReload) { "" } else { " --reload" }

$Command = @"
set -e
cd '$EscapedWslProjectRoot'
if [ ! -x ./.venv/bin/python ]; then
  echo '[dev-server] Creating Python virtual environment...'
  python3 -m venv .venv
fi
if ! ./.venv/bin/python -c 'import fastapi, httpx, uvicorn' >/dev/null 2>&1; then
  echo '[dev-server] Installing backend dependencies...'
  ./.venv/bin/pip install -r server/requirements.txt
fi
if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:$Port/api/health" >/dev/null 2>&1; then
  echo '[dev-server] FastAPI is already running on http://127.0.0.1:$Port'
  exit 0
fi
echo '[dev-server] Starting FastAPI on http://127.0.0.1:$Port'
exec ./.venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port $Port$ReloadArg
"@

wsl.exe bash -lc $Command
