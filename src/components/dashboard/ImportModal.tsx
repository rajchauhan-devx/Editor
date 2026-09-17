import React, { useState } from 'react';
import { Project } from '../../types';
import { inspectMedia, prepareSession, InspectedMediaResult } from '../../services/workerApi';
import { buttonClass, inputClass } from '../Panel';
export const ImportModal: React.FC<{isOpen: boolean; onClose: () => void; onStartAnalysis: (p: Project) => void}> = ({isOpen, onClose, onStartAnalysis}) => {
  const [path, setPath] = useState('');
  const [media, setMedia] = useState<InspectedMediaResult | null>(null);
  const [game, setGame] = useState('');
  const [mic, setMic] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!isOpen) return null;
  const inspect = async (value = path) => {
    setBusy(true); setError(''); setMedia(null); setConfirmed(false);
    try {
      const data = await inspectMedia(value);
      if (!data) throw new Error('Could not inspect this recording. Check the path and worker.');
      setMedia(data); setPath(data.file_path);
      setGame(String(data.suggested_mapping.game_track)); setMic(String(data.suggested_mapping.mic_track));
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const create = async () => {
    if (!media) return;
    setBusy(true); setError('');
    try {
      const id = `proj_${crypto.randomUUID()}`;
      const name = media.file_name.replace(/\.[^.]+$/, '');
      const result = await prepareSession({filePath: media.file_path, projectId: id, projectName: name, gameTrack: Number(game), micTrack: Number(mic)});
      if (!result?.success) throw new Error(result?.detail || 'Import failed. No completed project was created.');
      onStartAnalysis({id, name, game: 'Gameplay', status: 'Imported', duration: media.duration_formatted,
        durationSeconds: media.duration_seconds, sourceFile: media.file_name, resolution: media.resolution,
        fps: media.fps, codec: media.video_codec, audioTracks: media.audio_tracks, progress: 0,
        lastActive: 'Just now', costEstimate: 0, costBudget: 0, proxySizeMb: result.proxy.proxy_size_mb});
      onClose();
    } catch(e) { setError(String(e)); } finally { setBusy(false); }
  };
  return <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"><div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-2xl space-y-4">
    <h2 className="text-lg font-bold">Import gameplay recording</h2>
    <label className="block">Recording path<input className={inputClass} value={path} disabled={busy} onChange={e => {setPath(e.target.value); setMedia(null); setConfirmed(false);}} /></label>
    <div className="flex gap-2"><button className={buttonClass} disabled={busy || !path} onClick={() => inspect()}>Inspect</button>
      {window.electronAPI?.selectRecording && <button className={buttonClass} disabled={busy} onClick={async () => {const p = await window.electronAPI!.selectRecording!(); if(p) {setPath(p); await inspect(p);}}}>Browse</button>}</div>
    {media && <><p>{media.resolution} · {media.fps} FPS · {media.duration_formatted} · {media.audio_tracks.length} audio tracks</p>
      <div className="grid grid-cols-2 gap-4">{[['Game audio',game,setGame],['Microphone',mic,setMic]].map(([label,value,setter]) => <label key={String(label)}>{String(label)}<select disabled={busy} className={inputClass} value={String(value)} onChange={e => { (setter as (v:string)=>void)(e.target.value); setConfirmed(false); }}>{media.audio_tracks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>)}</div>
      <label className="block text-sm"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} /> I confirm these are separate game-only and microphone-only tracks.</label>
      <p className="text-sm text-slate-400">Import creates local audio tracks and a proxy. Analysis uploads the proxy to Gemini when you start it from the next screen.</p></>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {busy && <p role="status">Processing recording. Large sessions can take several minutes.</p>}
    <div className="flex justify-end gap-3"><button disabled={busy} onClick={onClose}>Cancel</button><button className={buttonClass} disabled={busy || !media || !confirmed || game === mic || media.audio_tracks.length < 2} onClick={create}>Create project</button></div>
  </div></div>;
};
