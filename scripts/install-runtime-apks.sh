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
readonly installed_before=/tmp/apk-installed-before
readonly installed_after=/tmp/apk-installed-after
readonly added_after=/tmp/apk-added-after
readonly removed_after=/tmp/apk-removed-after

cleanup() {
    rm -f "$tor_apk" "$installed_before" "$installed_after" "$added_after" "$removed_after"
}
trap cleanup EXIT

apk info -v | sort > "$installed_before"
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

apk info -v | sort > "$installed_after"
comm -13 "$installed_before" "$installed_after" \
    | sed 's/-\([^-]*-r[0-9][0-9]*\)$/=\1/' \
    > "$added_after"
comm -23 "$installed_before" "$installed_after" > "$removed_after"

if [ -s "$removed_after" ]; then
    printf 'APK installation replaced or removed base-image packages:\n' >&2
    cat "$removed_after" >&2
    exit 1
fi

if ! diff -u "$apk_lock" "$added_after"; then
    printf 'Installed APK closure differs from docker/runtime-apk.lock for %s\n' "$alpine_arch" >&2
    exit 1
fi
