---
name: deepdraw
description: Create diagrams for DeepDraw (deepdraw.ai) — hierarchical drawings where any shape can contain a whole nested drawing plus markdown notes. Writes the standalone .html file DeepDraw exports and imports, and can pull icons from Iconify. Use when asked to draw, diagram, or map out a system, flow, architecture, org chart or process for DeepDraw, or to produce a .deepdraw.json / DeepDraw HTML file.
---

# DeepDraw

DeepDraw draws **hierarchies**: any shape can hold a whole drawing of its own,
plus markdown notes. That is the thing to use it for. A flat box-and-arrow
diagram is a DeepDraw drawing with the interesting half left out — put the
detail *inside* the boxes instead of spreading it across the page.

You author a **spec** (JSON), run one script, and hand back a single `.html`
file. That file opens in any browser on its own, and imports into deepdraw.ai
through **☰ → Import…** unchanged.

Paths below are written against `$SKILL`, the directory this file is in — in
Claude Code that is `${CLAUDE_SKILL_DIR}`; elsewhere it is wherever you found
`SKILL.md`.

## Workflow

1. **Plan the hierarchy first.** What are the 4–8 shapes on the top level, and
   what does each one contain? Depth is the point; two or three levels is
   normal. See `reference/layout.md`.
2. **Write the spec** to a `.json` file — a tree of shapes, `children` for
   nested drawings, defaults omitted. Full grammar: `reference/spec.md`.
3. **Icons, if the drawing wants them:** `$SKILL/scripts/iconify.py search
   <query>` then `… get <name> --node`. See `reference/icons.md`.
4. **Build:**

   ```bash
   python3 "$SKILL/scripts/build_html.py" drawing.json -o drawing.html --json
   ```

   It validates first and refuses to write a drawing that would not render. Fix
   what it reports; do not hand over a file you have not built.
5. **Tell the user what they have**: the `.html` (open it, or import it into
   deepdraw.ai) and, with `--json`, the `.deepdraw.json` DeepDraw also imports.

## Rules that are easy to get wrong

- **Every drawing is auto-fitted to the pane.** Coordinates are *relative*, and
  a small drawing is simply zoomed in more. Lay out around 800–1200 units wide,
  and keep the same style of numbers at every level — see `reference/layout.md`.
- **Labels never wrap.** Put `\n` where you want a line break, and size the
  shape to fit the longest line (roughly `fontSize * 0.58` per character).
- **Arrows connect siblings.** An endpoint names a node id in the *same*
  drawing. To point at something in another drawing, add a `link` node here and
  aim at that. The builder warns when an arrow crosses drawings.
- **Coordinates are per drawing.** A nested drawing starts its own coordinate
  space; it is not offset inside its parent.
- **Notes are where the words go.** Anything longer than a label belongs in
  `notes` (markdown), not in a bigger box.

## Reference

| File | What is in it |
|---|---|
| `reference/spec.md` | The spec grammar the builder accepts — every field, every default |
| `reference/document-format.md` | DeepDraw's own document JSON, and what the HTML file is made of |
| `reference/layout.md` | Canvas size, coordinates, sizing, arrows, nesting, colour |
| `reference/icons.md` | Iconify search and how an icon is stored in a node |
| `reference/template.html` | The export template: DeepDraw inlined, two placeholders |
| `examples/checkout-service.json` | A three-level spec using most of the model |

## Editing an existing drawing

`build_html.py` also takes a **canonical document** — the `.deepdraw.json`
DeepDraw exports, or the JSON out of an existing `.html`. Pull it out, edit it,
build it again:

```bash
python3 - <<'PY'
import re, json, pathlib
html = pathlib.Path('drawing.html').read_text()
doc = re.search(r'<script id="dd-document" type="application/json">(.*?)</script>', html, re.S).group(1)
pathlib.Path('drawing.deepdraw.json').write_text(json.dumps(json.loads(doc), indent=2))
PY
```

Node ids are preserved, so the edit is a diff rather than a new drawing.
