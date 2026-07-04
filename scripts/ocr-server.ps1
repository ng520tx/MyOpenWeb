# 启动 PaddleOCR (PP-StructureV3) 文档解析服务 —— Windows 原生版。
#
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File scripts/ocr-server.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/ocr-server.ps1 -Port 8118
#
# 首次运行会在 server/ocr/.venv 建立独立虚拟环境并安装依赖（约几百 MB，需联网）。
# 后续运行直接复用该环境。服务对外暴露 POST /layout-parsing。
param(
    [int]$Port = 8118
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $repoRoot "server\ocr\.venv"
$reqFile = Join-Path $repoRoot "server\ocr\requirements.txt"

if (-not (Test-Path $venvDir)) {
    Write-Host "[ocr] 创建独立虚拟环境: $venvDir"
    python -m venv $venvDir
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "[ocr] 安装/更新依赖 ..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r $reqFile

# PP-StructureV3 管线 serving；端点为 POST /layout-parsing。
# 注意：确切 CLI 可能随 PaddleOCR/PaddleX 版本变化，如失败请查官方 serving 文档。
$paddlex = Join-Path $venvDir "Scripts\paddlex.exe"
Write-Host "[ocr] 启动 PP-StructureV3 服务于 0.0.0.0:$Port ..."
& $paddlex --serve --pipeline PP-StructureV3 --host 0.0.0.0 --port $Port
