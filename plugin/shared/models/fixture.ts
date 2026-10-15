import type { ModelOption, RoleRoute } from './types.ts';

// Read-only catalog captured from this machine on 2026-10-15. This preview never
// claims current availability or applies launch policy; no live agent is changed.
export const catalog: ModelOption[] = [
  {id:'gpt-6.1-sol',provider:'codex-lead',name:'GPT-6.1 Sol',description:'Lead provider · technical planning and integration',efforts:['high','xhigh','max'],available:true},
  {id:'gpt-6-luna',provider:'codex-peer',name:'GPT-6 Luna',description:'Peer provider · bounded implementation and research',efforts:['high','xhigh','max'],available:true},
  {id:'gpt-6.1-sol',provider:'codex-peer',name:'GPT-6.1 Sol',description:'Peer provider · deeper implementation',efforts:['high','xhigh','max'],available:true},
  {id:'gemini-3.8-flash',provider:'antigravity-cli',name:'Gemini 3.8 Flash',description:'Antigravity UI provider · design and frontend implementation',efforts:['high'],available:true},
  {id:'claude-opus-5-5',provider:'claude-ui',name:'Opus 5.5',description:'Claude UI provider · design and frontend implementation',efforts:['high'],available:true},
  {id:'claude-opus-5-5',provider:'claude-reviewer',name:'Opus 5.5',description:'Read-only reviewer provider · independent assessment',efforts:['high'],available:true},
];
export const initialRoutes: RoleRoute[] = [
  {id:'lead',name:'Lead',description:'Owns planning, integration and engineering acceptance.',modelKey:'codex-lead/gpt-6.1-sol',effort:'xhigh'},
  {id:'peer',name:'Peer',description:'Implements a bounded engineering task.',modelKey:'codex-peer/gpt-6-luna',effort:'high'},
  {id:'ui',name:'UI specialist',description:'Designs and implements the interface.',modelKey:'antigravity-cli/gemini-3.8-flash',effort:'high'},
  {id:'advisor',name:'Advisor',description:'Provides an independent, read-only assessment.',modelKey:'claude-reviewer/claude-opus-5-5',effort:'high'},
];
// Respect role provider boundaries while testing model selection. A reviewer must
// never become a writable UI provider simply because the model name matches.
const providersByRole: Record<string,string[]> = {
  lead:['codex-lead'], peer:['codex-peer'],
  ui:['antigravity-cli','claude-ui'], advisor:['claude-reviewer'],
};
export function catalogForRole(roleId:string, source:ModelOption[]=catalog):ModelOption[] {
  return source.filter(model => providersByRole[roleId]?.includes(model.provider));
}
