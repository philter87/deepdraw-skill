---
name: deepdraw
description: Draw a hierarchical diagram for DeepDraw (deepdraw.ai) and build it as an interactive, standalone HTML file.
disable-model-invocation: true
---

# DeepDraw

DeepDraw draws **hierarchies**: any shape can hold a whole drawing of its own,
plus markdown notes. That is what to use it for. A flat box-and-arrow diagram is
a DeepDraw drawing with the interesting half left out. Put the detail *inside*
the boxes rather than spreading it across the page.

You write a spec (JSON), run one script, and hand back a single `.html`: a page
that opens in any browser and imports into deepdraw.ai through **☰ → Import…**.

Subject of the drawing: **$ARGUMENTS**. If that is empty, take it from the
conversation, and ask when it is not obvious.

`$SKILL` below is the directory this file is in. In Claude Code that is
`${CLAUDE_SKILL_DIR}`; elsewhere it is wherever you found `SKILL.md`.

## Workflow

1. **Plan the hierarchy.** What are the 4 to 8 shapes on the top level, and what
   does each one contain? Depth is the point; two or three levels is normal.
2. **Read `$SKILL/reference/spec.md`** for the grammar and
   `$SKILL/reference/layout.md` for coordinates, sizing and colour. Then write
   the spec to a `.json` file.
3. **Find icons.** Most drawings are better with a few:
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

## Make it worth looking at

A correct drawing nobody wants to read is a failed drawing. Four things do most
of the work:

- **Colour carries a distinction.** Pick one thing colour means in this drawing
  (kind of component, ownership, which team, inside vs outside) and use the
  palette in `layout.md` for it. Then say what it means in the drawing's notes.
  A drawing where every box is white is a drawing that has not been thought
  about; a drawing where every box is a different colour says nothing either.
- **Icons make a shape recognisable before it is read.** A database, a queue, a
  browser, a lock, a robot. Use `icon` nodes for things that are more picture
  than prose, and set `style.textColor` to tint the glyph to match its
  neighbours. Two or three per level is plenty.
- **The pencil is for annotation.** A `draw` node is a freehand stroke through
  `points`, normalised to its own box, so `[0, 0.5, 1, 0.5]` is a line straight
  across the middle. Ring the thing that is under discussion, underline the hot
  path, cross out what is being retired. It reads as a human hand on top of a
  machine-drawn picture, which is exactly what it is. Do not draw shapes the
  other types give you for free.
- **Vary the shapes.** `diamond` for a decision, `ellipse` for a store,
  `container` for a boundary, `fatArrow` for a flow, `text` for a caption. A
  page of identical rectangles is a page nobody scans.

## Rules that are easy to get wrong

- **Never use an em dash.** Not in labels, not in notes, not in anything you
  write back to the person either. Rewrite the sentence, or use a comma, a
  colon, brackets, or a full stop. A hyphen in a compound word is fine.
- **The drawing needs notes of its own.** Set `notes` at the **top level of the
  spec**: it becomes the root shape's markdown, and it is the one panel a reader
  sees the moment the file opens, before they have clicked anything. Say what
  the drawing is, where to start, and what the colours mean. The builder warns
  when it is missing. Every other shape worth explaining gets `notes` too.
- **Arrows take notes as well as labels.** The label is one or two words on the
  line; the `notes` beside it is where the protocol, the failure mode, the
  retry policy or the number goes. A reader clicking an arrow in view mode gets
  that panel, exactly as they do for a box. Use it: the interesting part of most
  diagrams is the arrows.
- **Every drawing is auto-fitted to the pane**, so coordinates are *relative*
  and a small drawing is simply zoomed in more. Lay out around 800 to 1200 units
  wide at **every** level, or the same font size changes apparent size as the
  reader moves through the hierarchy.
- **Coordinates are per drawing.** A nested drawing starts its own coordinate
  space; it is not offset inside its parent.
- **Labels never wrap.** Put `\n` where the break goes, and size the shape to
  the longest line: roughly `fontSize × 0.58` per character.
- **Arrows connect siblings.** An endpoint names a node id in the *same*
  drawing. To reach something a level away, put a `link` node here and aim at
  that. The builder warns when an arrow crosses drawings.
- **Notes are where the words go.** Anything longer than a two-word label
  belongs in `notes` (markdown), not in a bigger box.
- **Labels are plain text; notes are markdown.** Write `<img>` in a label, not
  `&lt;img&gt;`: entities render literally. In notes it is the reverse, so put
  tag names in backticks to keep markdown from eating them.
- **A `@[mention]` needs the target's whole label.** Bracket it unless it is one
  bare word, and only single-line labels can be linked: the match is against the
  entire `text`, newline included, even though the tree shows only the first
  line. The builder warns about mentions that resolve to nothing.
- **Write only what you change.** Every field has a default (`spec.md` lists
  them) and DeepDraw fills the rest in when it reads the file. A shape naming
  only `fill` keeps the stroke, font and alignment it never mentioned.

## Reference

Read these when the step above says to, not before.

| File | What is in it |
|---|---|
| `$SKILL/reference/spec.md` | The spec grammar: every field, type and default |
| `$SKILL/reference/layout.md` | Canvas size, coordinates, sizing, arrows, nesting, colour |
| `$SKILL/reference/icons.md` | Iconify search, and how an icon lives in a node |
| `$SKILL/reference/document-format.md` | DeepDraw's own JSON, and how to edit a drawing that already exists |
| `$SKILL/examples/checkout-service.json` | A three-level spec using most of the model |
