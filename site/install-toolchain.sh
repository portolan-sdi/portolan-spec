#!/usr/bin/env bash
# Official asset digests from the GitHub releases API for these exact releases.
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: $0 <dest-dir>" >&2
  exit 2
fi
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo 'The pinned toolchain requires Linux x86_64.' >&2
  exit 1
fi
mkdir -p "$1/bin"
dest=$(cd "$1" && pwd)
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
curl --fail --location --retry 3 --output "$staging/pandoc.tar.gz" \
  https://github.com/jgm/pandoc/releases/download/3.14/pandoc-3.14-linux-amd64.tar.gz
printf '%s  %s\n' c5f4720cdefb3f7bdc5d07202ef579feef0d1370773c873804dd8fdaa8c4f1b8 "$staging/pandoc.tar.gz" | sha256sum --check
curl --fail --location --retry 3 --output "$staging/typst.tar.xz" \
  https://github.com/typst/typst/releases/download/v0.15.1/typst-x86_64-unknown-linux-musl.tar.xz
printf '%s  %s\n' a6d077d0a95eed5a2eba715b2dae06be954f624ccbf85758a03f389ded33118c "$staging/typst.tar.xz" | sha256sum --check
tar -xzf "$staging/pandoc.tar.gz" -C "$staging"
tar -xJf "$staging/typst.tar.xz" -C "$staging"
install -m 755 "$staging/pandoc-3.14/bin/pandoc" "$dest/bin/pandoc"
install -m 755 "$staging/typst-x86_64-unknown-linux-musl/typst" "$dest/bin/typst"
"$dest/bin/pandoc" --version
"$dest/bin/typst" --version
