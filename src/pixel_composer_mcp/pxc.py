"""Read/write Pixel Composer project files (.pxc) without the app.

On-disk layout (see Pixel-Composer scripts/save_function, load_function):
  "PXCX" u32 header_size [ "THMB" u32 len bytes ] "META" u32 len u32 save_version cstring version
  then zlib( json + "\\0" ) starting at header_size.
Older or hand-written files may be bare JSON; the app accepts both.
"""

import json
import struct
import uuid
import zlib
from pathlib import Path

EXPORT_TEMPLATE = Path(__file__).with_name("templates") / "export_node.json"


class Project:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        # Keep the original header verbatim so a save only swaps the JSON body.
        self.header = b""
        body = raw
        if raw[:4] == b"PXCX":
            size = struct.unpack("<I", raw[4:8])[0]
            self.header, body = raw[:size], raw[size:]
        try:
            body = zlib.decompress(body)
            self.compressed = True
        except zlib.error:
            self.compressed = False
        self.data = json.loads(body.rstrip(b"\0").decode("utf-8"))

    def save(self, path: str | Path | None = None) -> Path:
        out = Path(path) if path else self.path
        body = json.dumps(self.data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self.compressed:
            body = zlib.compress(body + b"\0")
        out.write_bytes(self.header + body)
        return out

    def nodes(self) -> list[dict]:
        """All nodes, including those nested inside groups."""
        def walk(ns):
            for n in ns:
                yield n
                if isinstance(n.get("nodes"), list):
                    yield from walk(n["nodes"])
        return list(walk(self.data.get("nodes", [])))

    def find(self, ref: str) -> dict:
        """Match a node by id, internal name (iname) or display name."""
        hits = [n for n in self.nodes() if ref in (n.get("id"), n.get("iname"), n.get("name"))]
        if not hits:
            raise KeyError(f"node not found: {ref}")
        if len(hits) > 1:
            ids = ", ".join(f"{n['id']} ({n.get('iname')})" for n in hits)
            raise KeyError(f"'{ref}' is ambiguous, use one of: {ids}")
        return hits[0]

    def summary(self, max_value_len: int = 120) -> dict:
        names = {n["id"]: n.get("iname") or n.get("name") for n in self.nodes()}
        out = []
        for n in self.nodes():
            inputs = []
            for i, inp in enumerate(n.get("inputs") or []):
                if not isinstance(inp, dict):
                    continue
                item: dict = {"index": i}
                if inp.get("from_node"):
                    item["from"] = f"{names.get(inp['from_node'], inp['from_node'])}[{inp.get('from_index', 0)}]"
                if "r" in inp and isinstance(inp["r"], dict) and "d" in inp["r"]:
                    v = json.dumps(inp["r"]["d"], ensure_ascii=False)
                    item["value"] = inp["r"]["d"] if len(v) <= max_value_len else v[:max_value_len] + "…"
                if inp.get("animators") or inp.get("anim"):
                    item["animated"] = True
                if len(item) > 1:
                    inputs.append(item)
            out.append({"id": n["id"], "iname": n.get("iname"), "name": n.get("name"),
                        "type": n.get("type"), "inputs": inputs})
        return {"path": str(self.path), "version": self.data.get("version"),
                "node_count": len(out), "nodes": out}

    def _input(self, ref: str, index: int) -> tuple[dict, dict]:
        node = self.find(ref)
        inputs = node.setdefault("inputs", [])
        while len(inputs) <= index:
            inputs.append({})
        return node, inputs[index]

    def connect(self, src: str, out_index: int, dst: str, in_index: int) -> dict:
        s = self.find(src)
        d, inp = self._input(dst, in_index)
        inp["from_node"], inp["from_index"] = s["id"], out_index
        return {"from": s["id"], "from_index": out_index, "to": d["id"], "in_index": in_index}

    def disconnect(self, dst: str, in_index: int) -> dict:
        d, inp = self._input(dst, in_index)
        was = inp.pop("from_node", None)
        inp.pop("from_index", None)
        return {"node": d["id"], "in_index": in_index, "was_from": was}

    def set_input(self, ref: str, index: int, value) -> dict:
        node, inp = self._input(ref, index)
        if inp.get("from_node"):
            # A linked input ignores its stored value, so a silent write would do nothing.
            raise ValueError(f"input {index} of {ref} is driven by a connection; edit the source node instead")
        old = (inp.get("r") or {}).get("d")
        inp.setdefault("r", {})["d"] = value
        return {"node": node["id"], "index": index, "old": old, "new": value}

    def add_export_node(self, x: int, y: int, path: str) -> str:
        """Add an Export node from a bundled template (no app involved).

        The app can't create one via nodeBuild: manual creation opens a modal save dialog.
        """
        node = json.loads(EXPORT_TEMPLATE.read_text(encoding="utf-8"))
        node["id"] = "mcpexport" + uuid.uuid4().hex[:23]
        node["iname"] = f"Export_{node['id'][-6:]}"
        node["x"], node["y"] = x, y
        node["inputs"][1]["r"]["d"] = path
        self.data.setdefault("nodes", []).append(node)
        return node["id"]

    def export_nodes(self) -> list[dict]:
        return [n for n in self.nodes() if n.get("type") == "Node_Export"]
