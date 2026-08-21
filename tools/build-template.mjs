#!/usr/bin/env node
// Regenerates `skills/deepdraw/reference/template.html` from a DeepDraw checkout.
//
// The template is DeepDraw's own "Export → HTML" output with two holes punched
// in it, the title and the document JSON, which is why it is generated rather
// than edited: the file the skill hands over has to be byte-for-byte the kind of
// file the app writes, or the two drift and only the reader finds out.
//
//   node tools/build-template.mjs [--deepdraw ../deepdraw]
//
// It needs the library built there first (`cd lib && npm run build`).

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const flag = process.argv.indexOf('--deepdraw');
const deepdraw = resolve(here, '..', flag === -1 ? '../deepdraw' : process.argv[flag + 1]);

const dist = join(deepdraw, 'lib/dist');
const { createDocument, toStandaloneHtml } = await import(pathToFileURL(join(dist, 'deepdraw.esm.js')));
const library = readFileSync(join(dist, 'deepdraw.min.js'), 'utf8');

const TITLE_MARK = '__DEEPDRAW_TITLE__';
const DOCUMENT_MARK = '__DEEPDRAW_DOCUMENT_JSON__';

// A drawing built by the skill is signed by the skill as well as by DeepDraw:
// whoever wants another one wants the thing that made this one.
const html = toStandaloneHtml(createDocument(TITLE_MARK), library, {
  credit: { name: 'deepdraw-skill', url: 'https://github.com/philter87/deepdraw-skill' },
});

// The whole document, including the placeholder title inside it, is replaced.
// `build_html.py` writes the real one in.
const withHoles = html.replace(
  /(<script id="dd-document" type="application\/json">)[\s\S]*?(<\/script>)/,
  `$1${DOCUMENT_MARK}$2`,
);
if (!withHoles.includes(DOCUMENT_MARK)) throw new Error('the document script tag has moved');
if (!withHoles.includes(`<title>${TITLE_MARK}</title>`)) throw new Error('the title tag has moved');

const out = join(here, '../skills/deepdraw/reference/template.html');
writeFileSync(out, withHoles);
console.log(`wrote ${out} (${Math.round(withHoles.length / 1024)} KB)`);
