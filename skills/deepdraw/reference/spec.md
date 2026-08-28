# The spec

What `$SKILL/scripts/build_html.py` reads. It is DeepDraw's model written as a tree
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
| `notes` | `""` | **The drawing's own markdown.** It lands on the root shape, which is what a reader sees the moment the file opens, before anything is selected. Say what this is, where to start, and what the colours mean. The builder warns when it is missing |
| `shapes` | `[]` | The top-level drawing, as a list of nodes |
| `id`, `rootId` | generated / `"root"` | Only worth setting to keep ids stable across rebuilds |

## Node

| Field | Default | Meaning |
|---|---|---|
| `id` | generated | Give one to anything an arrow, a link or a later edit names |
| `type` | `"rect"` | See **Types** below |
| `x`, `y` | `0` | Top-left corner, in this drawing's own coordinates |
| `w`, `h` | per type | Size in document units |
| `text` | `""` | The label drawn on the shape. **Plain text, never wraps**, so put `\n` where a break goes |
| `notes` (or `markdown`) | `""` | Markdown shown in the notes pane when the shape is selected |
| `style` | per type | Any subset of the style fields; the rest come from the type |
| `rotation` | `0` | Degrees clockwise about the shape's centre |
| `children` | none | This shape's **nested drawing**: the same node grammar, one level down |
| `groupId` | none | Siblings sharing a string move together |
| `href` | none | `image`: a file path, an http(s) address, or a `data:` URI (see [Pictures](#pictures)). `icon`: raw inline `<svg>` markup |
| `points` | none | `draw` only: `x, y, x, y…` normalised to the node's own box |
| `link` | none | Makes this a **link node**: the id of the node it stands in for |

## Types

| `type` | Default size | Looks like |
|---|---|---|
| `rect` | 160×100 | Rounded box (`radius: 8`). The workhorse |
| `ellipse` | 140×100 | Ellipse filling the box |
| `diamond` | 140×100 | Decisions |
| `container` | 320×240 | Transparent, dashed, label at the top. Groups shapes *visually*; it does not own them |
| `fatArrow` | 160×70 | A block arrow pointing right; rotate it to point elsewhere |
| `sticky` | 140×140 | A yellow sticky note with a folded corner; its label is written from the **top left** |
| `text` | 160×32 | The label alone: no fill, no stroke, left-aligned |
| `icon` | 64×64 | Inline SVG in `href`, recoloured with `textColor`, label below |
| `image` | 160×120 | A picture named by `href`, label below (see [Pictures](#pictures)) |
| `arrow` | none | A line with a head; geometry comes from `from`/`to`, not from `x/y/w/h` |
| `draw` | 160×100 | A freehand stroke through `points` |

`square` and `group` exist in the model but are legacy or structural; do not
author them. `root` is created for you.

## Style

Any subset. What you leave out comes from the type's own defaults, which are
already right for that type. Override colour and size, rarely the rest.

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
| `vAlign` | `middle` | `above` · `top` · `middle` · `bottom` · `below`. `above`/`below` put the label *outside* the shape |
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

Both ends must be in the **same drawing** as the arrow.

An arrow carries **`text` and `notes`, like any other shape**. The label is one
or two words drawn at the midpoint; the notes are markdown, and a reader
clicking the arrow in view mode gets them in the panel exactly as they would for
a box. That is where the protocol, the payload, the failure mode or the number
belongs, and it is usually the most interesting thing on the page:

```json
{ "type": "arrow", "from": "api", "to": "db", "text": "writes",
  "notes": "One transaction per transition. The row *is* the state." }
```

## Links

A link node stands in for a node from somewhere else in the hierarchy: it shows
that node's content (its nested drawing and notes) while keeping its own
position, size and, optionally, its own `text` and `style` here.

```json
{ "id": "api-db", "link": "db", "x": 300, "y": 190, "w": 170, "h": 80 }
```

Use one to draw an arrow at something that lives in another drawing, or to show
one component in several places without duplicating it.

A link carries **`x`, `y`, `w`, `h`, `text` and `style`, and nothing else**. Its
notes and its nested drawing are the target's, by definition, so `notes`, `type`,
`href` and `points` on a link are refused rather than quietly dropped. Leave
`text` out too and it shows the target's label.

## Pictures

An `image` node's `href` names a picture three ways, and all three end up as the
same thing in the file that is written:

```jsonc
"href": "./screenshots/dashboard.png"        // a file, relative to the spec
"href": "https://example.com/logo.png"       // an address
"href": "data:image/png;base64,iVBORw0K…"    // the bytes already
```

**The builder reads the first two in and inlines them**, so the `.html` it
writes carries the picture itself and needs nothing else to render. That is what
makes it work when it is mailed on, when it is imported into deepdraw.ai (whose
`img-src` refuses to load a picture from another origin), and when it is
exported to PNG (where an SVG rasterized through an `<img>` loads no external
references at all).

- **A picture that cannot be read stops the build.** A 404, a path that does not
  exist, a file that turns out to be HTML. Each is an error naming the node, not
  a warning. A drawing quietly missing a picture is the failure inlining exists
  to prevent.
- **PNG, JPEG, GIF, WebP and AVIF.** Not SVG: a vector glyph belongs in an
  `icon` node, which takes inline `<svg>` markup and draws in whatever colour
  the shape's `textColor` says.
- **Keep them small.** One picture over 2 MB is warned about, over 10 MB is
  refused, and the whole drawing passing 5 MB is warned about too. That last
  number is the image storage deepdraw.ai gives an **anonymous** browser (50 MB
  signed in), so a picture-heavy drawing is one to import signed in.
- **Size the node to the picture's aspect ratio.** The image is fitted inside
  `w`×`h` (`xMidYMid meet`), so a wrong ratio is empty space, not a stretch.

## Labels are plain text

`text` is drawn as characters, not parsed as markup. Write the angle brackets
you want to see:

```jsonc
"text": "<img> arrives"      // correct
"text": "&lt;img&gt; arrives"   // renders the entities literally
```

Notes are the opposite. They are markdown, so wrap tag names in backticks
(`` `<img>` ``) to keep the renderer from eating them.

## Mentions in notes

`@[Some label]` in a `notes` string becomes a chip that navigates to the node
with that label. Two rules decide whether it actually resolves, and both are
easy to get wrong because a dead mention still *renders* as a chip:

- **Use the bracket form for anything but one bare word.** Unbracketed, `@`
  captures a single `[\w][\w.-]*` token, so `@Order state` links "Order" and
  leaves " state" as text.
- **The label must equal the target's whole `text`, exactly** (case-insensitive,
  trimmed). So **a node whose label contains `\n` can never be mentioned**: the
  bracket form cannot contain a newline. Note the trap: the hierarchy tree and
  breadcrumb show only the *first line*, so a shape labelled
  `"The wire\nHTTP/0.9 → HTTP/3"` is listed as "The wire", and `@[The wire]`
  still fails.

If you want a shape to be mentionable, give it a single-line label and move the
second line into its `notes`. `--check` reports mentions that resolve to
nothing.

## What the builder writes

**What you wrote, and nothing else.** The builder never fills a default in: no
size, no style, no alignment, not even an arrow's bounding box, which the
renderer works out from the endpoints every time. So the `.deepdraw.json` beside
the HTML is a file a person can read, roughly half the size of a full export.

Defaults are filled back in by whatever reads it, in all three places that read
a document: the library (`normalizeDocument`), the server behind deepdraw.ai's
Import button, and the standalone page's own boot script. Feeding that JSON
straight back into `build_html.py` reproduces the same drawing.

That is worth knowing when you hand-edit a document: **write what changed and
nothing else**. A node needs a type at most, and one that is already terse comes
out of the builder exactly as terse as it went in.

## Building

```bash
python3 "$SKILL/scripts/build_html.py" spec.json -o out.html   # the drawing
python3 "$SKILL/scripts/build_html.py" spec.json --check       # validate only
python3 "$SKILL/scripts/build_html.py" spec.json --json        # also write the canonical JSON
python3 "$SKILL/scripts/build_html.py" spec.json --seed 7      # reproducible generated ids
```

Errors stop the build (an arrow pointing at nothing, an unknown type, a style
value the renderer will not take, a `parentId` cycle, a `link` carrying notes of
its own). Warnings do not (an arrow across drawings, an `icon` with no `href`, a
style property DeepDraw does not have, a label drawn across a box, a line
through a shape that is neither of its ends, two shapes on top of each other, a
level laid out at a different scale from the rest, an em dash), but read them
anyway: both mean the drawing will not look how you meant.
