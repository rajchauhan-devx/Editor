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
      const id = `proj_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
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
    {media && <>
      <p className="text-sm text-slate-300 font-medium">{media.resolution} · {media.fps} FPS · {media.duration_formatted} · {media.audio_tracks.length} audio {media.audio_tracks.length === 1 ? 'track' : 'tracks'}</p>
      
      {media.audio_tracks.length === 1 ? (
        <div className="p-3 bg-blue-950/40 border border-blue-800/60 rounded-lg text-sm text-blue-200 space-y-1">
          <p className="font-semibold text-blue-100">Single audio track detected</p>
          <p className="text-xs text-blue-300">Track 1 will be used for both gameplay audio and AI speech detection / dubbing.</p>
        </div>
      ) : media.audio_tracks.length > 1 ? (
        <>
          <div className="grid grid-cols-2 gap-4">
            {[['Game audio', game, setGame], ['Microphone', mic, setMic]].map(([label, value, setter]) => (
              <label key={String(label)} className="text-sm font-medium">{String(label)}
                <select disabled={busy} className={inputClass} value={String(value)} onChange={e => { (setter as (v: string) => void)(e.target.value); setConfirmed(false); }}>
                  {media.audio_tracks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
            ))}
          </div>
          {game === mic && (
            <p className="text-xs text-amber-300 bg-amber-950/40 border border-amber-800/60 p-2 rounded">
              Notice: Both Game audio and Microphone are set to the same track. Multi-track ducking is optimal when recorded on separate tracks.
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-red-400 bg-red-950/40 border border-red-800/60 p-2 rounded">
          No audio tracks detected in this recording. Audio is required for speech analysis.
        </p>
      )}

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input type="checkbox" checked={confirmed} disabled={busy || media.audio_tracks.length === 0} onChange={e => setConfirmed(e.target.checked)} className="rounded text-indigo-600 focus:ring-indigo-500" />
        {media.audio_tracks.length === 1
          ? "I confirm this recording is ready for import and analysis."
          : "I confirm track assignment for this recording."}
      </label>
      
      <p className="text-xs text-slate-400">Import creates local audio tracks and a proxy. Analysis uploads the proxy to Gemini when you start it from the next screen.</p>
    </>}
    {error && <p role="alert" className="text-red-300 text-sm">{error}</p>}
    {busy && <p role="status" className="text-sm text-cyan-300 animate-pulse">Processing recording. Large sessions can take several minutes...</p>}
    <div className="flex justify-end items-center gap-3">
      {!confirmed && media && media.audio_tracks.length > 0 && !busy && (
        <span className="text-xs text-slate-400">Please confirm above to continue</span>
      )}
      <button className="px-4 py-2 rounded text-slate-300 hover:text-white" disabled={busy} onClick={onClose}>Cancel</button>
      <button 
        className={buttonClass} 
        disabled={busy || !media || !confirmed || media.audio_tracks.length === 0} 
        onClick={create}
      >
        Create project
      </button>
    </div>
  </div></div>;
};
