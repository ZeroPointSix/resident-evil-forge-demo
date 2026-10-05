#!/usr/bin/env python3
"""Capture a controlled real-client scene on a dedicated 1280x720 Xvfb display.

Both sides load the same built release JAR in isolated official Forge profiles.
The client is installed with minecraft-launcher-lib's maintained Forge support.
This is automated rendering/combat evidence, not a human playtest or full E2E.
Only a new temporary world is modified; the server binds to 127.0.0.1 only.
Requires Java 17, Python 3.11+, Xvfb, Openbox, xdotool, Mesa and ffmpeg/ffprobe.
"""

from __future__ import annotations

import argparse
from array import array
import configparser
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import uuid
import zipfile


MC_VERSION = "1.20.1"
FORGE_VERSION = "47.2.0"
GECKO_VERSION = "4.4.9"
MUSIC_EVENT = "re_demo:encounter_theme"
CAMERA = "EvidenceCamera"
SIZE = (1280, 720)
MOBS = (("licker", "Licker", 0, 0.7), ("tyrant", "Tyrant", 6, 1.6),
        ("g1_birkin", "G1 Birkin", 12, 1.7))
FORGE_URL = ("https://maven.minecraftforge.net/net/minecraftforge/forge/"
             f"{MC_VERSION}-{FORGE_VERSION}/forge-{MC_VERSION}-{FORGE_VERSION}-installer.jar")
GECKO_NAME = f"geckolib-forge-{MC_VERSION}-{GECKO_VERSION}.jar"
GECKO_URL = ("https://dl.cloudsmith.io/public/geckolib3/geckolib/maven/software/bernie/geckolib/"
             f"geckolib-forge-{MC_VERSION}/{GECKO_VERSION}/{GECKO_NAME}")

# The installer runs in a bounded subprocess so download/processor failures
# cannot leave an unbounded background installation or hide processor stderr.
INSTALL_CLIENT = r"""
import shutil
import subprocess
import sys
from minecraft_launcher_lib import mod_loader
try:
    profile = mod_loader.get_mod_loader('forge').install(
        sys.argv[2], sys.argv[1], loader_version=sys.argv[3],
        java=shutil.which('java'), callback={'setStatus': lambda s: print(s, flush=True)})
    print('Installed official Forge client profile:', profile, flush=True)
except subprocess.CalledProcessError as exc:
    if exc.stdout:
        print(exc.stdout.decode(errors='replace') if isinstance(exc.stdout, bytes) else exc.stdout)
    if exc.stderr:
        print(exc.stderr.decode(errors='replace') if isinstance(exc.stderr, bytes) else exc.stderr)
    raise
"""


class EvidenceError(RuntimeError):
    pass


def check_external_geckolib(archive: zipfile.ZipFile) -> None:
    if any(name.startswith("software/bernie/geckolib/") for name in archive.namelist()):
        raise EvidenceError("Release JAR must not bundle GeckoLib; install 4.4.9 separately")
    for name in archive.namelist():
        if name.startswith("META-INF/jarjar/") and name.endswith(".jar"):
            with zipfile.ZipFile(io.BytesIO(archive.read(name))) as nested:
                if any(path.startswith("software/bernie/geckolib/") for path in nested.namelist()):
                    raise EvidenceError("Release JAR must not embed GeckoLib as a jar-in-jar dependency")


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


def sync_rows(log: str, role: str) -> list[dict]:
    marker = f"RE_DEMO_SYNC_{role} "
    return [dict(re.findall(r"(\w+)=([^\s]+)", line.split(marker, 1)[1]))
            for line in log.splitlines() if marker in line]


def validate_animation_sync(client: str, server: str) -> dict:
    samples = sync_rows(client, "CLIENT")
    server_frames = {(r["uuid"], r["seq"], r["attack"], r["tick"]) for r in sync_rows(server, "SERVER")}
    late = {}
    reentries = {}
    seen_attacks = {}
    identities = {}
    for row in samples:
        identity = (row["uuid"], row["seq"], row["attack"], row["tick"])
        if identity not in server_frames:
            raise EvidenceError(f"Client sample has no matching authoritative server frame: {identity}")
        expected = min((int(row["tick"]) + float(row["partial"])) * float(row["speed"]),
                       math.nextafter(float(row["length"]), -math.inf))
        prefix, segment, point = (float(row[k]) for k in ("prefix", "segment", "point"))
        # GeckoLib 4.4.9 uses segment-relative ticks, except its final-keyframe
        # overrun branch, which stores the absolute clip tick instead.
        beyond = row["last"] == "true" and expected >= prefix + segment
        expected_point = expected if beyond else expected - prefix
        if (row["state"] != "RUNNING" or not math.isfinite(float(row["value"]))
                or expected < prefix - 1e-5 or (not beyond and expected > prefix + segment + 1e-5)
                or abs(point - expected_point) > 1e-5):
            raise EvidenceError(f"Actual GeckoLib keyframe sample is not server-aligned: {row}")
        identities.setdefault(row["asset"], set()).add((row["uuid"], row["seq"]))
        if row["first"] == "true" and int(row["tick"]) >= 4:
            late.setdefault(row["asset"], row)
        attack_identity = identity[:3]
        previous_tick = seen_attacks.get(attack_identity)
        if (row["resumed"] == "true" and row["first"] == "false"
                and previous_tick is not None and int(row["tick"]) - previous_tick >= 4):
            reentries.setdefault(row["asset"], row)
        seen_attacks[attack_identity] = int(row["tick"])
    required = {mob[0] for mob in MOBS}
    if required - late.keys():
        raise EvidenceError(f"Missing real-client mid-attack first-frame samples: {sorted(required - late.keys())}")
    if required - reentries.keys():
        raise EvidenceError(f"Missing real-client same-attack re-entry samples: {sorted(required - reentries.keys())}")
    if any(len(identities.get(asset, ())) < 2 for asset in required):
        raise EvidenceError("Animation evidence must cover more than one attack identity per creature")
    return {"passed": True, "sample_count": len(samples), "late_first_frames": late,
            "same_attack_reentries": reentries,
            "attack_identities": {k: len(v) for k, v in identities.items()},
            "source": "Actual GeckoLib 4.4.9 bone-animation queues in the installed real Forge client",
            "alignment": "(replicated ATTACK_TICK + render partialTick) * animation speed; unique attack sequence",
            "scope": "Received server state, not zero network latency; Tyrant integer-duration rounding remains sub-tick"}


def download(url: str, target: Path) -> None:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "re-demo-client-evidence/1"})
            with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
         "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise EvidenceError(f"No decodable video/image stream: {path.name}")
    stream = data["streams"][0]
    if (stream.get("width"), stream.get("height")) != SIZE:
        raise EvidenceError(f"Unexpected image size for {path.name}: {stream}")
    return data


def frame_pixels(path: Path, seconds: float = 0) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path), "-frames:v", "1",
         "-vf", "scale=64:36,format=rgb24", "-f", "rawvideo", "-"],
        check=True, capture_output=True, timeout=30,
    )
    if len(result.stdout) != 64 * 36 * 3:
        raise EvidenceError(f"Incomplete frame in {path.name}")
    return result.stdout


def check_frame(path: Path) -> dict:
    probe(path)
    pixels = frame_pixels(path)
    luminance = [sum(pixels[i:i + 3]) / 3 for i in range(0, len(pixels), 3)]
    unique = len({pixels[i:i + 3] for i in range(0, len(pixels), 3)})
    deviation = statistics.pstdev(luminance)
    if unique < 64 or deviation < 8 or max(luminance) - min(luminance) < 32:
        raise EvidenceError(f"Blank/near-uniform frame: {path.name}")
    return {"sample_colors": unique, "luminance_stddev": round(deviation, 2)}


def check_audio(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_streams",
         "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=30)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise EvidenceError(f"No recorded client audio: {path.name}")
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "8000",
         "-f", "f32le", "-"], check=True, capture_output=True, timeout=30)
    samples = array("f")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    rms = math.sqrt(sum(v * v for v in samples) / max(1, len(samples)))
    if not math.isfinite(rms) or rms < 0.001:
        raise EvidenceError(f"Silent or invalid client audio: {path.name} (RMS={rms})")
    return {"codec": streams[0]["codec_name"], "rms": round(rms, 6),
            "peak": round(max(abs(v) for v in samples), 6),
            "source": "live Forge client output via isolated PulseAudio monitor; no overdub"}


def audio_rms(path: Path, start: float, seconds: float) -> float:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(seconds), "-i", str(path),
         "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
        check=True, capture_output=True, timeout=30)
    samples = array("f")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return math.sqrt(sum(v * v for v in samples) / max(1, len(samples))) if samples else 0.0


