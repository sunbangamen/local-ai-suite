const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // 향상된 AI 채팅 API
  aiChat: (params) => ipcRenderer.invoke('ai-chat', params),

  // 모델 상태 조회
  getModelStatus: () => ipcRenderer.invoke('get-model-status'),

  // 환경 변수 접근 (추후 설정 관리용)
  getEnv: (key) => process.env[key],

  // 개발 모드 감지
  isDev: process.argv.includes('--dev')
});