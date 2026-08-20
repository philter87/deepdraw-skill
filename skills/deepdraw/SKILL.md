---
name: deepdraw
description: Draw a hierarchical diagram for DeepDraw (deepdraw.ai) and build it as an interactive, standalone HTML file.
disable-model-invocation: true
---

# DeepDraw

DeepDraw draws **hierarchies**: any shape can hold a whole drawing of its own,
plus markdown notes. That is what to use it for — a flat box-and-arrow diagram
is a DeepDraw drawing with the interesting half left out. Put the detail
*inside* the boxes rather than spreading it across the page.

You write a spec (JSON), run one script, and hand back a single `.html`: a page
that opens in any browser and imports into deepdraw.ai through **☰ → Import…**.

Subject of the drawing: **$ARGUMENTS**. If that is empty, take it from the
conversation, and ask when it is not obvious.

`$SKILL` below is the directory this file is in — in Claude Code that is
`${CLAUDE_SKILL_DIR}`; elsewhere it is wherever you found `SKILL.md`.

## Workflow

1. **Plan the hierarchy.** What are the 4–8 shapes on the top level, and what
   does each one contain? Depth is the point; two or three levels is normal.
2. **Read `$SKILL/reference/spec.md`** for the grammar and
   `$SKILL/reference/layout.md` for coordinates, sizing and colour. Then write
   the spec to a `.json` file.
3. **Icons, only if the drawing wants them:**
   `python3 "$SKILL/scripts/iconify.py" search <query> --sets material-symbols`,
   then `get <prefix:name> --node`. Details: `$SKILL/reference/icons.md`.
4. **Build:**

   ```bash
   python3 "$SKILL/scripts/build_html.py" drawing.json -o drawing.html --json
   ```

   It validates first and refuses to write a drawing that would not render. Fix
   what it reports; never hand over a file you have not built.
5. **Say what they have:** the `.html` to open or import, and the
   `.deepdraw.json` beside it, which DeepDraw imports too.

## Rules that are easy to get wrong

- **Every drawing is auto-fitted to the pane**, so coordinates are *relative*
  and a small drawing is simply zoomed in more. Lay out around 800–1200 units
  wide at **every** level, or the same font size changes apparent size as the
  reader moves through the hierarchy.
- **Coordinates are per drawing.** A nested drawing starts its own coordinate
  space; it is not offset inside its parent.
- **Labels never wrap.** Put `\n` where the break goes, and size the shape to
  the longest line — roughly `fontSize × 0.58` per character.
- **Arrows connect siblings.** An endpoint names a node id in the *same*
  drawing. To reach something a level away, put a `link` node here and aim at
  that. The builder warns when an arrow crosses drawings.
- **Notes are where the words go.** Anything longer than a two-word label
  belongs in `notes` (markdown), not in a bigger box.
- **The pencil is for annotation.** A `draw` node is a freehand stroke through
  `points` — flat `x, y, x, y…` normalised to its own box, so
  `[0, 0.5, 1, 0.5]` is a line straight across the middle. Ring or underline
  something that is already on the page with it; do not draw shapes the other
  types give you for free.

## Reference

Read these when the step above says to, not before.

| File | What is in it |
|---|---|
| `$SKILL/reference/spec.md` | The spec grammar — every field, type and default |
| `$SKILL/reference/layout.md` | Canvas size, coordinates, sizing, arrows, nesting, colour |
| `$SKILL/reference/icons.md` | Iconify search, and how an icon lives in a node |
| `$SKILL/reference/document-format.md` | DeepDraw's own JSON, and how to edit a drawing that already exists |
| `$SKILL/examples/checkout-service.json` | A three-level spec using most of the model |
