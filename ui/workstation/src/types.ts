export type Envelope<T=unknown>={status?:string;request_id:string;generated_at?:string;data:T;metadata:Record<string,unknown>};
export type ArtifactState={exists:boolean;stale:boolean;modified_at:string|null;age_seconds:number|null;path:string};
export type Overview=Record<string,ArtifactState>;
export type Health={service:string;milestone:number;status:string};
export type Readiness={ready:boolean;components:Record<string,ArtifactState>};
export type WorkspaceKey='overview'|'portfolio'|'risk'|'execution'|'positions'|'exits' | 'command';
