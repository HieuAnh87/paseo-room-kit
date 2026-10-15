import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ModelSettings} from '../../plugin/client/models/model-settings.tsx';
import {catalog,catalogForRole,initialRoutes} from '../../plugin/shared/models/fixture.ts';
const params=new URLSearchParams(location.search);
const dark=params.get('theme')!=='light';
const colors={surface0:dark?'#131416':'#fafafa',surface1:dark?'#1b1c1f':'#ffffff',surface2:dark?'#25262b':'#efeff1',foreground:dark?'#efeff1':'#202126',foregroundMuted:dark?'#a7a8af':'#62636c',border:dark?'#33353c':'#dcdee3',accent:dark?'#a5b4fc':'#4355be',accentForeground:dark?'#181b31':'#ffffff',statusWarning:dark?'#ebc374':'#805800',statusDanger:dark?'#fb9ca7':'#b0243c',statusSuccess:dark?'#7bd9a0':'#207342'};
function App(){
 const [width,setWidth]=useState(innerWidth);
 useEffect(()=>{const resize=()=>setWidth(innerWidth);addEventListener('resize',resize);return()=>removeEventListener('resize',resize)},[]);
 const previewCatalog=params.has('unavailable')?catalog.map(m=>({...m,available:m.provider!=='claude-ui'})):catalog;
 const save=params.has('saveError')?async()=>{await new Promise(r=>setTimeout(r,400));throw new Error('Preview save failed. Your changes are still here.');}:undefined;
 return <ModelSettings theme={{colors}} layout={{compact:width<760,platform:'web'}} catalog={previewCatalog} modelsForRole={catalogForRole} initialRoutes={initialRoutes} onSave={save}/>;
}
createRoot(document.getElementById('root')!).render(<App/>);
