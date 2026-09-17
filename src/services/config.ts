// Credentials stay in memory in browser development. Electron uses OS encryption.
let apiKey = '';
export const getApiKey = async () => window.electronAPI?.getApiKey ? window.electronAPI.getApiKey() : apiKey;
export const saveApiKey = async (key: string) => {
  if (window.electronAPI?.saveApiKey) await window.electronAPI.saveApiKey(key);
  else apiKey = key;
};
export const getModel = () => localStorage.getItem('director-model') || 'gemini-2.5-flash';
