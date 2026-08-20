# The spec

What `scripts/build_html.py` reads. It is DeepDraw's model written as a tree
with the defaults left out; the builder fills them in and emits the canonical
document (`document-format.md`).

```json
{
  "title": "Checkout service",
  "shapes": [
    { "id": "api", "type": "rect", "x": 300, "y": 60, "w": 180, "h": 90,
      "text": "Checkout API",
      "notes": "# Checkout API\n\nOwns the order state machine.",
      "style": { "fill": "#ecfdf5", "stroke": "#059669" },
      "children": [
        { "id": "http", "type": "rect", "x": 40, "y": 40, "w": 170, "h": 80, "text": "HTTP layer" },
        { "id": "state", "type": "rect", "x": 40, "y": 190, "w": 170, "h": 80, "text": "Order state" },
        { "type": "arrow", "from": "http", "to": "state", "fromSide": "bottom", "toSide": "top" }
      ] }
  ]
}
```

## Document

| Field | Default | Meaning |
|---|---|---|
| `title` | `"Untitled drawing"` | Names the drawing, the browser tab, and the root of the tree |
| `shapes` | `[]` | The top-level drawing, as a list of nodes |
| `id`, `rootId` | generated / `"root"` | Only worth setting to keep ids stable across rebuilds |

## Node

| Field | Default | Meaning |
|---|---|---|
| `id` | generated | Give one to anything an arrow, a link or a later edit names |
| `type` | `"rect"` | See **Types** below |
| `x`, `y` | `0` | Top-left corner, in this drawing's own coordinates |
| `w`, `h` | per type | Size in document units |
| `text` | `""` | The label drawn on the shape. **Never wraps** — use `\n` |
| `notes` (or `markdown`) | `""` | Markdown shown in the notes pane when the shape is selected |
| `style` | per type | Any subset of the style fields; the rest come from the type |
| `rotation` | `0` | Degrees clockwise about the shape's centre |
| `children` | — | This shape's **nested drawing**: the same node grammar, one level down |
| `groupId` | — | Siblings sharing a string move together |
| `href` | — | `image`: a `data:` URI. `icon`: raw inline `<svg>` markup |
| `points` | — | `draw` only: `x, y, x, y…` normalised to the node's own box |
| `link` | — | Makes this a **link node**: the id of the node it stands in for |

## Types

| `type` | Default size | Looks like |
|---|---|---|
| `rect` | 160×100 | Rounded box (`radius: 8`). The workhorse |
| `ellipse` | 140×100 | Ellipse filling the box |
| `diamond` | 140×100 | Decisions |
| `container` | 320×240 | Transparent, dashed, label at the top. Groups shapes *visually* — it does not own them |
| `fatArrow` | 160×70 | A block arrow pointing right; rotate it to point elsewhere |
| `text` | 160×32 | The label alone: no fill, no stroke, left-aligned |
| `icon` | 64×64 | Inline SVG in `href`, recoloured with `textColor`, label below |
| `image` | 160×120 | A `data:` URI in `href`, label below |
| `arrow` | — | A line with a head; geometry comes from `from`/`to`, not from `x/y/w/h` |
| `draw` | 160×100 | A freehand stroke through `points` |

`square` and `group` exist in the model but are legacy or structural; do not
author them. `root` is created for you.

## Style

Any subset. What you leave out comes from the type's own defaults, which are
already right for that type — override colour and size, rarely the rest.

| Field | Default | Values |
|---|---|---|
| `fill` | `#ffffff` | Any CSS colour, or `transparent` / `none` |
| `stroke` | `#334155` | Any CSS colour |
| `strokeWidth` | `2` | Number |
| `strokeStyle` | `solid` | `solid` · `dashed` · `dotted` |
| `radius` | `8` | Corner radius, `rect` and `container` only |
| `textColor` | `#0f172a` | Also the ink an `icon` is drawn in |
| `fontSize` | `14` | Number, in document units |
| `fontFamily` | `system-ui, sans-serif` | CSS font stack |
| `hAlign` | `center` | `left` · `center` · `right` |
| `vAlign` | `middle` | `above` · `top` · `middle` · `bottom` · `below` — `above`/`below` put the label *outside* the shape |
| `opacity` | `1` | 0–1 |

## Arrows

`from` and `to` each take one of three forms:

```jsonc
"from": "api"                            // that node, meeting its border
"from": { "node": "api", "side": "right" }  // pinned to one side
"from": { "x": 40, "y": 120 }               // a free point in this drawing
```

Unpinned, an endpoint slides around the shape's border to face the other end,
which is usually what you want. Pin a `side` when the direction carries meaning
(a flow that must leave downward) or when two arrows would otherwise overlap.

Shorthand: `"fromSide": "right"` / `"toSide": "left"` beside a plain string
endpoint does the same thing.

Both ends must be in the **same drawing** as the arrow. An arrow may carry
`text`, drawn at its midpoint.

## Links

A link node stands in for a node from somewhere else in the hierarchy: it shows
that node's content (its nested drawing and notes) while keeping its own
position, size and — optionally — its own `text` and `style` here.

```json
{ "id": "api-db", "link": "db", "x": 300, "y": 190, "w": 170, "h": 80 }
```

Use one to draw an arrow at something that lives in another drawing, or to show
one component in several places without duplicating it.

## Building

```bash
python3 "$SKILL/scripts/build_html.py" spec.json -o out.html   # the drawing
python3 "$SKILL/scripts/build_html.py" spec.json --check       # validate only
python3 "$SKILL/scripts/build_html.py" spec.json --json        # also write the canonical JSON
python3 "$SKILL/scripts/build_html.py" spec.json --seed 7      # reproducible generated ids
```

Errors stop the build (an arrow pointing at nothing, a missing style field, a
`parentId` cycle). Warnings do not (an arrow across drawings, an `icon` with no
`href`) — read them anyway; both mean the drawing will not look how you meant.
