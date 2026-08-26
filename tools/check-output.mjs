#!/usr/bin/env node
// Builds the bundled example and checks that what comes out actually works.
//
//   node tools/check-output.mjs
//
// There is one thing here worth checking above all others, and it is the thing
// that was broken for two releases without anybody noticing: **the library
// inlined in a generated page has to parse.** It did not. `build_html.py` filled
// in a mark that also appeared inside the minified bundle, splicing the
// drawing's JSON into a string literal, so every page this skill wrote threw a
// SyntaxError on load and rendered nothing. The file was the right size, opened
// without complaint, and was blank.
//
// Nothing about the shape of that failure is visible from the outside, which is
// why it survived: no output to diff, no error to grep, and the only symptom is
// a reader seeing an empty page. So the check is to take the page apart and run
// the parser over it.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const skill = join(here, '../skills/deepdraw');
const work = mkdtempSync(join(tmpdir(), 'deepdraw-skill-check-'));

let failures = 0;
const check = (name, run) => {
  try {
    run();
    console.log(`  ok    ${name}`);
  } catch (error) {
    failures++;
    console.log(`  FAIL  ${name}\n        ${error.message}`);
  }
};

try {
  const out = join(work, 'drawing.html');
  let html;
  try {
    execFileSync(
      'python3',
      [join(skill, 'scripts/build_html.py'), join(skill, 'examples/checkout-service.json'), '-o', out, '--seed', '1'],
      { stdio: 'pipe' },
    );
    html = readFileSync(out, 'utf8');
  } catch (error) {
    // A build that refuses is a *result*, not a crash: `build_html.py` rejecting
    // a template whose marks have doubled is exactly what this script exists to
    // surface, and a stack trace would bury the one line that says why.
    const said = (error.stderr?.toString() || error.message).trim();
    console.log(`  FAIL  the example builds at all\n        ${said}`);
    console.log('\n1 check(s) failed');
    process.exit(1);
  }

  check('the inlined library parses', () => {
    const match = /<script id="dd-library">([\s\S]*?)<\/script>/.exec(html);
    if (!match) throw new Error('there is no dd-library script in the page');
    // `new Function` compiles without running: a SyntaxError here is exactly
    // what the browser would hit, and nothing else executes.
    new Function(match[1]);
  });

  check('the document is valid JSON and holds the drawing', () => {
    const match = /<script id="dd-document" type="application\/json">([\s\S]*?)<\/script>/.exec(html);
    if (!match) throw new Error('there is no dd-document script in the page');
    const doc = JSON.parse(match[1]);
    if (!doc.nodes || Object.keys(doc.nodes).length === 0) throw new Error('the document has no nodes');
  });

  check('no mark is left unfilled', () => {
    for (const mark of ['__DEEPDRAW_TITLE__', '__DEEPDRAW_DOCUMENT_JSON__', '__DEEPDRAW_CREDIT__']) {
      if (html.includes(mark)) throw new Error(`${mark} is still in the output`);
    }
  });

  check('the page is signed by both', () => {
    if (!html.includes('deepdraw.ai')) throw new Error('the DeepDraw credit is missing');
    if (!html.includes('deepdraw-skill')) throw new Error('the skill credit is missing');
  });

  check('the vendored template matches the version it is stamped with', () => {
    const stamped = readFileSync(join(skill, 'reference/.deepdraw-version'), 'utf8').trim();
    const template = readFileSync(join(skill, 'reference/template.html'), 'utf8');
    // The bundle states its own version, so the page can be asked rather than
    // trusted. A stamp that has moved on without the template being rebuilt is
    // the drift the stamp exists to make visible.
    if (!template.includes(`"${stamped}"`) && !template.includes(`'${stamped}'`)) {
      throw new Error(`template.html does not carry ${stamped}; rebuild it with tools/build-template.mjs`);
    }
  });
} finally {
  rmSync(work, { recursive: true, force: true });
}

console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed');
process.exit(failures ? 1 : 0);
