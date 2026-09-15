#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACKAGE_ROOT=${ESRA_PACKAGE_ROOT:-"$SCRIPT_DIR"}
HERMES_ROOT=${HERMES_HOME:-"$HOME/.hermes"}
PLUGIN_DEST="$HERMES_ROOT/plugins/esra-agents"

for required in plugin.yaml __init__.py review_wakeup.py runtime skills esra-conformance.json; do
  if [ ! -e "$PACKAGE_ROOT/$required" ]; then
    echo "error: missing Hermes package input: $PACKAGE_ROOT/$required" >&2
    exit 1
  fi
done

if find "$PACKAGE_ROOT/plugin.yaml" "$PACKAGE_ROOT/__init__.py" "$PACKAGE_ROOT/runtime" "$PACKAGE_ROOT/skills" -type l -print -quit | grep -q .; then
  echo "error: refusing an installer source containing symlinks" >&2
  exit 1
fi

if [ -e "$PLUGIN_DEST" ]; then
  echo "error: plugin already exists: $PLUGIN_DEST" >&2
  echo "Remove or move it explicitly before reinstalling." >&2
  exit 1
fi

mkdir -p "$HERMES_ROOT/plugins" "$PLUGIN_DEST"
chmod 700 "$HERMES_ROOT" "$HERMES_ROOT/plugins" "$PLUGIN_DEST" 2>/dev/null || true
cp "$PACKAGE_ROOT/plugin.yaml" "$PACKAGE_ROOT/__init__.py" "$PACKAGE_ROOT/review_wakeup.py" "$PACKAGE_ROOT/esra-conformance.json" "$PLUGIN_DEST/"
cp -R "$PACKAGE_ROOT/runtime" "$PACKAGE_ROOT/skills" "$PLUGIN_DEST/"
chmod 600 "$PLUGIN_DEST/plugin.yaml" "$PLUGIN_DEST/__init__.py" "$PLUGIN_DEST/esra-conformance.json"

echo "Installed native ESRA Agents plugin in $PLUGIN_DEST"
echo "Enable it with: hermes plugins enable esra-agents"
echo "Restart the Hermes gateway or start a fresh Hermes session."
