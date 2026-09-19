from app.schemas import AIVisualSpec
from app.services.visuals import render_svg


def test_sequence_diagram_renders_and_escapes():
    spec = AIVisualSpec(kind="sequence", title="TCP <handshake>", actors=["Client", "Server"],
                        messages=[{"from": "Client", "to": "Server", "label": "SYN"}, {"from": "Server", "to": "Client", "label": "SYN-ACK"}])
    svg = render_svg(spec)
    assert svg.startswith("<svg") and "SYN-ACK" in svg and "&lt;handshake&gt;" in svg


def test_none_and_empty_specs_render_nothing():
    assert render_svg(AIVisualSpec(kind="none")) is None
    assert render_svg(AIVisualSpec(kind="sequence")) is None


def test_all_kinds():
    assert render_svg(AIVisualSpec(kind="layers", items=["App", "Transport"]))
    assert render_svg(AIVisualSpec(kind="steps", items=["a", "b", "c"]))
    assert render_svg(AIVisualSpec(kind="array", values=["1", "3", "5"], highlights=[1]))
    assert render_svg(AIVisualSpec(kind="network", layer_sizes=[3, 4, 2]))
    assert render_svg(AIVisualSpec(kind="curve"))
    assert render_svg(AIVisualSpec(kind="table_relation", left=["users", "id"], right=["orders", "user_id"]))
    assert render_svg(AIVisualSpec(kind="tree", root="A", children={"A": ["B", "C"]}))
