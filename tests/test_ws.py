import socket
import struct
import threading

import pytest

from pixel_composer_mcp import app


def fake_terminal(frames: list[bytes]) -> tuple[int, threading.Thread]:
    """Accept one WebSocket client, answer the handshake, collect unmasked text frames."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        conn.recv(4096)
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\n\r\n")
        conn.settimeout(2)
        buf = b""
        try:
            while chunk := conn.recv(65536):
                buf += chunk
        except OSError:
            pass
        while buf:
            n = buf[1] & 0x7F
            off = 2
            if n == 126:
                n, off = struct.unpack(">H", buf[2:4])[0], 4
            mask, data = buf[off:off + 4], buf[off + 4:off + 4 + n]
            frames.append(bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
            buf = buf[off + 4 + n:]
        conn.close()
        srv.close()

    th = threading.Thread(target=run, daemon=True)
    th.start()
    return srv.getsockname()[1], th


def test_long_multiline_command_is_split_on_line_boundaries(monkeypatch):
    frames: list[bytes] = []
    port, th = fake_terminal(frames)
    monkeypatch.setattr(app, "PORT", port)
    lines = [f"nodeBuild Node_Particle {i * 160} 0" for i in range(30)]  # ~1 KB, over the app's limit
    app.ws_send("\n".join(lines))
    th.join(5)  # the fake server parses frames after the client closes
    assert all(len(f) <= app.MAX_FRAME for f in frames) and len(frames) > 1
    assert "\n".join(f.decode() for f in frames).split("\n") == lines


def test_single_line_over_limit_is_refused(monkeypatch):
    monkeypatch.setattr(app, "PORT", fake_terminal([])[0])
    with pytest.raises(app.PxcError, match="too long"):
        app.ws_send("print " + "a" * 500)
