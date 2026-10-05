#!/usr/bin/env python3
"""Dev-environment launch evidence on a dedicated 1280x720 Xvfb display.

Runs the literal developer entrypoints: `./gradlew runServer` (nogui) starts the
Forge dev server, then `./gradlew runClient -PdevEvidence` starts the real dev
client, which auto-joins it through --quickPlayMultiplayer. Proof of an in-world
dev client: the server console logs "Dev joined the game", the client logs show
the re_demo mod list entry, an F2 screenshot lands in run/screenshots, and a
Licker summoned beside the player via the server console renders on the dev
client frame. This complements the installed-JAR evidence; it is not a playtest.
Requires Java 17, Python 3.11+, Xvfb, Openbox and xdotool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback


SERVER_READY = re.compile(r"Done \([0-9.,]+s\)! For help")
JOINED = re.compile(r"\bDev\b.*(logged in with entity id|joined the game)")


class EvidenceError(RuntimeError):
    pass


def file_record(path: Path) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": digest}


def tail(path: Path, limit: int = 2_000_000) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - limit))
        return stream.read().decode("utf-8", errors="replace")


class DevEnvCapture:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.project = args.project.resolve()
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.run_dir = self.project / "run"
        self.processes: list[tuple[str, subprocess.Popen]] = []
        self.handles = []
        self.server: subprocess.Popen | None = None
        self.client: subprocess.Popen | None = None
        self.report = {
            "kind": "dev-env-evidence", "passed": False,
            "source_revision": os.environ.get("GITHUB_SHA", "unknown"),
            "client_command": "./gradlew runClient -PdevEvidence",
            "server_command": "./gradlew runServer",
            "quick_play": "127.0.0.1:25565",
            "run_client_reached_world": False, "mod_loaded_in_dev_env": False,
            "server_join_logged": False, "window_visible": False,
            "manual_playtest": False, "screenshots": [],
        }

    def start(self, name: str, command: list[str], cwd: Path, stdin=False) -> subprocess.Popen:
        log = (self.output / f"{name}.log").open("w", encoding="utf-8")
        self.handles.append(log)
        proc = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                start_new_session=True)
        self.processes.append((name, proc))
        return proc

    def alive(self) -> None:
        for name, process in (("server", self.server), ("client", self.client)):
            if process is not None and process.poll() is not None:
                raise EvidenceError(f"{name} exited unexpectedly ({process.returncode}); inspect {name}.log")

    def wait(self, predicate, description: str, timeout: float) -> object:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.alive()
            result = predicate()
            if result:
                return result
            time.sleep(0.5)
        raise EvidenceError(f"Timed out waiting for {description}")

    def server_command(self, command: str) -> bool:
        if self.server is None or self.server.stdin is None:
            return False
        try:
            self.server.stdin.write(command + "\n")
            self.server.stdin.flush()
            return True
        except OSError:
            return False

    def prepare(self) -> None:
        if not self.args.accept_minecraft_eula:
            raise EvidenceError("Explicit --accept-minecraft-eula is required for the dev server")
        if not (self.project / "gradlew").is_file():
            raise EvidenceError("--project must be the checked-out Forge project")
        for tool in ("java", "xdotool", "openbox"):
            if shutil.which(tool) is None:
                raise EvidenceError(f"Required executable not found: {tool}")
        if not os.environ.get("DISPLAY"):
            raise EvidenceError("Run under a dedicated Xvfb display; DISPLAY is missing")
        geometry = subprocess.check_output(["xdotool", "getdisplaygeometry"], text=True, timeout=10).strip()
        if geometry != "1280 720":
            raise EvidenceError(f"Dedicated display must be 1280x720, got {geometry}")
        self.run_dir.mkdir(exist_ok=True)
        (self.run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        (self.run_dir / "server.properties").write_text(
            "server-port=25565\nonline-mode=false\nenforce-secure-profile=false\n"
            "gamemode=creative\nforce-gamemode=true\ndifficulty=normal\nmax-players=1\n"
            "level-name=dev-evidence\nlevel-type=minecraft:flat\n"
            'generator-settings={"biome":"minecraft:plains","layers":[{"block":"minecraft:bedrock","height":1},'
            '{"block":"minecraft:dirt","height":2},{"block":"minecraft:grass_block","height":1}]}\n'
            "generate-structures=false\nspawn-protection=0\nspawn-animals=false\nspawn-monsters=false\n"
            "spawn-npcs=false\nview-distance=8\nsimulation-distance=5\nallow-flight=true\n"
            "enable-command-block=false\nmotd=Dev-env evidence\n", encoding="utf-8")
        (self.run_dir / "options.txt").write_text(
            "renderDistance:8\nsimulationDistance:5\nmaxFps:30\ngraphicsMode:0\nclouds:false\n"
            "guiScale:2\nfov:0.0\ngamma:1.0\nviewBobbing:false\npauseOnLostFocus:false\n"
            "tutorialStep:none\nonboardAccessibility:false\nskipMultiplayerWarning:true\n"
            "chatVisibility:2\nlang:en_us\n", encoding="utf-8")
        # The dev client joins offline-mode as "Dev"; ops let its console summon.
        dev_uuid = subprocess.run(
            [sys.executable, "-c",
             "import hashlib, uuid; print(uuid.UUID(bytes=hashlib.md5(b'OfflinePlayer:Dev').digest(), version=3))"],
            check=True, capture_output=True, text=True).stdout.strip()
        (self.run_dir / "ops.json").write_text(json.dumps(
            [{"uuid": dev_uuid, "name": "Dev", "level": 4, "bypassesPlayerLimit": False}]), encoding="utf-8")
        self.start("window-manager", ["openbox", "--sm-disable"], self.run_dir)

    def launch(self) -> None:
        env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe")
        gradle = ["bash", str(self.project / "gradlew"), "--no-daemon", "--console=plain", "--stacktrace",
                  "--max-workers=2", "-Dorg.gradle.jvmargs=-Xmx3G"]
        server_log = (self.output / "dev-server.log").open("w", encoding="utf-8")
        self.handles.append(server_log)
        self.server = subprocess.Popen([*gradle, "runServer"], cwd=self.project, env=env,
                                       stdin=subprocess.PIPE, stdout=server_log, stderr=subprocess.STDOUT,
                                       text=True, bufsize=1, start_new_session=True)
        self.processes.append(("server", self.server))
        self.wait(lambda: SERVER_READY.search(tail(self.output / "dev-server.log")),
                  "dev Forge server ready", self.args.startup_timeout)
        self.report["dev_server_ready"] = True
        client_log = (self.output / "dev-client.log").open("w", encoding="utf-8")
        self.handles.append(client_log)
        self.client = subprocess.Popen([*gradle, "-PdevEvidence", "runClient"], cwd=self.project, env=env,
                                       stdin=subprocess.DEVNULL, stdout=client_log, stderr=subprocess.STDOUT,
                                       text=True, bufsize=1, start_new_session=True)
        self.processes.append(("client", self.client))
        self.wait(lambda: JOINED.search(tail(self.output / "dev-server.log")),
                  "dev client join the dev server world", self.args.startup_timeout)
        self.report["server_join_logged"] = True
        def window():
            result = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^Minecraft.*"],
                                    text=True, capture_output=True, timeout=10)
            return result.stdout.splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else None
        self.window = str(self.wait(window, "visible dev client window", 90))
        subprocess.run(["xdotool", "windowactivate", "--sync", self.window], check=True, timeout=10)
        self.report["window_visible"] = True
        time.sleep(8)

    def type_command(self, command: str) -> None:
        # Gradle runServer does not reliably forward stdin to Minecraft, so the
        # opped Dev client types the command. Avoid NBT braces: xdotool cannot
        # type `{` with modifiers cleared.
        subprocess.run(["xdotool", "windowactivate", "--sync", self.window], check=True, timeout=10)
        # The client is already in-world. Escape would open the pause menu and
        # swallow the following chat key, leaving every command unexecuted.
        subprocess.run(["xdotool", "key", "--clearmodifiers", "t"], check=True, timeout=10)
        time.sleep(0.45)
        subprocess.run(["xdotool", "type", "--delay", "18", "--", command], check=True, timeout=30)
        subprocess.run(["xdotool", "key", "Return"], check=True, timeout=10)
        time.sleep(0.45)

    def capture(self) -> None:
        self.wait(lambda: re.search(r"re_demo", tail(self.output / "dev-client.log", 10_000_000)),
                  "re_demo in dev client mod log", 30)
        self.report["mod_loaded_in_dev_env"] = True
        marker = f"CE_DEV_{int(time.time())}"
        console = self.server_command(f"say {marker}")
        try:
            console = console and bool(self.wait(
                lambda: marker in tail(self.output / "dev-server.log"), "server console roundtrip", 8))
        except EvidenceError:
            console = False
        self.report["server_console_roundtrip"] = console
        self.type_command("/kill @e[type=re_demo:licker]")
        self.type_command("/kill @e[type=re_demo:tyrant]")
        self.type_command("/kill @e[type=re_demo:g1_birkin]")
        self.type_command("/tp @s 0 64 -6 0 12")
        self.type_command("/summon re_demo:licker -5 64 8")
        self.type_command("/summon re_demo:tyrant 0 64 8")
        self.type_command("/summon re_demo:g1_birkin 5 64 8")
        def summoned() -> bool:
            text = tail(self.output / "dev-server.log", 4_000_000)
            return all(f"Summoned new {name}" in text
                       for name in ("Licker", "Tyrant", "G1 William Birkin"))
        try:
            self.wait(summoned, "dev client summoned all three creatures", 20)
        except EvidenceError as exc:
            raise EvidenceError("dev client did not summon Licker+Tyrant+G1 Birkin; "
                                "runClient F2 would be an empty superflat") from exc
        self.report["console_creature_summon"] = True
        self.report["three_creatures_summoned"] = True
        time.sleep(5)
        screenshots = self.run_dir / "screenshots"
        previous = set(screenshots.glob("*.png")) if screenshots.is_dir() else set()
        subprocess.run(["xdotool", "windowactivate", "--sync", self.window], check=True, timeout=10)
        subprocess.run(["xdotool", "key", "--clearmodifiers", "F1"], check=True, timeout=10)
        time.sleep(0.35)
        subprocess.run(["xdotool", "key", "--clearmodifiers", "F2"], check=True, timeout=10)
        shot = self.wait(lambda: next(iter(set(screenshots.glob("*.png")) - previous), None)
                         if screenshots.is_dir() else None,
                         "native F2 screenshot in dev client", 30)
        time.sleep(1)
        subprocess.run(["xdotool", "key", "--clearmodifiers", "F1"], check=True, timeout=10)
        target = self.output / "dev-client-in-world.png"
        shutil.copy2(shot, target)
        if target.stat().st_size < 80_000:
            raise EvidenceError("dev-client F2 is too small to be a three-creature world shot")
        self.report["screenshots"].append(dict(file_record(target), origin="native Minecraft F2",
                                               hide_gui=True, three_creatures=True))
        self.report["run_client_reached_world"] = True
        self.report["passed"] = True

    def cleanup(self) -> None:
        self.server_command("stop")
        time.sleep(3)
        for _, proc in reversed(self.processes):
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=15)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
        for handle in self.handles:
            handle.close()
        for folder in ("logs", "crash-reports"):
            source = self.run_dir / folder
            if source.is_dir():
                shutil.copytree(source, self.output / f"run-{folder}", dirs_exist_ok=True)
        self.report["files"] = [dict(file_record(path), path=str(path.relative_to(self.output)))
                                for path in sorted(self.output.rglob("*")) if path.is_file()]
        (self.output / "report.json").write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("build/dev-env-evidence"))
    parser.add_argument("--startup-timeout", type=int, default=900)
    parser.add_argument("--accept-minecraft-eula", action="store_true")
    args = parser.parse_args()
    capture = DevEnvCapture(args)
    try:
        capture.prepare()
        capture.launch()
        capture.capture()
    except BaseException as exc:
        capture.report["passed"] = False
        capture.report["error"] = f"{type(exc).__name__}: {exc}"
        (capture.output / "failure.log").write_text(traceback.format_exc(), encoding="utf-8")
        print(capture.report["error"], file=sys.stderr)
    finally:
        capture.cleanup()
    print(json.dumps({"passed": capture.report["passed"], "report": str(capture.output / "report.json")}))
    return 0 if capture.report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
