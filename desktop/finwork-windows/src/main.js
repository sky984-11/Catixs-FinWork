const path = require('node:path')
const { app, BrowserWindow, Menu, shell } = require('electron')

const APP_URL = process.env.FINWORK_URL || 'https://finwork.catixs.net'
const APP_HOST = new URL(APP_URL).host

let mainWindow = null

function isAppUrl(url) {
  try {
    return new URL(url).host === APP_HOST
  } catch {
    return false
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1100,
    minHeight: 720,
    title: 'Catixs FinWork',
    backgroundColor: '#f5f7fb',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isAppUrl(url)) return { action: 'allow' }
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (isAppUrl(url)) return
    event.preventDefault()
    shell.openExternal(url)
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    const message = encodeURIComponent(`FinWork 加载失败：${errorDescription || errorCode}`)
    mainWindow.loadURL(`data:text/html;charset=utf-8,${offlinePage(message)}`)
  })

  mainWindow.loadURL(APP_URL)
}

function offlinePage(message) {
  return `
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Catixs FinWork</title>
  <style>
    body { margin: 0; height: 100vh; display: grid; place-items: center; background: #f5f7fb; font-family: "Microsoft YaHei", Arial, sans-serif; color: #0f172a; }
    main { width: min(420px, calc(100vw - 48px)); padding: 28px; border: 1px solid #dbe3ef; border-radius: 12px; background: #fff; box-shadow: 0 16px 40px rgba(15, 23, 42, .08); }
    h1 { margin: 0 0 10px; font-size: 22px; }
    p { margin: 0 0 18px; color: #64748b; line-height: 1.7; }
    button { height: 36px; border: 0; border-radius: 6px; padding: 0 16px; background: #ff4d1f; color: #fff; cursor: pointer; }
  </style>
</head>
<body>
  <main>
    <h1>Catixs FinWork</h1>
    <p>${decodeURIComponent(message)}</p>
    <button onclick="location.href='${APP_URL}'">重新加载</button>
  </main>
</body>
</html>`
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
