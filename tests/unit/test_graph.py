"""Mermaid + HTML graph emitters (id sanitization, label softening, HTML escaping)."""

from __future__ import annotations

from confos.output.graph import to_html, to_mermaid


def test_to_mermaid_injective_ids_and_softened_labels() -> None:
    # These two ids would collide under a lossy char-substitution scheme; positional
    # ids (n0/n1) keep them distinct.
    nodes = [
        {"id": "email:a.b@x.com", "label": 'Alice "A" Smith', "degree": 1},
        {"id": "email:a-b@x.com", "label": "Bob [Tan]", "degree": 1},
    ]
    edges = [["email:a.b@x.com", "email:a-b@x.com"]]
    out = to_mermaid(nodes, edges)
    assert out.startswith("graph LR")
    assert "n0[\"Alice 'A' Smith\"]" in out
    assert 'n1["Bob (Tan)"]' in out
    assert "n0 --- n1" in out  # the edge maps to the two distinct node ids


def test_to_mermaid_label_strips_newline() -> None:
    out = to_mermaid([{"id": "x", "label": "Line1\nLine2", "degree": 0}], [])
    assert 'n0["Line1 Line2"]' in out  # newline collapsed, statement intact


def test_to_mermaid_label_softens_statement_breakers() -> None:
    # ';' (statement separator), '#' (entity start) and backticks must be neutralised so
    # an author name like 'A; B #1 `x`' can't break the diagram.
    out = to_mermaid([{"id": "x", "label": "A; B #1 `x`", "degree": 0}], [])
    label = out.splitlines()[1]  # the single node line
    assert ";" not in label and "#" not in label and "`" not in label
    assert label == "    n0[\"A, B  1 'x'\"]"


def test_to_html_escapes_free_text() -> None:
    # A label with HTML metacharacters must be escaped so it can't break the page.
    mermaid = to_mermaid([{"id": "x", "label": "A <script> & B", "degree": 0}], [])
    html_doc = to_html("topic <x> & y", mermaid)
    assert "<!doctype html>" in html_doc
    assert "&lt;script&gt;" in html_doc  # escaped, not a live tag
    assert "&lt;x&gt; &amp; y" in html_doc  # title escaped
    assert "<script>A" not in html_doc  # no unescaped injection
    assert 'class="mermaid"' in html_doc
