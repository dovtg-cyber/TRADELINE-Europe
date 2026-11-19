#!/usr/bin/env bash
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PUBLIC="$ROOT/public"

for file in core.js client.js chat.js admin.js paypal-qr.jpg style.css; do
  if [ ! -s "$ROOT/$file" ]; then
    echo "Required frontend file is missing or empty: $file" >&2
    exit 1
  fi
done

mkdir -p "$PUBLIC/js" "$PUBLIC/css" "$PUBLIC/assets"
cp "$ROOT/core.js" "$ROOT/client.js" "$ROOT/chat.js" "$ROOT/admin.js" "$PUBLIC/js/"
cp "$ROOT/style.css" "$PUBLIC/css/style.css"
cp "$ROOT/paypal-qr.jpg" "$PUBLIC/assets/paypal-qr.jpg"

for file in index.html config.js css/style.css css/enhancements.css js/core.js js/client.js js/chat.js js/admin.js js/enhancements.js assets/paypal-qr.jpg; do
  if [ ! -s "$PUBLIC/$file" ]; then
    echo "Publish output is missing or empty: public/$file" >&2
    exit 1
  fi
done

echo "Static site assembled successfully in public/."
