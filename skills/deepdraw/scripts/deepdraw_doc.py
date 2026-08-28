"""Turn an authoring spec into a canonical DeepDraw document.

The canonical document is what DeepDraw itself exports (see
`reference/document-format.md`): a flat `nodes` map keyed by id, with every
node carrying a *complete* `style` object. The spec this module accepts is the
same model written as a tree, with defaults left out. See `reference/spec.md`.

Nothing here talks to the network or to the browser; it is arithmetic on
dictionaries, so it can be imported and unit-tested on its own.
"""

from __future__ import annotations

import math
import random
import re
import string
from typing import Any

DOC_VERSION = 1

# --- what the checks here need to know about the model ------------------------
#
# A document written by this builder carries **only what the author set**, and
# every reader fills the rest in before anything renders: `normalizeDocument` in
# `lib/src/model.ts`, `DocumentDefaults` on the server, and the standalone page,
# which is the library again. So nothing below is a default waiting to be
# written into a file; a node is built from what the spec says and no more.
#
# What is mirrored from the library is the little the *checks* need in order to
# work out where things land on the paper: the size each type is drawn at, and
# where its text sits inside it. A new shape type only has to appear here if it
# differs from a rect in one of those two ways.

SHAPE_TYPES = {
    "root", "rect", "square", "ellipse", "diamond", "fatArrow",
    "container", "sticky", "text", "image", "icon", "arrow", "draw", "group",
}

#: Types the toolbar offers. `square` is legacy (a rect with radius 0) and
#: `root`/`group` are structural, so a spec should stick to these.
AUTHORABLE_TYPES = {
    "rect", "ellipse", "diamond", "fatArrow", "container", "sticky",
    "text", "image", "icon", "arrow", "draw",
}

STROKE_STYLES = {"solid", "dashed", "dotted"}
H_ALIGNS = {"left", "center", "right"}
V_ALIGNS = {"above", "top", "middle", "bottom", "below"}
SIDES = {"top", "right", "bottom", "left"}

#: Every style property the model has, as names only. Three of them carry
#: values here (below); the rest are listed so that a misspelled one can be
#: pointed out, because DeepDraw drops what it does not recognise in silence.
STYLE_KEYS = {
    "fill", "stroke", "strokeWidth", "strokeStyle", "radius", "textColor",
    "fontSize", "fontFamily", "hAlign", "vAlign", "opacity",
    "arrowStart", "arrowEnd",
}

#: How big a label is and where it sits when nothing says otherwise. These are
#: the only style *values* the checks read: everything else about a style is
#: colour, and colour cannot put a label on top of a box.
DEFAULT_TEXT_STYLE: dict[str, Any] = {
    "fontSize": 14,
    "hAlign": "center",
    "vAlign": "middle",
}

#: Types whose text sits somewhere other than the middle of the box, from
#: `TYPE_STYLE` in `model.ts`.
TYPE_TEXT_STYLE: dict[str, dict[str, Any]] = {
    "container": {"vAlign": "top"},
    # Paper, not a box: a sticky is written on from the corner you start
    # writing in, so its label begins at the top left.
    "sticky": {"hAlign": "left", "vAlign": "top"},
    "text": {"hAlign": "left"},
    # An icon and a picture are captioned underneath.
    "image": {"vAlign": "below"},
    "icon": {"vAlign": "below"},
}

#: The size each type is drawn at when the file does not say, from
#: `DEFAULT_SIZE` in `model.ts`.
DEFAULT_SIZE: dict[str, tuple[float, float]] = {
    "square": (120, 120),
    "ellipse": (140, 100),
    "diamond": (140, 100),
    "container": (320, 240),
    "sticky": (140, 140),
    "text": (160, 32),
    "image": (160, 120),
    "icon": (64, 64),
    "fatArrow": (160, 70),
}
FALLBACK_SIZE = (160.0, 100.0)

#: The smallest square a drawing is ever framed at, in document units. A
#: drawing smaller than this opens with room to spare around it, so laying out
#: inside roughly 300x300 or larger is what fills the pane.
MIN_CANVAS = 300

_ALPHABET = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_"


class SpecError(ValueError):
    """A spec that cannot become a document, with the reason a human needs."""


def nanoid(size: int = 12, rng: random.Random | None = None) -> str:
    r = rng or random
    return "".join(r.choice(_ALPHABET) for _ in range(size))


# --- reading a node that only says what it changed ---------------------------
#
# Everything below answers a question about a node the way DeepDraw will answer
# it when it reads the file: what type is this, whose drawing is it in, how big
# is it, where does its text sit. A node that says nothing gets the same answer
# the reader would give it, which is what lets the checks run over a file that
# is mostly absences.


def kind_of(node: dict[str, Any]) -> str:
    """`link` or `shape`; a `targetId` makes a node a link on its own."""
    return "link" if node.get("kind") == "link" or "targetId" in node else "shape"


