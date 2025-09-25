const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  aiChat: (message, model) => ipcRenderer.invoke('ai-chat', message, model)
});