# API Sözleşmesi — Backend ⇄ Frontend

Bu dosya 3 branch'in birbirini beklemeden çalışabilmesi için sabitlenmiş sözleşmedir. Değiştirmeden önce diğer iki kişiyle konuşun.

Backend: `http://localhost:8000`

## GET /ping
Sağlık kontrolü. Electron açılışta bunu bekler.
```json
{ "status": "ok" }
```

## POST /speech-to-text
Mikrofonla kaydedilen sesi (multipart/form-data, alan adı `audio`, webm/opus vb.) YEREL bir Whisper modeliyle (`backend/speech.py`, `faster-whisper`) Türkçe metne çevirir. API anahtarı/hesap/internet gerektirmez — Electron'daki `webkitSpeechRecognition`'ın Google API anahtarı olmadan çalışmaması sorununu bu şekilde aştık. Model backend başlarken önceden yüklenir (`lifespan` içinde `speech.warm_up()`), ilk istekte beklemez.

**Request:** `multipart/form-data`, `audio` alanında ses dosyası.

**Response**
```json
{ "text": "Randevumu 15 Ağustos tarihine aldım" }
```

## POST /chat
Kullanıcı mesajını orchestrator'a gönderir.

**Request**
```json
{ "message": "Merhaba, annem için yardım arıyorum, 72 yaşında" }
```

**Response**
```json
{
  "reply": "Anlıyorum, size yardımcı olayım...",
  "active_subagent": "eligibility",
  "case": { "...": "bkz. GET /case şeması" }
}
```
- `active_subagent`: `"eligibility" | "guide" | "tracking" | "security" | null` — UI'da "hangi uzman konuşuyor" göstergesi için (opsiyonel gösterim, olmazsa da olur).
- `case`: her `/chat` cevabında güncel tam case-file state'i döner (frontend ayrıca `/case` çağırmasa da olur, ama debug için `/case` de açık kalsın).

## GET /case
Güncel vaka dosyası state'i.
```json
{
  "eligibility": [
    { "program": "Yaşlılık Aylığı", "eligible": true, "reason": "65 yaş üstü ve gelir sınırının altında", "notes": "2026 Temmuz-Aralık dönemi aylık tutarı 7.257 TL'dir." }
  ],
  "checklist": [
    { "item": "Nüfus cüzdanı fotokopisi", "done": false },
    { "item": "Gelir beyanı", "done": false }
  ],
  "notifications": [
    { "type": "reminder", "message": "Heyet raporu için MHRS randevusu almanız gerekiyor", "timestamp": "2026-08-13T10:00:00" }
  ],
  "appointments": [
    { "description": "Randevu: MHRS randevumu 20.08.2026 tarihine aldım", "due_date": "2026-08-20", "reminded": false }
  ],
  "profile": { "age": 70, "disability_status": "reported", "disability_percent": 60, "household_income_tl": 20000, "household_size": 2, "income_band": "below_minimum", "city": "İstanbul", "living_situation": "family" },
  "next_step": "Şimdi yapmanız gereken: Nüfus cüzdanı fotokopisi"
}
```
- `profile`: `POST /profile` ile doldurulur, henüz doldurulmadıysa `null`.
- `eligibility[].notes`: ilgili programın `benefits.json`'daki `notes` alanı (tutar/ek bilgi) — sadece "Sorgula & Eşleştir" sonuçlarında gösterim amaçlı, `eligible=false` ise genelde boş bırakılır.
- `next_step`: `backend/state.py::get_next_step()` ile hesaplanan, kullanıcıya gösterilecek TEK öncelikli adım (randevu → bekleyen belge → profil doldurma → "bekleyen işlem yok" sırasıyla). Her `GET /case` çağrısında yeniden hesaplanır.
- `appointments`: kullanıcının bildirdiği randevu/son tarihler (Subagent C, `/case/status` içindeki serbest metinden tarih çıkarabilirse otomatik ekler; tarih yoksa netleştirme sorusu döner). Son tarihe 3 gün veya daha az kaldığında (ya da geçtiğinde), her randevu için **bir kez** `notifications`'a otomatik bir `reminder` kaydı düşer — `GET /case` her çağrıldığında bu kontrol yapılır, ek bir endpoint/polling gerekmez.

## GET /edevlet-guide
Statik, doğrulanmış e-Devlet okuryazarlığı içeriği (`backend/data/edevlet_guide.json`) — LLM'e bırakılmaz, "e-Devlet Kılavuzu" sekmesinde akordiyon olarak gösterilir.
```json
{ "sections": [ { "id": "nedir", "title": "e-Devlet nedir?", "body": "..." }, "..." ] }
```

## POST /profile
"Sorgula & Eşleştir" formundan yapılandırılmış kullanıcı bilgisini alır, **deterministik** (LLM'siz) bir uygunluk değerlendirmesi yapıp anında kaydeder — bkz. `backend/agents/eligibility_agent.py::assess_profile`.

**Request**
```json
{
  "age": 70,
  "disability_status": "reported",
  "disability_percent": 60,
  "household_income_tl": 20000,
  "household_size": 2,
  "income_band": "below_minimum",
  "city": "İstanbul",
  "living_situation": "family"
}
```
- `disability_status`: `"none" | "unreported" | "reported"`
- `income_band`: `"none" | "below_minimum" | "around_minimum" | "above_minimum"` — sadece `household_income_tl`/`household_size` boşsa kullanılan kaba yedek tahmin.
- `household_income_tl` / `household_size`: doluysa, gerçek 2026 net asgari ücret rakamıyla **kesin** kişi başı gelir hesabı yapılır (daha doğru sonuç).

**Response:** güncel `case` state'i (yukarıdaki şema, `eligibility` ve `next_step` alanları bu forma göre anında güncellenmiş olur). Ayrıca bu bilgi, kullanıcı sonradan Sohbet'e geçerse aynı soruları tekrar sormaması için arka planda (yanıtı beklemeden) orchestrator'ın konuşma geçmişine de eklenir.

## POST /case/status
Kullanıcı/aile bir durumu bildirir (örn. "başvurdum", "bu belge bende yok", "randevumu 20.08.2026'ya aldım"). Subagent C bunu işler, `notifications` (ve varsa `appointments`/`checklist`) günceller.

**Request**
```json
{ "update": "Nüfus cüzdanı fotokopisini henüz alamadım" }
```
**Response:** güncel `case` state'i (yukarıdaki şema). Not: bu endpoint artık her çağrıda genel bir "kaydedildi" bildirimi eklemiyor — Subagent C'nin ürettiği tek, anlamlı bildirim yeterli.

## POST /scenario/missing-document
Scripted demo tetikleyici — deterministic. Parametre gerekmez. Subagent C'nin eksik belge hatırlatmasını tetikler, `notifications`'a sabit bir kayıt ekler.

## POST /scenario/suspicious-sms
Scripted demo tetikleyici — deterministic. Subagent D'nin dolandırıcılık uyarısını tetikler, `notifications`'a sabit bir kayıt ekler.

Her ikisi de `/case/status` ile aynı response şemasını döner (güncel `case`).

---

## Notlar
- Backend ilk aşamada bu endpoint'leri **mock/sabit veriyle** döndürüyor (bkz. `backend/main.py`) — Kişi 3 (frontend) bunun üzerine gerçek UI'ı inşa edebilir. Kişi 1 ve Kişi 2, mock mantığı gerçek orchestrator/subagent çağrılarıyla değiştirecek, **response şeması aynı kalacak**.
- CORS: mock backend `*` origin'e açık (Electron renderer'dan localhost'a erişim için).
