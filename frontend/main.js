// Sahiplik: Kişi 1 (ali-erdem) — Electron↔Python bağlantısı bu dosyanın en kritik parçası.
//
// Electron main process. Önce backend zaten ayrı bir terminalde çalışıyor mu diye
// /ping ile kontrol eder (demo sırasında en güvenilir yöntem budur — backend'i elle,
// ayrı bir terminalde başlatın). Çalışmıyorsa birkaç olası python yolunu sırayla
// deneyerek otomatik başlatmaya çalışır VE gerçekten ayağa kalktığını /ping ile
// doğrular — sadece "bir süreç başlattım" demek yetmez, o süreç bir saniye sonra
// çökebilir (ör. eksik pip paketi). Başarısız olursa sessizce boş bir pencere
// açmak yerine kullanıcıya AÇIK bir hata penceresi gösteriyoruz.

const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const PROJECT_ROOT = path.join(__dirname, "..");
const BACKEND_PORT = 8000;
const PING_URL = `http://127.0.0.1:${BACKEND_PORT}/ping`;
const BACKEND_START_TIMEOUT_MS = 45000; // Whisper modeli ilk yüklemede birkaç saniye sürebilir

let backendProcess = null;
let backendStderrTail = "";

async function pingOnce() {
  try {
    const res = await fetch(PING_URL, { signal: AbortSignal.timeout(1000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function waitForBackend(timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await pingOnce()) return true;
    // backend süreci başlatılamadan (spawn hatası) veya çökerek erken
    // kapandıysa, kalan süreyi beklemeye gerek yok.
    if (backendProcess && backendProcess.exitCode !== null) return false;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
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

function trySpawn(pythonBin) {
  console.log(`[backend] deneniyor: ${pythonBin}`);
  backendStderrTail = "";
  const proc = spawn(
    pythonBin,
    ["-m", "uvicorn", "backend.main:app", "--port", String(BACKEND_PORT)],
    { cwd: PROJECT_ROOT }
  );

  proc.stdout.on("data", (chunk) => process.stdout.write(chunk));
  proc.stderr.on("data", (chunk) => {
    process.stderr.write(chunk);
    backendStderrTail = (backendStderrTail + chunk.toString()).slice(-4000);
  });
  proc.on("exit", (code) => {
    if (code !== null && code !== 0) {
      console.error(`[backend] "${pythonBin}" beklenmedik şekilde kapandı (kod ${code}).`);
    }
  });

  backendProcess = proc;
  return new Promise((resolve) => {
    proc.on("error", (err) => {
      backendStderrTail += `\n[spawn hatası] ${err.message}`;
      resolve(false);
    });
    // spawn hatası hemen gelmezse, waitForBackend zaten exitCode'u izleyip
    // erken çıkışı (ör. ImportError) yakalayacak.
    resolve(true);
  });
}

async function ensureBackend() {
  if (await pingOnce()) {
    console.log("[backend] zaten çalışıyor, ayrıca başlatılmayacak.");
    return true;
  }

  for (const pythonBin of candidatePythonPaths()) {
    const spawned = await trySpawn(pythonBin);
    if (!spawned) continue;
    const ok = await waitForBackend(BACKEND_START_TIMEOUT_MS);
    if (ok) return true;
    if (backendProcess) backendProcess.kill();
  }
  return false;
}

function showBackendFailureDialog() {
  const detail =
    "Backend başlatılamadı ya da hemen çöktü. En sık sebep: Python paketleri eksik/güncel değil.\n\n" +
    "Terminalde şunu çalıştırıp tekrar deneyin:\n" +
    "  source .venv/bin/activate\n" +
    "  pip install -r backend/requirements.txt\n" +
    "  uvicorn backend.main:app --port 8000\n\n" +
    (backendStderrTail ? `Son hata çıktısı:\n${backendStderrTail.slice(-1500)}` : "");

  dialog.showErrorBox("Backend'e bağlanılamadı", detail);
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 750,
    title: "Yaşlı Bakım Rehberi",
    webPreferences: {
      contextIsolation: true,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.setName("Yaşlı Bakım Rehberi");

app.whenReady().then(async () => {
  const backendReady = await ensureBackend();
  if (!backendReady) showBackendFailureDialog();
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
