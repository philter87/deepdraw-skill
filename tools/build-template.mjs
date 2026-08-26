#!/usr/bin/env node
// Regenerates `skills/deepdraw/reference/template.html` from a DeepDraw checkout.
//
//   node tools/build-template.mjs [--deepdraw ../deepdraw]
//
// It needs the library built there first (`cd lib && npm run build`).
//
// **The library hands over the template; this script does not carve one out.**
// `templateHtml` is an export of the bundle, and asking it for the page is the
// whole of the job. It used to be done here instead — export a real drawing
// with `toStandaloneHtml`, then cut the title and the document back out with a
// regular expression — and that is a contract enforced downstream of the code
// that can break it, in a repository that finds out only when a reader does.
//
// Which is exactly what happened. `toStandaloneHtml` inlines the bundle
// verbatim, and the bundle *states the marks itself* (`TEMPLATE_MARKS` is an
// export), so the carved template carried a second copy of every mark inside
// the minified source. `build_html.py` replaces all occurrences, so every
// drawing this skill generated spliced its own title and its whole JSON into a
// string literal in the library — a page whose script does not parse and which
// therefore rendered nothing at all.
//
// `templateHtml` is built for precisely that: it spells the marks inside the
// bundle without spelling them (`hideMarks` writes the final underscore as a
// unicode escape — the same character to JavaScript, a different one to a
// search), and it refuses to return a page where any mark is not findable
// exactly once. So the failure above is now a build error here rather than a
// blank page for somebody else.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const flag = process.argv.indexOf('--deepdraw');
const deepdraw = resolve(here, '..', flag === -1 ? '../deepdraw' : process.argv[flag + 1]);

const dist = join(deepdraw, 'lib/dist');
const { templateHtml, TEMPLATE_MARKS } = await import(pathToFileURL(join(dist, 'deepdraw.esm.js')));
const library = readFileSync(join(dist, 'deepdraw.min.js'), 'utf8');

const html = templateHtml(library);

// `templateHtml` already refuses a page whose marks are not findable exactly
// once, so this is belt and braces — but it is the assertion the old approach
// lacked, and it costs nothing to keep saying it out loud.
for (const [name, mark] of Object.entries(TEMPLATE_MARKS)) {
  const found = html.split(mark).length - 1;
  if (found !== 1) throw new Error(`the ${name} mark appears ${found} times in the template, not once`);
}

const out = join(here, '../skills/deepdraw/reference/template.html');
writeFileSync(out, html);
console.log(`wrote ${out} (${Math.round(html.length / 1024)} KB)`);
