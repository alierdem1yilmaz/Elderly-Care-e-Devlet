// Sahiplik: Kişi 1 (ali-erdem) — Electron↔Python bağlantısı bu dosyanın en kritik parçası.
//
// Electron main process. Önce backend zaten ayrı bir terminalde çalışıyor mu diye
// /ping ile kontrol eder (demo sırasında en güvenilir yöntem budur — backend'i elle,
// ayrı bir terminalde başlatın). Çalışmıyorsa birkaç olası python yolunu sırayla
// deneyerek otomatik başlatmaya çalışır.

const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const PROJECT_ROOT = path.join(__dirname, "..");
const BACKEND_PORT = 8000;
const PING_URL = `http://127.0.0.1:${BACKEND_PORT}/ping`;

let backendProcess = null;

async function isBackendAlreadyRunning() {
  try {
    const res = await fetch(PING_URL, { signal: AbortSignal.timeout(1000) });
    return res.ok;
  } catch {
    return false;
  }
}

function candidatePythonPaths() {
  const candidates = [];
  if (process.env.PYTHON_BIN) candidates.push(process.env.PYTHON_BIN);
  candidates.push(path.join(PROJECT_ROOT, ".venv", "bin", "python3"));
  candidates.push(path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")); // Windows venv
  candidates.push("python3");
  candidates.push("python");
  return candidates.filter((p, i, arr) => arr.indexOf(p) === i);
}

function trySpawn(pythonBin, remaining) {
  console.log(`[backend] deneniyor: ${pythonBin}`);
  const proc = spawn(
    pythonBin,
    ["-m", "uvicorn", "backend.main:app", "--port", String(BACKEND_PORT)],
    { cwd: PROJECT_ROOT, stdio: "inherit" }
  );

  proc.on("error", (err) => {
    console.warn(`[backend] "${pythonBin}" başarısız: ${err.message}`);
    if (remaining.length > 0) {
      trySpawn(remaining[0], remaining.slice(1));
    } else {
      console.error(
        "[backend] Hiçbir python yolu çalışmadı. Backend'i elle başlatın:\n" +
          "  source .venv/bin/activate && uvicorn backend.main:app --port 8000"
      );
    }
  });

  backendProcess = proc;
}

async function ensureBackend() {
  if (await isBackendAlreadyRunning()) {
    console.log("[backend] zaten çalışıyor, ayrıca başlatılmayacak.");
    return;
  }
  const [first, ...rest] = candidatePythonPaths();
  trySpawn(first, rest);
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

app.whenReady().then(async () => {
  await ensureBackend();
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
