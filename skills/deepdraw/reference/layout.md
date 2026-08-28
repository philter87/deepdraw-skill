# Laying out a drawing

## There is no page, but there is a pane

DeepDraw has no fixed canvas size. A drawing's canvas is **whatever it
contains**, grown about its centre until neither side is shorter than **300
document units**, and that rectangle is then fitted into the pane with 32 units
of padding.

The pane is smaller than you think. The hierarchy tree on one side and the
notes panel on the other take roughly **half the window**, so on a 1440-wide
screen the drawing gets about **850 × 800 px**, and on a 1280-wide one about
**690 × 700**. Take off the padding and the honest budget is around
**620 × 640 px**.

Four consequences worth building on:

- **A unit is about a pixel.** Not exactly, but close enough to design with: a
  drawing laid out 620 units wide fills the pane at roughly 1:1, so `fontSize:
  14` arrives on screen as 14 px. Draw at the size you want it read at.
- **A big drawing is a shrunk drawing.** Fit scale is
  `(620 ÷ drawing width)`, and it applies to the text too. The same
  `fontSize: 14` comes out at 14 px in a 600-wide drawing, 11 px in an
  800-wide one, and **9 px in a 1200-wide one**, which is the usual reason a
  finished drawing turns out unreadable. There is no zoom cap downward: nothing
  stops a wide drawing from shrinking its own labels into noise.
- **Keep every level to the same scale.** Lay each drawing out around
  **500–700 units wide, and no taller than it is wide** (the pane is close to
  square, so height costs the same as width), whichever level it is on,
  and text stays both readable and the same size as the reader moves through
  the hierarchy. Mixing a 400-unit drawing with a 1600-unit one makes the same
  14pt label look four times as big in one of them. The builder warns when one
  level is more than twice the size of the rest, and again when a level is laid
  out so wide that its own labels land under 11 px, because nothing in the file
  itself shows either.
- **If a level truly needs more room, scale the type with it.** Width and
  `fontSize` have to move together: `fontSize ≈ width ÷ 45` keeps labels at
  about 14 px on screen. A 900-unit level wants `fontSize: 20` on every node in
  it, and boxes about a third larger to hold the same words. Prefer splitting
  the level into a nested drawing over growing it.

`x`/`y` are the **top-left corner**. Y grows downward. Negative coordinates are
fine: a drawing is framed by what it holds, not by an origin.

## Numbers that work

| | Units |
|---|---|
| Drawing extent, any level | 500–700 wide · no taller than wide |
| A box with a short label | 140–190 × 70–90 |
| Gap between boxes on a row | 60–100 |
| Gap an arrow's **label** has to fit in | wider than the label |
| Gap between rows | 80–120 |
| `container` padding around its contents | 30–40 |
| Body text | `fontSize` 14 · headings 18–20 · captions 12–13 |

Three boxes across a row is comfortable at this scale, four is tight, five
wants either a nested level or the bigger type above. That is the constraint
doing its job: a level with eight boxes on it was two levels all along.

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

`vAlign: "above"` and `"below"` draw the label *outside* the shape, which is
how `icon` and `image` are captioned by default. `container` puts its label at
the top, out of the way of what is inside it, and `sticky` writes from the
**top left**, the way somebody writes on a real note: a couple of short lines
that start at the corner, not a centred caption.

## Leave room for the label

A label is drawn at the centre of its node's box with **nothing behind it**. No
halo, no background: a label that lands on a box is simply printed over it, and
the file cannot tell you, because it renders perfectly.

For an arrow, "its box" is the rectangle spanned by the two endpoints, so the
label sits at the **midpoint of the line**, in the gap between the two shapes.
The gap therefore has to be wider than the label:

```
label width ≈ characters × fontSize × 0.58
```

"cell to cell" at `fontSize: 14` is about 100 units wide, so two boxes 40 apart
have it printed across both of them. At this scale a gap that wide is most of a
row, so the fix is usually the label, not the gap: say it in two words and move
the sentence into `notes`, which is where it wanted to be.

A 40 to 60 unit gap is fine for a **vertical** arrow, where the label lies along
the gap rather than across it. Horizontal and diagonal runs are what need room.

