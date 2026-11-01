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
# The addon drops whatever follows roughly the first 490 payload bytes of a frame (measured on
# 1.22.0.5), so commands are packed into frames well under that.
MAX_FRAME = 400
ADDON = "Remote Terminal"

READY = "Entering main loop."
ERROR_RE = re.compile(r"ERROR in action|Export error|Export failed|Export: Path is empty|Unable to ")
EXPORT_RE = re.compile(r"EXPORT: Export \w+ at (.+?)\s*\W?$")
# Sequence/folder/tilemap exports log "Export N images complete." etc. with no path, so
# completion is counted separately from path extraction.
EXPORT_DONE_RE = re.compile(r"EXPORT: Export .*(?: at |complete)")


class PxcError(RuntimeError):
    pass


# Node types whose manual creation opens a modal file dialog (Node_create_* checks NODE_NEW_MANUAL),
# blocking the app's main loop. Node_Export is handled separately via a JSON template.
DIALOG_NODES = frozenset({
    "Node_3D_Json", "Node_3D_Obj", "Node_ASE_File_Read", "Node_CSV_File_Read", "Node_Display_Image",
    "Node_Image", "Node_Image_Animated", "Node_Image_Sequence", "Node_Image_gif", "Node_Image_mp4",
    "Node_Json_File_Read", "Node_Krita_File_Read", "Node_ORA_File_Read", "Node_PXC", "Node_Text_File_Read",
    "Node_WAV_File_Read", "Node_XML_File_Read",
})


# File-reading node types the app can create without the dialog: Node_create_<X>_path(x, y, path)
# sets the file directly (verified for Node_ASE_File_Read; the others share the same source pattern).
FILE_NODES = frozenset({
    "Node_3D_Json", "Node_ASE_File_Read", "Node_CSV_File_Read", "Node_Display_Image", "Node_Image",
    "Node_Image_gif", "Node_Image_mp4", "Node_Json_File_Read", "Node_Krita_File_Read", "Node_ORA_File_Read",
    "Node_PXC", "Node_Text_File_Read", "Node_WAV_File_Read", "Node_XML_File_Read",
})


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


def _frames(command: str) -> list[bytes]:
    """Pack lines into payloads of at most MAX_FRAME bytes, never splitting a line."""
    out, cur = [], b""
    for line in command.encode().split(b"\n"):
        if len(line) > MAX_FRAME:
            raise PxcError(f"command line too long ({len(line)} bytes, max {MAX_FRAME}): {line[:60]!r}...")
        if cur and len(cur) + 1 + len(line) > MAX_FRAME:
            out.append(cur)
            cur = line
        else:
            cur = cur + b"\n" + line if cur else line
    return out + [cur]


def ws_send(command: str) -> None:
    """Send console commands as WebSocket text frames. The addon never replies; results only
    show in app stdout. Multi-line commands run line by line, in order."""
    frames = _frames(command)
    with socket.create_connection(("127.0.0.1", PORT), timeout=5) as s:
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        if b" 101 " not in s.recv(1024).split(b"\r\n", 1)[0]:
            raise PxcError("Remote Terminal refused the WebSocket handshake")
        for data in frames:
            mask, n = os.urandom(4), len(data)
            head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
            s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
            time.sleep(0.3)  # one frame per app network event; also lets the last land before close


def _export_dir(node: dict) -> Path | None:
    d = str(((node.get("inputs") or [{}, {}])[1].get("r") or {}).get("d") or "")
    if not d:
        return None
    p = Path(d)
    return p.parent if p.suffix else p


def _export_path_warnings(proj: Project) -> list[str]:
    """Export nodes whose target folder does not exist, e.g. a project made on another machine."""
    out = []
    for n in proj.export_nodes():
        d = _export_dir(n)
        if d is not None and not d.is_dir():
            out.append(f"{n.get('iname') or n['id']} exports to {d.as_posix()}, which does not exist; "
                       f"repoint it with set_input('{n.get('iname') or n['id']}', 1, '<new path>')")
    return out


class Instance:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self.lock = threading.Lock()
        self.project: Path | None = None  # the file the agent edits
        self.loaded: Path | None = None   # the file the app opened (a space-free copy when needed)
        # mtime of self.project when the app and the file last agreed. A later mtime means the file
        # was edited without a reload, and an app SAVE would overwrite those edits.
        self.synced: int | None = None
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
        self.synced = path.stat().st_mtime_ns
        return {"project": str(path), "loaded_as": str(target), "mode": self.mode(),
                "errors": [l for l in self.since(mark) if ERROR_RE.search(l)],
                "warnings": _export_path_warnings(Project(path))}

    @property
    def dirty(self) -> bool:
        """The project file holds edits the app has not loaded yet."""
        return self.project is not None and self.project.stat().st_mtime_ns != self.synced

    def save(self, timeout: float = 30) -> dict:
        """Save the app's open project and copy it back to the agent's file if it was loaded from a copy.

        File edits made without a reload are loaded into the app first, so the save keeps them.
        """
        if self.project is None or self.loaded is None:
            raise PxcError("open a project first")
        if self.dirty:
            self.open(self.project)
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
        self.synced = self.project.stat().st_mtime_ns
        return {"saved": str(self.project)}

    def add_node(self, node_type: str, x: int = 0, y: int = 0, file: str | None = None) -> dict:
        command = f"nodeBuild {node_type} {int(x)} {int(y)}"
        if file is not None:
            if node_type not in FILE_NODES:
                raise PxcError(f"{node_type} does not take a file; file-reading types: {', '.join(sorted(FILE_NODES))}")
            path = Path(file).resolve()
            if " " in str(path):
                raise PxcError(f"{path}: the console splits on spaces; use a path without spaces")
            if not path.exists():
                raise PxcError(f"{path} not found")
            command = f"Node_create_{node_type[len('Node_'):]}_path {int(x)} {int(y)} {path.as_posix()}"
        elif node_type in DIALOG_NODES:
            hint = " (pass file=<path>)" if node_type in FILE_NODES else "; add it in the Pixel Composer window instead"
            raise PxcError(f"{node_type} opens a file dialog when created and would freeze the app{hint}")
        if node_type == "Node_Export":
            self.save()
            assert self.project is not None
            proj = Project(self.project)
            nid = proj.add_export_node(int(x), int(y), "")
            proj.save()
            self.open(self.project)
            return {"type": node_type, "id": nid, "iname": proj.find(nid)["iname"]}
        self.save()
        assert self.project is not None  # save() raised otherwise
        before = {n["id"] for n in Project(self.project).nodes()}
        ws_send(command)
        # The app builds the node over a few frames; save until it shows up in the file.
        new: list[dict] = []
        for _ in range(20):
            time.sleep(0.5)
            self.save()
            new = [n for n in Project(self.project).nodes() if n["id"] not in before]
            if new:
                break
        if not new:
            raise PxcError(f"Pixel Composer did not create '{node_type}' (unknown node type?)")
        return {"type": new[0]["type"], "id": new[0]["id"], "iname": new[0].get("iname")}

    def export(self, timeout: float = 180, settle: float = 1.5) -> dict:
        if self.project is None:
            raise PxcError("open a project first")
        if self.dirty:  # export what the file says, not the graph the app loaded earlier
            self.open(self.project)
        nodes = Project(self.project).export_nodes()
        if not nodes:
            raise PxcError("project has no Export node; add one in Pixel Composer")
        dirs = {d for n in nodes if (d := _export_dir(n)) is not None}

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
