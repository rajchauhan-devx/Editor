import React, { useState } from 'react';
import { testGeminiApiKey } from '../../services/workerApi';
import { saveApiKey, getModel } from '../../services/config';
import { Panel, buttonClass, inputClass } from '../Panel';
export function SettingsView() {
  const [key, setKey] = useState(''); const [model, setModel] = useState(getModel);
  const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  return <Panel title="Settings"><p>Enter your own Gemini API key. Desktop credentials use OS encryption; browser development keeps the key in memory for this session.</p>
    <label className="block">Gemini API key<input type="password" autoComplete="off" className={inputClass} value={key} onChange={e=>setKey(e.target.value)} /></label>
    <label className="block">Director model ID<input className={inputClass} value={model} onChange={e=>setModel(e.target.value)} /></label>
    <button className={buttonClass} disabled={busy || !key.trim() || !model.trim()} onClick={async()=>{setBusy(true); try { const result=await testGeminiApiKey(key.trim()); if(!result.success) throw new Error(result.message || 'Connection failed'); await saveApiKey(key.trim()); localStorage.setItem('director-model',model.trim()); setKey(''); setMessage('Connection verified. Settings saved.'); } catch(e){setMessage(String(e));} finally{setBusy(false);}}}>Test connection and save</button>
    <p role="status">{message}</p><p className="text-amber-300">API cost estimates and a hard project budget cap are not implemented. Check billing in your Google account before analysis.</p>
  </Panel>;
}
