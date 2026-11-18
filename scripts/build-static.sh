#!/usr/bin/env bash
set -eu

# Assemble the existing root-level frontend into Render's configured publish directory.
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PUBLIC="$ROOT/public"

for file in core.js client.js chat.js admin.js paypal-qr.jpg; do
  if [ ! -f "$ROOT/$file" ]; then
    echo "Required frontend file is missing: $file" >&2
    exit 1
  fi
done

mkdir -p "$PUBLIC/js" "$PUBLIC/css" "$PUBLIC/assets"
cp "$ROOT/core.js" "$ROOT/client.js" "$ROOT/chat.js" "$ROOT/admin.js" "$PUBLIC/js/"
cp "$ROOT/paypal-qr.jpg" "$PUBLIC/assets/paypal-qr.jpg"

# Fail the build rather than publish a broken page when a referenced resource is absent.
for file in index.html config.js css/style.css js/core.js js/client.js js/chat.js js/admin.js assets/paypal-qr.jpg; do
  if [ ! -s "$PUBLIC/$file" ]; then
    echo "Publish output is missing or empty: public/$file" >&2
    exit 1
  fi
done

echo "Static site assembled successfully in public/."
