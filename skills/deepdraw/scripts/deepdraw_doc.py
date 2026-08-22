"""Turn an authoring spec into a canonical DeepDraw document.

The canonical document is what DeepDraw itself exports (see
`reference/document-format.md`): a flat `nodes` map keyed by id, with every
node carrying a *complete* `style` object. The spec this module accepts is the
same model written as a tree, with defaults left out. See `reference/spec.md`.

Nothing here talks to the network or to the browser; it is arithmetic on
dictionaries, so it can be imported and unit-tested on its own.
"""

from __future__ import annotations

import random
import re
import string
from typing import Any

DOC_VERSION = 1

# --- the pieces of the model the library defines -----------------------------

SHAPE_TYPES = {
    "root", "rect", "square", "ellipse", "diamond", "fatArrow",
    "container", "text", "image", "icon", "arrow", "draw", "group",
}

#: Types the toolbar offers. `square` is legacy (a rect with radius 0) and
#: `root`/`group` are structural, so a spec should stick to these.
AUTHORABLE_TYPES = {
    "rect", "ellipse", "diamond", "fatArrow", "container",
    "text", "image", "icon", "arrow", "draw",
}

STROKE_STYLES = {"solid", "dashed", "dotted"}
H_ALIGNS = {"left", "center", "right"}
V_ALIGNS = {"above", "top", "middle", "bottom", "below"}
SIDES = {"top", "right", "bottom", "left"}

DEFAULT_STYLE: dict[str, Any] = {
    "fill": "#ffffff",
    "stroke": "#334155",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "radius": 8,
    "textColor": "#0f172a",
    "fontSize": 14,
    "fontFamily": "system-ui, sans-serif",
    "hAlign": "center",
    "vAlign": "middle",
    "opacity": 1,
}

#: Per-type deviations from DEFAULT_STYLE, exactly as `model.ts` applies them.
TYPE_STYLE: dict[str, dict[str, Any]] = {
    "root": {"fill": "transparent", "stroke": "transparent", "strokeWidth": 0, "radius": 0},
    "square": {"radius": 0},
    "ellipse": {"radius": 0},
    "diamond": {"radius": 0},
    "container": {"fill": "transparent", "strokeStyle": "dashed", "vAlign": "top", "radius": 4},
    "text": {"fill": "transparent", "stroke": "transparent", "strokeWidth": 0, "hAlign": "left"},
    "image": {"fill": "transparent", "stroke": "transparent", "strokeWidth": 0, "vAlign": "below"},
    "icon": {"fill": "transparent", "stroke": "transparent", "strokeWidth": 0, "vAlign": "below"},
    "arrow": {"fill": "none", "strokeWidth": 2},
    "draw": {"fill": "none", "strokeWidth": 2, "radius": 0},
    "fatArrow": {"fill": "#e2e8f0"},
    "group": {"fill": "transparent", "stroke": "transparent", "strokeWidth": 0},
}

