const { app, BrowserWindow, ipcMain, shell, safeStorage, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
let worker = null;

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#080b11',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https:') || url.startsWith('http:')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event) => event.preventDefault());

  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(() => {
  const workerPath = app.isPackaged
    ? path.join(process.resourcesPath, 'python-worker', 'server.py')
    : path.join(__dirname, '..', 'python-worker', 'server.py');
  worker = spawn(process.env.AIGE_PYTHON || 'python', [workerPath], { windowsHide: true, stdio: 'ignore' });
  worker.on('error', () => { worker = null; });
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => { if (worker) worker.kill(); });

function trusted(event) {
  if (!mainWindow || event.sender !== mainWindow.webContents || event.senderFrame !== mainWindow.webContents.mainFrame) {
    throw new Error('Untrusted desktop request');
  }
}
ipcMain.handle('save-api-key', (event, key) => {
  trusted(event);
  if (typeof key !== 'string' || key.length > 1024) throw new Error('Invalid key');
  if (!safeStorage.isEncryptionAvailable()) throw new Error('OS credential encryption is unavailable');
  fs.writeFileSync(path.join(app.getPath('userData'), 'gemini-key.bin'), safeStorage.encryptString(key));
});
ipcMain.handle('get-api-key', event => {
  trusted(event);
  const filename = path.join(app.getPath('userData'), 'gemini-key.bin');
  return fs.existsSync(filename) ? safeStorage.decryptString(fs.readFileSync(filename)) : '';
});
ipcMain.handle('get-worker-token', async event => {
  trusted(event);
  const filename = path.join(process.env.LOCALAPPDATA || app.getPath('home'), 'AIGamingEditor', 'worker-token');
  for (let attempt = 0; attempt < 40; attempt++) {
    if (fs.existsSync(filename)) return fs.readFileSync(filename, 'utf8').trim();
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error('Local worker did not start. Check Python and worker dependencies.');
});
ipcMain.handle('select-recording', async event => {
  trusted(event);
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'], filters: [{name: 'Gameplay recordings', extensions: ['mkv', 'mp4', 'mov', 'webm', 'avi']}],
  });
  return result.canceled ? null : result.filePaths[0];
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Window controls IPC
ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('window-is-maximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});
