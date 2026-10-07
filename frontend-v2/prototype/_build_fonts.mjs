import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const nm = path.join(root, 'node_modules');
const outDir = path.join(root, 'assets', 'fonts');
const filesDir = path.join(outDir, 'files');
fs.mkdirSync(filesDir, { recursive: true });

const wants = [
  ['@fontsource/noto-serif-sc', ['700', '900']],
  ['@fontsource/noto-sans-sc', ['300', '400', '500', '700']],
  ['@fontsource/jetbrains-mono', ['400', '500', '700']],
  ['@fontsource/instrument-serif', ['400']],
];

let merged = [];
let copied = 0;
for (const [pkg, weights] of wants) {
  const pkgShort = pkg.split('/')[1];
  const pkgDir = path.join(nm, pkg);
  for (const w of weights) {
    const css = fs.readFileSync(path.join(pkgDir, w + '.css'), 'utf8');
    const re = /\/\* ([^*]+?) \*\/\s*@font-face\s*\{([^}]+)\}/g;
    let m;
    let out = '';
    while ((m = re.exec(css))) {
      const subset = m[1];
      const body = m[2];
      if (subset === 'symbols' || subset === 'math') continue;
      const urlMatch = body.match(/url\(\.\/files\/([^)]+\.woff2)\)/);
      if (!urlMatch) continue;
      const fname = urlMatch[1];
      const src = path.join(pkgDir, 'files', fname);
      const destName = pkgShort + '-' + fname;
      fs.copyFileSync(src, path.join(filesDir, destName));
      copied++;
      out += '/* ' + pkgShort + ' ' + w + ' ' + subset + ' */\n@font-face {' + body.replace(/\.\/files\//g, './files/' + pkgShort + '-') + '}\n';
    }
    merged.push(out);
  }
}
fs.writeFileSync(path.join(outDir, 'fonts.css'), merged.join('\n'));
console.log('copied files:', copied, 'css bytes:', fs.statSync(path.join(outDir, 'fonts.css')).size);
