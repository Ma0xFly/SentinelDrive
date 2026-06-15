#!/bin/sh
set -eu

ENV_FILE="${ENV_FILE:-.env}"

lookup_env() {
	name="$1"
	eval "value=\${$name-}"
	if [ -n "${value:-}" ]; then
		printf '%s' "$value"
		return
	fi

	if [ -f "$ENV_FILE" ]; then
		awk -v key="$name" '
			/^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
			index($0, key "=") == 1 {
				value = substr($0, length(key) + 2)
				gsub(/^["'\''"]|["'\''"]$/, "", value)
				print value
				exit
			}
		' "$ENV_FILE"
	fi
}

is_unsafe_placeholder() {
	value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
	[ -z "$value" ] && return 0
	case "$value" in
		*change-me*|*example.test*) return 0 ;;
		*) return 1 ;;
	esac
}

require_replaced() {
	name="$1"
	value="$(lookup_env "$name")"
	if is_unsafe_placeholder "$value"; then
		unsafe_names="${unsafe_names} ${name}"
	fi
}

app_env="$(lookup_env APP_ENV)"
case "$(printf '%s' "${app_env:-development}" | tr '[:upper:]' '[:lower:]')" in
	production|prod|staging)
		unsafe_names=""
		require_replaced APP_SECRET_KEY
		require_replaced POSTGRES_PASSWORD
		require_replaced DATABASE_URL
		require_replaced ADMIN_BOOTSTRAP_EMAIL
		require_replaced ADMIN_BOOTSTRAP_PASSWORD
		caddy_host="$(lookup_env CADDY_HOST)"
		if [ "$(printf '%s' "${caddy_host:-localhost}" | tr '[:upper:]' '[:lower:]')" = "localhost" ]; then
			unsafe_names="${unsafe_names} CADDY_HOST"
		fi

		if [ -n "$unsafe_names" ]; then
			printf 'Unsafe production configuration: replace placeholder values for:%s\n' "$unsafe_names" >&2
			exit 1
		fi
		;;
esac

printf 'Configuration validation passed for %s environment.\n' "${app_env:-development}"
