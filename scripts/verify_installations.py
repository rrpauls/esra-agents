#!/usr/bin/env python3
"""Validate packages and available host CLIs in disposable profiles.

Default runs cold native validators only. --install permits installation solely
in temporary profiles. No user plugin configuration or global installation is
modified. --source optionally exercises tracked Git install/update at a chosen
already-published revision; it never publishes the working tree.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_distributions import ROOT, build, read_source
from scripts.distribution_contract import version
from scripts.validate_distributions import validate

HOSTS = {"codex": "openai", "claude": "claude", "grok": "claude",
         "hermes": "hermes", "openclaw": "openclaw", "antigravity": "antigravity"}


def profile_env(profile: Path) -> dict[str, str]:
    # Do not inherit real profile locations, auth settings or API credentials.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "LANG", "TMPDIR") if key in os.environ}
    env.update({"HOME": str(profile), "USERPROFILE": str(profile),
                "CODEX_HOME": str(profile / ".codex"), "CLAUDE_CONFIG_DIR": str(profile / ".claude"),
                "HERMES_HOME": str(profile / ".hermes"), "OPENCLAW_STATE_DIR": str(profile / ".openclaw"),
                "OPENCLAW_CONFIG_PATH": str(profile / ".openclaw/openclaw.json"),
                "XDG_CONFIG_HOME": str(profile / ".config"), "XDG_CACHE_HOME": str(profile / ".cache"),
                "PYTHONDONTWRITEBYTECODE": "1", "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    for name in (".codex", ".claude", ".hermes", ".openclaw", ".grok", ".config", ".cache"):
        (profile / name).mkdir(parents=True, exist_ok=True)
    return env


def run_command(command: list[str], env: dict[str, str], cwd: Path) -> tuple[str, str]:
    try:
        result = subprocess.run(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"") + (exc.stderr or b"")
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return "FAIL", f"native command timed out after 45 seconds: {output[-4000:]}"
    except OSError as exc:
        return "FAIL", str(exc)
    output = (result.stdout + result.stderr).strip()
    # Unavailable host bootstrap is not an ESRA validation failure.
    if ".install.lock" in output and "Operation not permitted" in output:
        return "SKIPPED", "Hermes launcher cannot access its managed runtime lock; supply --hermes-cli for a prepared environment"
    if "was not published" in output and "uv.lock" in output and "No such file" in output:
        return "SKIPPED", "Hermes package-manager environment is missing its own uv.lock; native managed installation requires a repaired host runtime"
    if result.returncode == 0 and command[1:] in (["plugin", "list", "--json"], ["inspect", "--json"]):
        try:
            value = json.loads(result.stdout)
            if command[1] == "inspect":
                plugins = value["plugins"]
                found = next(p for p in plugins if p["name"] == "esra-agents")
                assert found["provides"]["skills"] == 5 and found["provides"]["hooks"] is True
            else:
                plugins = value["installed"] if isinstance(value, dict) else value
                found = next(p for p in plugins if p.get("name") == "esra-agents" or p.get("id") == "esra-agents@esra-agents")
                assert found["version"] == version()
        except (ValueError, KeyError, TypeError, StopIteration, AssertionError):
            return "FAIL", "native discovery did not report the expected ESRA version/five skills/hooks"
    return ("PASS" if result.returncode == 0 else "FAIL"), output[-4000:]


@contextmanager
def git_fixture(workspace: Path):
    """Serve an exact disposable working-tree snapshot through native Git HTTP.

    Only a fixture bare repository is exposed on loopback, never host profiles,
    user configuration, secrets, or the original checkout's .git directory.
    """
    fixture = workspace / "git-fixture"
    checkout = fixture / "checkout"
    served = fixture / "served"
    served.mkdir(parents=True)
    checkout.mkdir()

    class QuietHandler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.git_backend()

        def do_POST(self):
            self.git_backend()

        def git_backend(self):
            request = urlsplit(self.path)
            if request.path not in {"/esra-agents.git/info/refs", "/esra-agents.git/git-upload-pack"}:
                self.send_error(404)
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            env = {"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_CONFIG_GLOBAL": os.devnull, "GIT_PROJECT_ROOT": str(served),
                   "GIT_HTTP_EXPORT_ALL": "1", "REQUEST_METHOD": self.command,
                   "PATH_INFO": request.path, "QUERY_STRING": request.query,
                   "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                   "CONTENT_LENGTH": str(len(body)), "REMOTE_ADDR": "127.0.0.1"}
            result = subprocess.run(["git", "http-backend"], env=env, input=body, capture_output=True, timeout=30)
            headers, separator, content = result.stdout.partition(b"\r\n\r\n")
            if result.returncode or not separator:
                self.send_error(500)
                return
            self.send_response(200)
            for line in headers.decode().splitlines():
                key, _, value = line.partition(":")
                if key.lower() != "status":
                    self.send_header(key, value.strip())
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    source = f"http://127.0.0.1:{server.server_port}/esra-agents.git"
    try:
        listed = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
        for relative in sorted(set(listed) - {""}):
            path = ROOT / relative
            if not path.is_file():
                continue
            dest = checkout / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(read_source(path))
        for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            path = checkout / relative
            value = json.loads(path.read_text())
            value["plugins"][0]["source"] = {"source": "url", "url": source, "ref": "stable"}
            path.write_text(json.dumps(value))
        env = profile_env(fixture / "profile")
        def git(*args, cwd=checkout):
            subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)
        git("init", "-b", "stable")
        git("add", ".")
        git("-c", "user.name=ESRA fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Isolated installation fixture")
        git("clone", "--bare", str(checkout), str(served / "esra-agents.git"))
        git("update-server-info", cwd=served / "esra-agents.git")
        yield source
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def commands(host: str, cli: str, plugin: Path, *, install: bool, source: str | None) -> list[list[str]]:
    if host == "codex":
        if not install:
            return []  # No cold validator; archive and marketplace contract checks run above.
        market = plugin.parents[1]
        return [[cli, "plugin", "marketplace", "add", source or str(market)],
                [cli, "plugin", "add", "esra-agents@esra-agents"],
                [cli, "plugin", "list", "--json"],
                *([[cli, "plugin", "marketplace", "upgrade", "esra-agents"]] if source else []),
                [cli, "plugin", "remove", "esra-agents@esra-agents"]]
    if host == "claude":
        steps = [[cli, "plugin", "validate", "--strict", str(plugin / ".claude-plugin/plugin.json")],
                 [cli, "plugin", "validate", "--strict", str(plugin / ".claude-plugin/marketplace.json")]]
        if install:
            if not source:
                # Local relative source tests this build; never silently fetch stable instead.
                path = plugin / ".claude-plugin/marketplace.json"
                value = json.loads(path.read_text())
                value["plugins"][0]["source"] = "./"
                path.write_text(json.dumps(value))
            steps += [[cli, "plugin", "marketplace", "add", source or str(plugin)],
                      [cli, "plugin", "install", "esra-agents@esra-agents"],
                      [cli, "plugin", "list", "--json"],
                      [cli, "plugin", "update", "esra-agents@esra-agents"],
                      [cli, "plugin", "uninstall", "esra-agents@esra-agents"]]
        return steps
    if host == "grok":
        steps = [[cli, "plugin", "validate", str(plugin)]]
        if install:
            steps += [[cli, "plugin", "install", source or str(plugin), "--trust"],
                      [cli, "plugin", "details", "esra-agents"], [cli, "inspect", "--json"]]
            if source:
                steps += [[cli, "plugin", "update", "esra-agents"]]
            steps += [[cli, "plugin", "uninstall", "esra-agents", "--confirm"]]
        return steps
    if host == "hermes":
        steps = [[cli, "plugins", "validate", str(plugin), "--json"]]
        if install and source:
            steps += [[cli, "plugins", "install", source, "--no-enable"],
                      [cli, "plugins", "check-updates"], [cli, "plugins", "update", "esra-agents"],
                      [cli, "plugins", "remove", "esra-agents"]]
        return steps
    if host == "openclaw":
        steps = [[cli, "plugins", "validate", "--root", str(plugin), "--json"]]
        if install:
            steps += [[cli, "plugins", "install", source or str(plugin), "--force", "--no-enable"],
                      [cli, "plugins", "inspect", "esra-agents", "--runtime", "--json"]]
            if source:
                steps += [[cli, "plugins", "update", "esra-agents", "--dry-run"]]
            steps += [[cli, "plugins", "uninstall", "esra-agents", "--force"]]
        return steps
    if host == "antigravity" and install:
        return [[cli, "plugin", "install", str(plugin)], [cli, "plugin", "list"],
                [cli, "plugin", "uninstall", "esra-agents"]]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=list(HOSTS))
    parser.add_argument("--install", action="store_true", help="Allow native installs into temporary profiles only")
    parser.add_argument("--source", help="Opt-in published Git source for selected host; requires --host and --install")
    parser.add_argument("--git-fixture", action="store_true", help="Test native Git tracking with a disposable loopback repository")
    parser.add_argument("--trust-source", action="store_true", help="Explicitly accept Hermes caution findings for an isolated source install; never bypasses dangerous findings")
    parser.add_argument("--pin-fixture", action="store_true", help="Verify exact-commit Hermes install/update refusal using the Git fixture")
    parser.add_argument("--hermes-cli", help="Prepared Hermes environment entry point (avoids bootstrap repair)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.source and not (args.install and args.host):
        parser.error("--source requires --host and --install")
    if args.git_fixture and (not args.install or not args.host or args.source):
        parser.error("--git-fixture requires --host and --install, and cannot be combined with --source")
    if args.trust_source and not (args.install and args.host == "hermes" and (args.source or args.git_fixture)):
        parser.error("--trust-source requires a Hermes --install with --source or --git-fixture")
    if args.pin_fixture and not (args.git_fixture and args.host == "hermes"):
        parser.error("--pin-fixture requires a Hermes Git fixture")
    results = []
    with tempfile.TemporaryDirectory(prefix="esra-installations-") as temporary:
        workspace = Path(temporary)
        dist = workspace / "dist"
        build(dist)
        errors = validate(dist)
        results.append({"host": "packages", "status": "FAIL" if errors else "PASS", "detail": "; ".join(errors) or "all archive contracts and checksums"})
        if not errors:
            for host in [args.host] if args.host else HOSTS:
                cli = args.hermes_cli if host == "hermes" and args.hermes_cli else shutil.which("agy" if host == "antigravity" else host)
                if not cli:
                    results.append({"host": host, "status": "SKIPPED", "detail": "host CLI unavailable"})
                    continue
                if host == "hermes" and not args.hermes_cli:
                    launcher = Path(cli)
                    try:
                        wrapped = "hermes-agent/.hermes/bin/hermes" in launcher.read_text()
                    except (OSError, UnicodeDecodeError):
                        wrapped = False
                    if wrapped:
                        results.append({"host": host, "status": "SKIPPED", "detail": "managed bootstrap launcher; supply --hermes-cli for a prepared environment"})
                        continue
                profile = workspace / host
                env = profile_env(profile)
                packages = profile / "packages"
                packages.mkdir()
                with ZipFile(dist / f"esra-agents-{HOSTS[host]}.zip") as archive:
                    archive.extractall(packages)  # Members validated above, isolated empty destination.
                plugin = packages / f"esra-agents-{HOSTS[host]}"
                if host == "codex":
                    plugin = plugin / "plugins/esra-agents"
                from contextlib import nullcontext
                fixture_context = git_fixture(workspace) if args.git_fixture else nullcontext(args.source)
                with fixture_context as source:
                    steps = commands(host, cli, plugin, install=args.install, source=source)
                    pin = None
                    if args.pin_fixture:
                        pin = subprocess.check_output(["git", "ls-remote", source, "HEAD"], env=env).decode().split()[0]
                        for command in steps:
                            if command[1:3] == ["plugins", "install"]:
                                command.extend(["--ref", pin])
                    if args.trust_source:
                        for command in steps:
                            if command[1:3] == ["plugins", "install"]:
                                command.extend(["--force", "--no-deps"])
                    for command in steps:
                        status, detail = run_command(command, env, profile)
                        if args.pin_fixture and command[1:3] == ["plugins", "update"]:
                            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=profile / ".hermes/plugins/esra-agents", env=env).decode().strip()
                            if status == "FAIL" and "pinned" in detail.lower() and head == pin:
                                status, detail = "PASS", "native updater refused the pinned source and HEAD remained unchanged"
                            else:
                                status, detail = "FAIL", "native pinned-update contract was not enforced"
                        results.append({"host": host, "status": status, "command": command[1:], "detail": detail})
                        if status != "PASS":
                            break
                    if host == "hermes":
                        config = profile / ".hermes/config.yaml"
                        if config.exists() and re.search(r"^\s*auto_apply:\s*(true|yes|on)\s*(?:#.*)?$", config.read_text(), re.M | re.I):
                            results.append({"host": host, "status": "FAIL", "detail": "installation silently enabled auto_apply"})
                if not steps:
                    results.append({"host": host, "status": "SKIPPED", "detail": "no cold validator; use --install for isolated discovery"})
                    continue
                if args.install and host == "hermes" and not (args.source or args.git_fixture):
                    results.append({"host": host, "status": "SKIPPED", "detail": "tracked Git lifecycle requires explicit --source; local native registration probed by validator"})
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            scope = " ".join(result.get("command", [])[:3])
            detail = result["detail"] if result["status"] != "PASS" else scope or result["detail"]
            print(f'{result["status"]} {result["host"]}: {detail}')
    return int(any(result["status"] == "FAIL" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
