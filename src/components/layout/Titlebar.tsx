import React, { useState, useEffect } from 'react';
import { Minus, Square, Copy, X, Sparkles } from 'lucide-react';

interface TitlebarProps {
  projectName?: string;
  projectStatus?: string;
}

export const Titlebar: React.FC<TitlebarProps> = ({ projectName, projectStatus }) => {
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.isMaximized().then(setIsMaximized);
    }
  }, []);

  const handleMinimize = () => {
    if (window.electronAPI) window.electronAPI.minimize();
  };

  const handleMaximize = () => {
    if (window.electronAPI) {
      window.electronAPI.maximize();
      window.electronAPI.isMaximized().then(setIsMaximized);
    }
  };

  const handleClose = () => {
    if (window.electronAPI) window.electronAPI.close();
  };

  return (
    <div className="h-9 w-full bg-[#0a0e17] border-b border-[#1b253b] flex items-center justify-between px-3 select-none drag-region text-xs z-50">
      {/* Brand & Project Info */}
      <div className="flex items-center space-x-3 no-drag">
        <div className="flex items-center space-x-2">
          <div className="w-5 h-5 rounded bg-gradient-to-br from-cyan-500 to-indigo-600 flex items-center justify-center shadow-sm shadow-cyan-500/30">
            <Sparkles className="w-3 h-3 text-white" />
          </div>
          <span className="font-bold tracking-wider text-slate-200 text-xs">AI GAMING EDITOR</span>
        </div>

        <div className="h-3 w-[1px] bg-slate-700 mx-1" />

        {projectName ? (
          <div className="flex items-center space-x-2">
            <span className="text-slate-400 font-medium">{projectName}</span>
            {projectStatus && (
              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wide uppercase ${
                projectStatus === 'Analyzing'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse'
                  : projectStatus === 'Plan Ready'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : projectStatus === 'Completed'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400'
              }`}>
                {projectStatus}
              </span>
            )}
          </div>
        ) : (
          <span className="text-slate-500 text-[11px]">Gemini Director Edition • Windows</span>
        )}
      </div>

      {/* Dragging space */}
      <div className="flex-1 h-full drag-region" />

      {/* Window Controls */}
      <div className="flex items-center space-x-1 no-drag">
        <button
          onClick={handleMinimize}
          className="w-7 h-6 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
          title="Minimize"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={handleMaximize}
          className="w-7 h-6 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
          title={isMaximized ? "Restore" : "Maximize"}
        >
          {isMaximized ? <Copy className="w-3 h-3 rotate-180" /> : <Square className="w-3 h-3" />}
        </button>
        <button
          onClick={handleClose}
          className="w-7 h-6 flex items-center justify-center text-slate-400 hover:text-white hover:bg-red-600 rounded transition-colors"
          title="Close"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
