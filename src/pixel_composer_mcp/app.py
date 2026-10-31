"""Drive a Pixel Composer GUI instance through its built-in "Remote Terminal" addon.

Why not --headless: in 1.22.x the headless mode swaps the UI theme for a hand-written stub
that misses keys every Surface input touches (e.g. THEME.node_junction_surface_uv), so nearly
every real project fails to load. The --server TCP port accepts connections but drops data.
The Remote Terminal addon (WebSocket, default port 22400) is the path that works: each text
frame is run through the in-app console (cmd_submit), which can call any GML function by name.
"""

import atexit
import base64
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

from .pxc import Project

INSTALL_DIR = Path(os.environ.get("PXC_DIR", r"C:\Program Files (x86)\Steam\steamapps\common\Pixel Composer"))
DATA_DIR = Path(os.environ.get("PXC_DATA_DIR") or Path(os.environ.get("LOCALAPPDATA", "")) / "PixelComposer")
PORT = int(os.environ.get("PXC_TERMINAL_PORT", "22400"))
STEAM_APP_ID = "2299510"
ADDON = "Remote Terminal"

READY = "Entering main loop."
ERROR_RE = re.compile(r"ERROR in action|Export error|Export failed|Export: Path is empty|Unable to ")
EXPORT_RE = re.compile(r"EXPORT: Export \w+ at (.+?)\s*\W?$")
# Sequence/folder/tilemap exports log "Export N images complete." etc. with no path, so
# completion is counted separately from path extraction.
EXPORT_DONE_RE = re.compile(r"EXPORT: Export .*(?: at |complete)")


class PxcError(RuntimeError):
    pass


def ensure_addon() -> bool:
    """Make Remote Terminal start with the app; merge, never overwrite other addons.

    Returns True when the config had to be changed (takes effect on the next app start).
    """
    path = DATA_DIR / "Addons" / "__init.json"
    enabled = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if ADDON in enabled:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(enabled + [ADDON]), encoding="utf-8")
    return True


def port_open() -> bool:
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
        return True
    except OSError:
        return False


def app_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq PixelComposer.exe", "/NH"],
                         capture_output=True, text=True, errors="replace").stdout
    return "PixelComposer.exe" in out


def ws_send(command: str) -> None:
    """One-shot WebSocket text frame. The addon never replies; results only show in app stdout."""
    with socket.create_connection(("127.0.0.1", PORT), timeout=5) as s:
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        if b" 101 " not in s.recv(1024).split(b"\r\n", 1)[0]:
            raise PxcError("Remote Terminal refused the WebSocket handshake")
        data, mask = command.encode(), os.urandom(4)
        n = len(data)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        time.sleep(0.3)  # let the frame land before the close handshake


