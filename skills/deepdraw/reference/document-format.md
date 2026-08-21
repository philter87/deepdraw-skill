# DeepDraw's document format

What the builder emits, what DeepDraw exports, and what its Import button
reads. You rarely write this by hand, since `spec.md` is for that, but you need it
to edit an exported drawing, and to know why the spec has the shape it has.

## One document, every level

The whole hierarchy is **one JSON document**. Nodes live in a flat `nodes` map
and form a tree through `parentId`; a node's children *are* its nested drawing.
There is no separate drawing entity, and drilling into a shape means rendering
that shape's children.

```jsonc
{
  "version": 1,
  "id": "laf0KBZdM_mn",
  "title": "Checkout service",
  "rootId": "root",
  "nodes": {
    "root": { "kind": "shape", "type": "root", "parentId": null, "index": 0,
              "x": 0, "y": 0, "w": 0, "h": 0, "rotation": 0,
              "text": "", "markdown": "", "style": { /* … */ } },
    "api":  { "kind": "shape", "type": "rect", "parentId": "root", "index": 1, /* … */ },
    "http": { "kind": "shape", "type": "rect", "parentId": "api",  "index": 0, /* … */ }
  }
}
```

`index` is z-order and tree order among siblings: sparse, ties broken by id.
The root node is always `w: 0, h: 0` and its label is the document `title`.

## Shape node

```jsonc
{
  "kind": "shape",
  "id": "api",
  "parentId": "root",
  "index": 1,
  "x": 300, "y": 60, "w": 180, "h": 90,
  "rotation": 0,
  "type": "rect",
  "text": "Checkout API",
  "markdown": "# Checkout API\n\nOwns the order state machine.",
  "style": {
    "fill": "#ecfdf5", "stroke": "#059669", "strokeWidth": 2,
    "strokeStyle": "solid", "radius": 8, "textColor": "#0f172a",
    "fontSize": 14, "fontFamily": "system-ui, sans-serif",
    "hAlign": "center", "vAlign": "middle", "opacity": 1
  },
  "groupId": null
}
```

That is the document written out **in full**, which is what an export looks
like: a snapshot that left things out would be lying about them.

**A file you write does not have to be.** Every reader fills the defaults back
in before anything renders, in all three places that read a document: the
library (`normalizeDocument`), the server behind deepdraw.ai's Import button,
and the standalone page's own boot script. So the shape above is also legal as:

```jsonc
"api": { "parentId": "root", "index": 1, "x": 300, "y": 60, "w": 180, "h": 90,
         "text": "Checkout API",
         "markdown": "# Checkout API\n\nOwns the order state machine.",
         "style": { "fill": "#ecfdf5", "stroke": "#059669" } }
```

Each rule is the obvious reading of an absence:

| Left out | Read as |
|---|---|
| `kind` | `"shape"` (or `"link"`, if there is a `targetId`) |
| `type` | `"rect"`, and `"root"` for the node named by `rootId` |
| `parentId`, or one naming a node that is not in the file | the top level |
| `index` | declaration order |
| `x`, `y`, `rotation` | `0` |
| `w`, `h` | the type's own default size |
| `text`, `markdown` | empty |
| a style property | the type's default for **that property**, so naming only `fill` keeps the stroke and font |
| a root node | one is created, so a bare list of shapes is a one-level drawing |
| an arrow endpoint written as `"api"` | `{ "nodeId": "api" }` |

`build_html.py` writes documents this way (`compact` in `deepdraw_doc.py`), so
the `.deepdraw.json` beside a drawing is about half the size of a full export
and is a file a person can read. It is idempotent in both directions: a full
export compacts, a compact document expands, and either can be fed back into the
builder.

Type-specific fields:

- `arrow`: `from` and `to`, each `{ nodeId?, side?, x?, y? }`. `x/y/w/h` on the
  arrow itself are the bounding box of the line as drawn; the renderer
  recomputes them from the endpoints, so they are a record, not an input.
- `icon`: `href` holds **raw inline SVG markup**, not a URL.
- `image`: `href` holds a `data:` URI. An export inlines remote images, so a
  file that leaves DeepDraw keeps working when it is moved.
- `draw`: `points`, flat `x, y, x, y…` normalised to the node's own box (`0` is
  its left/top edge, `1` its right/bottom). That is what makes a stroke an
  ordinary shape: move, resize and rotate are the same arithmetic as for a box.

## Link node

```jsonc
{ "kind": "link", "id": "api-db", "parentId": "api", "index": 4,
  "targetId": "db", "x": 344, "y": 26, "w": 62, "h": 39, "rotation": 0 }
```

No `type`, no `markdown`, and `style`/`text` only when they override the
target's. It resolves to `targetId` for content and draws with the target's
type; its geometry is its own.

## The three export formats

All three carry the *whole* document, so all three import again. DeepDraw tells
them apart by their bytes, not by their extension.

| Format | Where the document sits |
|---|---|
| **JSON** | The file itself |
| **PNG** | A `tEXt` chunk under the keyword `deepdraw` (the draw.io trick) |
| **HTML** | `<script id="dd-document" type="application/json">…</script>` |

## The HTML file

`$SKILL/reference/template.html` is DeepDraw's own HTML export with two placeholders:

```
__DEEPDRAW_TITLE__           in <title>, HTML-escaped
__DEEPDRAW_DOCUMENT_JSON__   inside <script id="dd-document" type="application/json">
```

Everything else is already there: the stylesheet, the whole bundled library,
and the boot script that mounts it read-only in view mode. The page needs no
network and no server.

The JSON must have every `<` written as `\u003c`, or a `<` in a label or in an
icon's inline SVG closes the script tag early and takes the document with it.
`build_html.py` does that; `\u003c` is ordinary JSON escaping, so what comes
back out parses unchanged.

## Editing a drawing that already exists

`build_html.py` takes a canonical document as well as a spec, so an existing
drawing is edited rather than redrawn: node ids survive and the change is a
diff. Use the `.deepdraw.json` beside the file, or pull the document out of the
`.html` itself:

```bash
python3 - <<'EOF'
import re, json, pathlib
html = pathlib.Path('drawing.html').read_text()
doc = re.search(r'<script id="dd-document" type="application/json">(.*?)</script>', html, re.S).group(1)
pathlib.Path('drawing.deepdraw.json').write_text(json.dumps(json.loads(doc), indent=2))
EOF
```

That regex is the whole reader: DeepDraw uses it in the browser, and again on
the server when a file is imported.
