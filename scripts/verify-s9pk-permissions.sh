#!/usr/bin/env bash
set -euo pipefail

# Verifies that javascript.squashfs inside one or more packed .s9pk files is
# world-readable/traversable.
#
# StartOS loads index.js on the host, outside of any container, as a
# package-scoped uid that is neither the uid nor the gid that packed the
# artifact. mksquashfs preserves the on-disk mode/owner of the ./javascript
# directory verbatim, so any permission narrower than directory=rwxr-xr-x /
# file=rw-r--r-- for the "other" class ships a payload StartOS cannot read,
# independent of which umask the packaging shell happened to have. This
# inspects the final packed squashfs bytes directly, not the source
# workspace, because the workspace can be correct while the packed artifact
# is not (see issue #12).

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <path-to-s9pk> [<path-to-s9pk> ...]" >&2
  exit 2
fi

status=0
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

for s9pk in "$@"; do
  if [[ ! -f "$s9pk" ]]; then
    echo "::error::s9pk not found: $s9pk"
    status=1
    continue
  fi

  echo "Verifying javascript.squashfs permissions in ${s9pk}"
  squashfs_blob="${workdir}/$(basename "$s9pk").javascript.squashfs"

  if ! start-cli s9pk inspect "$s9pk" cat javascript.squashfs > "$squashfs_blob"; then
    echo "::error::${s9pk}: failed to extract javascript.squashfs"
    status=1
    continue
  fi

  listing="$(sqfs2tar --root-becomes . "$squashfs_blob" | tar -tv)"
  if [[ -z "$listing" ]]; then
    echo "::error::${s9pk}: javascript.squashfs is empty"
    status=1
    continue
  fi

  while IFS= read -r entry; do
    mode="${entry:0:10}"
    entry_type="${mode:0:1}"
    other_bits="${mode:7:3}"
    entry_path="${entry##* }"

    case "$entry_type" in
      d)
        if [[ "${other_bits:0:1}" != r || "${other_bits:2:1}" != x ]]; then
          echo "::error::${s9pk}: javascript.squashfs directory '${entry_path}' is not world-traversable (mode ${mode})"
          status=1
        fi
        ;;
      -)
        if [[ "${other_bits:0:1}" != r ]]; then
          echo "::error::${s9pk}: javascript.squashfs file '${entry_path}' is not world-readable (mode ${mode})"
          status=1
        fi
        ;;
      *)
        # Symlinks and other special types carry no meaningful "other" mode
        # bits of their own; target resolution depends on the target's mode.
        ;;
    esac
  done <<< "$listing"
done

exit "$status"