def match_music(recording: Path, original: Path) -> dict:
    def envelope(path):
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-t", "8", "-vn", "-ac", "1",
             "-ar", "4000", "-f", "f32le", "-"], check=True, capture_output=True, timeout=30)
        samples = array("f")
        samples.frombytes(decoded.stdout)
        if sys.byteorder != "little":
            samples.byteswap()
        return [math.sqrt(sum(v * v for v in samples[i:i + 160]) / 160)
                for i in range(0, len(samples) - 159, 160)]

    # A normalized four-second amplitude fingerprint tolerates device latency
    # and gain changes, while rejecting silence and unrelated background audio.
    reference, captured = envelope(original)[:100], envelope(recording)
    if len(reference) != 100 or len(captured) < 100:
        raise EvidenceError("Music identity check needs at least four recorded seconds")
    centered = [v - statistics.mean(reference) for v in reference]
    norm = sum(v * v for v in centered)
    best, delay = -1.0, 0
    for offset in range(len(captured) - len(reference) + 1):
        window = captured[offset:offset + len(reference)]
        mean = statistics.mean(window)
        current = [v - mean for v in window]
        denominator = math.sqrt(norm * sum(v * v for v in current))
        correlation = sum(a * b for a, b in zip(centered, current)) / denominator if denominator else 0
        if correlation > best:
            best, delay = correlation, offset
    if not math.isfinite(best) or best < 0.8:
        raise EvidenceError(f"Recorded audio does not match the original cue: correlation={best:.3f}")
    return {"envelope_correlation": round(best, 4), "matched_window_offset_seconds": round(delay * 0.04, 2),
            "matched_seconds": 4, "reference_sha256": file_record(original)["sha256"]}