def type_of(node: dict[str, Any], root_id: str | None = None) -> str:
    """The type a node is drawn as. A link is drawn as its target, but for size
    and text placement the reader treats it as a rect, so that is what it is."""
    if root_id is not None and node.get("id") == root_id:
        return "root"
    if kind_of(node) == "link":
        return "rect"
    return node.get("type") or "rect"


def parent_of(doc: dict[str, Any], node: dict[str, Any]) -> str | None:
    """Which drawing a node is in: what it says, the top level when it says
    nothing or names a node that is not here, and nothing at all for the root."""
    if node.get("id") == doc["rootId"]:
        return None
    parent = node.get("parentId")
    return parent if parent in doc["nodes"] else doc["rootId"]


def endpoint_of(node: dict[str, Any], which: str) -> dict[str, Any] | None:
    """An arrow end as an object. `"from": "api"` is the hand-written spelling
    of `{"nodeId": "api"}`, and the reader understands it, so this does too."""
    end = node.get(which)
    if isinstance(end, str):
        return {"nodeId": end}
    return end if isinstance(end, dict) else None


def _own_style(node: dict[str, Any]) -> dict[str, Any]:
    style = node.get("style")
    return style if isinstance(style, dict) else {}


def size_of(node: dict[str, Any], root_id: str | None = None) -> tuple[float, float]:
    """Width and height as drawn: what the node says, else its type's own size."""
    default_w, default_h = DEFAULT_SIZE.get(type_of(node, root_id), FALLBACK_SIZE)
    w = node.get("w")
    h = node.get("h")
    return (float(default_w if w is None else w), float(default_h if h is None else h))


def box_of(node: dict[str, Any], root_id: str | None = None) -> dict[str, float]:
    """A node's rectangle, with everything it left out filled in as drawn."""
    w, h = size_of(node, root_id)
    return {"x": float(node.get("x") or 0), "y": float(node.get("y") or 0), "w": w, "h": h}


