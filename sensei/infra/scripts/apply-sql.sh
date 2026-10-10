#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "${script_dir}/../.." && pwd)"
project_version="${SENSEI_VERSION:-$(awk -F'"' '/^version = "/ { print $2; exit }' "${project_dir}/pyproject.toml")}"
sql_dir="${SENSEI_SQL_DIR:-${project_dir}/infra/sql/${project_version}}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required; run task setup or install the PostgreSQL client" >&2
  exit 1
fi

command -v op >/dev/null 2>&1 || {
  echo "1Password CLI (op) is required" >&2
  exit 1
}
op_vault="${HIVE_OP_VAULT:-homelab}"
op_item="${HIVE_OP_ITEM:-hive}"
export PGPASSWORD="$(op read "op://${op_vault}/${op_item}/DATABASE_PASSWORD")"

export PGHOST="${PGHOST:-192.168.1.200}"
export PGPORT="${PGPORT:-9000}"
export PGDATABASE="${PGDATABASE:-hive}"
export PGUSER="${PGUSER:-hive}"

if [[ ! -d "${sql_dir}" ]]; then
  echo "SQL directory does not exist for version ${project_version}: ${sql_dir}" >&2
  exit 1
fi

for sql_file in "${sql_dir}"/*.sql; do
  [[ -f "${sql_file}" ]] || continue
  echo "Applying $(basename "${sql_file}") for Sensei ${project_version}"
  psql --no-password --set ON_ERROR_STOP=1 --file "${sql_file}"
done

unset PGPASSWORD
