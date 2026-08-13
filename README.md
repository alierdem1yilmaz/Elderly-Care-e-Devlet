# Yaşlı Bakım Rehberlik Asistanı — DemoDay

Yaşlı vatandaşların hak sahibi oldukları sosyal yardımlara ulaşmasını ve e-Devlet sürecini anlamasını kolaylaştıran, **yönlendirici (guide-only)** bir masaüstü asistan. Detaylı mimari/karar gerekçeleri için: `/Users/user/.claude/plans/soft-strolling-meadow.md`. API şeması için: `API_CONTRACT.md`.

**Temel ilke: sistem hiçbir işlemi kullanıcı adına yapmaz** (form doldurmaz, e-Devlet'e giriş yapmaz, başvuru göndermez). Sadece bilgilendirir, adım adım anlatır, checklist üretir, hatırlatır.

## Kurulum

```bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

## Çalıştırma (geliştirme sırasında)

```bash
# Terminal 1 — backend
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm start
```

(`frontend/main.js` backend'i otomatik başlatmayı dener ama en güvenilir yöntem, geliştirme sırasında backend'i ayrı bir terminalde elle çalıştırmaktır.)

## Görev Dağılımı (3 kişi)

| Kişi | Branch | Kapsam |
|---|---|---|
| **Kişi 1** | `feature/backend-core` | `backend/main.py`, `backend/agents/orchestrator.py`, `backend/agents/eligibility_agent.py`, `backend/agents/security_agent.py` — Claude Agent SDK entegrasyonu, "guide-only" ilkesinin merkezi uygulanması |
| **Kişi 2** | `feature/backend-content` | `backend/data/benefits.json` (gerçek kriter araştırması), `backend/agents/guide_agent.py`, `backend/agents/tracking_agent.py`, `backend/state.py` |
| **Kişi 3** | `feature/frontend` | `frontend/` altındaki her şey — Electron UI, TTS, rehber/aile panelleri, scripted senaryo butonları, görsel tasarım, demo prova |

Her dosyada kod içi `# Sahiplik:` ve `TODO(...)` yorumları hangi kişinin neyi tamamlayacağını gösteriyor. Mock/iskelet zaten çalışır durumda (bkz. `API_CONTRACT.md`) — herkes kendi branch'inde bu iskelet üzerine gerçek mantığı ekleyecek.

### Branch akışı
```bash
git checkout -b feature/backend-core      # Kişi 1
git checkout -b feature/backend-content   # Kişi 2
git checkout -b feature/frontend          # Kişi 3
```
Bitince her biri `main`'e PR/merge eder. `API_CONTRACT.md`'deki şemaları değiştirmeden önce diğer ikisine haber verin — üçünüz de o sözleşmeye göre paralel çalışıyorsunuz.

## Kapsam dışı (bilerek yapılmadı)
Gerçek e-Devlet/MHRS entegrasyonu, telefon/IVR hattı, otomatik mevzuat güncelleme — bkz. plan dosyasındaki gerekçe (devlet sistemine karşı otomasyon risk taşıyor).
# Elderly-Care-e-Devlet
