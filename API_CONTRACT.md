# API Sözleşmesi — Backend ⇄ Frontend

Bu dosya 3 branch'in birbirini beklemeden çalışabilmesi için sabitlenmiş sözleşmedir. Değiştirmeden önce diğer iki kişiyle konuşun.

Backend: `http://localhost:8000`

## GET /ping
Sağlık kontrolü. Electron açılışta bunu bekler.
```json
{ "status": "ok" }
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
    { "program": "Yaşlılık Aylığı", "eligible": true, "reason": "65 yaş üstü ve gelir sınırının altında" }
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
  ]
}
```
- `appointments`: kullanıcının bildirdiği randevu/son tarihler (Subagent C, `/case/status` içindeki serbest metinden tarih çıkarabilirse otomatik ekler). Son tarihe 3 gün veya daha az kaldığında (ya da geçtiğinde), her randevu için **bir kez** `notifications`'a otomatik bir `reminder` kaydı düşer — `GET /case` her çağrıldığında bu kontrol yapılır, ek bir endpoint/polling gerekmez.

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
