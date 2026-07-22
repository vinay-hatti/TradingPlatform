export const asArray=(v:any):any[]=>Array.isArray(v)?v:Array.isArray(v?.items)?v.items:Array.isArray(v?.positions)?v.positions:Array.isArray(v?.orders)?v.orders:Array.isArray(v?.assessments)?v.assessments:Array.isArray(v?.instructions)?v.instructions:[];
export const firstNumber=(o:any,keys:string[],fallback=0)=>{for(const k of keys){const n=Number(o?.[k]);if(Number.isFinite(n))return n}return fallback};
export const money=(v:any)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(Number(v)||0);
export const pct=(v:any)=>`${((Number(v)||0)*(Math.abs(Number(v)||0)<=1?100:1)).toFixed(1)}%`;
export const statusTone=(v:any)=>{const s=String(v||'').toUpperCase();if(/PASS|ALLOW|UP|READY|FILLED|OPEN/.test(s))return 'good';if(/WARN|REVIEW|PARTIAL|PENDING|STALE/.test(s))return 'warn';if(/BLOCK|FAIL|CRITICAL|REJECT|CLOSE/.test(s))return 'bad';return 'neutral'};