def text_style(doc: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """Font size and alignment as drawn: the type's, then what the node names.

    A link shows its target's shape, so it starts from the target's style and
    layers its own overrides on top, the way `effectiveStyle` does in the app.
    """
    layers = [_own_style(node)]
    seen = {node.get("id")}
    current = node
    while kind_of(current) == "link":
        current = doc["nodes"].get(current.get("targetId")) or {}
        if current.get("id") in seen:
            break  # a link cycle; `validate` has more to say about it than this
        seen.add(current.get("id"))
        layers.append(_own_style(current))

    style = {**DEFAULT_TEXT_STYLE, **TYPE_TEXT_STYLE.get(type_of(current, doc["rootId"]), {})}
    for layer in reversed(layers):
        style.update({k: v for k, v in layer.items() if k in DEFAULT_TEXT_STYLE})
    return style


# --- numbers a person has to read --------------------------------------------


def whole_numbers(doc: dict[str, Any]) -> dict[str, Any]:
    """The same document with `760.0` written as `760`.

    The arithmetic here is in floats and the file is read by people; a
    coordinate with a pointless `.0` on it is noise in a diff.
    """
    return {**doc, "nodes": {k: _whole_numbers(v) for k, v in doc["nodes"].items()}}


def _whole_numbers(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _whole_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_whole_numbers(v) for v in value]
    return value


# --- spec -> document --------------------------------------------------------


def build_document(spec: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """The document for `spec`, validated and ready to write.

    A spec that is already a document (a `nodes` *mapping* plus a `rootId`) is
    taken as it stands instead, so a drawing exported from DeepDraw can be
    edited and fed straight back in.
    """
    if isinstance(spec.get("nodes"), dict) and spec.get("rootId"):
        return _adopt_document(spec)
    return _from_tree(spec, seed)


def _adopt_document(doc: dict[str, Any]) -> dict[str, Any]:
    """A document taken as it stands: nothing filled in, only what is missing
    from the *file* as a file.

    A node's id is its key, so a hand-written document does not have to say it
    twice; the checks below address nodes by id, so it is copied in. A drawing
    with no root node still describes a drawing, so it is given one, the way
    every reader does. Sizes, styles and alignments are left exactly as written,
    absences included: `size_of`, `text_style` and the rest answer for those.
    """
    root_id = doc["rootId"]
    out = {
        "version": doc.get("version", DOC_VERSION),
        "id": doc.get("id") or nanoid(),
        "title": doc.get("title") or "Untitled drawing",
        "rootId": root_id,
        "nodes": {},
    }
    for node_id, node in doc["nodes"].items():
        node = dict(node)
        node["id"] = node_id
        out["nodes"][node_id] = node

    out["nodes"].setdefault(root_id, {
        "id": root_id, "parentId": None, "index": 0, "type": "root", "w": 0, "h": 0,
    })
    validate(out)
    return whole_numbers(out)


def _from_tree(spec: dict[str, Any], seed: int | None) -> dict[str, Any]:
    rng = random.Random(seed) if seed is not None else None
    title = spec.get("title") or "Untitled drawing"
    root_id = spec.get("rootId") or "root"

    nodes: dict[str, Any] = {
        # The root's zero size is its own, not a default: the drawing is framed
        # by what it holds, and a root the size of a rect would frame it wrong.
        root_id: {
            "id": root_id,
            "parentId": None,
            "index": 0,
            "w": 0, "h": 0,
            "type": "root",
            # The drawing's own notes. They are what a reader sees the moment
            # the file opens, before anything is selected, so a drawing without
            # them starts on an empty panel and an unexplained picture.
            "markdown": spec.get("notes") or spec.get("markdown") or "",
        }
    }

    children = spec.get("shapes") or spec.get("nodes") or []
    if isinstance(children, dict):
        raise SpecError("a `nodes` mapping is a canonical document: it needs a `rootId` too")
    if not isinstance(children, list):
        raise SpecError("`shapes` must be a list of nodes")

    used: set[str] = {root_id}
    _add_children(children, root_id, root_id, nodes, used, rng)

    doc = {
        "version": DOC_VERSION,
        "id": spec.get("id") or nanoid(rng=rng),
        "title": title,
        "rootId": root_id,
        "nodes": nodes,
    }
    validate(doc)
    return whole_numbers(doc)


def _add_children(
    items: list[dict[str, Any]],
    parent_id: str,
    root_id: str,
    nodes: dict[str, Any],
    used: set[str],
    rng: random.Random | None,
) -> None:
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SpecError(f"node {index} under {parent_id!r} is not an object")
        node_id = item.get("id") or nanoid(rng=rng)
        if node_id in used:
            raise SpecError(f"duplicate node id {node_id!r}")
        used.add(node_id)

        node = _node_from_item(item, node_id, parent_id, root_id, index)
        nodes[node_id] = node

        nested = item.get("children") or []
        if nested:
            if not isinstance(nested, list):
                raise SpecError(f"`children` of {node_id!r} must be a list")
            _add_children(nested, node_id, root_id, nodes, used, rng)


def _node_from_item(
    item: dict[str, Any], node_id: str, parent_id: str, root_id: str, index: int
) -> dict[str, Any]:
    """One node, carrying what the author wrote and nothing else.

    No size, no style, no alignment is filled in here. DeepDraw fills its own
    defaults in wherever the file is read, so a node saying only `type` is a
    whole node, and one that says more says it because the author meant it.

    What is added is what the file cannot work out for itself: the node's id,
    which drawing it is in, and its place among its siblings. Even the parent is
    left out at the top level, where an absent one already means exactly that.
    """
    node: dict[str, Any] = {"id": node_id, "index": int(item.get("index", index))}
    if parent_id != root_id:
        node["parentId"] = parent_id
    for field in ("x", "y", "w", "h", "rotation"):
        if item.get(field) is not None:
            node[field] = float(item[field])
    if item.get("style"):
        node["style"] = dict(item["style"])
    if item.get("groupId"):
        node["groupId"] = item["groupId"]

    # A link borrows its target's content; only geometry and overrides are its own.
    if "link" in item:
        # Anything else here would be dropped on the floor, and the author would
        # go on believing the panel says what they wrote. It does not: it says
        # what the target says.
        ignored = [k for k in ("notes", "markdown", "type", "href", "points") if item.get(k)]
        if ignored:
            raise SpecError(
                f"link node {node_id!r} carries {', '.join(ignored)}, which a link "
                f"cannot have: it shows its target's notes and its target's nested "
                f"drawing. A link takes x, y, w, h, text and style, and nothing else"
            )
        node["kind"] = "link"
        node["targetId"] = item["link"]
        if item.get("text"):
            node["text"] = item["text"]
        return node

    node_type = item.get("type", "rect")
    if node_type not in SHAPE_TYPES:
        raise SpecError(f"node {node_id!r} has unknown type {node_type!r}")
    if node_type != "rect":
        node["type"] = node_type
    if item.get("text"):
        node["text"] = item["text"]
    markdown = item.get("markdown") or item.get("notes")
    if markdown:
        node["markdown"] = markdown

    if node_type == "arrow":
        node["from"] = _endpoint(item.get("from"), node_id, "from")
        node["to"] = _endpoint(item.get("to"), node_id, "to")
        if item.get("fromSide"):
            node["from"]["side"] = item["fromSide"]
        if item.get("toSide"):
            node["to"]["side"] = item["toSide"]

    if item.get("href"):
        node["href"] = item["href"]
    if item.get("points"):
        node["points"] = [float(p) for p in item["points"]]
    return node


def _endpoint(value: Any, node_id: str, which: str) -> dict[str, Any]:
    """An arrow end: a node id, `{node, side}`, or a free `{x, y}` point."""
    if value is None:
        raise SpecError(f"arrow {node_id!r} has no `{which}`")
    if isinstance(value, str):
        return {"nodeId": value}
    if isinstance(value, dict):
        end: dict[str, Any] = {}
        target = value.get("node") or value.get("nodeId")
        if target:
            end["nodeId"] = target
        if value.get("side"):
            end["side"] = value["side"]
        if "x" in value:
            end["x"] = float(value["x"])
        if "y" in value:
            end["y"] = float(value["y"])
        if not end:
            raise SpecError(f"arrow {node_id!r} has an empty `{which}`")
        return end
    raise SpecError(f"arrow {node_id!r} has a `{which}` that is neither an id nor an object")


# --- geometry ----------------------------------------------------------------


def _border_point_toward(rect: dict[str, float], toward: tuple[float, float]) -> tuple[float, float]:
    cx = rect["x"] + rect["w"] / 2
    cy = rect["y"] + rect["h"] / 2
    dx = toward[0] - cx
    dy = toward[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = min(
        float("inf") if dx == 0 else (rect["w"] / 2) / abs(dx),
        float("inf") if dy == 0 else (rect["h"] / 2) / abs(dy),
    )
    return cx + dx * scale, cy + dy * scale


def _side_point(rect: dict[str, float], side: str) -> tuple[float, float]:
    if side == "top":
        return rect["x"] + rect["w"] / 2, rect["y"]
    if side == "bottom":
        return rect["x"] + rect["w"] / 2, rect["y"] + rect["h"]
    if side == "left":
        return rect["x"], rect["y"] + rect["h"] / 2
    return rect["x"] + rect["w"], rect["y"] + rect["h"] / 2


def arrow_points(doc: dict[str, Any], node: dict[str, Any]):
    """Both ends of an arrow in document coordinates, the way `geometry.ts` does.

    Each end is resolved *toward* the other, which is why an arrow between two
    boxes meets their borders rather than their centres.
    """
    nodes = doc["nodes"]
    root_id = doc["rootId"]
    start = endpoint_of(node, "from")
    end_ = endpoint_of(node, "to")
    src = nodes.get((start or {}).get("nodeId"))
    dst = nodes.get((end_ or {}).get("nodeId"))
    own = box_of(node, root_id)

    def centre(n):
        rect = box_of(n, root_id)
        return rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2

    from_hint = centre(dst) if dst else (
        (end_ or {}).get("x", own["x"] + own["w"]),
        (end_ or {}).get("y", own["y"] + own["h"]),
    )
    to_hint = centre(src) if src else (
        (start or {}).get("x", own["x"]),
        (start or {}).get("y", own["y"]),
    )

    def anchor(end, toward):
        if not end:
            return toward
        target = nodes.get(end.get("nodeId"))
        if not target:
            return end.get("x", toward[0]), end.get("y", toward[1])
        rect = box_of(target, root_id)
        if end.get("side"):
            return _side_point(rect, end["side"])
        return _border_point_toward(rect, toward)

    return anchor(start, from_hint), anchor(end_, to_hint)


def rect_of(doc: dict[str, Any], node: dict[str, Any]) -> dict[str, float]:
    """The rectangle a node is drawn in.

    An arrow's is the box its line spans, worked out from the endpoints every
    time rather than stored on the node: that is what the renderer does with it
    (`boundsOf` in `shapes.ts`), so an arrow in a file never has to carry a box
    of its own, and one that carries a stale box is not believed.
    """
    if kind_of(node) == "shape" and type_of(node, doc["rootId"]) == "arrow":
        (ax, ay), (bx, by) = arrow_points(doc, node)
        return {"x": min(ax, bx), "y": min(ay, by), "w": abs(ax - bx), "h": abs(ay - by)}
    return box_of(node, doc["rootId"])


def canvas_bounds(doc: dict[str, Any], drawing_id: str) -> dict[str, float]:
    """The paper one drawing opens on: its contents, never smaller than MIN_CANVAS."""
    children = [rect_of(doc, n) for n in doc["nodes"].values() if parent_of(doc, n) == drawing_id]
    if not children:
        return {"x": 0.0, "y": 0.0, "w": float(MIN_CANVAS), "h": float(MIN_CANVAS)}
    xs0 = min(n["x"] for n in children)
    ys0 = min(n["y"] for n in children)
    xs1 = max(n["x"] + n["w"] for n in children)
    ys1 = max(n["y"] + n["h"] for n in children)
    w = max(xs1 - xs0, MIN_CANVAS)
    h = max(ys1 - ys0, MIN_CANVAS)
    return {
        "x": xs0 + ((xs1 - xs0) - w) / 2,
        "y": ys0 + ((ys1 - ys0) - h) / 2,
        "w": w,
        "h": h,
    }


# --- validation --------------------------------------------------------------


# Mirrors the viewer: @[any label here] or a single bare @token. JS `\w` is
# ASCII, so spell the classes out rather than using Python's Unicode \w.
_MENTION_RE = re.compile(r"@(?:\[([^\]\n]{1,60})\]|([A-Za-z0-9_][A-Za-z0-9_.-]{0,59}))")
_FENCED_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _mention_warnings(doc: dict[str, Any]) -> list[str]:
    """A mention still renders as a chip when it matches nothing, so flag those.

    The viewer resolves one by comparing the label against a node's *entire*
    `text`, case-insensitively, which is why a multi-line label can never be
    reached, even though the tree lists it by its first line.
    """
    nodes = doc["nodes"]
    root_id = doc["rootId"]

    labels: set[str] = set()
    for node_id, node in nodes.items():
        if node_id == root_id:
            continue
        text = node.get("text")
        if text is None and kind_of(node) == "link":
            target = nodes.get(node.get("targetId")) or {}
            text = target.get("text")
        if text and text.strip():
            labels.add(text.strip().lower())

    # First lines of multi-line labels: the shapes the tree makes look mentionable.
    first_line = {t.split("\n", 1)[0].strip(): t for t in labels if "\n" in t}

    warnings: list[str] = []
    for node_id, node in nodes.items():
        notes = node.get("markdown") or ""
        if "@" not in notes:
            continue
        # The viewer skips mentions inside code spans and fences; so do we.
        scannable = _INLINE_CODE_RE.sub(" ", _FENCED_RE.sub(" ", notes))
        for match in _MENTION_RE.finditer(scannable):
            label = (match.group(1) or match.group(2) or "").strip()
            if not label or label.lower() in labels:
                continue
            hint = ""
            if label.lower() in first_line:
                hint = ": that shape's label has a second line, so it cannot be mentioned"
            elif match.group(2):
                hint = ": bracket it as @[…] if the label is more than one word"
            warnings.append(f"{node_id!r}: notes mention @{label} but no shape has that label{hint}")
    return warnings


# --- crowding, scale, and the house style ------------------------------------

#: Rough advance width of one character, as a fraction of the font size. The
#: renderer never measures text (it hands an SVG `<text>` to the browser), so
#: this is the same estimate `reference/layout.md` tells an author to size a
#: box with. It is why the checks below allow a few units of slack.
CHAR_WIDTH = 0.58
LINE_HEIGHT = 1.25  # `wn()` in the viewer: fontSize * 1.25 per line
TEXT_PAD = 6        # and its 6 units of padding inside the box

#: How far two things may overlap before it is worth saying so. Small numbers
#: are the estimate above being wrong; large ones are a label nobody can read.
CROWDING_SLACK = 6.0
MAX_CROWDING_WARNINGS = 40

#: Types with a body drawn on the paper, which a label or a line can be lost
#: against. A `container` is meant to enclose things and a `draw` is meant to be
#: scribbled over them, so neither counts as being in the way.
SOLID_TYPES = {"rect", "square", "ellipse", "diamond", "fatArrow", "sticky", "image", "icon"}


def label_box(doc: dict[str, Any], node: dict[str, Any]) -> dict[str, float] | None:
    """Where a node's label actually lands, the way `wn()` in the viewer puts it.

    Labels never wrap, so the width comes from the longest line and not from
    the node's `w`: a `text` node or an `icon` caption routinely draws well
    outside its own box, which is exactly how it ends up on top of a neighbour.
    """
    text = (node.get("text") or "").strip()
    if not text:
        return None
    style = text_style(doc, node)
    rect = rect_of(doc, node)
    size = float(style["fontSize"])
    lines = text.split("\n")
    w = max(len(line) for line in lines) * size * CHAR_WIDTH
    h = len(lines) * size * LINE_HEIGHT

    if style["hAlign"] == "left":
        x = rect["x"] + TEXT_PAD
    elif style["hAlign"] == "right":
        x = rect["x"] + rect["w"] - TEXT_PAD - w
    else:
        x = rect["x"] + (rect["w"] - w) / 2

    v_align = style["vAlign"]
    if v_align == "above":
        y = rect["y"] - h - TEXT_PAD
    elif v_align == "top":
        y = rect["y"] + TEXT_PAD
    elif v_align == "bottom":
        y = rect["y"] + rect["h"] - h - TEXT_PAD
    elif v_align == "below":
        y = rect["y"] + rect["h"] + TEXT_PAD
    else:
        y = rect["y"] + (rect["h"] - h) / 2
    return {"x": x, "y": y, "w": w, "h": h}


def _contains(outer: dict[str, float], inner: dict[str, float]) -> bool:
    return (
        inner["x"] >= outer["x"] and inner["y"] >= outer["y"]
        and inner["x"] + inner["w"] <= outer["x"] + outer["w"]
        and inner["y"] + inner["h"] <= outer["y"] + outer["h"]
    )


def _join(ids: list[str]) -> str:
    quoted = [repr(i) for i in ids]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + " and " + quoted[-1]


def _overlap(a: dict[str, float], b: dict[str, float]) -> tuple[float, float]:
    return (
        min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]),
        min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]),
    )


