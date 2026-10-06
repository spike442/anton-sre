#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "${script_dir}/../.." && pwd)"

project_version="${ANTON_VERSION:-$(awk -F'"' '/^version = "/ { print $2; exit }' "${project_dir}/pyproject.toml")}"
sql_dir="${ANTON_SQL_DIR:-${project_dir}/infra/sql/${project_version}}"

if [[ -z "${project_version}" ]]; then
  echo "Unable to determine the project version from pyproject.toml" >&2
  exit 1
fi

if [[ ! -d "${sql_dir}" ]]; then
  echo "SQL directory does not exist for version ${project_version}: ${sql_dir}" >&2
  exit 1
fi

if [[ -n "${DATABASE_PASSWORD_FILE:-}" ]]; then
  if [[ ! -r "${DATABASE_PASSWORD_FILE}" ]]; then
    echo "DATABASE_PASSWORD_FILE is not readable: ${DATABASE_PASSWORD_FILE}" >&2
    exit 1
  fi
  export PGPASSWORD="$(<"${DATABASE_PASSWORD_FILE}")"
elif [[ -n "${DATABASE_PASSWORD:-}" ]]; then
  export PGPASSWORD="${DATABASE_PASSWORD}"
elif command -v op >/dev/null 2>&1; then
  op_vault="${ANTON_OP_VAULT:-homelab}"
  op_item="${ANTON_OP_ITEM:-anton}"
  export PGPASSWORD="$(op read "op://${op_vault}/${op_item}/DATABASE_PASSWORD")"
else
  echo "1Password CLI is required, or set DATABASE_PASSWORD_FILE/DATABASE_PASSWORD" >&2
  exit 1
fi

if [[ -z "${PGPASSWORD}" ]]; then
  echo "The database password loaded from 1Password is empty" >&2
  exit 1
fi

export PGHOST="${PGHOST:-${ANTON_DATABASE_HOST:-192.168.1.200}}"
export PGPORT="${PGPORT:-${ANTON_DATABASE_PORT:-9000}}"
export PGDATABASE="${PGDATABASE:-anton}"
export PGUSER="${PGUSER:-anton}"

required=(PGHOST PGPORT PGDATABASE PGUSER)
for variable in "${required[@]}"; do
  if [[ -z "${!variable:-}" ]]; then
    echo "${variable} must be set" >&2
    exit 1
  fi
done

mapfile -t sql_files < <(find "${sql_dir}" -maxdepth 1 -type f -name '*.sql' -print | sort)
if [[ "${#sql_files[@]}" -eq 0 ]]; then
  echo "No SQL files found in ${sql_dir}" >&2
  exit 1
fi

run_sql() {
  local sql_file="$1"

  if command -v psql >/dev/null 2>&1; then
    psql --no-password --set ON_ERROR_STOP=1 --file "${sql_file}"
    return
  fi

  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      --network host \
      --env PGPASSWORD \
      --volume "${sql_dir}:/sql:ro" \
      postgres:17-alpine \
      psql \
      --no-password \
      --set ON_ERROR_STOP=1 \
      --host "${PGHOST}" \
      --port "${PGPORT}" \
      --username "${PGUSER}" \
      --dbname "${PGDATABASE}" \
      --file "/sql/$(basename "${sql_file}")"
    return
  fi

  echo "psql is required; install PostgreSQL client or Docker" >&2
  exit 1
}

echo "Applying SQL version ${project_version}"
for sql_file in "${sql_files[@]}"; do
  echo "Applying $(basename "${sql_file}")"
  run_sql "${sql_file}"
done

unset PGPASSWORD
echo "SQL version ${project_version} applied successfully"
