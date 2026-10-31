"""Input/output names for a node type, read from a Pixel Composer source clone.

.pxc files store inputs by index only; the names live in each node's constructor
(`newInput(<index>, nodeValue_<Kind>("<Name>", ...))`). Inputs a node inherits from a base
class (declared as `input_len + N`) are not listed.
"""

import re
from pathlib import Path

INPUT_RE = re.compile(r'newInput\(\s*(\d+)\s*,\s*nodeValue_?(\w*)\(\s*"([^"]+)"')
OUTPUT_RE = re.compile(r'newOutput\(\s*(\d+)\s*,\s*nodeValue_Output\(\s*"([^"]+)"')


def describe_node(node_type: str, source_dir: Path) -> dict:
    stem = node_type.lower()
    # File names don't always match the type's casing (Node_VFX_Spawner -> node_VFX_spawner.gml).
    hits = [f for f in Path(source_dir, "scripts").glob("*/*.gml") if f.stem.lower() == stem]
    if not hits:
        raise KeyError(f"no source file for {node_type} under {source_dir}/scripts")
    text = hits[0].read_text(encoding="utf-8", errors="replace")
    inputs = {int(i): {"index": int(i), "name": name, "kind": kind} for i, kind, name in INPUT_RE.findall(text)}
    outputs = {int(i): {"index": int(i), "name": name} for i, name in OUTPUT_RE.findall(text)}
    return {"type": node_type, "file": str(hits[0]),
            "inputs": [inputs[k] for k in sorted(inputs)], "outputs": [outputs[k] for k in sorted(outputs)]}
