import React, { useEffect, useState } from 'react';
import { Project } from '../../types';
import { requestWorker, fetchProjectData } from '../../services/workerApi';
import { getApiKey, getModel } from '../../services/config';
import { Panel, buttonClass } from '../Panel';
export function AnalysisView({project,onOpenEditor}: {project:Project; onOpenEditor:()=>void}) {
  const [state,setState]=useState<any>({status:'idle',stage:'Ready to analyze'});
  const [data,setData]=useState<any>(null); const [error,setError]=useState(''); const [starting,setStarting]=useState(false);
  useEffect(()=>{let alive=true; const poll=async()=>{try {const [s,d]=await Promise.all([requestWorker(`/api/pipeline/status/${project.id}`),fetchProjectData(project.id)]); if(alive){setState(s);setData(d);}}catch(e){if(alive)setError(String(e));}}; poll(); const timer=setInterval(poll,2000); return()=>{alive=false;clearInterval(timer);};},[project.id]);
  const stages=[['Media and proxy',data?.media],['Transcript',data?.transcript],['Story map and English rewrite',data?.edit_plan],['English voice track',data?.voice_manifest],['Final export',data?.render_manifest]];
  return <Panel title={`Analysis: ${project.name}`}><p role="status">{state.stage} — {state.status}</p>
    <ul className="space-y-3">{stages.map(([label,artifact])=><li key={label as string}>{artifact?'✓ Saved':'○ Pending'} · {label as string}</li>)}</ul>
    <p className="text-slate-400">Start/resume reuses completed stages. New analysis sends the video proxy and transcript to Google Gemini. API charges may apply; the app does not yet enforce a budget cap.</p>
    {(error || state.error) && <p role="alert" className="text-red-300">{error || state.error}</p>}
    <div className="flex gap-3"><button className={buttonClass} disabled={starting || ['running','queued'].includes(state.status)} onClick={async()=>{setStarting(true);setError('');try{await requestWorker('/api/pipeline/start',{method:'POST',body:JSON.stringify({project_id:project.id,api_key:await getApiKey(),model_name:getModel()})});setState({status:'queued',stage:'Starting'});}catch(e){setError(String(e));}finally{setStarting(false);}}}>Start / resume analysis</button><button className={buttonClass} onClick={onOpenEditor}>Open editor</button></div>
  </Panel>;
}
