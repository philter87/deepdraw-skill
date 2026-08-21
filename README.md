# deepdraw-skill

An agent skill for [**DeepDraw**](https://deepdraw.ai): interactive drawings
with markdown.

Great for software architecture, or for anything else with more in it than fits
on one page. Any shape can hold a whole drawing of its own, so the top level
stays the five boxes somebody should remember and the detail lives inside them.

Ask for a diagram and the agent generates **an interactive HTML file**: one
self-contained page you can open in any browser, click through, and import
straight into deepdraw.ai.

![Clicking into a drawing the skill generated](docs/demo.gif)

## See one

**[How the Web Evolved, 1989 to 2026](https://deepdraw.ai/docs/yvWsxwhm8PWM)**
is the skill working at full stretch: six eras across the top, three threads
running underneath them, and every box opening into its own drawing with notes
beside it. Click a shape twice to go in, and the breadcrumb to come back out.

That is the shape to aim for. A drawing worth keeping has:

- **Notes on the drawing itself**, so a reader who has just opened it knows what
  they are looking at before they click anything.
- **Colour that means one thing**, said out loud in those notes.
- **Two or three levels**, because a flat diagram is the one thing DeepDraw is
  not for.
- **Notes on the arrows too.** The protocol, the failure mode and the number all
  live there, and a reader clicking an arrow gets them.

## Install

The skill is the `skills/deepdraw/` directory. Every agent below reads the same
`SKILL.md`; they only disagree about where to put it.

### Claude Code

One command, from inside Claude Code:

```
/plugin marketplace add philter87/deepdraw-skill
/plugin install deepdraw@deepdraw-skill
```

Or copy it in by hand. `~/.claude/skills/` for every project, `.claude/skills/`
for one:

```bash
git clone https://github.com/philter87/deepdraw-skill
mkdir -p ~/.claude/skills && cp -r deepdraw-skill/skills/deepdraw ~/.claude/skills/
```

### GitHub Copilot

```bash
git clone https://github.com/philter87/deepdraw-skill
mkdir -p ~/.copilot/skills && cp -r deepdraw-skill/skills/deepdraw ~/.copilot/skills/
```

Per repository instead: `.github/skills/deepdraw/`.

### Codex

```bash
git clone https://github.com/philter87/deepdraw-skill
mkdir -p ~/.agents/skills && cp -r deepdraw-skill/skills/deepdraw ~/.agents/skills/
```

Per repository instead: `.agents/skills/deepdraw/`.

`~/.agents/skills/` is read by Copilot as well, so one copy there covers both.

## Use

Trigger it deliberately, with the subject after the command:

```
/deepdraw the checkout service and how it talks to payments
```

`/deepdraw` in Claude Code, `$deepdraw` in Codex, `/deepdraw` in Copilot. The
agent plans the hierarchy, writes a spec, builds it, and hands back the `.html`.

The skill sets `disable-model-invocation: true`, so in Claude Code it never
fires on its own: asking for "a diagram" gets you a diagram some other way until
you type the command. Copilot and Codex ignore that field and may still pick the
skill up from its description.

Nothing to install beyond Python 3. The scripts have no dependencies.

## What you get back

Two files beside each other:

- `drawing.html`, the page. It needs no network and no server, and the whole
  drawing travels inside it.
- `drawing.deepdraw.json`, the same drawing as JSON. It is written **compact**,
  with every DeepDraw default left out, so it is about half the size of a full
  export and small enough to read and edit by hand.

Either one imports into deepdraw.ai through **☰ → Import…**, which is where you
go to edit a drawing after the fact.

## Rebuilding the template

`skills/deepdraw/reference/template.html` is DeepDraw's own HTML export with the
title and the document punched out of it. It is generated, not edited. With a
DeepDraw checkout beside this one and its library built:

```bash
node tools/build-template.mjs --deepdraw ../deepdraw
```

## Licence

MIT. DeepDraw itself is a separate project; the library bundled inside
`skills/deepdraw/reference/template.html` belongs to it.
