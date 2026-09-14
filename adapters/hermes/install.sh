#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HERMES_ROOT=${HERMES_HOME:-"$HOME/.hermes"}
ESRA_ROOT=${ESRA_HOME:-"$HERMES_ROOT/esra"}
SKILLS_DEST="$HERMES_ROOT/skills/esra"
RUNTIME_DEST="$ESRA_ROOT/runtime"

if [ ! -d "$SCRIPT_DIR/skills" ] || [ ! -d "$SCRIPT_DIR/runtime" ]; then
  echo "error: run the installer from an extracted esra-agents Hermes distribution" >&2
  exit 1
fi

if find "$SCRIPT_DIR/skills" "$SCRIPT_DIR/runtime" -type l -print -quit | grep -q .; then
  echo "error: refusing an installer source containing symlinks" >&2
  exit 1
fi

mkdir -p "$SKILLS_DEST" "$RUNTIME_DEST"
chmod 700 "$HERMES_ROOT" "$HERMES_ROOT/skills" "$SKILLS_DEST" "$ESRA_ROOT" "$RUNTIME_DEST" 2>/dev/null || true

for skill in "$SCRIPT_DIR"/skills/*; do
  [ -d "$skill" ] || continue
  name=$(basename "$skill")
  target="$SKILLS_DEST/$name"
  if [ -e "$target" ]; then
    backup="$target.pre-esra-agents"
    if [ -e "$backup" ]; then
      echo "error: backup already exists: $backup" >&2
      exit 1
    fi
    mv "$target" "$backup"
  fi
  cp -R "$skill" "$target"
done

for runtime_file in "$SCRIPT_DIR"/runtime/*.py; do
  [ -f "$runtime_file" ] || continue
  cp "$runtime_file" "$RUNTIME_DEST/$(basename "$runtime_file")"
done
cp "$SCRIPT_DIR/esra-conformance.json" "$ESRA_ROOT/conformance.json"
cp "$SCRIPT_DIR/adapters/hermes/adapter.json" "$ESRA_ROOT/adapter.json"
cp "$SCRIPT_DIR/adapters/hermes/legacy-skill-map.json" "$ESRA_ROOT/legacy-skill-map.json"
chmod 600 "$ESRA_ROOT"/*.json 2>/dev/null || true
chmod 755 "$RUNTIME_DEST"/*.py 2>/dev/null || true

echo "Installed ESRA Agents skills in $SKILLS_DEST"
echo "Installed the shared runtime in $RUNTIME_DEST"
echo "Restart Hermes or refresh its skill catalog before use."
