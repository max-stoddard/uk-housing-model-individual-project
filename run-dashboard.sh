#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dashboard_dir="${script_dir}/dashboard"

if [[ ! -d "${dashboard_dir}" ]]; then
  echo "Dashboard directory not found at ${dashboard_dir}" >&2
  exit 1
fi

cd "${dashboard_dir}"

if [[ ! -d node_modules ]]; then
  echo "[dashboard] Installing npm dependencies..."
  npm install
fi

echo "[dashboard] UI:  http://localhost:5173"
echo "[dashboard] API: http://localhost:8787/api/versions"
echo "[dashboard] Starting API + React dev server..."

npm run dev
