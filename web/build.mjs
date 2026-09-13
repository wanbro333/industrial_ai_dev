import { build } from 'esbuild';
import { mkdir, copyFile, cp } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(root, '../unity/Assets/WebGLTemplates/Industrial');
await mkdir(out,{recursive:true});
await build({entryPoints:[path.join(root,'src/main.js')],bundle:true,minify:true,format:'iife',platform:'browser',target:'es2020',
  outfile:path.join(out,'app.js'),legalComments:'linked'});
await copyFile(path.join(root,'index.html'),path.join(out,'index.html'));
await copyFile(path.join(root,'style.css'),path.join(out,'style.css'));
await cp(path.join(root,'../third_party'),path.join(out,'ThirdParty'),{recursive:true});
console.log('Unity WebGL template built: ' + out);
