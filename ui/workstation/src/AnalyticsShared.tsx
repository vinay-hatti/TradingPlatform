import type { ReactNode } from 'react';

export const fmt=(value:unknown,digits=1)=>Number(value??0).toLocaleString(undefined,{maximumFractionDigits:digits});
export const tone=(value:string)=>/UNDERPRICED|HIGH|READY|BULL|POSITIVE/.test(value.toUpperCase())?'positive':/OVERPRICED|LOW|FAILED|BEAR|NEGATIVE/.test(value.toUpperCase())?'negative':'neutral';

export function AnalyticsMetric({label,value,detail}:{label:string;value:ReactNode;detail?:ReactNode}){
  return <article className="analytics-metric"><span>{label}</span><strong>{value}</strong>{detail&&<small>{detail}</small>}</article>;
}

export function DistributionBars({title,rows,valueLabel='count',onSelect,selected}:{title:string;rows:any[];valueLabel?:string;onSelect?:(row:any)=>void;selected?:string|null}){
  const max=Math.max(1,...rows.map(row=>Number(row.count??row.average??0)));
  return <section className="analytics-panel"><header><h3>{title}</h3></header><div className="distribution-bars">{rows.slice(0,18).map(row=>{const value=Number(row.count??row.average??0);const key=String(row.name??row.label);return <div className={`distribution-row ${onSelect?'interactive':''} ${selected===key?'selected':''}`} key={key} onClick={()=>onSelect?.(row)} role={onSelect?'button':undefined} tabIndex={onSelect?0:undefined} onKeyDown={event=>{if(onSelect&&(event.key==='Enter'||event.key===' ')){event.preventDefault();onSelect(row)}}}><span title={key}>{key}</span><i><b style={{width:`${Math.max(2,value/max*100)}%`}}/></i><strong>{fmt(value,2)}</strong><small>{valueLabel}</small></div>})}</div></section>;
}

export function Histogram({title,rows,markers=[],onSelect,selected}:{title:string;rows:any[];markers?:{label:string;value:number}[];onSelect?:(row:any)=>void;selected?:string|null}){
 const max=Math.max(1,...rows.map(row=>Number(row.count??0)));
 return <section className="analytics-panel histogram-panel"><header><h3>{title}</h3><div className="analytics-markers">{markers.map(marker=><span key={marker.label}>{marker.label} {marker.value}</span>)}</div></header><div className="histogram">{rows.map(row=><div className={`histogram-column ${onSelect?'interactive':''} ${selected===String(row.label)?'selected':''}`} key={row.label} onClick={()=>onSelect?.(row)} role={onSelect?'button':undefined} tabIndex={onSelect?0:undefined} onKeyDown={event=>{if(onSelect&&(event.key==='Enter'||event.key===' ')){event.preventDefault();onSelect(row)}}}><strong>{row.count}</strong><i style={{height:`${Math.max(3,Number(row.count??0)/max*100)}%`}}/><span>{row.label}</span></div>)}</div></section>;
}

export function AnalyticsTable({columns,rows,onSelect}:{columns:{key:string;label:string;render?:(row:any)=>ReactNode}[];rows:any[];onSelect?:(row:any)=>void}){
 return <div className="analytics-table-wrap"><table className="analytics-table"><thead><tr>{columns.map(column=><th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={row.snapshot_id??row.symbol+index} onClick={()=>onSelect?.(row)} className={onSelect?'selectable':''}>{columns.map(column=><td key={column.key}>{column.render?column.render(row):String(row[column.key]??'—')}</td>)}</tr>)}</tbody></table></div>;
}

const section=(title:string,value:any)=>value&&typeof value==='object'&&Object.keys(value).length?<><h3>{title}</h3><pre>{JSON.stringify(value,null,2)}</pre></>:null;

export function DetailDrawer({title,row,onClose}:{title:string;row:any;onClose:()=>void}){
 const scalarEntries=Object.entries(row??{}).filter(([,v])=>typeof v!=='object');
 return <div className="analytics-drawer-backdrop" onClick={onClose}><aside className="analytics-drawer" onClick={event=>event.stopPropagation()}><header><div><span className="eyebrow">Analytics detail</span><h2>{title}</h2></div><button onClick={onClose}>Close</button></header><div className="drawer-grid">{scalarEntries.map(([key,value])=><div key={key}><span>{key.replaceAll('_',' ')}</span><strong>{String(value??'—')}</strong></div>)}</div>{section('Components',row?.components)}{section('Coverage',row?.coverage)}{section('Relative value',row?.relative_value)}{section('Event pricing',row?.event_pricing)}{section('Segmentation',row?.segmentation)}{section('Evidence',row?.evidence)}{section('Conflicting evidence',row?.conflicting_evidence)}{section('Option legs',row?.legs)}</aside></div>;
}