DEFAULT_SIZE: dict[str, tuple[float, float]] = {
    "square": (120, 120),
    "ellipse": (140, 100),
    "diamond": (140, 100),
    "container": (320, 240),
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


def style_for(node_type: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """A complete style object: defaults, then per-type, then the overrides."""
    style = dict(DEFAULT_STYLE)
    style.update(TYPE_STYLE.get(node_type, {}))
    style.update(overrides or {})
    return style


# --- document -> a smaller file ----------------------------------------------


def compact(doc: dict[str, Any]) -> dict[str, Any]:
    """The same document with everything DeepDraw already assumes left out.

    DeepDraw's reader fills defaults in on the way back (``normalizeDocument``
    in the library, ``DocumentDefaults`` on the server, and the boot script of
    the standalone page), so a file does not have to spell out eleven style
    properties per shape that are already the type's own. It is the same
    document, written the way a person would write it: what changed, and
    nothing else.

    Only what the reader is guaranteed to reconstruct is dropped:

    - ``kind`` when it is ``shape``, ``type`` when it is ``rect``.
    - ``x``/``y`` at 0, ``rotation`` at 0, ``text``/``markdown`` empty.
    - ``w``/``h`` when they equal the type's default size.
    - Style properties equal to the type's default, and ``style`` itself when
      that leaves it empty.
    - ``parentId`` when it is the root, since a parentless node is top level.

    ``index`` and ``id`` stay. Order among siblings is what ``index`` carries,
    and a reader falling back on declaration order would put it at the mercy of
    how some JSON library happened to sort the keys.
    """
    nodes: dict[str, Any] = {}
    for node_id, node in doc["nodes"].items():
        nodes[node_id] = _whole_numbers(_compact_node(node, doc["rootId"]))
    return {**doc, "nodes": nodes}


def _whole_numbers(value: Any) -> Any:
    """`760.0` written as `760`. The arithmetic here is in floats; the file is
    read by people, and a coordinate with a pointless `.0` on it is noise."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _whole_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_whole_numbers(v) for v in value]
    return value


def _compact_node(node: dict[str, Any], root_id: str) -> dict[str, Any]:
    out = {k: v for k, v in node.items() if k not in ("style", "kind")}
    if node.get("kind") == "link":
        out["kind"] = "link"
        style = {k: v for k, v in (node.get("style") or {}).items()}
        if style:
            out["style"] = style
        return out

    node_type = node.get("type", "rect")
    default_w, default_h = DEFAULT_SIZE.get(node_type, FALLBACK_SIZE)
    defaults = {
        "type": "rect",
        "x": 0,
        "y": 0,
        "w": default_w,
        "h": default_h,
        "rotation": 0,
        "text": "",
        "markdown": "",
        "groupId": None,
        "parentId": root_id,
    }
    for field, default in defaults.items():
        if field in out and out[field] == default:
            del out[field]

    reference = style_for(node_type)
    style = {k: v for k, v in (node.get("style") or {}).items() if reference.get(k) != v}
    if style:
        out["style"] = style
    return out


# --- spec -> document --------------------------------------------------------


def build_document(spec: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """The canonical document for `spec`.

    A spec that is already a canonical document (a `nodes` *mapping* plus a
    `rootId`) is normalised in place instead: missing styles are filled in and
    everything else is left alone, so a document exported from DeepDraw can be
    edited and fed straight back in.
    """
    if isinstance(spec.get("nodes"), dict) and spec.get("rootId"):
        return _normalise_document(spec)
    return _from_tree(spec, seed)


def _normalise_document(doc: dict[str, Any]) -> dict[str, Any]:
    """A whole document out of one that may be missing most of itself.

    This is the reading half of :func:`compact`, and it mirrors
    ``normalizeDocument`` in DeepDraw's own library: what a file leaves out, the
    reader puts back. So an exported drawing, a compacted one, and a document
    somebody hand-edited down to the parts they cared about all arrive here as
    the same thing.
    """
    root_id = doc["rootId"]
    out = {
        "version": doc.get("version", DOC_VERSION),
        "id": doc.get("id") or nanoid(),
        "title": doc.get("title") or "Untitled drawing",
        "rootId": root_id,
        "nodes": {},
    }
    for ordinal, (node_id, node) in enumerate(doc["nodes"].items()):
        node = dict(node)
        node["id"] = node_id
        is_link = node.get("kind") == "link" or "targetId" in node
        node_type = "root" if node_id == root_id else node.get("type", "rect")
        if is_link:
            node["kind"] = "link"
        else:
            node["kind"] = "shape"
            node["type"] = node_type
            node.setdefault("text", "")
            node.setdefault("markdown", "")
            node["style"] = style_for(node_type, node.get("style"))
            # A bare node name is what somebody writing an arrow by hand means.
            if node_type == "arrow":
                for which in ("from", "to"):
                    if isinstance(node.get(which), str):
                        node[which] = {"nodeId": node[which]}

        default_w, default_h = DEFAULT_SIZE.get("rect" if is_link else node_type, FALLBACK_SIZE)
        for field, default in (
            ("x", 0), ("y", 0), ("w", default_w), ("h", default_h),
            ("rotation", 0), ("index", ordinal),
        ):
            node.setdefault(field, default)
        # A missing parent, or one naming nothing, is the top level.
        if node_id == root_id:
            node["parentId"] = None
        elif node.get("parentId") not in doc["nodes"]:
            node["parentId"] = root_id
        out["nodes"][node_id] = node

    out["nodes"].setdefault(root_id, {
        "kind": "shape", "id": root_id, "parentId": None, "index": 0,
        "x": 0, "y": 0, "w": 0, "h": 0, "rotation": 0,
        "type": "root", "text": "", "markdown": "", "style": style_for("root"),
    })
    _resolve_arrow_bounds(out)
    validate(out)
    return out


def _from_tree(spec: dict[str, Any], seed: int | None) -> dict[str, Any]:
    rng = random.Random(seed) if seed is not None else None
    title = spec.get("title") or "Untitled drawing"
    root_id = spec.get("rootId") or "root"

    nodes: dict[str, Any] = {
        root_id: {
            "kind": "shape",
            "id": root_id,
            "parentId": None,
            "index": 0,
            "x": 0, "y": 0, "w": 0, "h": 0,
            "rotation": 0,
            "type": "root",
            "text": "",
            # The drawing's own notes. They are what a reader sees the moment
            # the file opens, before anything is selected, so a drawing without
            # them starts on an empty panel and an unexplained picture.
            "markdown": spec.get("notes") or spec.get("markdown") or "",
            "style": style_for("root"),
        }
    }

    children = spec.get("shapes") or spec.get("nodes") or []
    if isinstance(children, dict):
        raise SpecError("a `nodes` mapping is a canonical document: it needs a `rootId` too")
    if not isinstance(children, list):
        raise SpecError("`shapes` must be a list of nodes")

    used: set[str] = {root_id}
    _add_children(children, root_id, nodes, used, rng)

    doc = {
        "version": DOC_VERSION,
        "id": spec.get("id") or nanoid(rng=rng),
        "title": title,
        "rootId": root_id,
        "nodes": nodes,
    }
    _resolve_arrow_bounds(doc)
    validate(doc)
    return doc


def _add_children(
    items: list[dict[str, Any]],
    parent_id: str,
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

        node = _node_from_item(item, node_id, parent_id, index)
        nodes[node_id] = node

        nested = item.get("children") or []
        if nested:
            if not isinstance(nested, list):
                raise SpecError(f"`children` of {node_id!r} must be a list")
            _add_children(nested, node_id, nodes, used, rng)


def _node_from_item(
    item: dict[str, Any], node_id: str, parent_id: str, index: int
) -> dict[str, Any]:
    geometry = {
        "x": float(item.get("x", 0)),
        "y": float(item.get("y", 0)),
        "rotation": float(item.get("rotation", 0)),
    }

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
        node = {
            "kind": "link",
            "id": node_id,
            "parentId": parent_id,
            "index": int(item.get("index", index)),
            "targetId": item["link"],
            "w": float(item.get("w", FALLBACK_SIZE[0])),
            "h": float(item.get("h", FALLBACK_SIZE[1])),
            **geometry,
        }
        if "text" in item:
            node["text"] = item["text"]
        if item.get("style"):
            node["style"] = dict(item["style"])
        if item.get("groupId"):
            node["groupId"] = item["groupId"]
        return node

    node_type = item.get("type", "rect")
    if node_type not in SHAPE_TYPES:
        raise SpecError(f"node {node_id!r} has unknown type {node_type!r}")

    default_w, default_h = DEFAULT_SIZE.get(node_type, FALLBACK_SIZE)
    node = {
        "kind": "shape",
        "id": node_id,
        "parentId": parent_id,
        "index": int(item.get("index", index)),
        "w": float(item.get("w", default_w)),
        "h": float(item.get("h", default_h)),
        "type": node_type,
        "text": item.get("text", ""),
        "markdown": item.get("markdown", item.get("notes", "")),
        "style": style_for(node_type, item.get("style")),
        **geometry,
    }

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
    if item.get("groupId"):
        node["groupId"] = item["groupId"]
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
    src = nodes.get((node.get("from") or {}).get("nodeId"))
    dst = nodes.get((node.get("to") or {}).get("nodeId"))

    def centre(n):
        return n["x"] + n["w"] / 2, n["y"] + n["h"] / 2

    from_hint = centre(dst) if dst else (
        (node.get("to") or {}).get("x", node["x"] + node["w"]),
        (node.get("to") or {}).get("y", node["y"] + node["h"]),
    )
    to_hint = centre(src) if src else (
        (node.get("from") or {}).get("x", node["x"]),
        (node.get("from") or {}).get("y", node["y"]),
    )

    def anchor(end, toward):
        if not end:
            return toward
        target = nodes.get(end.get("nodeId"))
        if not target:
            return end.get("x", toward[0]), end.get("y", toward[1])
        rect = {"x": target["x"], "y": target["y"], "w": target["w"], "h": target["h"]}
        if end.get("side"):
            return _side_point(rect, end["side"])
        return _border_point_toward(rect, toward)

    return anchor(node.get("from"), from_hint), anchor(node.get("to"), to_hint)


def _resolve_arrow_bounds(doc: dict[str, Any]) -> None:
    """Stores each arrow's drawn bounding box, as the app does on every edit."""
    for node in doc["nodes"].values():
        if node.get("kind") == "shape" and node.get("type") == "arrow":
            (ax, ay), (bx, by) = arrow_points(doc, node)
            node["x"] = min(ax, bx)
            node["y"] = min(ay, by)
            node["w"] = abs(ax - bx)
            node["h"] = abs(ay - by)


def canvas_bounds(doc: dict[str, Any], drawing_id: str) -> dict[str, float]:
    """The paper one drawing opens on: its contents, never smaller than MIN_CANVAS."""
    children = [n for n in doc["nodes"].values() if n.get("parentId") == drawing_id]
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
        if text is None and node.get("kind") == "link":
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
SOLID_TYPES = {"rect", "square", "ellipse", "diamond", "fatArrow", "image", "icon"}


def label_box(node: dict[str, Any]) -> dict[str, float] | None:
    """Where a node's label actually lands, the way `wn()` in the viewer puts it.

    Labels never wrap, so the width comes from the longest line and not from
    the node's `w`: a `text` node or an `icon` caption routinely draws well
    outside its own box, which is exactly how it ends up on top of a neighbour.
    """
    text = (node.get("text") or "").strip()
    if not text:
        return None
    style = node.get("style") or {}
    size = float(style.get("fontSize", DEFAULT_STYLE["fontSize"]))
    lines = text.split("\n")
    w = max(len(line) for line in lines) * size * CHAR_WIDTH
    h = len(lines) * size * LINE_HEIGHT

    h_align = style.get("hAlign", "center")
    if h_align == "left":
        x = node["x"] + TEXT_PAD
    elif h_align == "right":
        x = node["x"] + node["w"] - TEXT_PAD - w
    else:
        x = node["x"] + (node["w"] - w) / 2

    v_align = style.get("vAlign", "middle")
    if v_align == "above":
        y = node["y"] - h - TEXT_PAD
    elif v_align == "top":
        y = node["y"] + TEXT_PAD
    elif v_align == "bottom":
        y = node["y"] + node["h"] - h - TEXT_PAD
    elif v_align == "below":
        y = node["y"] + node["h"] + TEXT_PAD
    else:
        y = node["y"] + (node["h"] - h) / 2
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
    children: dict[str, list[dict[str, Any]]] = {}
    for node in doc["nodes"].values():
        parent = node.get("parentId")
        if parent is not None:
            children.setdefault(parent, []).append(node)
    for parent, kids in children.items():
        extents[parent] = (
            max(n["x"] + n["w"] for n in kids) - min(n["x"] for n in kids),
            max(n["y"] + n["h"] for n in kids) - min(n["y"] for n in kids),
        )
    return extents


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
    nodes = doc["nodes"]
    drawings: dict[str, list[dict[str, Any]]] = {}
    for node in nodes.values():
        parent = node.get("parentId")
        if parent is not None:
            drawings.setdefault(parent, []).append(node)

    warnings: list[str] = []
    for siblings in drawings.values():
        siblings = sorted(siblings, key=lambda n: n["id"])
        solids = [
            n for n in siblings
            if n.get("kind") == "link" or n.get("type") in SOLID_TYPES
        ]
        labels = [(n, label_box(n)) for n in siblings if n.get("type") != "container"]
        labels = [(n, box) for n, box in labels if box]
        solid_ids = {n["id"] for n in solids}

        for node, box in labels:
            over = [
                other["id"] for other in solids
                if other["id"] != node["id"]
                and all(d > CROWDING_SLACK for d in _overlap(box, other))
            ]
            if over:
                what = "label" if node.get("type") == "arrow" else "text"
                warnings.append(
                    f"{node['id']!r}: its {what} {_short(node)} is drawn across "
                    f"{_join(over)}; widen the gap, shorten it, or move it"
                )

        # Labels that leave their own box (an arrow's, a caption, an icon's
        # text, which is drawn below the glyph) can also land on each other.
        # A label that stays inside a shape is that shape, and was checked above.
        stray = [
            (n, box) for n, box in labels
            if n["id"] not in solid_ids or not _contains(n, box)
        ]
        for i, (node, box) in enumerate(stray):
            for other, other_box in stray[i + 1:]:
                if all(d > CROWDING_SLACK for d in _overlap(box, other_box)):
                    warnings.append(
                        f"{node['id']!r}: its text {_short(node)} lands on the "
                        f"label of {other['id']!r}"
                    )

        for node in siblings:
            if node.get("kind") != "shape" or node.get("type") != "arrow":
                continue
            ends = {(node.get(w) or {}).get("nodeId") for w in ("from", "to")}
            p1, p2 = arrow_points(doc, node)
            for other in solids:
                if other["id"] in ends:
                    continue
                if _crosses(p1, p2, other):
                    warnings.append(
                        f"{node['id']!r}: the line runs through {other['id']!r}, which is "
                        f"neither end of it; an arrow is a straight line, so move a box "
                        f"or pin a `side`"
                    )

        for i, node in enumerate(solids):
            for other in solids[i + 1:]:
                dx, dy = _overlap(node, other)
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
        kind = node.get("kind")
        if kind not in ("shape", "link"):
            problems.append(f"{node_id!r}: kind must be 'shape' or 'link'")
            continue

        parent = node.get("parentId")
        if node_id == root_id:
            if parent is not None:
                problems.append("the root node must have parentId null")
        elif parent not in nodes:
            problems.append(f"{node_id!r}: parentId {parent!r} is not a node")

        if kind == "link":
            if node.get("targetId") not in nodes:
                problems.append(f"{node_id!r}: link target {node.get('targetId')!r} is not a node")
            continue

        node_type = node.get("type")
        if node_type not in SHAPE_TYPES:
            problems.append(f"{node_id!r}: unknown type {node_type!r}")
        style = node.get("style")
        if not isinstance(style, dict):
            problems.append(f"{node_id!r}: `style` is required on every shape node")
        else:
            missing = sorted(set(DEFAULT_STYLE) - set(style))
            if missing:
                problems.append(f"{node_id!r}: style is missing {', '.join(missing)}")
            if style.get("strokeStyle") not in STROKE_STYLES:
                problems.append(f"{node_id!r}: strokeStyle must be one of {sorted(STROKE_STYLES)}")
            if style.get("hAlign") not in H_ALIGNS:
                problems.append(f"{node_id!r}: hAlign must be one of {sorted(H_ALIGNS)}")
            if style.get("vAlign") not in V_ALIGNS:
                problems.append(f"{node_id!r}: vAlign must be one of {sorted(V_ALIGNS)}")

        if node_type == "arrow":
            for which in ("from", "to"):
                end = node.get(which)
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
                elif nodes[target_id].get("parentId") != parent:
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

    # A cycle would make the tree infinite; the renderer walks it by parentId.
    for node_id in nodes:
        seen = set()
        cur = node_id
        while cur is not None and cur not in seen:
            seen.add(cur)
            cur = nodes[cur].get("parentId") if cur in nodes else None
        if cur is not None:
            problems.append(f"{node_id!r}: parentId chain is a cycle")
            break

    if problems:
        raise SpecError("\n".join("- " + p for p in problems))
    return warnings
