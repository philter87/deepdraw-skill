#!/usr/bin/env python3
"""Wrap a drawing spec in DeepDraw's standalone-HTML export format.

    python3 build_html.py spec.json -o drawing.html

The result is byte-for-byte the kind of file DeepDraw's "Export → HTML" button
writes: the library inlined, and the document in a
`<script id="dd-document" type="application/json">`. It opens on its own in a
browser and imports back into deepdraw.ai through Import → File.

`--json` writes the canonical document beside it, which is the other format
deepdraw.ai imports.

The page opens **editable**: whoever has the file can move shapes, write notes
and press Save to write the file back. `--view-only` builds the read-only page
instead.

An `image` node's `href` may be a `data:` URI, a path to a file beside the spec,
or an http(s) address; the last two are read in and inlined here, so what is
written stands on its own (`inline_images.py` says why that matters).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deepdraw_doc import SpecError, build_document, canvas_bounds, parent_of, validate  # noqa: E402
from inline_images import ImageError, inline_images  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "reference" / "template.html"
TITLE_MARK = "__DEEPDRAW_TITLE__"
DOCUMENT_MARK = "__DEEPDRAW_DOCUMENT_JSON__"
CREDIT_MARK = "__DEEPDRAW_CREDIT__"

# The corner's second name. DeepDraw signs the page it writes; a page this skill
# wrote is signed by the skill too, because whoever wants another drawing like
# this one wants the thing that made it. The shape is `toStandaloneHtml`'s own,
# so a file from here and a file exported from the app are the same file.
CREDIT = (
    ' &middot; <a href="https://github.com/philter87/deepdraw-skill"'
    ' target="_blank" rel="noreferrer noopener">deepdraw-skill</a>'
)

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


def fill(template: str, mark: str, value: str) -> str:
    """Fills one hole, and insists there was exactly one of it.

    The count is the whole point. The template inlines DeepDraw's bundle, and
    that bundle *states these marks itself* — `TEMPLATE_MARKS` is one of its
    exports. A template built the old way (export a drawing, cut the pieces back
    out with a regex) therefore carried a second copy of every mark inside the
    minified source, and this replacement filled that one in too: the drawing's
    title and its entire JSON spliced into a string literal in the library. The
    page loaded, the script failed to parse, and nothing rendered at all — for
    every drawing this skill produced.

    `templateHtml` on the library side now hides its own copies, so there is
    genuinely one of each. This is what says so instead of assuming it: a
    template that regains a duplicate is a loud failure here rather than a blank
    page somebody else opens.
    """
    found = template.count(mark)
    if found != 1:
        raise SystemExit(
            f"{TEMPLATE}: {mark} appears {found} times, not once — "
            "rebuild it with `node tools/build-template.mjs`."
        )
    return template.replace(mark, value)


def to_standalone_html(document: dict, allow_edit: bool = True) -> str:
    """The page for `document`. Editable unless told otherwise.

    `allowEdit` sits *beside* the document rather than in it — it is about this
    file, not about the drawing — and the page's bootstrap reads it to decide
    whether it opens in edit mode with a Save button or as a read-only view.
    A drawing is something to think with, so the default is the editable one:
    whoever opens the page can move a box, write a note and save the file back.
    A page built with `--view-only` is the exception, for handing a drawing to
    someone who should read it and not change it.
    """
    payload = dict(document)
    if allow_edit:
        payload["allowEdit"] = True
    template = TEMPLATE.read_text(encoding="utf-8")
    html = fill(template, TITLE_MARK, escape_html(document.get("title") or "DeepDraw"))
    html = fill(html, DOCUMENT_MARK, embed(payload))
    return fill(html, CREDIT_MARK, CREDIT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", help="the drawing spec, or a canonical DeepDraw document")
    parser.add_argument("-o", "--out", help="where to write the HTML (default: <spec>.html)")
    parser.add_argument("--json", dest="json_out", nargs="?", const=True,
                        help="also write the canonical document JSON")
    parser.add_argument("--check", action="store_true",
                        help="validate and report only; write nothing")
    parser.add_argument("--view-only", dest="view_only", action="store_true",
                        help="build a read-only page (default: the page opens editable and can save itself back)")
    parser.add_argument("--seed", type=int, help="seed the generated ids, for reproducible output")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{spec_path}: not valid JSON. {error}", file=sys.stderr)
        return 1

    try:
        document = build_document(spec, seed=args.seed)
        warnings = validate(document)
    except SpecError as error:
        print(f"{spec_path}: this spec cannot be drawn\n{error}", file=sys.stderr)
        return 1

    # Pictures become the bytes themselves, so the file that leaves here needs
    # nothing else to render. A picture that cannot be read is a refusal rather
    # than a warning: a drawing quietly missing the image somebody asked for is
    # the exact failure inlining exists to prevent.
    try:
        warnings += inline_images(document, spec_path.resolve().parent)
    except ImageError as error:
        print(f"{spec_path}: this drawing's pictures could not be read\n{error}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    drawings = sum(1 for n in document["nodes"].values() if parent_of(document, n) == document["rootId"])
    bounds = canvas_bounds(document, document["rootId"])
    print(
        f"{document['title']}: {len(document['nodes']) - 1} nodes, "
        f"{drawings} on the top level, canvas {bounds['w']:.0f}x{bounds['h']:.0f}"
    )

    if args.check:
        return 0

    # The document says what the author changed and nothing else: DeepDraw
    # fills its own defaults in wherever the file is read, which is what makes
    # the JSON beside it something a person can read and edit.
    out = Path(args.out) if args.out else spec_path.with_suffix(".html")
    out.write_text(to_standalone_html(document, allow_edit=not args.view_only), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")

    if args.json_out:
        json_out = out.with_suffix(".deepdraw.json") if args.json_out is True else Path(args.json_out)
        json_out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
