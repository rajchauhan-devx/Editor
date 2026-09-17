import React, { useState } from 'react';
import { 
  Film, 
  Mic, 
  Sparkles, 
  Palette, 
  Download, 
  ArrowLeft, 
  Save, 
  Check, 
  DollarSign 
} from 'lucide-react';
import { Project, StorySegment } from '../../types';
import { TimelineTab } from './TimelineTab';
import { VoiceTab } from './VoiceTab';
import { AIEditTab } from './AIEditTab';
import { EnhancementTab } from './EnhancementTab';
import { ExportTab } from './ExportTab';


export type EditorSubTab = 'timeline' | 'voice' | 'aiedit' | 'enhancement' | 'export';

interface EditorWorkspaceProps {
  project: Project;
  initialSubTab?: EditorSubTab;
  onBackToDashboard: () => void;
}

export const EditorWorkspace: React.FC<EditorWorkspaceProps> = ({
  project,
  initialSubTab = 'timeline',
  onBackToDashboard,
}) => {
  const [activeTab, setActiveTab] = useState<EditorSubTab>(initialSubTab);
  const [segments] = useState<StorySegment[]>([]);
  const tabs = [
    { id: 'timeline', label: 'Timeline', icon: Film },
    { id: 'voice', label: 'Voice', icon: Mic, badge: 'Hindi→En' },
    { id: 'aiedit', label: 'AI Edit', icon: Sparkles, badge: 'Story Map' },
    { id: 'enhancement', label: 'Enhancement', icon: Palette },
    { id: 'export', label: 'Export', icon: Download, badge: '1440p' },
  ];

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0a0e17] overflow-hidden">
      {/* Top Workspace Bar */}
      <header className="h-12 bg-[#0e1320] border-b border-[#1b253b] px-4 flex items-center justify-between select-none">
        {/* Left: Back button & Project Title */}
        <div className="flex items-center space-x-3">
          <button
            onClick={onBackToDashboard}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Back to Dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-xs font-bold text-white uppercase tracking-wider">
                {project.name}
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                {project.game}
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">
              {project.duration} • {project.resolution} {project.fps} FPS Master • {project.audioTracks.length} Audio Tracks
            </p>
          </div>
        </div>

        {/* Center: Tabs Switcher (Section 3: Timeline | Voice | AI Edit | Enhancement | Export) */}
        <nav className="flex items-center bg-[#131b2c] p-1 rounded-xl border border-slate-800">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as EditorSubTab)}
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-sm shadow-cyan-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className={`text-[9px] px-1 py-0.2 rounded font-mono ${
                    isActive ? 'bg-black/30 text-white' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right: Budget & Save status */}
        <div className="flex items-center space-x-3">



        </div>
      </header>

      {/* Tab Content Display */}
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {activeTab === 'timeline' && (
          <TimelineTab project={project} segments={segments} />
        )}
        {activeTab === 'voice' && <VoiceTab project={project} />}
        {activeTab === 'aiedit' && <AIEditTab project={project} />}
        {activeTab === 'enhancement' && <EnhancementTab />}
        {activeTab === 'export' && <ExportTab project={project} />}
      </main>
    </div>
  );
};
