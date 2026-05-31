"""Mermaid + HTML graph emitters (id sanitization, label softening, HTML escaping)."""

from __future__ import annotations

from confos.output.graph import to_html, to_mermaid


def test_to_mermaid_sanitizes_ids_and_labels() -> None:
    nodes = [
        {"id": "~Alice_Smith1", "label": 'Alice "A" Smith', "degree": 1},
        {"id": "email:bob@x.com", "label": "Bob [Tan]", "degree": 1},
    ]
    edges = [["~Alice_Smith1", "email:bob@x.com"]]
    out = to_mermaid(nodes, edges)
    assert out.startswith("graph LR")
    # node ids are alnum-safe (no ~, @, :, .)
    assert "n__Alice_Smith1" in out
    assert "n_email_bob_x_com" in out
    # label quotes/brackets softened so the mermaid ["..."] doesn't break
    assert "Alice 'A' Smith" in out
    assert "Bob (Tan)" in out
    # the edge connects the two sanitized ids
    assert "n__Alice_Smith1 --- n_email_bob_x_com" in out


def test_to_html_escapes_free_text() -> None:
    # A label with HTML metacharacters must be escaped so it can't break the page.
    mermaid = to_mermaid([{"id": "x", "label": "A <script> & B", "degree": 0}], [])
    html_doc = to_html("topic <x> & y", mermaid)
    assert "<!doctype html>" in html_doc
    assert "&lt;script&gt;" in html_doc  # escaped, not a live tag
    assert "&lt;x&gt; &amp; y" in html_doc  # title escaped
    assert "<script>A" not in html_doc  # no unescaped injection
    assert 'class="mermaid"' in html_doc
