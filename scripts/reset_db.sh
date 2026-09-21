#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
db_path="$root_dir/data/finloop.db"

if [[ -f "$db_path" ]]; then
  backup_path="$root_dir/data/finloop.$(date +%Y%m%d%H%M%S).db.bak"
  mv "$db_path" "$backup_path"
  echo "数据库已备份到 $backup_path"
fi

PYTHONPATH="$root_dir/backend" "$root_dir/.venv/bin/python" -c "from app.db import Database; Database().initialize()"
echo "演示数据库已重新生成。"
