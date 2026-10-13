#!/usr/bin/env python3
"""Opt-in Git source availability check; separate from offline package validation."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json")


def verify_source(url, ref):
    """Check an advertised branch/tag, or fetch and checkout an exact SHA."""
    try:
        if re.fullmatch(r"[a-fA-F0-9]{40}", ref):
            with tempfile.TemporaryDirectory(prefix="esra-published-sha-") as directory:
                def git(*args):
                    return subprocess.run(["git", *args], cwd=directory, capture_output=True,
                                          text=True, timeout=60, check=True)
                git("init", "--quiet")
                git("fetch", "--depth=1", url, ref)
                git("checkout", "--detach", "FETCH_HEAD")
                head = git("rev-parse", "HEAD").stdout.strip()
                return [] if head.lower() == ref.lower() else [f"{url}: SHA checkout mismatch"]
        result = subprocess.run(["git", "ls-remote", "--exit-code", url,
                                 f"refs/heads/{ref}", f"refs/tags/{ref}"],
                                capture_output=True, text=True, timeout=60)
        if result.returncode or not result.stdout.strip():
            return [f"{url}: advertised ref {ref!r} unavailable: {result.stderr.strip() or 'no matching remote ref'}"]
        return []
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"{url}: advertised ref {ref!r} verification failed: {exc}"]


def verify_catalogs(root):
    errors = []
    seen = set()
    for relative in CATALOGS:
        value = json.loads((root / relative).read_text())
        for entry in value["plugins"]:
            source = entry["source"]
            url = source.get("url") or f'https://github.com/{source["repo"]}.git'
            pair = (url, source["ref"])
            if pair not in seen:
                errors.extend(verify_source(*pair))
                seen.add(pair)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, default=ROOT,
                        help="Read catalogs from this checkout or a staged catalog directory")
    args = parser.parse_args()
    errors = verify_catalogs(args.catalog_root)
    for error in errors:
        print(f"FAIL published-source: {error}")
    if not errors:
        print("PASS published-source: all advertised Git refs resolve (native loading not tested)")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