class Capture:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.project = args.project.resolve()
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.processes: list[tuple[str, subprocess.Popen]] = []
        self.handles = []
        self.work: Path | None = None
        self.server: subprocess.Popen | None = None
        self.client: subprocess.Popen | None = None
        self.audio: subprocess.Popen | None = None
        self.audio_temp = None
        self.nonce = uuid.uuid4().hex[:12]
        self.sequence = 0
        self.report = {
            "kind": "controlled-real-client-scene", "passed": False,
            "source_revision": os.environ.get("GITHUB_SHA", "unknown"),
            "minecraft": MC_VERSION, "forge": FORGE_VERSION, "geckolib": GECKO_VERSION,
            "client_mode": "Official Forge client profile; release JAR and original GeckoLib in mods/",
            "server_mode": "Official Forge installer; release JAR and original GeckoLib in mods/",
            "installed_jar_server_verified": False, "installed_jar_client_verified": False,
            "manual_playtest": False, "full_gameplay_acceptance": False,
            "visual_quality_review_required": True, "player_joined": False,
            "client_input_roundtrip_verified": False,
            "staging": "Creative camera; daylight flat arena; NoAI model portraits, then normal mob AI. "
                       "The three creatures attack separate stationary high-health golems in one group scene; "
                       "targets receive no scripted damage and retaliation is seeded on each attacker. "
                       "Licker wall-climb is a separate mossy-cobblestone obstacle with a blocked target. "
                       "Sneak-vs-sprint runs the same camera in survival mode; the ceiling ambush stages "
                       "a hovering licker beneath a lit stone roof.",
            "dev_client_launch": ("Official Forge 1.20.1-47.2.0 client profile via minecraft-launcher-lib "
                                  "(not Gradle runClient). Same installed release JAR as the dedicated server."),
            "dev_env_launch": ("Separate same-workflow artifact: gradlew runServer + "
                               "gradlew runClient -PdevEvidence enters the dev world."),
            "screenshots": [], "clips": [], "confirmations": [],
        }

    def start(self, name: str, command: list[str], cwd: Path, stdin=False) -> subprocess.Popen:
        log = (self.output / f"{name}.log").open("w", encoding="utf-8")
        self.handles.append(log)
        proc = subprocess.Popen(command, cwd=cwd, env=self.env, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
        self.processes.append((name, proc))
        return proc

    def alive(self) -> None:
        for name, process in (("server", self.server), ("client", self.client), ("audio", self.audio)):
            if process is not None and process.poll() is not None:
                raise EvidenceError(f"{name} exited unexpectedly ({process.returncode}); inspect {name}.log")

    def wait(self, predicate, description: str, timeout: float) -> object:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.alive()
            result = predicate()
            if result:
                return result
            time.sleep(0.3)
        raise EvidenceError(f"Timed out waiting for {description}")

    def run_logged(self, name: str, command: list[str], cwd: Path, timeout: float) -> None:
        proc = self.start(name, command, cwd)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise EvidenceError(f"{name} exceeded {timeout}s") from exc
        if code != 0:
            raise EvidenceError(f"{name} failed ({code}); inspect {name}.log")

    def command(self, command: str) -> None:
        self.alive()
        assert self.server is not None and self.server.stdin is not None
        with (self.output / "server-commands.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{time.monotonic():.3f} {command}\n")
        self.server.stdin.write(command + "\n")
        self.server.stdin.flush()

    def confirm(self, condition: str, label: str, timeout: float = 30) -> None:
        self.sequence += 1
        marker = f"CE_{self.nonce}_{self.sequence}"
        # `execute as <entity> ... run say` echoes with the entity's display
        # name as sender (e.g. "[Licker]"), not "[Server]", so match only the
        # unique marker token; nothing else can produce it.
        pattern = re.compile(re.escape(marker) + r"\b")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.command(f"execute {condition} run say {marker}")
            time.sleep(0.7)
            if pattern.search(tail(self.output / "server.log")):
                self.report["confirmations"].append({"check": label, "server_marker": marker})
                return
        raise EvidenceError(f"Server condition not satisfied: {label}")

    def gradle(self, task: str) -> list[str]:
        assert self.work is not None
        return ["bash", str(self.project / "gradlew"), "--no-daemon", "--console=plain", "--stacktrace",
                "--max-workers=2", "-Dorg.gradle.jvmargs=-Xmx3G", task]

    def prepare(self) -> None:
        if not self.args.accept_minecraft_eula:
            raise EvidenceError("Explicit --accept-minecraft-eula is required for this temporary test server")
        if not (self.project / "gradlew").is_file():
            raise EvidenceError("--project must be the checked-out Forge project")
        config = configparser.ConfigParser(interpolation=None)
        config.read_string("[project]\n" + (self.project / "gradle.properties").read_text())
        for key, value in (("minecraft_version", MC_VERSION), ("forge_version", FORGE_VERSION),
                           ("geckolib_version", GECKO_VERSION), ("mod_id", "re_demo")):
            if config["project"].get(key) != value:
                raise EvidenceError(f"This fixture requires {key}={value}")
        for tool in ("java", "ffmpeg", "ffprobe", "xdotool", "openbox", "glxinfo", "pulseaudio", "pactl"):
            if shutil.which(tool) is None:
                raise EvidenceError(f"Required executable not found: {tool}")
        if not os.environ.get("DISPLAY"):
            raise EvidenceError("Run under a dedicated Xvfb display; DISPLAY is missing")
        geometry = subprocess.check_output(["xdotool", "getdisplaygeometry"], text=True, timeout=10).strip()
        if geometry != "1280 720":
            raise EvidenceError(f"Dedicated display must be 1280x720, got {geometry}")
        with socket.socket() as port_check:
            port_check.bind(("127.0.0.1", self.args.port))
        build = self.project / "build"
        build.mkdir(exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="client-evidence-work-", dir=build))
        self.server_dir, self.client_dir = self.work / "server", self.work / "client"
        self.server_dir.mkdir()
        self.client_dir.mkdir()
        self.env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe")
        (self.client_dir / "options.txt").write_text(
            "fullscreen:true\nrenderDistance:8\nsimulationDistance:5\nmaxFps:30\n"
            "graphicsMode:0\nclouds:false\nparticles:1\nentityShadows:true\n"
            "guiScale:2\nfov:0.0\ngamma:1.0\nviewBobbing:false\npauseOnLostFocus:false\n"
            "tutorialStep:none\nonboardAccessibility:false\nskipMultiplayerWarning:true\n"
            "chatVisibility:2\nshowSubtitles:false\nlang:en_us\n"
            "soundCategory_master:1.0\nsoundCategory_music:1.0\n", encoding="utf-8")
        self.prepare_audio()
        self.run_logged("graphics", ["glxinfo", "-B"], self.work, 30)
        self.start("window-manager", ["openbox", "--sm-disable"], self.work)
        self.run_logged("build", self.gradle("build"),
                        self.project, self.args.build_timeout)
        self.install_server()
        self.install_client()

    def prepare_audio(self) -> None:
        # A short private /tmp path avoids AF_UNIX's 108-byte socket limit.
        # No default sound server or shared desktop audio settings are changed.
        self.audio_temp = tempfile.TemporaryDirectory(prefix="ce-audio-")
        runtime = Path(self.audio_temp.name)
        endpoint = runtime / "native"
        self.env.update(PULSE_SERVER=f"unix:{endpoint}", PULSE_RUNTIME_PATH=str(runtime),
                        PULSE_SINK="re_demo_capture", ALSOFT_DRIVERS="pulse")
        config = runtime / "capture.pa"
        config.write_text(
            f"load-module module-native-protocol-unix socket={endpoint} auth-anonymous=1\n"
            "load-module module-null-sink sink_name=re_demo_capture rate=44100 channels=2\n"
            "set-default-sink re_demo_capture\n"
            "set-default-source re_demo_capture.monitor\n", encoding="utf-8")
        self.audio = self.start("pulseaudio", [
            "pulseaudio", "--daemonize=no", "--exit-idle-time=-1", "--use-pid-file=no",
            "--disable-shm=yes", "--log-target=stderr", "-n", "-F", str(config)], runtime)
        self.wait(lambda: endpoint.exists(), "private audio socket", 20)
        self.run_logged("audio-device", ["pactl", "info"], runtime, 15)
        self.report["audio_capture"] = "private local Unix socket and null-sink monitor; no TCP listener"

    def record_video(self, path: Path, seconds: int) -> subprocess.Popen:
        return self.start(f"ffmpeg-{path.stem}", [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
            "-thread_queue_size", "1024", "-f", "x11grab", "-framerate", "20",
            "-video_size", "1280x720", "-i", self.env["DISPLAY"],
            "-thread_queue_size", "1024", "-f", "pulse", "-i", "re_demo_capture.monitor",
            "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(path)], self.work)

    def play_music(self) -> None:
        self.command(f"stopsound {CAMERA} music")
        self.command(f"execute at {CAMERA} store success score ce_music ce_health run "
                     f"playsound {MUSIC_EVENT} music {CAMERA} ~ ~ ~ 0.65 1")
        self.confirm("if score ce_music ce_health matches 1", "registered music event sent to installed client")

    def verify_music_playback(self) -> None:
        # No creatures remain after isolated_action_scenes. Record a separate
        # quiet sound check before the brawl so combat sounds cannot mask silence.
        self.command(f"stopsound {CAMERA}")
        time.sleep(1)
        path = self.output / "original-music-client.wav"
        recorder = self.start("ffmpeg-music-check", [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
            "-f", "pulse", "-i", "re_demo_capture.monitor", "-t", "8",
            "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2", str(path)], self.work)
        time.sleep(1)
        self.play_music()
        if recorder.wait(timeout=25) != 0:
            raise EvidenceError("Client music sound check failed")
        original = self.project / "src/main/resources/assets/re_demo/sounds/music/containment_pulse.ogg"
        self.report["original_music"] = dict(file_record(path), event=MUSIC_EVENT, audio=check_audio(path),
                                               identity=match_music(path, original))
        self.command(f"stopsound {CAMERA} music {MUSIC_EVENT}")

    def install_server(self) -> None:
        assert self.work is not None
        installer = self.work / "forge-installer.jar"
        sidecar = self.work / "forge-installer.jar.sha1"
        download(FORGE_URL, installer)
        download(FORGE_URL + ".sha1", sidecar)
        expected = sidecar.read_text().strip().split()[0].lower()
        with installer.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha1").hexdigest()
        if not re.fullmatch(r"[0-9a-f]{40}", expected) or actual != expected:
            raise EvidenceError("Official Forge installer SHA-1 sidecar mismatch")
        self.report["forge_installer"] = dict(file_record(installer), url=FORGE_URL, official_sha1=actual)
        self.run_logged("forge-install", ["java", "-jar", str(installer), "--installServer"],
                        self.server_dir, self.args.build_timeout)
        if not (self.server_dir / "run.sh").is_file():
            raise EvidenceError("Official Forge installation did not generate run.sh")
        jar = self.args.jar if self.args.jar.is_absolute() else self.project / self.args.jar
        if not jar.is_file():
            raise EvidenceError(f"Built release JAR missing: {jar.name}")
        with zipfile.ZipFile(jar) as archive:
            if "META-INF/mods.toml" not in archive.namelist():
                raise EvidenceError("Release JAR lacks Forge mods.toml")
            check_external_geckolib(archive)
        mods = self.server_dir / "mods"
        mods.mkdir(exist_ok=True)
        shutil.copy2(jar, mods / jar.name)
        tested = self.output / "tested-mod"
        tested.mkdir()
        shutil.copy2(jar, tested / jar.name)
        self.report["installed_mod"] = file_record(mods / jar.name)
        home = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
        cached = list(home.glob(f"caches/modules-2/files-2.1/software.bernie.geckolib/"
                                f"geckolib-forge-{MC_VERSION}/{GECKO_VERSION}/*/{GECKO_NAME}"))
        gecko = mods / GECKO_NAME
        if cached:
            shutil.copy2(cached[0], gecko)
        else:
            download(GECKO_URL, gecko)
        with zipfile.ZipFile(gecko) as archive:
            if "geckolib" not in archive.read("META-INF/mods.toml").decode("utf-8"):
                raise EvidenceError("Unexpected GeckoLib artifact")
        self.report["installed_geckolib"] = dict(file_record(gecko), upstream=GECKO_URL,
                                                source="original Gradle cache" if cached else "upstream Maven")
        (self.server_dir / "user_jvm_args.txt").write_text("-Xms512m\n-Xmx2G\n-Dre_demo.animationTrace=true\n", encoding="utf-8")
        (self.server_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        (self.server_dir / "server.properties").write_text(
            f"server-ip=127.0.0.1\nserver-port={self.args.port}\nonline-mode=false\n"
            "enforce-secure-profile=false\nenable-rcon=false\nenable-query=false\n"
            "gamemode=creative\nforce-gamemode=true\ndifficulty=normal\nmax-players=1\n"
            "level-name=controlled-evidence\nlevel-seed=612401\nlevel-type=minecraft:flat\n"
            'generator-settings={"biome":"minecraft:plains","layers":[{"block":"minecraft:bedrock","height":1},{"block":"minecraft:dirt","height":2},{"block":"minecraft:grass_block","height":1}]}\n'
            "generate-structures=false\nspawn-protection=0\nspawn-animals=false\nspawn-monsters=false\n"
            "spawn-npcs=false\nview-distance=8\nsimulation-distance=5\nallow-flight=true\n"
            "enable-command-block=false\nmotd=Controlled real-client evidence\n", encoding="utf-8")

    def install_client(self) -> None:
        from importlib.metadata import version
        from minecraft_launcher_lib import command, mod_loader, utils

        self.report["launcher_library"] = {"name": "minecraft-launcher-lib", "version": version("minecraft-launcher-lib")}
        self.run_logged("client-install", [sys.executable, "-c", INSTALL_CLIENT, str(self.client_dir),
                                           MC_VERSION, FORGE_VERSION], self.client_dir, self.args.build_timeout)
        profile = mod_loader.get_mod_loader("forge").get_installed_version(MC_VERSION, FORGE_VERSION)
        profile_json = self.client_dir / "versions" / profile / f"{profile}.json"
        if not profile_json.is_file() or json.loads(profile_json.read_text()).get("id") != profile:
            raise EvidenceError("Official Forge client profile was not installed")
        client_mods = self.client_dir / "mods"
        client_mods.mkdir(exist_ok=True)
        for source in (self.server_dir / "mods").glob("*.jar"):
            shutil.copy2(source, client_mods / source.name)
        installed = client_mods / self.report["installed_mod"]["name"]
        if file_record(installed) != self.report["installed_mod"]:
            raise EvidenceError("Client/server mod JAR bytes differ")
        self.report["client_profile"] = profile
        self.report["client_installed_mod"] = file_record(installed)
        # The library's documented development-test identity is used only for
        # this temporary loopback server. No account credentials are requested.
        options = utils.generate_test_options()
        options.update({"username": CAMERA, "gameDirectory": str(self.client_dir),
                        "executablePath": shutil.which("java"),
                        "jvmArguments": ["-Xms512m", "-Xmx3G", "-Dre_demo.animationTrace=true"],
                        "customResolution": True, "resolutionWidth": "1280", "resolutionHeight": "720",
                        "quickPlayMultiplayer": f"127.0.0.1:{self.args.port}"})
        self.client_command = command.get_minecraft_command(profile, self.client_dir, options) + ["--fullscreen"]
        if "--quickPlayMultiplayer" not in self.client_command:
            raise EvidenceError("Launcher did not enable the requested local multiplayer connection")

    def launch(self) -> None:
        self.server = self.start("server", ["bash", "run.sh", "nogui"], self.server_dir, stdin=True)
        self.wait(lambda: re.search(r'Done \([0-9.,]+s\)! For help', tail(self.output / "server.log")),
                  "installed-JAR Forge server ready", self.args.startup_timeout)
        self.client = self.start("client", self.client_command, self.client_dir)
        self.wait(lambda: re.search(r"\b" + CAMERA + r"\b.*logged in with entity id", tail(self.output / "server.log")),
                  "real client player login", self.args.startup_timeout)
        self.confirm(f"if entity @a[name={CAMERA},gamemode=creative]", "real creative camera joined")
        self.report["player_joined"] = True
        def window():
            result = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^Minecraft.*"],
                                    text=True, capture_output=True, timeout=10)
            return result.stdout.splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else None
        self.window = str(self.wait(window, "visible Minecraft client window", 60))
        subprocess.run(["xdotool", "windowactivate", "--sync", self.window], check=True, timeout=10)
        self.setup_scene()

    def setup_scene(self) -> None:
        for command in ("gamerule doMobSpawning false", "gamerule doDaylightCycle false",
                        "gamerule doWeatherCycle false", "gamerule mobGriefing false",
                        "gamerule sendCommandFeedback false", "time set noon", "weather clear",
                        "forceload add -16 -32 31 15", "scoreboard objectives add ce_health dummy"):
            self.command(command)
        loaded = " ".join(f"if loaded {x} 63 {z}" for x in (-16, 0, 16) for z in (-32, -16, 0))
        self.confirm(loaded, "all arena chunks loaded", 90)
        self.command("fill -12 63 -20 28 63 12 minecraft:polished_andesite")
        self.command("fill -8 64 8 24 71 8 minecraft:white_concrete")
        self.confirm("if block 0 63 4 minecraft:polished_andesite if block 16 66 8 minecraft:white_concrete",
                     "controlled arena built")
        # Keep the review camera well lit even while generated-chunk skylight settles.
        self.command(f"effect give {CAMERA} minecraft:night_vision 999999 0 true")
        self.report["capture_lighting"] = "Daylight plus camera-only night vision; capture does not edit textures or models"
        for entity, label, x, _ in MOBS:
            name = json.dumps({"text": label}, separators=(",", ":"))
            self.command(f"summon re_demo:{entity} {x} 64 4 "
                         f"{{Tags:[\"ce_{entity}\"],PersistenceRequired:1b,NoAI:1b,Rotation:[180.0f,0.0f],"
                         f"CustomName:'{name}',CustomNameVisible:1b}}")
            self.confirm(f"if entity @e[type=re_demo:{entity},tag=ce_{entity},limit=1]",
                         f"release JAR entity summoned: {entity}")
        self.report["installed_jar_server_verified"] = True

    def camera(self, x: float, z: float, focus_x: float, focus_y: float, focus_z: float, label: str,
               cam_y: float = 64.0) -> None:
        dx, dz = focus_x - x, focus_z - z
        yaw = -math.degrees(math.atan2(dx, dz))
        pitch = -math.degrees(math.atan2(focus_y - (cam_y + 1.62), math.hypot(dx, dz)))
        self.command(f"tp {CAMERA} {x:.3f} {cam_y:.3f} {z:.3f} {yaw:.3f} {pitch:.3f}")
        self.confirm(f"positioned {x:.3f} {cam_y:.3f} {z:.3f} if entity @a[name={CAMERA},distance=..0.3]",
                     f"camera positioned: {label}")
        self.command(f"title {CAMERA} actionbar " + json.dumps({"text": f"{label} | controlled real-client scene"}))
        time.sleep(3)

    def screenshot(self, name: str) -> None:
        screenshots = self.client_dir / "screenshots"
        previous = set(screenshots.glob("*.png"))
        subprocess.run(["xdotool", "windowactivate", "--sync", self.window], check=True, timeout=10)
        subprocess.run(["xdotool", "key", "--clearmodifiers", "F2"], check=True, timeout=10)
        source = self.wait(lambda: next(iter(set(screenshots.glob("*.png")) - previous), None),
                           f"native Minecraft F2 screenshot: {name}", 30)
        time.sleep(1)
        target = self.output / name
        shutil.copy2(source, target)
        metrics = check_frame(target)
        pixels = frame_pixels(target)
        center = [sum(pixels[(y * 64 + x) * 3:(y * 64 + x) * 3 + 3]) / 3
                  for y in range(10, 21) for x in range(16, 48)]
        metrics["center_mean_luminance"] = round(statistics.mean(center), 2)
        if metrics["center_mean_luminance"] < 40:
            raise EvidenceError(f"Model review area is too dark: {name}")
        self.report["screenshots"].append(dict(file_record(target), origin="native Minecraft F2", pixels=metrics))

    def key(self, name: str, down: bool) -> None:
        subprocess.run(["xdotool", "keydown" if down else "keyup", "--clearmodifiers", name],
                       check=True, timeout=10)

    def sneak_scene(self) -> None:
        # One real client on one flat lane, twice: silent sneak-walk, then a
        # loud sprint. Only the sprint may pull the Licker (NoiseEvents radius
        # 0 vs 20). The comparison runs back-to-back in a single clip.
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity}]")
        self.command("kill @e[type=minecraft:iron_golem]")
        self.command("kill @e[type=minecraft:arrow]")
        time.sleep(2)
        selector = '@e[type=re_demo:licker,tag=ce_sneak,limit=1]'
        self.command('summon re_demo:licker 6 64 4 '
                     '{Tags:["ce_sneak"],PersistenceRequired:1b,Rotation:[-90.0f,0.0f]}')
        self.confirm(f"if entity {selector}", "sneak control: live-AI licker staged")
        # Only a real survival-mode player emits footstep noise events.
        self.command(f"gamemode survival {CAMERA}")
        self.command(f"effect give {CAMERA} minecraft:resistance 999999 4 true")
        # 8.5 blocks out: close enough that an un-sneaked walk (radius-9
        # footstep noise) would pull the licker, so phase A only passes when
        # the shift key really kept the player silent.
        self.command(f"tp {CAMERA} 14.5 64 4 90 0")
        self.confirm(f"positioned 14.5 64 4 if entity @a[name={CAMERA},distance=..0.3]",
                     "sneak control: camera 8.5 blocks from the licker")
        sneaked = False
        path = self.output / "licker-sneak-vs-sprint.mp4"
        seconds = 18
        for attempt in range(2):
            recorder = self.record_video(path, seconds)
            time.sleep(1)
            self.command(f"title {CAMERA} actionbar " +
                         json.dumps({"text": "phase A: sneak-walk is silent | controlled real-client scene"}))
            subprocess.run(["xdotool", "windowactivate", "--sync", self.window], check=True, timeout=10)
            self.key("shift", True)
            for _ in range(2):
                self.key("w", True)
                time.sleep(0.5)
                self.key("w", False)
                time.sleep(1.4)
            self.key("shift", False)
            try:
                self.confirm(f"as {selector} at @s unless entity @a[name={CAMERA},distance=..6]",
                             "sneak: silent sneak-walk did not pull the licker", timeout=6)
                self.command(f"data get entity {selector} Pos")
                self.command(f"data get entity @a[name={CAMERA},limit=1] Pos")
                self.screenshot("licker-sneak-silent.png")
                sneaked = True
                break
            except EvidenceError:
                if recorder.poll() is None:
                    recorder.wait(timeout=seconds + 15)
                if attempt == 1:
                    raise
                # A random stroll may drift toward the camera; retake once.
                self.command(f"kill {selector}")
                self.command(f"tp {CAMERA} 14.5 64 4 90 0")
                self.command('summon re_demo:licker 6 64 4 '
                             '{Tags:["ce_sneak"],PersistenceRequired:1b,Rotation:[-90.0f,0.0f]}')
                time.sleep(2)
        if not sneaked:
            raise EvidenceError("sneak control: could not stage a quiet phase")
        self.command(f"title {CAMERA} actionbar " +
                     json.dumps({"text": "phase B: sprint is audible | controlled real-client scene"}))
        self.key("ctrl", True)
        self.key("w", True)
        time.sleep(1.6)
        self.key("w", False)
        self.key("ctrl", False)
        self.confirm(f"as {selector} at @s if entity @a[name={CAMERA},distance=..5]",
                     "sprint: footstep noise hunted and reached the camera", timeout=12)
        # SoundInvestigateGoal pathfinds to the noise without always calling
        # setTarget (hear() only locks a living source on a repeated ping).
        # The Review ask is sneak vs sprint aggro distance, not a claw frame.
        self.command(f"data get entity {selector} Pos")
        self.command(f"data get entity @a[name={CAMERA},limit=1] Pos")
        self.screenshot("licker-sprint-hunt.png")
        deadline = time.monotonic() + seconds + 20
        while recorder.poll() is None and time.monotonic() < deadline:
            self.alive()
            time.sleep(0.3)
        if recorder.poll() != 0:
            raise EvidenceError("Sneak-vs-sprint recording failed/timed out")
        info = probe(path)
        duration = float(info["format"]["duration"])
        if duration < seconds - 1:
            raise EvidenceError(f"Sneak control recording truncated: {duration}s")
        metrics = check_frame(path)
        first, later = frame_pixels(path, 0.5), frame_pixels(path, duration - 1)
        difference = sum(abs(a - b) for a, b in zip(first, later)) / len(first)
        if difference < 0.05:
            raise EvidenceError("Sneak control recording appears frozen")
        self.report["clips"].append(dict(
            file_record(path), duration_seconds=duration, pixels=metrics,
            sampled_motion=round(difference, 3), scenario="sneak-vs-sprint",
            sneak_phase="silent sneak-walk: licker stayed beyond 6 blocks",
            sprint_phase="radius-20 noise: licker closed to within 5 blocks of the camera",
            silent_min_distance_blocks=6, sprint_max_distance_blocks=5,
            silent_still="licker-sneak-silent.png", sprint_still="licker-sprint-hunt.png",
            claw_frames_logged=False, camera_gamemode="survival", camera_resistance=4,
            audio=check_audio(path)))
        self.command(f"kill {selector}")
        self.command(f"gamemode creative {CAMERA}")
        self.command(f"effect clear {CAMERA} minecraft:resistance")
        self.command(f"tp {CAMERA} 6 64 -3 180 0")
        time.sleep(2)

    def ambush_scene(self) -> None:
        # Low stone roof over the flat lane: hovering airborne beneath it with
        # a heard sound is exactly what engages the Licker's ceiling ambush.
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity}]")
        self.command("kill @e[type=minecraft:iron_golem]")
        self.command("kill @e[type=minecraft:arrow]")
        time.sleep(2)
        self.command("fill 12 68 -2 20 68 2 minecraft:stone")
        self.command("fill 12 68 -2 20 68 -2 minecraft:glowstone")
        self.command("fill 12 68 2 20 68 2 minecraft:glowstone")
        self.command("fill 12 68 -1 12 68 1 minecraft:glowstone")
        self.command("fill 20 68 -1 20 68 1 minecraft:glowstone")
        self.confirm("if block 16 68 0 minecraft:stone if block 16 68 -2 minecraft:glowstone "
                     "if block 16 68 2 minecraft:glowstone", "ambush: lit stone roof placed")
        selector = '@e[type=re_demo:licker,tag=ce_ambush,limit=1]'
        dummy = '@e[type=minecraft:iron_golem,tag=ce_ambush_dummy,limit=1]'
        self.command('summon re_demo:licker 16 66.9 0 '
                     '{Tags:["ce_ambush"],PersistenceRequired:1b,NoAI:1b,NoGravity:1b}')
        self.command('summon minecraft:iron_golem 24 64 0 '
                     '{Tags:["ce_ambush_dummy"],NoAI:1b,PersistenceRequired:1b,Health:1000.0f,'
                     'Attributes:[{Name:"minecraft:generic.max_health",Base:1000.0d},'
                     '{Name:"minecraft:generic.knockback_resistance",Base:1.0d}]}')
        self.confirm(f"if entity {selector} if entity {dummy}",
                     "ambush: hovering licker under the roof, distant target")
        self.camera(23, -8, 16, 67, 0, "Licker ceiling ambush", cam_y=64.0)
        path = self.output / "licker-ambush.mp4"
        seconds = 16
        recorder = self.record_video(path, seconds)
        time.sleep(1)
        before = len(tail(self.output / "server.log", 10_000_000))
        # A real projectile impact is a noise event the Licker must record.
        self.command('summon minecraft:arrow 16 69.6 0 {Motion:[0.0,-0.4,0.0],pickup:0b}')
        time.sleep(0.8)
        self.command(f"damage {selector} 1 minecraft:mob_attack by {dummy}")
        self.confirm(f"if entity @e[type=re_demo:licker,tag=ce_ambush,y=66.3,dy=0.9]",
                     "ambush: licker holding under the ceiling", timeout=8)
        time.sleep(0.9)
        self.screenshot("licker-ambush.png")
        self.command(f"data merge entity {selector} {{NoAI:0b,NoGravity:0b}}")
        # The release window opens once the dummy is pulled inside 7 blocks.
        self.command(f"tp {dummy} 18 64 0")
        self.wait(lambda: re.search(r"RE_DEMO_SYNC_SERVER [^\n]*asset=licker[^\n]*attack=4",
                                    tail(self.output / "server.log", 10_000_000)[before:]),
                  "ambush release attack frames", 12)
        self.command(f"execute store result score ambush_land ce_health run data get entity {selector} Pos[1] 100")
        self.confirm("if score ambush_land ce_health matches ..6600",
                     "ambush: licker dropped off the ceiling")
        self.command(f"execute store result score ambush_hp ce_health run data get entity {dummy} Health 100")
        self.confirm("if score ambush_hp ce_health matches ..98700",
                     "ambush: release strike landed at least 13 damage", timeout=10)
        deadline = time.monotonic() + seconds + 20
        while recorder.poll() is None and time.monotonic() < deadline:
            self.alive()
            time.sleep(0.3)
        if recorder.poll() != 0:
            raise EvidenceError("Ceiling ambush recording failed/timed out")
        info = probe(path)
        duration = float(info["format"]["duration"])
        if duration < seconds - 1:
            raise EvidenceError(f"Ceiling ambush recording truncated: {duration}s")
        metrics = check_frame(path)
        first, later = frame_pixels(path, 0.5), frame_pixels(path, duration - 1)
        difference = sum(abs(a - b) for a, b in zip(first, later)) / len(first)
        if difference < 0.05:
            raise EvidenceError("Ceiling ambush recording appears frozen")
        self.report["clips"].append(dict(
            file_record(path), duration_seconds=duration, pixels=metrics,
            sampled_motion=round(difference, 3), scenario="ceiling-ambush",
            roof="minecraft:stone+glowstone at y=68", release_attack_logged="attack=4",
            target_min_damage_hp=13, audio=check_audio(path)))
        self.command(f"kill {selector}")
        self.command(f"kill {dummy}")
        time.sleep(2)

    def identify_scene(self) -> None:
        # 20-block identification under plain daylight: the review camera's
        # night vision is removed and the stand-ins carry no name tags.
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity}]")
        self.command("kill @e[type=minecraft:iron_golem]")
        self.command("kill @e[type=minecraft:arrow]")
        time.sleep(2)
        self.command(f"effect clear {CAMERA} minecraft:night_vision")
        for entity, _, x, _ in MOBS:
            self.command(f"summon re_demo:{entity} {x} 64 8 "
                         f'{{Tags:["ce_id"],PersistenceRequired:1b,NoAI:1b,Rotation:[180.0f,0.0f]}}')
            self.confirm(f"if entity @e[type=re_demo:{entity},tag=ce_id,limit=1]",
                         f"identification: unnamed {entity} staged")
        self.camera(6, -12, 6, 64.8, 8, "three creatures, 20 blocks, daylight, no name tags")
        self.screenshot("20-block-identification.png")
        for entity, label, x, height in MOBS:
            self.camera(x, -12, x, 64 + height, 8, f"{label} at 20 blocks")
            self.screenshot(f"{entity}-20blocks.png")
        self.command(f"effect give {CAMERA} minecraft:night_vision 999999 0 true")
        self.command("kill @e[tag=ce_id]")
        time.sleep(2)

    def verify_in_world_input(self) -> None:
        # Login alone also occurs while Loading Terrain is visible. A real key
        # press must move the camera on the flat floor before any evidence passes.
        subprocess.run(["xdotool", "keydown", "--clearmodifiers", "w"], check=True, timeout=10)
        try:
            time.sleep(0.8)
        finally:
            subprocess.run(["xdotool", "keyup", "w"], check=True, timeout=10)
        self.confirm(f"positioned 6 64 -10 if entity @a[name={CAMERA}] "
                     f"unless entity @a[name={CAMERA},distance=..0.15]", "real client movement packet received")
        self.report["client_input_roundtrip_verified"] = True

    def combat_clip(self, entity: str, x: int, scenario: str = "attack", target_distance: float = 1.8) -> None:
        selector = f"@e[type=re_demo:{entity},tag=ce_{entity},limit=1]"
        dummy = f"@e[type=minecraft:iron_golem,tag=ce_dummy_{entity},limit=1]"
        before, after = f"before_{entity}", f"after_{entity}"
        self.command(f"summon minecraft:iron_golem {x + target_distance} 64 4 "
                     f"{{Tags:[\"ce_dummy_{entity}\"],NoAI:1b,PersistenceRequired:1b,Health:1000.0f,"
                     'Attributes:[{Name:"minecraft:generic.max_health",Base:1000.0d},'
                     '{Name:"minecraft:generic.knockback_resistance",Base:1.0d}]}')
        self.confirm(f"if entity {dummy}", f"{entity}: controlled target summoned")
        self.command(f"execute store result score {before} ce_health run data get entity {dummy} Health 100")
        self.confirm(f"if score {before} ce_health matches 100000", f"{entity}: stationary target at full health")
        path = self.output / f"{entity}-{scenario}.mp4"
        clip_seconds = max(14, self.args.clip_seconds) if entity == "g1_birkin" else self.args.clip_seconds
        recorder = self.record_video(path, clip_seconds)
        time.sleep(1)
        self.command(f"data merge entity {selector} {{NoAI:0b}}")
        self.command(f"damage {selector} 1 minecraft:mob_attack by {dummy}")
        deadline = time.monotonic() + clip_seconds + 40
        while recorder.poll() is None and time.monotonic() < deadline:
            self.alive()
            time.sleep(0.3)
        if recorder.poll() != 0:
            raise EvidenceError(f"Recording failed/timed out for {entity}")
        self.command(f"execute store result score {after} ce_health run data get entity {dummy} Health 100")
        self.confirm(f"if score {after} ce_health < {before} ce_health if score {after} ce_health matches 1..",
                     f"{entity}: real server attack dealt damage")
        self.command(f"data get entity {dummy} Health")
        self.command(f"data merge entity {selector} {{NoAI:1b}}")
        self.command(f"kill {dummy}")
        info = probe(path)
        duration = float(info["format"]["duration"])
        if duration < clip_seconds - 1:
            raise EvidenceError(f"Recording truncated for {entity}: {duration}s")
        metrics = check_frame(path)
        first, later = frame_pixels(path, 0.5), frame_pixels(path, min(4, duration - 1))
        difference = sum(abs(a - b) for a, b in zip(first, later)) / len(first)
        if difference < 0.05:
            raise EvidenceError(f"Recording appears frozen for {entity}")
        self.report["clips"].append(dict(file_record(path), duration_seconds=duration, pixels=metrics,
                                         sampled_motion=round(difference, 3), server_target_damaged=True,
                                         scenario=scenario, initial_target_distance=target_distance,
                                         audio=check_audio(path)))

    def brawl_scene(self, seconds: int = 55) -> None:
        # Put all three installed creatures in one real-client combat scene.
        # Each creature gets its own stationary high-health target so target
        # selection cannot make one participant's damage assertion flaky.
        lineup = (("tyrant", 2, 4), ("g1_birkin", 8, 4), ("licker", 14, 4))
        actors = {
            entity: f"@e[type=re_demo:{entity},tag=ce_group_{entity},limit=1]"
            for entity, _, _ in lineup
        }
        targets = {
            entity: f"@e[type=minecraft:iron_golem,tag=ce_group_dummy_{entity},limit=1]"
            for entity, _, _ in lineup
        }
        for entity, x, z in lineup:
            self.command(f"summon re_demo:{entity} {x} 64 {z} "
                         f'{{Tags:["ce_group_{entity}"],PersistenceRequired:1b,NoAI:1b}}')
            self.command(f"summon minecraft:iron_golem {x + 1.8} 64 {z} "
                         f'{{Tags:["ce_group_dummy_{entity}"],NoAI:1b,PersistenceRequired:1b,Health:1000.0f,'
                         'Attributes:[{Name:"minecraft:generic.max_health",Base:1000.0d},'
                         '{Name:"minecraft:generic.knockback_resistance",Base:1.0d}]}')
            self.confirm(f"if entity {actors[entity]}", f"group combat: {entity} staged")
            self.confirm(f"if entity {targets[entity]}", f"group combat: {entity} target staged")
            self.command(f"execute store result score target_threshold_{entity} ce_health "
                         f"run data get entity {targets[entity]} Health 100")
            self.confirm(f"if score target_threshold_{entity} ce_health matches 100000",
                         f"group combat: {entity} target at full health")
            # The target receives no scripted damage. Lowering only the stored
            # threshold means the later assertion requires over 5 HP of AI damage.
            self.command(f"scoreboard players remove target_threshold_{entity} ce_health 500")

        self.camera(8, -10, 8, 64.6, 4, "three-creature controlled combat")
        path = self.output / "creature-brawl.mp4"
        recorder = self.record_video(path, seconds)
        time.sleep(1)
        self.play_music()
        self.command(f"title {CAMERA} actionbar " +
                     json.dumps({"text": "three creatures attack controlled targets | real client"}))
        for entity, _, _ in lineup:
            self.command(f"data merge entity {actors[entity]} {{NoAI:0b}}")
            # Retaliation is seeded on the attacker, exactly as in the isolated
            # combat clips. The tracked target itself receives no scripted damage.
            self.command(f"damage {actors[entity]} 1 minecraft:mob_attack by {targets[entity]}")

        deadline = time.monotonic() + seconds + 40
        while recorder.poll() is None and time.monotonic() < deadline:
            self.alive()
            time.sleep(0.3)
        if recorder.poll() != 0:
            raise EvidenceError("Group combat recording failed/timed out")

        self.command("scoreboard players set group_attackers_verified ce_health 0")
        time.sleep(1)
        for entity, _, _ in lineup:
            self.command(f"data merge entity {actors[entity]} {{NoAI:1b}}")
            self.command(f"data get entity {actors[entity]} Pos")
            self.command(f"data get entity {targets[entity]} Pos")
            self.command(f"data get entity {targets[entity]} UUID")
            self.command(f"execute store result score after_group_{entity} ce_health "
                         f"run data get entity {targets[entity]} Health 100")
            self.confirm(f"if score after_group_{entity} ce_health < target_threshold_{entity} ce_health "
                         f"if score after_group_{entity} ce_health matches 1..",
                         f"group combat: {entity} dealt more than 5 HP of real AI damage")
            self.command("scoreboard players add group_attackers_verified ce_health 1")
            self.command(f"data get entity {targets[entity]} Health")
        self.confirm("if score group_attackers_verified ce_health matches 3",
                     "group combat: all three creatures independently dealt more than 5 HP")
        for entity, _, _ in lineup:
            self.command(f"kill @e[type=re_demo:{entity},tag=ce_group_{entity}]")
            self.command(f"kill @e[type=minecraft:iron_golem,tag=ce_group_dummy_{entity}]")

        info = probe(path)
        duration = float(info["format"]["duration"])
        if duration < seconds - 1:
            raise EvidenceError(f"Group combat recording truncated: {duration}s")
        metrics = check_frame(path)
        first, later = frame_pixels(path, 0.5), frame_pixels(path, duration - 1)
        difference = sum(abs(a - b) for a, b in zip(first, later)) / len(first)
        if difference < 0.05:
            raise EvidenceError("Group combat recording appears frozen")
        self.report["clips"].append(dict(
            file_record(path),
            duration_seconds=duration,
            pixels=metrics,
            sampled_motion=round(difference, 3),
            scenario="three-creature-combat",
            controlled_targets_damaged=True,
            all_three_attackers_verified=True,
            minimum_target_loss_hp=5,
            scripted_target_damage_hp=0,
            retaliation_seed_hp=1,
            target_type="minecraft:iron_golem",
            controlled_attack_lanes=[
                {"attacker": entity, "target": "minecraft:iron_golem"}
                for entity, _, _ in lineup
            ],
            audio=check_audio(path),
        ))

    def isolated_action_scenes(self) -> None:
        # Previously fought NoAI mobs still collide and can block the next actor.
        # Each normal-AI scene gets a fresh actor and a single stationary target.
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity},tag=ce_{entity}]")
        time.sleep(4)
        for entity, scenario, distance in (("tyrant", "attack", 1.8),
                                            ("g1_birkin", "attack", 1.8),
                                            ("licker", "attack", 1.8),
                                            ("tyrant", "charge", 7.0),
                                            ("licker", "tongue", 3.4),
                                            ("licker", "crawl", 12.0)):
            x = 4
            self.command(f"summon re_demo:{entity} {x} 64 4 "
                         f"{{Tags:[\"ce_{entity}\"],PersistenceRequired:1b,NoAI:1b,Rotation:[-90.0f,0.0f]}}")
            self.confirm(f"if entity @e[type=re_demo:{entity},tag=ce_{entity},limit=1]",
                         f"fresh normal-AI {scenario} scene")
            center = x + distance * 0.5
            self.camera(center + 1, -3 if scenario in ("tongue", "attack") else -6 if scenario == "charge" else -9,
                        center, 64.6 if entity == "licker" else 65.1, 4,
                        f"{entity}: {scenario}")
            self.combat_clip(entity, x, scenario, distance)
            self.command(f"kill @e[type=re_demo:{entity},tag=ce_{entity}]")
            time.sleep(4)

    def climb_scene(self) -> None:
        # Wide 2-thick wall with the dummy ON TOP so the only short hunt path is
        # vertical. Side funnels previously let the Licker skirt the slab at Y=64
        # after a 1.2-block hop, which looked like floor pursuit.
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity}]")
        self.command("kill @e[type=minecraft:iron_golem]")
        time.sleep(2)
        self.command("fill 8 64 -11 28 69 -10 minecraft:mossy_cobblestone")
        self.command("fill 24 64 -13 24 69 -13 minecraft:orange_wool")
        self.confirm("if block 18 64 -10 minecraft:mossy_cobblestone "
                     "if block 18 69 -11 minecraft:mossy_cobblestone "
                     "if block 24 67 -13 minecraft:orange_wool",
                     "licker climb: 6-block mossy wall and height ruler placed")
        selector = '@e[type=re_demo:licker,tag=ce_climb,limit=1]'
        dummy = '@e[type=minecraft:iron_golem,tag=ce_climb_dummy,limit=1]'
        self.command('summon re_demo:licker 18 64 -15 '
                     '{Tags:["ce_climb"],PersistenceRequired:1b,NoAI:1b,Rotation:[0.0f,0.0f]}')
        self.command('summon minecraft:iron_golem 18 70 -10.5 '
                     '{Tags:["ce_climb_dummy"],NoAI:1b,PersistenceRequired:1b,Health:1000.0f,'
                     'Attributes:[{Name:"minecraft:generic.max_health",Base:1000.0d},'
                     '{Name:"minecraft:generic.knockback_resistance",Base:1.0d}]}')
        self.confirm(f"if entity {selector} if entity {dummy} if block 18 70 -10 minecraft:air",
                     "licker climb: actor on floor and dummy on wall top")
        self.command(f"execute store result score climb_before ce_health run data get entity {selector} Pos[1] 100")
        self.command("scoreboard players operation climb_need ce_health = climb_before ce_health")
        self.command("scoreboard players add climb_need ce_health 250")
        self.command("scoreboard players operation climb_peak ce_health = climb_before ce_health")
        self.confirm("if score climb_before ce_health matches 6300..6500",
                     "licker climb: actor started on the arena floor")
        self.camera(27, -19, 18, 67.4, -10.5, "Licker wall climb", cam_y=64.0)
        path = self.output / "licker-climb.mp4"
        clip_seconds = 22
        recorder = self.record_video(path, clip_seconds)
        time.sleep(1)
        self.command(f"data merge entity {selector} {{NoAI:0b}}")
        self.command(f"damage {selector} 1 minecraft:mob_attack by {dummy}")
        climbed = False
        deadline = time.monotonic() + clip_seconds + 8
        while recorder.poll() is None and time.monotonic() < deadline:
            self.alive()
            self.command(f"execute store result score climb_now ce_health run data get entity {selector} Pos[1] 100")
            self.command("execute if score climb_now ce_health > climb_peak ce_health "
                         "run scoreboard players operation climb_peak ce_health = climb_now ce_health")
            self.command('tellraw @a [{"text":"CE_CLIMB_YVAL "},{"score":{"name":"climb_now","objective":"ce_health"}}]')
            self.command("execute if score climb_now ce_health >= climb_need ce_health run say CE_CLIMB_MID")
            if not climbed and re.search(r"\[Server\]\s+CE_CLIMB_MID\b", tail(self.output / "server.log")):
                climbed = True
                self.screenshot("licker-climb.png")
            time.sleep(0.4)
        if recorder.poll() != 0:
            raise EvidenceError("Licker climb recording failed/timed out")
        self.command(f"data get entity {selector} Pos")
        self.command(f"data get entity {dummy} Pos")
        self.confirm("if score climb_peak ce_health >= climb_need ce_health",
                     "licker climb: server Y gained at least 2.5 blocks on the wall", timeout=8)
        if not climbed:
            raise EvidenceError("Licker never reached +2.5 Y on the mossy wall while the camera was recording")
        info = probe(path)
        duration = float(info["format"]["duration"])
        if duration < clip_seconds - 1:
            raise EvidenceError(f"Climb recording truncated: {duration}s")
        metrics = check_frame(path)
        first, later = frame_pixels(path, 0.5), frame_pixels(path, min(10, duration - 1))
        difference = sum(abs(a - b) for a, b in zip(first, later)) / len(first)
        if difference < 0.05:
            raise EvidenceError("Climb recording appears frozen")
        self.report["clips"].append(dict(
            file_record(path), duration_seconds=duration, pixels=metrics,
            sampled_motion=round(difference, 3), scenario="wall-climb",
            obstacle="minecraft:mossy_cobblestone", wall_height_blocks=6,
            wall_thickness_blocks=2, dummy_on_wall_top=True,
            required_y_gain_blocks=2.5, server_y_gain_confirmed=True,
            target_blocked_los=True, audio=check_audio(path),
        ))
        self.command(f"kill {selector}")
        self.command(f"kill {dummy}")
        time.sleep(2)

    def death_cleanup_scene(self) -> None:
        # Creature audio must not linger after death/removal: one-shot hurt and
        # death cues inside the kill window are expected, silence must follow.
        path = self.output / "death-cleanup-audio.wav"
        recorder = self.start("ffmpeg-death-audio", [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin", "-y",
            "-f", "pulse", "-i", "re_demo_capture.monitor", "-t", "12",
            "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2", str(path)], self.work)
        time.sleep(1)
        for entity, _, x, _ in MOBS:
            self.command(f"summon re_demo:{entity} {x} 64 4 "
                         f'{{Tags:["ce_dead_{entity}"],PersistenceRequired:1b,NoAI:1b}}')
        self.confirm("if entity @e[type=re_demo:licker] if entity @e[type=re_demo:tyrant] "
                     "if entity @e[type=re_demo:g1_birkin]",
                     "death cleanup: three live fixtures")
        for entity, _, _, _ in MOBS:
            self.command(f"damage @e[type=re_demo:{entity},tag=ce_dead_{entity}] 6 minecraft:mob_attack")
            time.sleep(0.4)
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity}]")
            time.sleep(0.4)
        if recorder.wait(timeout=20) != 0:
            raise EvidenceError("Death cleanup audio capture failed")
        audio = check_audio(path)
        tail_rms = audio_rms(path, 7.0, 5.0)
        if tail_rms >= 0.001:
            raise EvidenceError(f"Residual creature audio after death/removal (tail RMS={tail_rms})")
        self.confirm("unless entity @e[type=re_demo:licker] unless entity @e[type=re_demo:tyrant] "
                     "unless entity @e[type=re_demo:g1_birkin]",
                     "death cleanup: no remaining demo creatures", timeout=20)
        self.camera(6, -10, 6, 65.3, 4, "Cleared after death")
        self.screenshot("99-death-cleared.png")
        self.report["death_audio_cleanup"] = dict(
            file_record(path), seconds=12, kill_window_seconds=6,
            whole_clip=audio, tail_rms_7_to_12s=tail_rms,
            scope="Client output returns to silence after creature deaths; one-shot hurt/death cues "
                  "are allowed inside the kill window. Does not claim the mod stops externally-played music.")

    def mid_attack_reveal_scenes(self) -> None:
        # New actors are spawned behind the camera and revealed only after the
        # real server AI has advanced an attack. No combat state is injected.
        for entity, _, _, _ in MOBS:
            self.command(f"kill @e[type=re_demo:{entity}]")
        self.command("kill @e[type=minecraft:iron_golem]")
        time.sleep(4)
        for entity, _, _, _ in MOBS:
            succeeded = False
            for attempt in range(4):
                self.command(f"tp {CAMERA} 6 64 -3 180 0")
                time.sleep(0.6)
                tag = f"ce_sync_{entity}_{attempt}"
                actor = f"@e[type=re_demo:{entity},tag={tag},limit=1]"
                target = f"@e[type=minecraft:iron_golem,tag={tag},limit=1]"
                self.command(f"summon re_demo:{entity} 4 64 4 {{Tags:[\"{tag}\"],NoAI:1b,PersistenceRequired:1b}}")
                self.command(f"summon minecraft:iron_golem 5.8 64 4 "
                             f"{{Tags:[\"{tag}\"],NoAI:1b,Health:1000.0f,"
                             'Attributes:[{Name:"minecraft:generic.max_health",Base:1000.0d},'
                             '{Name:"minecraft:generic.knockback_resistance",Base:1.0d}]}')
                self.confirm(f"if entity {actor} if entity {target}", f"{entity}: hidden live-AI fixture")
                before = len(tail(self.output / "server.log", 10_000_000))
                self.command(f"data merge entity {actor} {{NoAI:0b}}")
                self.command(f"damage {actor} 1 minecraft:mob_attack by {target}")
                frame = self.wait(lambda: next((r for r in sync_rows(
                    tail(self.output / "server.log", 10_000_000)[before:], "SERVER")
                    if r["asset"] == entity and int(r["tick"]) >= 4), None), "attack already in progress", 20)
                self.command(f"tp {CAMERA} 6 64 -3 0 0")
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    self.alive()
                    rows = sync_rows(tail(self.output / "client.log", 10_000_000), "CLIENT")
                    succeeded = any(r["uuid"] == frame["uuid"] and r["seq"] == frame["seq"]
                                    and r["first"] == "true" and int(r["tick"]) >= 4 for r in rows)
                    if succeeded:
                        break
                    time.sleep(0.1)
                if succeeded:
                    # Hide an already-rendered attack, then require the same sequence
                    # to resume after a real gap in GeckoLib's render processing.
                    self.command(f"tp {CAMERA} 6 64 -3 180 0")
                    time.sleep(0.35)
                    self.command(f"tp {CAMERA} 6 64 -3 0 0")
                    succeeded = False
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        self.alive()
                        rows = sync_rows(tail(self.output / "client.log", 10_000_000), "CLIENT")
                        succeeded = any(r["uuid"] == frame["uuid"] and r["seq"] == frame["seq"]
                                        and r["resumed"] == "true" and r["first"] == "false"
                                        and int(r["tick"]) >= int(frame["tick"]) + 4 for r in rows)
                        if succeeded:
                            break
                        time.sleep(0.1)
                self.command(f"kill {actor}")
                self.command(f"kill {target}")
                time.sleep(4)
                if succeeded:
                    break
            if not succeeded:
                raise EvidenceError(f"{entity}: missing late first frame or same-attack visibility re-entry")
        result = validate_animation_sync(tail(self.output / "client.log", 10_000_000),
                                         tail(self.output / "server.log", 10_000_000))
        proof = self.output / "animation-sync.json"
        proof.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        self.report["animation_sync"] = dict(file_record(proof), **result)

    def capture(self) -> None:
        self.camera(6, -10, 6, 65.3, 4, "Three creatures")
        self.verify_in_world_input()
        self.camera(6, -10, 6, 65.3, 4, "Three creatures")
        self.screenshot("00-three-creatures.png")
        self.command(f"item replace entity {CAMERA} hotbar.0 with re_demo:licker_spawn_egg")
        self.command(f"item replace entity {CAMERA} hotbar.1 with re_demo:tyrant_spawn_egg")
        self.command(f"item replace entity {CAMERA} hotbar.2 with re_demo:g1_birkin_spawn_egg")
        self.camera(6, -10, 6, 65.3, 4, "Spawn eggs on camera hotbar")
        self.screenshot("01-spawn-eggs.png")
        for entity, label, x, focus_height in MOBS:
            distance = 6.2 if entity == "licker" else 6.8
            self.camera(x + distance * 0.45, 4 - distance, x, 64 + focus_height, 4, label)
            self.screenshot(f"{entity}-model.png")
            self.camera(x + 6.4, 4, x, 64 + focus_height, 4, f"{label} side")
            self.screenshot(f"{entity}-model-side.png")
            self.camera(x - 0.5, 10.4, x, 64 + focus_height, 4, f"{label} back")
            self.screenshot(f"{entity}-model-back.png")
        self.isolated_action_scenes()
        self.sneak_scene()
        self.ambush_scene()
        self.climb_scene()
        self.verify_music_playback()
        self.brawl_scene()
        self.mid_attack_reveal_scenes()
        self.identify_scene()
        self.death_cleanup_scene()
        self.alive()
        errors = re.compile(r"(?:GeckoLibException|Rendering entity in world|"
                            r"(?:Unable|Failed|Could not|Missing).{0,100}(?:re_demo[:/]|assets/re_demo/))", re.I)
        for path in (self.output / "client.log", self.client_dir / "logs" / "latest.log"):
            match = errors.search(tail(path, 10_000_000))
            if match:
                raise EvidenceError(f"Client rendering/resource error in {path.name}: {match.group(0)}")
        expected_shots = {
            "00-three-creatures.png", "01-spawn-eggs.png", "licker-model.png", "tyrant-model.png",
            "g1_birkin-model.png", "licker-model-side.png", "tyrant-model-side.png",
            "g1_birkin-model-side.png", "licker-model-back.png", "tyrant-model-back.png",
            "g1_birkin-model-back.png", "licker-ambush.png", "20-block-identification.png",
            "licker-20blocks.png", "tyrant-20blocks.png", "g1_birkin-20blocks.png",
            "licker-climb.png", "licker-sneak-silent.png", "licker-sprint-hunt.png",
            "99-death-cleared.png",
        }
        expected_clips = {
            "creature-brawl.mp4", "tyrant-attack.mp4", "tyrant-charge.mp4", "g1_birkin-attack.mp4",
            "licker-crawl.mp4", "licker-tongue.mp4", "licker-attack.mp4", "licker-climb.mp4",
            "licker-ambush.mp4", "licker-sneak-vs-sprint.mp4",
        }
        got_shots = {item["name"] for item in self.report["screenshots"]}
        got_clips = {item["name"] for item in self.report["clips"]}
        if got_shots != expected_shots or got_clips != expected_clips:
            raise EvidenceError(f"Incomplete evidence set shots={sorted(got_shots)} clips={sorted(got_clips)}")
        ordered = ["creature-brawl.mp4", "licker-climb.mp4", "licker-ambush.mp4",
                   "licker-sneak-vs-sprint.mp4", "tyrant-attack.mp4", "tyrant-charge.mp4",
                   "g1_birkin-attack.mp4", "licker-crawl.mp4", "licker-tongue.mp4", "licker-attack.mp4"]
        playlist = self.output / "showcase-concat.txt"
        playlist.write_text("".join(f"file '{name}'\n" for name in ordered), encoding="utf-8")
        showcase = self.output / "encounter-showcase.mp4"
        self.run_logged("ffmpeg-showcase", ["ffmpeg", "-v", "warning", "-nostdin", "-y",
                        "-f", "concat", "-safe", "1", "-i", str(playlist), "-c", "copy",
                        "-movflags", "+faststart", str(showcase)], self.work, 60)
        self.report["showcase"] = dict(file_record(showcase), order=ordered,
                                        duration_seconds=float(probe(showcase)["format"]["duration"]),
                                        audio=check_audio(showcase))
        elapsed, timeline = 0.0, []
        for name in ordered:
            duration = float(probe(self.output / name)["format"]["duration"])
            timeline.append({"source_clip": name, "start_seconds": round(elapsed, 3),
                             "end_seconds": round(elapsed + duration, 3)})
            elapsed += duration
        self.report["showcase"]["timeline"] = timeline
        self.report["showcase"]["editing"] = ("Controlled three-creature combat followed by separately staged "
                                                       "normal-AI close-ups; no overdub")
        self.report["installed_jar_client_verified"] = True
        self.report["passed"] = True

    def cleanup(self) -> None:
        if self.server is not None and self.server.poll() is None:
            try:
                self.server.stdin.write("stop\n")
                self.server.stdin.flush()
                self.server.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                pass
        for _, proc in reversed(self.processes):
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=10)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
        for handle in self.handles:
            handle.close()
        if self.audio_temp is not None:
            self.audio_temp.cleanup()
        if self.work is not None:
            for role in ("client", "server"):
                for folder in ("logs", "crash-reports"):
                    source = self.work / role / folder
                    if source.is_dir():
                        shutil.copytree(source, self.output / f"{role}-{folder}", dirs_exist_ok=True)
            for name in ("server.properties", "eula.txt"):
                source = self.work / "server" / name
                if source.exists():
                    shutil.copy2(source, self.output / name)
        self.report["files"] = [dict(file_record(path), path=str(path.relative_to(self.output)))
                                for path in sorted(self.output.rglob("*")) if path.is_file()]
        (self.output / "report.json").write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("build/client-evidence"),
                        help="Must not already exist; records only this run's evidence")
    parser.add_argument("--jar", type=Path, default=Path("build/libs/re_demo-0.1.3.jar"))
    parser.add_argument("--port", type=int, default=25575)
    parser.add_argument("--clip-seconds", type=int, default=10)
    parser.add_argument("--build-timeout", type=int, default=1500)
    parser.add_argument("--startup-timeout", type=int, default=480)
    parser.add_argument("--accept-minecraft-eula", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not 6 <= args.clip_seconds <= 30:
        parser.error("port must be 1024..65535 and clip duration 6..30 seconds")
    capture = Capture(args)
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
