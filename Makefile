ARCHES := x86 arm

# The SDK's default JS_BUNDLE (node_modules/@start9labs/start-sdk/s9pk.mk)
# leaves ./javascript with whatever mode ncc's Node process happens to
# create, which is governed by the invoking shell's umask. start-cli s9pk
# pack then mksquashfs's that directory into javascript.squashfs verbatim,
# so a stricter-than-0022 umask anywhere upstream of `make` (e.g. a release
# workflow step that scopes a restrictive umask around signing-key
# material) ships an unreadable/untraversable payload StartOS cannot load.
# Override here, before the include, so it wins over the SDK's `?=` default
# and the permissions are deterministic regardless of ambient umask.
JS_BUNDLE := rm -rf javascript && npx ncc build startos/index.ts -o javascript && find javascript -type d -exec chmod 0755 {} + && find javascript -type f -exec chmod 0644 {} +

include node_modules/@start9labs/start-sdk/s9pk.mk
