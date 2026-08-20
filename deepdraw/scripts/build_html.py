#!/usr/bin/env python3
"""Wrap a drawing spec in DeepDraw's standalone-HTML export format.

    python3 build_html.py spec.json -o drawing.html

The result is byte-for-byte the kind of file DeepDraw's "Export → HTML" button
writes: the library inlined, and the document in a
`<script id="dd-document" type="application/json">`. It opens on its own in a
browser and imports back into deepdraw.ai through Import → File.

`--json` writes the canonical document beside it, which is the other format
deepdraw.ai imports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deepdraw_doc import SpecError, build_document, canvas_bounds, validate  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "reference" / "template.html"
TITLE_MARK = "__DEEPDRAW_TITLE__"
DOCUMENT_MARK = "__DEEPDRAW_DOCUMENT_JSON__"

_HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def escape_html(value: str) -> str:
    return "".join(_HTML_ESCAPES.get(c, c) for c in value)


def embed(document: dict) -> str:
    """The document as the `<script>` payload: `<` escaped the JSON way.

    It has to be escaped, or a `<` anywhere in a label or in an icon's inline
    SVG would close the script tag early. `\\u003c` keeps the text valid JSON
    for whoever imports the file again.
    """
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def to_standalone_html(document: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    if TITLE_MARK not in template or DOCUMENT_MARK not in template:
        raise SystemExit(f"{TEMPLATE} has lost its placeholders")
    html = template.replace(TITLE_MARK, escape_html(document.get("title") or "DeepDraw"))
    return html.replace(DOCUMENT_MARK, embed(document))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", help="the drawing spec, or a canonical DeepDraw document")
    parser.add_argument("-o", "--out", help="where to write the HTML (default: <spec>.html)")
    parser.add_argument("--json", dest="json_out", nargs="?", const=True,
                        help="also write the canonical document JSON")
    parser.add_argument("--check", action="store_true",
                        help="validate and report only; write nothing")
    parser.add_argument("--seed", type=int, help="seed the generated ids, for reproducible output")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{spec_path}: not valid JSON — {error}", file=sys.stderr)
        return 1

    try:
        document = build_document(spec, seed=args.seed)
        warnings = validate(document)
    except SpecError as error:
        print(f"{spec_path}: this spec cannot be drawn\n{error}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    drawings = sum(1 for n in document["nodes"].values() if n.get("parentId") == document["rootId"])
    bounds = canvas_bounds(document, document["rootId"])
    print(
        f"{document['title']}: {len(document['nodes']) - 1} nodes, "
        f"{drawings} on the top level, canvas {bounds['w']:.0f}x{bounds['h']:.0f}"
    )

    if args.check:
        return 0

    out = Path(args.out) if args.out else spec_path.with_suffix(".html")
    out.write_text(to_standalone_html(document), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")

    if args.json_out:
        json_out = out.with_suffix(".deepdraw.json") if args.json_out is True else Path(args.json_out)
        json_out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
