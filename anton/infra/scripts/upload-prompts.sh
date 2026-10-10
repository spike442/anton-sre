#!/usr/bin/env bash
set -euo pipefail

op_vault="homelab"
op_item="anton"

command -v op >/dev/null 2>&1 || {
  echo "1Password CLI (op) is required" >&2
  exit 1
}
S3_ACCESS_KEY_ID="$(op read "op://${op_vault}/${op_item}/S3_ACCESS_KEY_ID")"
S3_SECRET_ACCESS_KEY="$(op read "op://${op_vault}/${op_item}/S3_SECRET_ACCESS_KEY")"

export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY}"

s3_endpoint="https://s3.timcasa.me"
bucket="hive"
prefix="anton/prompts"
region="us-east-1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prompt_dir="${script_dir}/../prompts"

export AWS_DEFAULT_REGION="$region"
export AWS_EC2_METADATA_DISABLED=true
export AWS_S3_ADDRESSING_STYLE=path

aws --endpoint-url "$s3_endpoint" s3 cp \
  "${prompt_dir}/" \
  "s3://${bucket}/${prefix}/" \
  --recursive \
  --no-progress

checksum="$(sha256sum "${prompt_dir}/system.md" | awk '{print $1}')"
echo "Uploaded prompt directory to s3://${bucket}/${prefix}/"
echo "Set s3.prompt_sha256 to: ${checksum}"