class Instance:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self.lock = threading.Lock()
        self.project: Path | None = None  # the file the agent edits
        self.loaded: Path | None = None   # the file the app opened (a space-free copy when needed)
        atexit.register(self.close)

    # ---- process ----

    @property
    def launched(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def mode(self) -> str:
        if self.launched:
            return "launched"
        return "attached" if port_open() else "stopped"

    def _drain(self, stream):
        for line in stream:
            with self.lock:
                self.lines.append(line.rstrip("\r\n"))

    def mark(self) -> int:
        with self.lock:
            return len(self.lines)

    def since(self, mark: int) -> list[str]:
        with self.lock:
            return self.lines[mark:]

    def wait_line(self, pattern: str | re.Pattern, mark: int, timeout: float) -> str | None:
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        end = time.time() + timeout
        while time.time() < end:
            for line in self.since(mark):
                if rx.search(line):
                    return line
            if self.proc is not None and self.proc.poll() is not None:
                raise PxcError("Pixel Composer exited:\n" + "\n".join(self.since(mark)[-20:]))
            time.sleep(0.2)
        return None

    def connect(self, timeout: float = 120) -> str:
        """Attach to a running instance with the terminal port, or launch one."""
        if self.launched or port_open():
            return self.mode()
        if app_running():
            raise PxcError(f"Pixel Composer is running but port {PORT} is closed. The Remote Terminal addon "
                           "was enabled for the next start: close Pixel Composer and retry.")
        exe = INSTALL_DIR / "PixelComposer.exe"
        if not exe.exists():
            raise PxcError(f"{exe} not found; set PXC_DIR to the install folder")
        # Steam builds abort unless launched by Steam; Steam marks its launches with these vars.
        env = {**os.environ, "SteamAppId": STEAM_APP_ID, "SteamGameId": STEAM_APP_ID}
        with self.lock:
            self.lines = []
        # cwd matters: the app resolves pack/, ffmpeg/, ImageMagick/ relative to working_directory.
        self.proc = subprocess.Popen([str(exe)], cwd=INSTALL_DIR, env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     encoding="utf-8", errors="replace")
        threading.Thread(target=self._drain, args=(self.proc.stdout,), daemon=True).start()
        if not self.wait_line(re.escape(READY), 0, timeout):
            raise PxcError("Pixel Composer did not finish starting in time")
        end = time.time() + 15
        while not port_open():
            if time.time() > end:
                raise PxcError(f"started, but port {PORT} never opened (is the Remote Terminal addon enabled?)")
            time.sleep(0.3)
        return "launched"

    def close(self) -> str:
        """Quit only an instance this server launched; an attached one is left alone."""
        if not self.launched:
            return "nothing to close (attached instances are left running)"
        assert self.proc is not None
        try:
            ws_send("exit")
            self.proc.wait(15)
        except (OSError, PxcError, subprocess.TimeoutExpired):
            self.proc.terminate()
        self.proc = None
        return "closed"

    # ---- commands ----

    def command(self, command: str, wait: float = 1.0) -> list[str]:
        self.connect()
        mark = self.mark()
        ws_send(command)
        time.sleep(wait)
        return self.since(mark)

    def open(self, path: str | Path, timeout: float = 60) -> dict:
        path = Path(path).resolve()
        if not path.exists():
            raise PxcError(f"{path} not found")
        self.connect()
        # The console splits arguments on spaces with no quoting, so load a space-free copy.
        target = path
        if " " in str(path):
            work = DATA_DIR / "mcp_work"
            work.mkdir(parents=True, exist_ok=True)
            target = work / path.name.replace(" ", "_")
            shutil.copyfile(path, target)
        mark = self.mark()
        ws_send(f"load_file_path {target.as_posix()}")
        if self.launched:
            line = self.wait_line(r"FILE: load .* completed|ERROR in action", mark, timeout)
            if line is None or "ERROR" in line:
                raise PxcError("load failed:\n" + "\n".join(self.since(mark)[-25:]))
        time.sleep(1.5)  # give the graph a frame or two to render before anyone exports
        self.project, self.loaded = path, target
        return {"project": str(path), "loaded_as": str(target), "mode": self.mode(),
                "errors": [l for l in self.since(mark) if ERROR_RE.search(l)]}

    def save(self, timeout: float = 30) -> dict:
        """Save the app's open project and copy it back to the agent's file if it was loaded from a copy."""
        if self.project is None or self.loaded is None:
            raise PxcError("open a project first")
        before = self.loaded.stat().st_mtime_ns
        ws_send("SAVE")
        # Watch the file rather than the log so this also works when attached (no stdout).
        end = time.time() + timeout
        while self.loaded.stat().st_mtime_ns == before:
            if time.time() > end:
                raise PxcError(f"app did not save {self.loaded} within {timeout}s")
            time.sleep(0.2)
        size = -1
        while size != (size := self.loaded.stat().st_size):
            time.sleep(0.5)
        if self.loaded != self.project:
            shutil.copyfile(self.loaded, self.project)
        return {"saved": str(self.project)}

    def add_node(self, node_type: str, x: int = 0, y: int = 0) -> dict:
        self.save()
        assert self.project is not None  # save() raised otherwise
        before = {n["id"] for n in Project(self.project).nodes()}
        ws_send(f"nodeBuild {node_type} {int(x)} {int(y)}")
        time.sleep(0.5)
        self.save()
        new = [n for n in Project(self.project).nodes() if n["id"] not in before]
        if not new:
            raise PxcError(f"Pixel Composer did not create '{node_type}' (unknown node type?)")
        return {"type": new[0]["type"], "id": new[0]["id"], "iname": new[0].get("iname")}

    def export(self, timeout: float = 180, settle: float = 1.5) -> dict:
        if self.project is None:
            raise PxcError("open a project first")
        nodes = Project(self.project).export_nodes()
        if not nodes:
            raise PxcError("project has no Export node; add one in Pixel Composer")
        dirs = set()
        for n in nodes:
            d = str(((n.get("inputs") or [{}, {}])[1].get("r") or {}).get("d") or "")
            if d:
                p = Path(d)
                dirs.add(p.parent if p.suffix else p)

        self.connect()
        mark, t0 = self.mark(), time.time() - 1
        ws_send("exportAll")

        # Done = every Export node reported (or, when attached and blind, files appeared)
        # and no output file changed for `settle` seconds. GIF/MP4 are encoded by an async
        # ImageMagick/ffmpeg child after the EXPORT line, hence the size check.
        last, stable_since, end = None, time.time(), time.time() + timeout
        while time.time() < end:
            lines = self.since(mark)
            errors = [l for l in lines if ERROR_RE.search(l)]
            if errors:
                return {"ok": False, "errors": errors, "log": lines[-25:]}
            # The app logs '/' or '\' depending on the call site; normalise so a file counts once.
            reported = {os.path.normpath(m.group(1)) for l in lines if (m := EXPORT_RE.search(l))}
            done = sum(1 for l in lines if EXPORT_DONE_RE.search(l))
            found = {str(f) for d in dirs if d.is_dir() for f in d.iterdir()
                     if f.is_file() and f.stat().st_mtime >= t0}
            files = sorted(reported | found)
            snapshot = [(f, os.path.getsize(f)) for f in files if os.path.exists(f)]
            if snapshot != last:
                last, stable_since = snapshot, time.time()
            enough = done >= len(nodes) if self.launched else bool(found)
            if enough and snapshot and time.time() - stable_since >= settle:
                return {"ok": True, "files": [{"path": f, "bytes": s} for f, s in snapshot]}
            time.sleep(0.3)
        return {"ok": False, "errors": ["timed out"], "files": last or [], "log": self.since(mark)[-25:]}

    def status(self, tail: int = 20) -> dict:
        return {"mode": self.mode(), "pid": self.proc.pid if self.launched and self.proc else None,
                "port": PORT, "project": str(self.project) if self.project else None,
                "log_tail": self.since(max(0, self.mark() - tail))}
