"""Mermaid + HTML emitters for graphs (``viz network``).

The one real output-safety rule (SCHEMAS §"Free-text in HTML"): free text (author names)
is escaped before it lands in HTML, so a stray ``<`` can't break the page. Mermaid node
ids are sanitized to an alnum-safe form; labels have mermaid-breaking characters softened.
"""

from __future__ import annotations

import html
import re

_ID_UNSAFE = re.compile(r"[^A-Za-z0-9]")


def _node_id(raw: str) -> str:
    return "n_" + _ID_UNSAFE.sub("_", raw)


def _mermaid_label(label: str) -> str:
    # Quotes and brackets break a mermaid ["..."] label; soften them.
    return label.replace('"', "'").replace("[", "(").replace("]", ")")


def to_mermaid(nodes: list[dict[str, object]], edges: list[list[str]]) -> str:
    """A ``graph LR`` mermaid diagram: labelled nodes + undirected co-authorship edges."""
    lines = ["graph LR"]
    for node in nodes:
        node_id = _node_id(str(node["id"]))
        lines.append(f'    {node_id}["{_mermaid_label(str(node["label"]))}"]')
    for a, b in edges:
        lines.append(f"    {_node_id(a)} --- {_node_id(b)}")
    return "\n".join(lines)


def to_html(title: str, mermaid_source: str) -> str:
    """Wrap a mermaid diagram in a self-contained HTML page (mermaid.js via CDN).

    ``title`` and the mermaid source are HTML-escaped; the browser un-escapes the
    ``.mermaid`` text content for mermaid.js, so escaping is both safe and correct.
    """
    safe_title = html.escape(title)
    safe_source = html.escape(mermaid_source)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{safe_title}</title>\n"
        '<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>\n'
        "<script>mermaid.initialize({ startOnLoad: true });</script>\n"
        "</head>\n<body>\n"
        f"<h1>{safe_title}</h1>\n"
        f'<pre class="mermaid">\n{safe_source}\n</pre>\n'
        "</body>\n</html>\n"
    )
