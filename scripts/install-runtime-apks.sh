#!/bin/sh
set -eu

readonly lock_dir=/tmp/dependency-locks
readonly apk_lock="$lock_dir/runtime-apk.lock"
readonly tor_hash_lock="$lock_dir/tor-apk-sha256.lock"
readonly tor_version=0.4.9.11-r0

case "${TARGETARCH:-}" in
    amd64) alpine_arch=x86_64 ;;
    arm64) alpine_arch=aarch64 ;;
    *)
        printf 'Unsupported or missing TARGETARCH: %s\n' "${TARGETARCH:-<unset>}" >&2
        exit 1
        ;;
esac

tor_sha256="$(awk -v arch="$alpine_arch" '$1 == arch { print $2 }' "$tor_hash_lock")"
if [ -z "$tor_sha256" ]; then
    printf 'No Tor APK hash is locked for %s\n' "$alpine_arch" >&2
    exit 1
fi

readonly tor_apk=/tmp/tor.apk
readonly tor_url="https://dl-cdn.alpinelinux.org/alpine/edge/community/$alpine_arch/tor-$tor_version.apk"
wget --output-document "$tor_apk" "$tor_url"
printf '%s  %s\n' "$tor_sha256" "$tor_apk" | sha256sum -c -

set --
while IFS= read -r requirement; do
    case "$requirement" in
        ''|tor=*) ;;
        *) set -- "$@" "$requirement" ;;
    esac
done < "$apk_lock"

apk add --no-cache "$@" "$tor_apk"
rm -f "$tor_apk"

installed="$(mktemp)"
trap 'rm -f "$installed"' EXIT
apk info -v | sort > "$installed"
while IFS= read -r requirement; do
    package="${requirement%%=*}"
    version="${requirement#*=}"
    if ! grep -Fqx "$package-$version" "$installed"; then
        printf 'Locked APK not installed exactly: %s\n' "$requirement" >&2
        exit 1
    fi
done < "$apk_lock"
