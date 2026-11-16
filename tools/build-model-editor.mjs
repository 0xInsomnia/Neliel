// Packs model-editor/ into one self-contained HTML file (dist/model-editor.html)
// that works offline, opened straight from disk. Needs esbuild via npx.
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const root = new URL('..', import.meta.url);
const bundle = execFileSync('npx', ['--yes', 'esbuild@0.28', 'model-editor/editor.js',
  '--bundle', '--minify', '--format=iife', '--target=es2022', '--legal-comments=none'],
  { cwd: root, encoding: 'utf8', maxBuffer: 64 << 20 });
const html = readFileSync(new URL('model-editor/index.html', root), 'utf8');
const tag = '<script type="module" src="./editor.js"></script>';
if (!html.includes(tag)) throw new Error('Script tag not found in model-editor/index.html');
const inline = `<script>globalThis.NELIEL_STANDALONE=true;\n${bundle.replaceAll('</script', '<\\/script')}</script>`;
mkdirSync(new URL('dist/', root), { recursive: true });
writeFileSync(new URL('dist/model-editor.html', root), html.replace(tag, () => inline));
console.log(`dist/model-editor.html: ${Math.round((html.length + inline.length) / 1024)} kB`);
