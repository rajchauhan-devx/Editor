import React, { useState, useEffect } from 'react';
import { Titlebar } from './components/layout/Titlebar';
import { Sidebar, NavScreen } from './components/layout/Sidebar';
import { SystemBar } from './components/layout/SystemBar';
import { DashboardView } from './components/dashboard/DashboardView';
import { ImportModal } from './components/dashboard/ImportModal';
import { AnalysisView } from './components/analysis/AnalysisView';
import { EditorWorkspace, EditorSubTab } from './components/editor/EditorWorkspace';
import { AssetsView } from './components/assets/AssetsView';
import { ModelsView } from './components/models/ModelsView';
import { PrerequisitesView } from './components/prerequisites/PrerequisitesView';
import { SettingsView } from './components/settings/SettingsView';
import { Project } from './types';

import { fetchProjects } from './services/workerApi';

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean; error: string}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false, error: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message || 'An unexpected error occurred' };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('UI Crash caught by ErrorBoundary:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-950 text-white p-6 space-y-4">
          <h2 className="text-xl font-bold text-red-400">Application encountered an error</h2>
          <p className="text-sm text-slate-300 max-w-xl bg-slate-900 border border-slate-700 p-4 rounded-lg font-mono">
            {this.state.error}
          </p>
          <button 
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium"
            onClick={() => { this.setState({ hasError: false, error: '' }); window.location.reload(); }}
          >
            Reload Interface
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export const App: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeScreen, setActiveScreen] = useState<NavScreen>('dashboard');
  const [editorSubTab, setEditorSubTab] = useState<EditorSubTab>('timeline');
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  // Discover real projects on disk via local worker daemon
  useEffect(() => {
    let isMounted = true;
    async function loadRealProjects() {
      const real = await fetchProjects();
      if (isMounted) {
        setProjects(real);
        setActiveProject(previous => previous ? real.find(p => p.id === previous.id) || previous : null);
      }
    }
    loadRealProjects();
    const timer = setInterval(loadRealProjects, 4000);
    return () => { isMounted = false; clearInterval(timer); };
  }, []);

  const handleSelectProject = (project: Project, targetTab?: string) => {
    setActiveProject(project);
    if (targetTab === 'analysis') {
      setActiveScreen('analysis');
    } else if (targetTab === 'export') {
      setActiveScreen('editor');
      setEditorSubTab('export');
    } else {
      setActiveScreen('editor');
      setEditorSubTab('timeline');
    }
  };

  const handleStartNewAnalysis = (newProject: Project) => {
    setProjects(previous => [newProject, ...previous]);
    setActiveProject(newProject);
    setActiveScreen('analysis');
  };

  return (
    <ErrorBoundary>
      <div className="h-screen w-screen flex flex-col bg-[#080b11] text-slate-100 overflow-hidden select-none font-sans">
        {/* Frameless Windows Desktop Titlebar */}
        <Titlebar 
          projectName={activeProject ? activeProject.name : undefined}
          projectStatus={activeProject ? activeProject.status : undefined}
        />

        {/* Main Workspace Layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Compact Sidebar */}
          <Sidebar
            activeScreen={activeScreen}
            onNavigate={(screen) => setActiveScreen(screen)}
            activeProjectName={activeProject?.name}
            hasActiveProject={!!activeProject}
          />

          {/* Viewport Router */}
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[#0a0e17]">
            {activeScreen === 'dashboard' && (
              <DashboardView
                projects={projects}
                onOpenImport={() => setIsImportModalOpen(true)}
                onSelectProject={handleSelectProject}
              />
            )}

            {activeScreen === 'projects' && (
              <DashboardView
                projects={projects}
                onOpenImport={() => setIsImportModalOpen(true)}
                onSelectProject={handleSelectProject}
              />
            )}

            {activeScreen === 'editor' && activeProject && (
              <EditorWorkspace key={activeProject.id + editorSubTab}
                project={activeProject}
                initialSubTab={editorSubTab}
                onBackToDashboard={() => setActiveScreen('dashboard')}
              />
            )}

            {activeScreen === 'analysis' && activeProject && (
              <AnalysisView
                project={activeProject}
                onOpenEditor={() => {
                  setActiveScreen('editor');
                  setEditorSubTab('timeline');
                }}
              />
            )}

            {activeScreen === 'assets' && <AssetsView />}

            {activeScreen === 'prerequisites' && <PrerequisitesView />}

            {activeScreen === 'models' && <ModelsView />}

            {activeScreen === 'settings' && <SettingsView />}
          </main>
        </div>

        {/* Persistent System Resource Bar */}
        <SystemBar 
          apiCost={activeProject ? activeProject.costEstimate : 0}
          budgetCap={activeProject ? activeProject.costBudget : 2.00}
        />

        {/* New Project / OBS Recording Setup Modal */}
        {isImportModalOpen && <ImportModal
          isOpen={isImportModalOpen}
          onClose={() => setIsImportModalOpen(false)}
          onStartAnalysis={handleStartNewAnalysis}
        />}
      </div>
    </ErrorBoundary>
  );
};
export default App;
