// dist/index.html → dist/artifact.html: the page content the Artifact skeleton
// wraps (title, styles, root, script), without doctype/html/head/body tags.
import { readFileSync, writeFileSync } from 'node:fs';
const html = readFileSync('dist/index.html', 'utf8');
const title = html.match(/<title>[\s\S]*?<\/title>/)[0];
const styles = [...html.matchAll(/<style[^>]*>[\s\S]*?<\/style>/g)].map((m) => m[0]).join('\n');
const scripts = [...html.matchAll(/<script[^>]*>[\s\S]*?<\/script>/g)].map((m) => m[0].replace(/ crossorigin/g, '')).join('\n');
writeFileSync('dist/artifact.html', `${title}\n${styles}\n<div id="root"></div>\n${scripts}\n`);
console.log('dist/artifact.html', (readFileSync('dist/artifact.html').length / 1024).toFixed(0) + ' kB');
