const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const axios = require('axios');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC 핸들러
ipcMain.handle('ai-chat', async (event, message, model = 'qwen2.5-14b-instruct') => {
  try {
    const response = await axios.post('http://localhost:8000/v1/chat/completions', {
      model: model,
      messages: [{ role: 'user', content: message }],
      max_tokens: 512,
      temperature: 0.3
    });

    return {
      success: true,
      response: response.data.choices[0].message.content
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

console.log('🚀 Local AI Desktop App 시작됨');