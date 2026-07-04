#!/usr/bin/env bash
# 启动 PaddleOCR (PP-StructureV3) 文档解析服务 —— WSL / Linux 版。
#
# 用法（在仓库根目录）：
#   bash scripts/ocr-server.sh
#   PORT=8118 bash scripts/ocr-server.sh
#
# 首次运行会在 server/ocr/.venv 建立独立虚拟环境并安装依赖（约几百 MB，需联网）。
# 后续运行直接复用该环境。服务对外暴露 POST /layout-parsing。
set -euo pipefail

PORT="${PORT:-8118}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$REPO_ROOT/server/ocr/.venv"
REQ_FILE="$REPO_ROOT/server/ocr/requirements.txt"

if [ ! -d "$VENV_DIR" ]; then
  echo "[ocr] 创建独立虚拟环境: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"

echo "[ocr] 安装/更新依赖 ..."
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r "$REQ_FILE"

# PP-StructureV3 管线 serving；端点为 POST /layout-parsing。
# 注意：确切 CLI 可能随 PaddleOCR/PaddleX 版本变化，如失败请查官方 serving 文档。
echo "[ocr] 启动 PP-StructureV3 服务于 0.0.0.0:${PORT} ..."
"$VENV_DIR/bin/paddlex" --serve --pipeline PP-StructureV3 --host 0.0.0.0 --port "$PORT"