def _crosses(p1: tuple[float, float], p2: tuple[float, float], rect: dict[str, float]) -> bool:
    """Does the segment pass through the rect, shrunk by the usual slack?

    Liang-Barsky, which is short and does not care which way the segment runs.
    """
    x0, y0 = rect["x"] + CROWDING_SLACK, rect["y"] + CROWDING_SLACK
    x1, y1 = rect["x"] + rect["w"] - CROWDING_SLACK, rect["y"] + rect["h"] - CROWDING_SLACK
    if x1 <= x0 or y1 <= y0:
        return False
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p1[0] - x0), (dx, x1 - p1[0]), (-dy, p1[1] - y0), (dy, y1 - p1[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


#: An em dash and its wider cousin. SKILL.md rules them out of every label and
#: every note, and one is easy to miss in a wall of prose.
_EM_DASHES = ("\u2014", "\u2015")


def _dash_warnings(doc: dict[str, Any]) -> list[str]:
    """Em dashes, which the skill bans and which are invisible in a diff."""
    warnings: list[str] = []
    if any(d in (doc.get("title") or "") for d in _EM_DASHES):
        warnings.append("the title has an em dash in it; use a comma, a colon or a full stop")
    for node_id, node in sorted(doc["nodes"].items()):
        for field in ("text", "markdown"):
            value = node.get(field) or ""
            if any(d in value for d in _EM_DASHES):
                where = "label" if field == "text" else "notes"
                warnings.append(
                    f"{node_id!r}: an em dash in its {where}; use a comma, a colon or a full stop"
                )
                break
    return warnings


def drawing_extents(doc: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """The raw width and height of each drawing's contents, keyed by the node
    you click into. Unlike `canvas_bounds` this does not clamp to MIN_CANVAS,
    because what matters here is how big the drawing is against its siblings."""
    extents: dict[str, tuple[float, float]] = {}
    for parent, kids in _by_drawing(doc).items():
        rects = [rect_of(doc, n) for n in kids]
        extents[parent] = (
            max(r["x"] + r["w"] for r in rects) - min(r["x"] for r in rects),
            max(r["y"] + r["h"] for r in rects) - min(r["y"] for r in rects),
        )
    return extents


def _by_drawing(doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """The nodes of each drawing, keyed by the node you click into."""
    drawings: dict[str, list[dict[str, Any]]] = {}
    for node in doc["nodes"].values():
        parent = parent_of(doc, node)
        if parent is not None:
            drawings.setdefault(parent, []).append(node)
    return drawings


#: The drawing pane, in CSS pixels, on a laptop-sized window. The hierarchy
#: tree and the notes panel take about half of it, so a 1280-wide window leaves
#: roughly 690x700 for the drawing, and the 32-unit fit padding takes the rest.
#: A level laid out this wide arrives on screen at about 1:1.
PANE = (620.0, 640.0)

#: Below this, in CSS pixels, a label is there but nobody reads it.
MIN_READABLE_PX = 11.0


def _readability_warnings(doc: dict[str, Any]) -> list[str]:
    """Levels laid out so wide that their own labels come out too small.

    A drawing is fitted to the pane, text and all, so the apparent size of a
    label is `fontSize x (pane / drawing width)`. Lay a level out 1200 units
    wide and `fontSize: 14` reaches the reader at 9 px. The file renders
    perfectly and says nothing about it.
    """
    extents = drawing_extents(doc)
    children = _by_drawing(doc)

    warnings: list[str] = []
    for drawing_id, (w, h) in sorted(extents.items()):
        w = max(w, float(MIN_CANVAS))
        h = max(h, float(MIN_CANVAS))
        scale = min(PANE[0] / w, PANE[1] / h)
        if scale >= 1:
            continue
        sizes = [
            float(text_style(doc, n)["fontSize"])
            for n in children.get(drawing_id, [])
            if (n.get("text") or "").strip()
        ]
        if not sizes:
            continue
        smallest = min(sizes)
        rendered = smallest * scale
        if rendered >= MIN_READABLE_PX:
            continue
        wants = math.ceil(MIN_READABLE_PX / scale)
        warnings.append(
            f"{drawing_id!r}: this drawing is {w:.0f}x{h:.0f}, so it is shrunk to "
            f"{scale:.2f}x to fit the pane and its {smallest:.0f}pt labels reach the "
            f"reader at {rendered:.0f} px; lay it out closer to {PANE[0]:.0f} wide, or "
            f"raise every fontSize in it to about {wants:.0f}"
        )
    return warnings


def _scale_warnings(doc: dict[str, Any]) -> list[str]:
    """Levels laid out at wildly different scales.

    Every drawing is fitted to the pane, so a 400-unit drawing is simply a
    zoomed-in one: the same `fontSize: 14` comes out three times the size of
    the same label a level up. Nothing about the file says so, and the author
    only finds out by clicking through.
    """
    extents = drawing_extents(doc)
    if len(extents) < 3:
        return []
    widths = sorted(w for w, _ in extents.values())
    median = widths[len(widths) // 2]
    if median <= 0:
        return []

    warnings: list[str] = []
    for drawing_id, (w, _) in sorted(extents.items()):
        if w <= 0:
            continue
        if w * 2 < median or w > median * 2:
            factor = median / w if w < median else w / median
            bigger = "bigger" if w < median else "smaller"
            warnings.append(
                f"{drawing_id!r}: this drawing is {w:.0f} wide where most here are "
                f"about {median:.0f}, so its labels come out {factor:.1f}x {bigger} "
                f"than the rest; lay every level out at about the same width"
            )
    return warnings


def _crowding_warnings(doc: dict[str, Any]) -> list[str]:
    """Things drawn on top of each other: the failure the file itself cannot show.

    Everything here renders perfectly happily. A label sitting across a box is
    still drawn, in full, with no background behind it, and the only way to find
    out is to open the drawing and look. So look here instead, one drawing at a
    time, since coordinates only mean anything within one.
    """
    root_id = doc["rootId"]
    warnings: list[str] = []
    for siblings in _by_drawing(doc).values():
        siblings = sorted(siblings, key=lambda n: n["id"])
        rects = {n["id"]: rect_of(doc, n) for n in siblings}
        solids = [
            n for n in siblings
            if kind_of(n) == "link" or type_of(n, root_id) in SOLID_TYPES
        ]
        labels = [(n, label_box(doc, n)) for n in siblings if type_of(n, root_id) != "container"]
        labels = [(n, box) for n, box in labels if box]
        solid_ids = {n["id"] for n in solids}

        for node, box in labels:
            over = [
                other["id"] for other in solids
                if other["id"] != node["id"]
                and all(d > CROWDING_SLACK for d in _overlap(box, rects[other["id"]]))
            ]
            if over:
                what = "label" if type_of(node, root_id) == "arrow" else "text"
                warnings.append(
                    f"{node['id']!r}: its {what} {_short(node)} is drawn across "
                    f"{_join(over)}; widen the gap, shorten it, or move it"
                )

        # Labels that leave their own box (an arrow's, a caption, an icon's
        # text, which is drawn below the glyph) can also land on each other.
        # A label that stays inside a shape is that shape, and was checked above.
        stray = [
            (n, box) for n, box in labels
            if n["id"] not in solid_ids or not _contains(rects[n["id"]], box)
        ]
        for i, (node, box) in enumerate(stray):
            for other, other_box in stray[i + 1:]:
                if all(d > CROWDING_SLACK for d in _overlap(box, other_box)):
                    warnings.append(
                        f"{node['id']!r}: its text {_short(node)} lands on the "
                        f"label of {other['id']!r}"
                    )

        for node in siblings:
            if kind_of(node) != "shape" or type_of(node, root_id) != "arrow":
                continue
            ends = {(endpoint_of(node, w) or {}).get("nodeId") for w in ("from", "to")}
            p1, p2 = arrow_points(doc, node)
            for other in solids:
                if other["id"] in ends:
                    continue
                if _crosses(p1, p2, rects[other["id"]]):
                    warnings.append(
                        f"{node['id']!r}: the line runs through {other['id']!r}, which is "
                        f"neither end of it; an arrow is a straight line, so move a box "
                        f"or pin a `side`"
                    )

        for i, node in enumerate(solids):
            for other in solids[i + 1:]:
                dx, dy = _overlap(rects[node["id"]], rects[other["id"]])
                if dx > CROWDING_SLACK and dy > CROWDING_SLACK:
                    warnings.append(
                        f"{node['id']!r} and {other['id']!r} overlap by "
                        f"{dx:.0f}x{dy:.0f}: two shapes on the same paper"
                    )

    if len(warnings) > MAX_CROWDING_WARNINGS:
        extra = len(warnings) - MAX_CROWDING_WARNINGS
        warnings = warnings[:MAX_CROWDING_WARNINGS]
        warnings.append(f"and {extra} more crowded places, not listed")
    return warnings


def _short(node: dict[str, Any], limit: int = 28) -> str:
    text = (node.get("text") or "").replace("\n", " ")
    return repr(text if len(text) <= limit else text[: limit - 1] + "\u2026")


def validate(doc: dict[str, Any]) -> list[str]:
    """Raises SpecError on anything that would not render; returns warnings."""
    nodes = doc["nodes"]
    root_id = doc["rootId"]
    problems: list[str] = []
    warnings: list[str] = []

    if root_id not in nodes:
        raise SpecError(f"rootId {root_id!r} is not in `nodes`")

    for node_id, node in nodes.items():
        if node.get("id") != node_id:
            problems.append(f"{node_id!r}: `id` does not match its key")
        if node.get("kind") not in (None, "shape", "link"):
            problems.append(f"{node_id!r}: kind must be 'shape' or 'link'")
            continue
        kind = kind_of(node)

        # A parent naming nothing is not an error: every reader takes it for the
        # top level. It is rarely what somebody meant by it, though.
        if node_id == root_id:
            if node.get("parentId") is not None:
                problems.append("the root node must have parentId null")
        elif node.get("parentId") is not None and node["parentId"] not in nodes:
            warnings.append(
                f"{node_id!r}: parentId {node['parentId']!r} is not a node, so this "
                f"is read as being on the top level"
            )
        parent = parent_of(doc, node)

        if kind == "link":
            if node.get("targetId") not in nodes:
                problems.append(f"{node_id!r}: link target {node.get('targetId')!r} is not a node")
            continue

        node_type = type_of(node, root_id)
        if node.get("type") is not None and node["type"] not in SHAPE_TYPES:
            problems.append(f"{node_id!r}: unknown type {node['type']!r}")

        # A style says what it changes and nothing else, so there is nothing to
        # be missing. What can go wrong is a value the renderer will not take,
        # and a property name it does not know, which it drops without a word.
        style = node.get("style")
        if style is not None and not isinstance(style, dict):
            problems.append(f"{node_id!r}: `style` must be an object")
        elif isinstance(style, dict):
            for key in sorted(set(style) - STYLE_KEYS):
                warnings.append(
                    f"{node_id!r}: style has no property {key!r}, so it is ignored"
                )
            for key, allowed in (
                ("strokeStyle", STROKE_STYLES), ("hAlign", H_ALIGNS), ("vAlign", V_ALIGNS),
            ):
                if key in style and style[key] not in allowed:
                    problems.append(f"{node_id!r}: {key} must be one of {sorted(allowed)}")

        if node_type == "arrow":
            for which in ("from", "to"):
                end = endpoint_of(node, which)
                if not isinstance(end, dict):
                    problems.append(f"{node_id!r}: arrow needs a `{which}` endpoint")
                    continue
                if end.get("side") and end["side"] not in SIDES:
                    problems.append(f"{node_id!r}: `{which}.side` must be one of {sorted(SIDES)}")
                target_id = end.get("nodeId")
                if target_id is None:
                    if "x" not in end or "y" not in end:
                        problems.append(f"{node_id!r}: a free `{which}` needs both x and y")
                elif target_id not in nodes:
                    problems.append(f"{node_id!r}: `{which}` points at unknown node {target_id!r}")
                elif parent_of(doc, nodes[target_id]) != parent:
                    # Coordinates only mean something within one drawing, so an
                    # arrow reaching into another one lands somewhere arbitrary.
                    warnings.append(
                        f"{node_id!r}: `{which}` is in another drawing, so "
                        f"put a link node in {parent!r} and point at that instead"
                    )

        if node_type == "draw":
            points = node.get("points") or []
            if len(points) < 4 or len(points) % 2:
                problems.append(f"{node_id!r}: `points` needs an even count of at least 4")
        if node_type in ("image", "icon") and not node.get("href"):
            warnings.append(f"{node_id!r}: {node_type} has no `href`, so it draws as a placeholder")

    # The drawing's own notes are the first thing a reader sees: the panel is
    # open before anything is selected, so a drawing without them opens on an
    # empty panel beside a picture nobody has introduced.
    root = nodes[root_id]
    if not (root.get("markdown") or "").strip():
        warnings.append(
            "the drawing has no notes of its own: put a `notes` string at the top "
            "level of the spec saying what this is and where to look first"
        )

    warnings.extend(_mention_warnings(doc))
    warnings.extend(_dash_warnings(doc))
    warnings.extend(_crowding_warnings(doc))
    warnings.extend(_scale_warnings(doc))
    warnings.extend(_readability_warnings(doc))

    # A cycle would make the tree infinite; the renderer walks it by parentId.
    for node_id in nodes:
        seen = set()
        cur = node_id
        while cur is not None and cur not in seen:
            seen.add(cur)
            cur = parent_of(doc, nodes[cur]) if cur in nodes else None
        if cur is not None:
            problems.append(f"{node_id!r}: parentId chain is a cycle")
            break

    if problems:
        raise SpecError("\n".join("- " + p for p in problems))
    return warnings