The same arithmetic governs a `text` node and an `icon`'s caption. Neither wraps
and neither is clipped to its own `w`, so a 300-unit caption in a 160-wide box
draws straight across whatever sits to its right.

## Arrows

An endpoint with no `side` slides around its shape's border to face the other
end, so a plain `{"from": "a", "to": "b"}` always meets both borders cleanly and
keeps doing so if you move a box later. Reach for `side` only when:

- the direction is part of the meaning (a flow that must leave the bottom), or
- two arrows would otherwise leave the same point, or
- you want a straight run between shapes that are not aligned.

Arrowheads are drawn at the `to` end only. For a two-way relationship, use two
arrows or say so in the label.

An arrow is a **straight line between two points**, and nothing routes it around
what is in between. A box in the top left joined to one in the bottom right is
drawn over everything on that diagonal. When that happens: move a box, pin a
`side` so the line leaves by a different face, or aim at a `link` node put
somewhere clearer.

Both ends must live in the **same drawing** as the arrow. To point at something
a level away, put a `link` node in this drawing and aim at that.

**The builder checks all of this.** `build_html.py` warns about a label drawn
across a shape, a line running through a shape that is neither of its ends, two
shapes on top of each other, and two labels on top of each other, naming the
nodes each time. They are warnings, because the drawing still renders. Read them
anyway: the only other way to find any of it is to open the file and look.

## Nesting

This is the whole reason to use DeepDraw, and the part a flat diagram gets
wrong. Some patterns that work:

- **System → service → internals.** The top level is the 4–6 boxes someone
  should remember, two rows of three at this scale; each one contains how it is
  actually built. A level that will not fit in 700 units is a level that wanted
  splitting.
- **A `container` is not a parent.** It draws a dashed region around shapes that
  are its *siblings*: a zone, an environment, a team boundary. Nesting is
  `children`; grouping visually is a container. They are different tools and
  they compose.
- **Notes carry the prose.** A shape's `notes` is markdown, shown beside the
  drawing when the shape is selected, and `@[Some label]` in it links to another
  shape. Put the paragraph there and keep the label to two words. The link only
  resolves if the label matches that shape's **entire** `text`, so only
  single-line labels can be mentioned. See *Mentions in notes* in `spec.md`.
- **A shape with content is marked.** DeepDraw draws small badges in a shape's
  bottom-right corner when it has notes or a nested drawing, so a reader can see
  where the depth is without hunting. You get that for free by filling them in.

## Colour

The default palette (white fill, slate stroke `#334155`, near-black text) is
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
component, or ownership) and go on being readable; dark fills fight the label.
And DeepDraw's dark theme **inverts the drawing surface** rather than repainting
it: lightness flips, hue is kept. A light-blue box with a dark-blue edge becomes
a dark-blue box with a light-blue edge and reads correctly. A box already dark
comes out glaring.

**Use it, though.** Pick the one distinction the colours carry, tint every box
accordingly, and say what the colours mean in the drawing's own notes. An
all-white drawing looks like nobody decided anything; a rainbow looks the same,
for the opposite reason. Three or four colours on a level is usually right, and
an `icon` tinted with `textColor` to match the boxes around it ties the two
together.

## Two things that stop a drawing looking generated

- **Icons.** An `icon` node is a picture where a picture says it faster: a
  database, a queue, a lock, a browser, a robot, a brand mark. Caption it with
  `text` (drawn below by default) and tint the glyph with `style.textColor`.
  See `icons.md`. Two or three per level, beside the boxes rather than instead
  of them.
- **The pencil.** A `draw` node is a freehand stroke, and it reads as a human
  hand on top of a machine-drawn picture. Ring the step under discussion,
  underline the hot path, cross out what is being retired, put a wavy line
  under a number nobody believes. `points` are `x, y, x, y…` normalised to the
  node's own box, so a stroke is positioned and sized like any other shape:
  `[0, 0.5, 1, 0.5]` is a line straight across the middle, and a dozen points
  around the edge is a hand-drawn ring. Give it a `stroke` that stands out from
  the palette and a `strokeWidth` of 3.
