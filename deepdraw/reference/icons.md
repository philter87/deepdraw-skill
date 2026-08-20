# Icons

DeepDraw's icon picker searches the public **Iconify** API and stores what comes
back — raw `<svg>` markup — in the node's `href`. Nothing is fetched at render
time, so an exported drawing keeps its icons offline. `scripts/iconify.py` calls
the same two endpoints.

## Finding one

```bash
python3 scripts/iconify.py search database
python3 scripts/iconify.py search "message queue" --limit 40
python3 scripts/iconify.py search server --sets material-symbols,lucide
```

Names are `prefix:name` — `material-symbols:database`, `lucide:server`,
`simple-icons:postgresql`. Search ranks whole icon sets ahead of single glyphs,
so **pass `--sets` when a drawing should keep one visual family**; mixing sets
in one diagram looks like an accident. Good defaults:

| Set | For |
|---|---|
| `material-symbols` | General UI and infrastructure; what DeepDraw's picker shows first |
| `lucide` | Lighter line work, when the drawing is mostly strokes |
| `simple-icons` | Brand marks — AWS, Postgres, GitHub, Kubernetes |
| `logos` | Brand marks **in their own colours** (see below) |

## Putting it in the drawing

```bash
python3 scripts/iconify.py get material-symbols:database --node --label "Postgres"
```

prints a spec node ready to paste:

```json
{
  "id": "material-symbols-database",
  "type": "icon",
  "x": 0, "y": 0, "w": 64, "h": 64,
  "text": "Postgres",
  "href": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1em\" height=\"1em\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M18.375 9.825…\"/></svg>"
}
```

`--size` changes the box; 48–96 is the useful range. Without `--node` it prints
the markup alone, for pasting into an `href` you are editing.

## How an icon node behaves

- The SVG is scaled into the node's box, so `w` and `h` decide the size. Keep
  them square unless the glyph is not.
- Its ink is the node's **`textColor`**, because Iconify ships
  `fill="currentColor"`. Recolour an icon through
  `"style": { "textColor": "#2563eb" }`, not through `fill`.
- Its label is drawn **below** the box (`vAlign: "below"` by default), so leave
  ~24 units of room under it.
- `logos:*` icons carry their own colours and ignore `textColor`. Use them for
  brand marks and nothing else; a drawing of ten brand logos has no palette
  left of its own.

## When not to use one

An icon is a label with a picture on it. A box with a name in it says more, and
can be drilled into. Use icons for a legend, for a row of technologies, or
beside a box — not as the boxes themselves.
