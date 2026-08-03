import type { Envelope, Health, Overview, Readiness, ScannerRun, ScannerResults, DailyScanRequest, DataRefreshRequest, ScannerUniverse } from './types';
const API_ROOT=(import.meta.env.VITE_API_ROOT||'/api/v1/platform').replace(/\/$/,'');
const SCANNER_ROOT=(import.meta.env.VITE_SCANNER_API_ROOT||'/api/v1/scanner').replace(/\/$/,'');
export class ApiError extends Error { constructor(public status:number,message:string,public payload?:unknown){super(message)} }
function headers(json=false){const h:Record<string,string>={'Accept':'application/json'};if(json)h['Content-Type']='application/json';const key=sessionStorage.getItem('trading-ai-api-key');if(key){h['X-API-Key']=key;h['X-Actor']='workstation-user'}return h;}
async function request<T>(url:string, init:RequestInit={}):Promise<Envelope<T>>{const r=await fetch(url,init);let body:unknown;try{body=await r.json()}catch{body={detail:r.statusText}}if(!r.ok)throw new ApiError(r.status,(body as any)?.detail||r.statusText,body);return body as Envelope<T>}
export async function apiGet<T>(path:string,signal?:AbortSignal):Promise<Envelope<T>>{return request<T>(`${API_ROOT}${path}`,{headers:headers(),signal})}
export const platformApi={health:(s?:AbortSignal)=>apiGet<Health>('/health',s),readiness:(s?:AbortSignal)=>apiGet<Readiness>('/readiness',s),overview:(s?:AbortSignal)=>apiGet<Overview>('/overview',s),portfolio:(s?:AbortSignal)=>apiGet<any>('/portfolio',s),risk:(s?:AbortSignal)=>apiGet<any>('/risk',s),execution:(s?:AbortSignal)=>apiGet<any>('/execution',s),positions:(s?:AbortSignal)=>apiGet<any>('/positions',s),exits:(s?:AbortSignal)=>apiGet<any>('/exit-instructions',s)};
export const scannerApi={
  universes:(s?:AbortSignal)=>request<ScannerUniverse[]>(`${SCANNER_ROOT}/universes`,{headers:headers(),signal:s}),
  runs:(s?:AbortSignal)=>request<ScannerRun[]>(`${SCANNER_ROOT}/runs`,{headers:headers(),signal:s}),
  run:(id:string,s?:AbortSignal)=>request<ScannerRun>(`${SCANNER_ROOT}/runs/${id}`,{headers:headers(),signal:s}),
  results:(id:string,s?:AbortSignal)=>request<ScannerResults>(`${SCANNER_ROOT}/runs/${id}/results`,{headers:headers(),signal:s}),
  refresh:(payload:DataRefreshRequest)=>request<ScannerRun>(`${SCANNER_ROOT}/data-refresh`,{method:'POST',headers:headers(true),body:JSON.stringify(payload)}),
  scan:(payload:DailyScanRequest)=>request<ScannerRun>(`${SCANNER_ROOT}/runs`,{method:'POST',headers:headers(true),body:JSON.stringify(payload)}),
};
