import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Extend window type for electronAPI
declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void;
      maximize: () => void;
      close: () => void;
      isMaximized: () => Promise<boolean>;
      platform: string;
      getApiKey?: () => Promise<string>;
      saveApiKey?: (key: string) => Promise<void>;
      getWorkerToken?: () => Promise<string>;
      selectRecording?: () => Promise<string | null>;
    };
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
