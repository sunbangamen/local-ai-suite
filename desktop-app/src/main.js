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

// 키워드 기반 모델 자동 선택 로직 (AI CLI에서 포팅)
const CODE_KEYWORDS = [
  "코드", "함수", "변수", "클래스", "메서드", "알고리즘", "디버깅", "버그",
  "리팩토링", "최적화", "프로그래밍", "개발", "스크립트", "API", "데이터베이스",
  "code", "function", "variable", "class", "method", "algorithm", "debug",
  "bug", "refactor", "optimize", "programming", "development", "script",
  "api", "database", "python", "javascript", "java", "cpp", "html", "css",
  "sql", "git", "docker", "framework", "library", "import", "export",
  "def ", "class ", "function ", "var ", "let ", "const ", "if ", "for ",
  "while ", "return", "print(", "console.log", "import ", "from ", "#include"
];

function detectQueryType(query) {
  const queryLower = query.toLowerCase();

  // Check for code keywords
  for (const keyword of CODE_KEYWORDS) {
    if (queryLower.includes(keyword.toLowerCase())) {
      return 'code';
    }
  }

  // Check for code patterns
  const codePatterns = [
    /def\s+\w+/i,  // Python function definition
    /function\s+\w+/i,  // JavaScript function
    /class\s+\w+/i,  // Class definition
    /import\s+\w+/i,  // Import statements
    /console\.log/i,  // console.log
    /print\s*\(/i,  // print function
    /if\s*\(/i,  // if statements
    /for\s*\(/i,  // for loops
    /{\s*.*\s*}/i,  // Code blocks
    /#\s*TODO/i,  // TODO comments
  ];

  for (const pattern of codePatterns) {
    if (pattern.test(query)) {
      return 'code';
    }
  }

  return 'chat';
}

// IPC 핸들러 확장: mode와 autoDetect 지원
ipcMain.handle('ai-chat', async (event, { message, mode = 'auto', selectedModel = null }) => {
  try {
    let targetModel;

    // 모델 선택 로직
    if (mode === 'auto') {
      const queryType = detectQueryType(message);
      targetModel = queryType === 'code' ? 'code-7b' : 'chat-7b';
    } else if (mode === 'manual' && selectedModel) {
      targetModel = selectedModel;
    } else {
      targetModel = 'chat-7b'; // 기본값
    }

    const response = await axios.post('http://localhost:8000/v1/chat/completions', {
      model: targetModel,
      messages: [{ role: 'user', content: message }],
      max_tokens: 512,
      temperature: 0.3
    });

    return {
      success: true,
      response: response.data.choices[0].message.content,
      selectedModel: targetModel,
      autoDetected: mode === 'auto',
      queryType: mode === 'auto' ? detectQueryType(message) : null
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      selectedModel: null
    };
  }
});

// 현재 모델 상태 조회 IPC 핸들러
ipcMain.handle('get-model-status', async () => {
  try {
    const response = await axios.get('http://localhost:8000/v1/models');
    return {
      success: true,
      models: response.data.data || [],
      available: true
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      available: false
    };
  }
});

console.log('🚀 Local AI Desktop App 시작됨');