// Sahiplik: Kişi 3 (Frontend & Demo)
//
// Electron main process. Python backend'i çocuk süreç olarak başlatır (varsa),
// sonra renderer'ı yükler. Backend zaten ayrı bir terminalde çalışıyorsa
// (dev sırasında en pratik yöntem budur) bu spawn adımı sorun çıkarmaz —
// backend zaten dinliyorsa yeni bir tane daha başlatmaya çalışır, hata verirse yok sayılır.

const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const PROJECT_ROOT = path.join(__dirname, "..");
const BACKEND_PORT = 8000;

let backendProcess = null;

function startBackend() {
  // TODO(Kişi 3 / herkes): kendi venv python yolunuza göre gerekirse PYTHON_BIN'i
  // ortam değişkeni ile override edin: PYTHON_BIN=.venv/bin/python3 npm start
  const pythonBin = process.env.PYTHON_BIN || path.join(PROJECT_ROOT, ".venv", "bin", "python3");

  backendProcess = spawn(
    pythonBin,
    ["-m", "uvicorn", "backend.main:app", "--port", String(BACKEND_PORT)],
    { cwd: PROJECT_ROOT, stdio: "inherit" }
  );

  backendProcess.on("error", (err) => {
    console.warn(
      "Python backend otomatik başlatılamadı (muhtemelen zaten ayrı bir terminalde çalışıyor, veya PYTHON_BIN yanlış):",
      err.message
    );
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 750,
    webPreferences: {
      contextIsolation: true,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) backendProcess.kill();
});
