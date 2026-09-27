#!/usr/bin/env bash
# Write /opt/aia/develop/.env from SSM Parameter Store.
#
#   bin/write-env.sh
#
# Every parameter under /aia/develop/ becomes one line, NAME=value, where NAME is
# the parameter's last path segment upper-cased. Terraform writes the non-secret
# values (bucket names, registry, Cognito ids, hostname) and creates the secret
# ones as SecureString with a generated value; the instance role may read both.
# The file is root-only. Nothing is printed but the names written.
#
# AIA_IMAGE_TAG is preserved across rewrites: it records what is deployed, and
# only bin/deploy.sh changes it.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

REGION="${AWS_REGION:-$(curl -fsS --max-time 2 -H "X-aws-ec2-metadata-token: $(curl -fsS --max-time 2 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')" http://169.254.169.254/latest/meta-data/placement/region)}"
PREFIX="${AIA_SSM_PREFIX:-/aia/develop/}"

current_tag=""
[ -f "$ENV_FILE" ] && current_tag="$(grep '^AIA_IMAGE_TAG=' "$ENV_FILE" | cut -d= -f2 || true)"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
chmod 0600 "$tmp"

{
  printf '# written by bin/write-env.sh at %s from %s -- do not edit by hand\n' "$(date -u +%FT%TZ)" "$PREFIX"
  aws ssm get-parameters-by-path --path "$PREFIX" --recursive --with-decryption --region "$REGION" \
      --query 'Parameters[].[Name,Value]' --output text \
    | while IFS=$'\t' read -r name value; do
        key="$(basename "$name" | tr '[:lower:]' '[:upper:]')"
        # Single-quoted, because both readers expand `$` in an unquoted value:
        # Compose interpolates the env file and lib.sh sources it. A bcrypt
        # hash ($2a$14$...) written bare reaches Caddy as "$2a$14".
        case "$value" in *"'"*) die "$key contains a single quote, which the env file cannot carry" ;; esac
        printf "%s='%s'\n" "$key" "$value"
        printf '  %s\n' "$key" >&2
      done
  if [ -n "$current_tag" ]; then printf 'AIA_IMAGE_TAG=%s\n' "$current_tag"; fi
} > "$tmp"

grep -q "^POSTGRES_PASSWORD='.\+'" "$tmp" || die "POSTGRES_PASSWORD is not set under $PREFIX"
install -o root -g root -m 0600 "$tmp" "$ENV_FILE"
log "wrote $ENV_FILE ($(grep -c '=' "$ENV_FILE") entries)"
