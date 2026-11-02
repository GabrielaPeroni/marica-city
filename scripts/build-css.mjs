#!/usr/bin/env node
/**
 * npm run build:css
 *
 * 1. Copies the woff2 fonts into static/fonts/ (the @font-face rules live in app.css).
 * 2. Copies every Lucide icon used by {% icon "name" %} in templates, plus EXTRA_ICONS,
 *    into apps/core/icons/ (and removes icons nothing uses anymore).
 * 3. Copies the Basecoat JS we load into static/vendor/basecoat/.
 * 4. Compiles frontend/css/app.css into static/css/app.css with the Tailwind CLI.
 *
 * The outputs are committed: Docker and Vercel have no Node.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const nodeModules = path.join(root, 'node_modules');

// Icons whose name never appears literally in a template (defaults of cotton props, Python).
// Ícones vindos do Python (filtros de status do painel)
const EXTRA_ICONS = [
  'search',
  'layers',
  'sparkles',
  'circle-check',
  'square-pen',
  'archive',
  'hourglass',
  'star',
  'circle-x',
];

const FONTS = [
  '@fontsource-variable/inter/files/inter-latin-wght-normal.woff2',
  '@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2',
  '@fontsource-variable/fraunces/files/fraunces-latin-opsz-normal.woff2',
  '@fontsource-variable/fraunces/files/fraunces-latin-ext-opsz-normal.woff2',
];

const BASECOAT_JS = [
  'basecoat',
  'dropdown-menu',
  'popover',
  'toast',
  'sidebar',
  'tabs',
];

// {% icon "name" %} and icon="name" props on cotton components (<c-empty-state icon="map">)
const ICON_REFS = [
  /{%\s*icon\s+["']([a-z0-9-]+)["']/g,
  /<c-[a-z-]+\b[^>]*?\sicon="([a-z0-9-]+)"/g,
];

function walk(dir, ext) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full, ext);
    return entry.name.endsWith(ext) ? [full] : [];
  });
}

function writeIfChanged(file, content) {
  if (fs.existsSync(file) && fs.readFileSync(file).equals(Buffer.from(content))) return;
  fs.writeFileSync(file, content);
}

function copyFonts() {
  const outDir = path.join(root, 'static', 'fonts');
  fs.mkdirSync(outDir, { recursive: true });
  for (const font of FONTS) {
    writeIfChanged(
      path.join(outDir, path.basename(font)),
      fs.readFileSync(path.join(nodeModules, font))
    );
  }
}

// Strips the license comment, the lucide class and the whitespace so the tag can inline it.
function minifySvg(svg) {
  let uncommented = svg;
  let previous;
  do {
    previous = uncommented;
    uncommented = previous.replace(/<!--[\s\S]*?-->/g, '');
  } while (uncommented !== previous);
  return uncommented
    .replace(/\s+class="[^"]*"/, '')
    .replace(/\s+/g, ' ')
    .replace(/>\s+</g, '><')
    .replace(/\s+\/>/g, '/>')
    .replace(/<svg\s+/, '<svg ')
    .replace(/\s+>/g, '>')
    .trim();
}

function copyIcons() {
  const names = new Set(EXTRA_ICONS);
  for (const file of walk(path.join(root, 'templates'), '.html')) {
    const html = fs.readFileSync(file, 'utf8');
    for (const pattern of ICON_REFS) {
      for (const match of html.matchAll(pattern)) names.add(match[1]);
    }
  }
  const srcDir = path.join(nodeModules, 'lucide-static', 'icons');
  const outDir = path.join(root, 'apps', 'core', 'icons');
  fs.mkdirSync(outDir, { recursive: true });

  const missing = [...names].filter(
    name => !fs.existsSync(path.join(srcDir, `${name}.svg`))
  );
  if (missing.length) {
    console.error(`Unknown Lucide icon(s): ${missing.join(', ')}`);
    process.exit(1);
  }
  for (const name of names) {
    const svg = fs.readFileSync(path.join(srcDir, `${name}.svg`), 'utf8');
    writeIfChanged(path.join(outDir, `${name}.svg`), minifySvg(svg) + '\n');
  }
  for (const file of fs.readdirSync(outDir)) {
    if (file.endsWith('.svg') && !names.has(file.slice(0, -4))) {
      fs.rmSync(path.join(outDir, file));
    }
  }
  return names.size;
}

function copyBasecoatJs() {
  const outDir = path.join(root, 'static', 'vendor', 'basecoat');
  fs.mkdirSync(outDir, { recursive: true });
  for (const name of BASECOAT_JS) {
    const file = `${name}.min.js`;
    writeIfChanged(
      path.join(outDir, file),
      fs.readFileSync(path.join(nodeModules, 'basecoat-css', 'dist', 'js', file))
    );
  }
}

function buildCss() {
  const cli = path.join(nodeModules, '@tailwindcss', 'cli', 'dist', 'index.mjs');
  execFileSync(
    process.execPath,
    [
      cli,
      '--input',
      path.join('frontend', 'css', 'app.css'),
      '--output',
      path.join('static', 'css', 'app.css'),
      '--minify',
    ],
    { cwd: root, stdio: 'inherit' }
  );
}

copyFonts();
const iconCount = copyIcons();
copyBasecoatJs();
buildCss();
console.log(`build:css: ${FONTS.length} fonts, ${iconCount} icons, app.css`);
