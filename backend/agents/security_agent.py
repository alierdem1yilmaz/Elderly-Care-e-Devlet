# Sahiplik: Kişi 1 (Backend Omurga)
# Subagent D — Kimlik Doğrulama & Güvenlik Rehberliği
#
# TODO(Kişi 1): ÖNEMLİ İLKE — bu subagent kullanıcının e-Devlet şifresini/OTP'sini
# ASLA istemez, görmez, saklamaz. Sadece adım adım anlatır:
#   "e-Devlet'e girin -> TC kimlik no + şifrenizi siz girin -> gelen kodu siz girin,
#    kimseyle paylaşmayın". Biyometrik/mobil imza yoksa PTT şubesi alternatifini öner.
# Ayrıca basit kural-tabanlı dolandırıcılık farkındalık kontrolü (bkz. suspicious_sms mock'u main.py'de).


def login_guidance() -> str:
    # --- MOCK ---
    return (
        "Şimdi e-Devlet'e kendi cihazınızdan girin. TC kimlik numaranızı ve "
        "şifrenizi siz gireceksiniz. Telefonunuza gelecek kodu da siz "
        "gireceksiniz — bu kodu benimle veya başka biriyle asla paylaşmayın."
    )


def suspicious_sms_alert() -> str:
    # --- MOCK: scripted senaryo için sabit metin ---
    return (
        "Dikkat: Az önce aldığınız 'e-Devlet şifreniz güncellenmiştir, tıklayın' "
        "mesajı resmi bir kaynaktan gelmiyor. Bu tür linklere tıklamayın, "
        "şifrenizi veya kodunuzu kimseyle paylaşmayın."
    )
