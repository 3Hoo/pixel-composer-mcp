import pytest

from pixel_composer_mcp.nodesrc import describe_node

GML = '''function Node_VFX_Spawner(_x, _y, _group = noone) : Node(_x, _y, _group) constructor {
	newInput( 0, nodeValue_Surface( "Particle Sprite" ));
	newInput(18, nodeValue_Range(   "Speed", [1,2] ));
	newOutput(0, nodeValue_Output("Surface Out", VALUE_TYPE.surface, noone));
}
'''


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "scripts" / "node_VFX_spawner"
    d.mkdir(parents=True)
    (d / "node_VFX_spawner.gml").write_text(GML)
    return tmp_path


def test_describe_node_case_insensitive(src):
    d = describe_node("Node_VFX_Spawner", src)
    assert [i["index"] for i in d["inputs"]] == [0, 18]
    assert d["inputs"][1] == {"index": 18, "name": "Speed", "kind": "Range"}
    assert d["outputs"][0]["name"] == "Surface Out"


def test_describe_node_unknown(src):
    with pytest.raises(KeyError, match="Node_Nope"):
        describe_node("Node_Nope", src)


def test_describe_node_keeps_inputs_without_name(tmp_path):
    # Some constructors take no name string; the input still exists and uses the kind as its label.
    d = tmp_path / "scripts" / "node_shape"
    d.mkdir(parents=True)
    (d / "node_shape.gml").write_text('newInput(0, nodeValue_Dimension());\n'
                                      'newInput(1, nodeValue_Bool("Anti-aliasing", false));\n')
    inputs = describe_node("Node_Shape", tmp_path)["inputs"]
    assert inputs[0] == {"index": 0, "name": "Dimension", "kind": "Dimension"}
    assert inputs[1]["name"] == "Anti-aliasing"
