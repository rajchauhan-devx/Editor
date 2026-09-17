const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  platform: process.platform,
  getApiKey: () => ipcRenderer.invoke('get-api-key'),
  saveApiKey: (key) => ipcRenderer.invoke('save-api-key', key),
  getWorkerToken: () => ipcRenderer.invoke('get-worker-token'),
  selectRecording: () => ipcRenderer.invoke('select-recording'),
});
