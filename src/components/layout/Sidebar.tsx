import React from 'react';
import { 
  LayoutDashboard, 
  FolderKanban, 
  Film, 
  Layers, 
  Cpu, 
  Settings as SettingsIcon,
  Flame,
  Bot,
  DownloadCloud
} from 'lucide-react';

export type NavScreen = 'dashboard' | 'projects' | 'editor' | 'analysis' | 'assets' | 'models' | 'prerequisites' | 'settings';

interface SidebarProps {
  activeScreen: NavScreen;
  onNavigate: (screen: NavScreen) => void;
  activeProjectName?: string;
  hasActiveProject: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeScreen,
  onNavigate,
  activeProjectName,
  hasActiveProject,
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'projects', label: 'Projects', icon: FolderKanban, badge: '3' },
    { id: 'editor', label: 'Editor', icon: Film, disabled: !hasActiveProject },
    { id: 'assets', label: 'Assets', icon: Layers },
    { id: 'prerequisites', label: 'Prerequisites', icon: DownloadCloud, badge: 'Download' },
    { id: 'models', label: 'AI Pipeline', icon: Cpu, badge: 'RTX' },
    { id: 'settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <aside className="w-56 bg-[#0a0e17] border-r border-[#1a2337] flex flex-col justify-between select-none py-3">
      {/* Top Section */}
      <div>
        {/* App Title Header */}
        <div className="px-4 pb-4 mb-2 border-b border-[#161f33]">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-cyan-500 via-indigo-500 to-purple-600 flex items-center justify-center shadow-md shadow-cyan-500/20">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-xs font-black tracking-wider text-white uppercase flex items-center gap-1.5">
                AI GAMING EDITOR
              </h1>
              <span className="text-[10px] text-cyan-400 font-mono tracking-tight flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                Gemini Director
              </span>
            </div>
          </div>
        </div>

        {/* Navigation List */}
        <nav className="px-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeScreen === item.id;
            const isDisabled = item.disabled;

            return (
              <button
                key={item.id}
                disabled={isDisabled}
                onClick={() => onNavigate(item.id as NavScreen)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-500/15 to-indigo-500/10 text-cyan-300 border border-cyan-500/30 shadow-sm shadow-cyan-500/10'
                    : isDisabled
                    ? 'text-slate-600 cursor-not-allowed opacity-50'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>

                {item.badge && (
                  <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                    isActive 
                      ? 'bg-cyan-500/20 text-cyan-300' 
                      : 'bg-slate-800 text-slate-400'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Active Project Info Card */}
      <div className="px-3">
        {hasActiveProject ? (
          <div className="p-2.5 rounded-lg bg-[#111726] border border-[#1f2b45] text-left">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] uppercase font-mono text-slate-400 flex items-center gap-1">
                <Flame className="w-3 h-3 text-amber-400" /> Active Session
              </span>
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            </div>
            <p className="text-xs font-medium text-slate-200 truncate">{activeProjectName}</p>
            <button 
              onClick={() => onNavigate('editor')}
              className="mt-2 w-full text-center text-[10px] font-semibold py-1 rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition-colors"
            >
              Open Editor
            </button>
          </div>
        ) : (
          <div className="p-2 rounded-lg bg-slate-900/40 border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500">No project active</span>
          </div>
        )}

        <div className="mt-3 pt-2 border-t border-[#161f33] text-[10px] text-slate-500 flex justify-between items-center px-1">
          <span>v1.0.0 (Local+Cloud)</span>
          <span className="text-emerald-400 font-mono">DESKTOP</span>
        </div>
      </div>
    </aside>
  );
};
