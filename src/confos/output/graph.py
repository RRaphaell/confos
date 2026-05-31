"""Mermaid + HTML emitters for graphs (``viz network``).

The one real output-safety rule (SCHEMAS §"Free-text in HTML"): free text (author names)
is escaped before it lands in HTML, so a stray ``<`` can't break the page. Mermaid node
ids are positional (injective); labels have mermaid-breaking characters softened.
"""

from __future__ import annotations

import html


def _mermaid_label(label: str) -> str:
    # Quotes/brackets break a mermaid ["..."] label; newlines split the statement.
    return (
        label.replace('"', "'")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def to_mermaid(nodes: list[dict[str, object]], edges: list[list[str]]) -> str:
    """A ``graph LR`` mermaid diagram: labelled nodes + undirected co-authorship edges.

    Node ids are assigned by position (n0, n1, …) so they are injective — distinct
    author_ids that differ only in punctuation can never collapse into one node.
    """
    id_map = {str(node["id"]): f"n{index}" for index, node in enumerate(nodes)}
    lines = ["graph LR"]
    for node in nodes:
        lines.append(f'    {id_map[str(node["id"])]}["{_mermaid_label(str(node["label"]))}"]')
    for a, b in edges:
        if a in id_map and b in id_map:
            lines.append(f"    {id_map[a]} --- {id_map[b]}")
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
