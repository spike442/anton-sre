#!/usr/bin/env bash
set -euo pipefail

op_vault="homelab"
op_item="anton"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  command -v op >/dev/null || {
    echo "AWS credentials are not set and the 1Password CLI (op) is unavailable" >&2
    exit 1
  }
  AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(op read "op://${op_vault}/${op_item}/S3_ACCESS_KEY_ID")}"
  AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(op read "op://${op_vault}/${op_item}/S3_SECRET_ACCESS_KEY")}"
fi

export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

endpoint="https://rustfs.timcasa.me"
bucket="anton"
prefix="anton/prompts"
region="us-east-1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prompt_dir="${script_dir}/../prompts"

export AWS_DEFAULT_REGION="$region"
export AWS_EC2_METADATA_DISABLED=true
export AWS_S3_ADDRESSING_STYLE=path

aws --endpoint-url "$endpoint" s3 cp \
  "${prompt_dir}/" \
  "s3://${bucket}/${prefix}/" \
  --recursive \
  --no-progress

checksum="$(sha256sum "${prompt_dir}/system.md" | awk '{print $1}')"
echo "Uploaded prompt directory to s3://${bucket}/${prefix}/"
echo "Set s3.prompt_sha256 to: ${checksum}"
