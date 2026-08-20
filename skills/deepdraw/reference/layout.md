# Laying out a drawing

## There is no page

DeepDraw has no fixed canvas size. A drawing's canvas is **whatever it
contains**, grown about its centre until neither side is shorter than **300
document units**, and that rectangle is then fitted into the pane with 32 units
of padding. Zoom is capped at 8×.

Three consequences worth building on:

- **Coordinates are relative.** Only the ratios between your numbers matter.
  Everything below is a scale, not a size.
- **A small drawing is a zoomed-in drawing.** Four boxes across 400 units fill
  the screen just as four boxes across 1200 units do — but at 3× the apparent
  font size. So `fontSize: 14` means something only next to the drawing's own
  extent.
- **Keep every level to the same scale.** Lay each drawing out around
  **800–1200 units wide**, whichever level it is on, and text stays the same
  size as the reader moves through the hierarchy. Mixing a 400-unit drawing
  with a 1600-unit one makes the same 14pt label look twice as big in one of
  them.

`x`/`y` are the **top-left corner**. Y grows downward. Negative coordinates are
fine — a drawing is framed by what it holds, not by an origin.

## Numbers that work

| | Units |
|---|---|
| Drawing extent, any level | 800–1200 wide |
| A box with a short label | 160–200 × 80–100 |
| Gap between boxes on a row | 80–140 |
| Gap between rows | 100–160 |
| `container` padding around its contents | 40 |
| Body text | `fontSize` 14 · headings 18–20 · captions 12–13 |

## Labels do not wrap

`text` is drawn exactly as written; the only line break is a `\n` you put
there. Two things follow:

- Break long labels yourself, and keep them to 2–3 lines. Anything longer is
  `notes`, not a label.
- A label is **plain text**, not markup: write `<img>`, not `&lt;img&gt;`, or
  the entity appears on screen exactly as typed.
- Size the box to the **longest line**: roughly `fontSize × 0.58` per character,
  plus 24 units of breathing room. At `fontSize: 14`, "Checkout API" wants about
  120 units, so a 180-wide box is comfortable.

`vAlign: "above"` and `"below"` draw the label *outside* the shape — that is
how `icon` and `image` are captioned by default. `container` puts its label at
the top, out of the way of what is inside it.

## Arrows

An endpoint with no `side` slides around its shape's border to face the other
end, so a plain `{"from": "a", "to": "b"}` always meets both borders cleanly and
keeps doing so if you move a box later. Reach for `side` only when:

- the direction is part of the meaning (a flow that must leave the bottom), or
- two arrows would otherwise leave the same point, or
- you want a straight run between shapes that are not aligned.

Arrowheads are drawn at the `to` end only. For a two-way relationship, use two
arrows or say so in the label.

Both ends must live in the **same drawing** as the arrow. To point at something
a level away, put a `link` node in this drawing and aim at that.

## Nesting

This is the whole reason to use DeepDraw, and the part a flat diagram gets
wrong. Some patterns that work:

- **System → service → internals.** The top level is the 5–8 boxes someone
  should remember; each one contains how it is actually built.
- **A `container` is not a parent.** It draws a dashed region around shapes that
  are its *siblings* — a zone, an environment, a team boundary. Nesting is
  `children`; grouping visually is a container. They are different tools and
  they compose.
- **Notes carry the prose.** A shape's `notes` is markdown, shown beside the
  drawing when the shape is selected, and `@[Some label]` in it links to another
  shape. Put the paragraph there and keep the label to two words. The link only
  resolves if the label matches that shape's **entire** `text`, so only
  single-line labels can be mentioned — see *Mentions in notes* in `spec.md`.
- **A shape with content is marked.** DeepDraw draws small badges in a shape's
  bottom-right corner when it has notes or a nested drawing, so a reader can see
  where the depth is without hunting. You get that for free by filling them in.

## Colour

The default palette — white fill, slate stroke `#334155`, near-black text — is
deliberate and safe. When you tint, keep to **light fills with a matching darker
stroke**:

| | Fill | Stroke |
|---|---|---|
| Blue | `#eff6ff` | `#2563eb` |
| Green | `#ecfdf5` | `#059669` |
| Amber | `#fef3c7` | `#d97706` |
| Rose | `#fef2f2` | `#dc2626` |
| Violet | `#f5f3ff` | `#7c3aed` |
| Slate | `#f8fafc` | `#475569` |

Two reasons to stay in that shape. Colour should carry one distinction (kind of
component, or ownership) and go on being readable — dark fills fight the label.
And DeepDraw's dark theme **inverts the drawing surface** rather than repainting
it: lightness flips, hue is kept. A light-blue box with a dark-blue edge becomes
a dark-blue box with a light-blue edge and reads correctly. A box already dark
comes out glaring.
