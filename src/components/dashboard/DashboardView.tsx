import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Play, 
  Film, 
  Clock, 
  CheckCircle, 
  Loader2, 
  FolderOpen, 
  Cpu, 
  HardDrive, 
  Sparkles, 
  ArrowRight,
  TrendingUp,
  ShieldCheck
} from 'lucide-react';
import { Project } from '../../types';
import { fetchSystemStatus, LiveSystemStatus } from '../../services/workerApi';

interface DashboardViewProps {
  projects: Project[];
  onOpenImport: () => void;
  onSelectProject: (project: Project, targetTab?: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  projects,
  onOpenImport,
  onSelectProject,
}) => {
  const [telemetry, setTelemetry] = useState<LiveSystemStatus | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function pollTelemetry() {
      const data = await fetchSystemStatus();
      if (isMounted) {
        setTelemetry(data);
      }
    }
    pollTelemetry();
    const interval = setInterval(pollTelemetry, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);
  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#0a0e17]">
      {/* Top Header & New Project Action */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-black tracking-tight text-white">STUDIO DASHBOARD</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              {telemetry?.gpu.name || 'Hardware unavailable'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Import gameplay once. Gemini understands the session. Local workers execute the edit.
          </p>
        </div>

        <button
          onClick={onOpenImport}
          className="flex items-center space-x-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 transition-all transform active:scale-98"
        >
          <Plus className="w-4 h-4 text-white" />
          <span>+ NEW PROJECT</span>
        </button>
      </div>

      {/* Quick System Health Bar (Section 4 Wireframe) */}
      <div className="grid grid-cols-4 gap-3 bg-[#101624] border border-[#1d273c] rounded-xl p-3.5 text-xs font-mono">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center text-cyan-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-500 block uppercase">GPU Load</span>
            <span className="text-slate-200 font-semibold">
              {telemetry ? `${telemetry.gpu.load_percent}% Active` : 'Unavailable'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-500 block uppercase">VRAM Alloc</span>
            <span className="text-emerald-300 font-semibold">
              {telemetry 
                ? `${(telemetry.gpu.vram_used_mb / 1024).toFixed(1)} / ${(telemetry.gpu.vram_total_mb / 1024).toFixed(1)} GB`
                : 'Unavailable'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400">
            <HardDrive className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-500 block uppercase">Fast Disk</span>
            <span className="text-slate-200 font-semibold">
              {telemetry ? `${telemetry.disk.free_gb} GB Free (${telemetry.disk.drive})` : 'Unavailable'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center text-cyan-400">
            <Sparkles className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <span className="text-[10px] text-slate-500 block uppercase">Director AI</span>
            <span className="text-cyan-300 font-semibold flex items-center gap-1">
              Configure in Settings
            </span>
          </div>
        </div>
      </div>

      {/* Recent Projects Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold tracking-wider text-slate-300 uppercase flex items-center gap-2">
            <Film className="w-3.5 h-3.5 text-cyan-400" />
            Recent Projects
          </h2>
          <span className="text-[11px] text-slate-500">{projects.length} Total Sessions</span>
        </div>

        <div className="space-y-2.5">{projects.length === 0 && <p>No projects found. Import a recording to begin; ensure the local worker is online.</p>}
          {projects.map((proj) => {
            const isAnalyzing = proj.status === 'Analyzing' || proj.status === 'Imported';
            const isPlanReady = proj.status === 'Plan Ready';
            const isCompleted = proj.status === 'Completed';

            return (
              <div
                key={proj.id}
                className="bg-[#111827] hover:bg-[#151d30] border border-[#1f2b43] hover:border-cyan-500/40 rounded-xl p-4 transition-all duration-200 flex items-center justify-between group"
              >
                {/* Left: Info */}
                <div className="flex items-center space-x-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    isAnalyzing 
                      ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30' 
                      : isPlanReady 
                      ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30' 
                      : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  }`}>
                    {isAnalyzing ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : isPlanReady ? (
                      <Sparkles className="w-5 h-5" />
                    ) : (
                      <CheckCircle className="w-5 h-5" />
                    )}
                  </div>

                  <div>
                    <div className="flex items-center space-x-2.5">
                      <h3 className="text-sm font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                        {proj.name}
                      </h3>
                      <span className="text-[10px] px-2 py-0.5 rounded font-mono text-slate-400 bg-slate-800 border border-slate-700">
                        {proj.game}
                      </span>
                    </div>

                    <div className="flex items-center space-x-3 text-[11px] text-slate-400 mt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-500" /> {proj.duration}
                      </span>
                      <span>•</span>
                      <span>{proj.resolution} @ {proj.fps}fps</span>
                      <span>•</span>
                      <span className="text-slate-500 font-mono">Source: {proj.sourceFile}</span>
                    </div>

                    {isAnalyzing && (
                      <div className="mt-2 flex items-center space-x-2">
                        <div className="w-36 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div className="bg-amber-400 h-full transition-all duration-500" style={{ width: `${proj.progress}%` }} />
                        </div>
                        <span className="text-[10px] font-mono text-amber-300 font-semibold">{proj.progress}%</span>
                        <span className="text-[10px] text-slate-500 truncate max-w-xs">{proj.currentTask}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => onSelectProject(proj, 'analysis')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 text-cyan-300 text-xs"
                  >
                    Analysis / Resume
                  </button>
                  {/* Status Badge */}
                  <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase tracking-wide font-mono ${
                    isAnalyzing
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : isPlanReady
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  }`}>
                    {proj.status}
                  </span>

                  {/* Primary CTA Button depending on status */}
                  {isAnalyzing ? (
                    <button
                      onClick={() => onSelectProject(proj, 'analysis')}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40 text-xs font-semibold transition-colors"
                    >
                      <span>Open Monitor</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  ) : isPlanReady ? (
                    <button
                      onClick={() => onSelectProject(proj, 'editor')}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-bold shadow-md shadow-cyan-500/25 transition-all"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Review / Auto Edit</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => onSelectProject(proj, 'export')}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      <span>Open export</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Import Dropzone Promo Card */}
      <div 
        onClick={onOpenImport}
        className="border border-dashed border-[#243350] hover:border-cyan-500/50 bg-gradient-to-br from-[#101728] to-[#0c121e] rounded-xl p-6 text-center cursor-pointer transition-all duration-200 group"
      >
        <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/25 text-cyan-400 flex items-center justify-center mx-auto mb-2 group-hover:scale-105 transition-transform">
          <Plus className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-bold text-slate-200 group-hover:text-cyan-300 transition-colors">
          Start a new gameplay editing session
        </h3>
        <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
          Import your raw OBS recording with Hindi/Hinglish mic audio. Let Gemini Director structure the story and dub in English.
        </p>
      </div>
    </div>
  );
};
