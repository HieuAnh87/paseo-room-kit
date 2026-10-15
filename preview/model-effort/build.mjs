import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
const root=dirname(fileURLToPath(import.meta.url));
export async function buildPreview(){
 await build({entryPoints:[join(root,'main.tsx')],outfile:join(root,'dist/app.js'),bundle:true,jsx:'automatic',nodePaths:[join(root,'node_modules')],alias:{react:join(root,'node_modules/react'),'react-dom':join(root,'node_modules/react-dom'),'react-native':join(root,'node_modules/react-native-web')},define:{'process.env.NODE_ENV':'"development"'}});
}
if(process.argv[1]===fileURLToPath(import.meta.url)) await buildPreview();
