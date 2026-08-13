# Subagent D — Kimlik Doğrulama & Güvenlik Rehberliği
#
# Serbest konuşma mantığı artık backend/agents/orchestrator.py içinde AgentDefinition
# olarak tanımlı (SECURITY_PROMPT + add_notification tool'u, bkz. backend/tools.py).
#
# Aşağıdaki fonksiyon SADECE demo günü "scripted senaryo" butonu için kullanılan
# sabit/deterministic metindir (bkz. backend/main.py: /scenario/suspicious-sms) —
# canlı demoda LLM'in o an ne söyleyeceğine güvenmemek için bilerek sabit tutuldu.


def suspicious_sms_alert() -> str:
    return (
        "Dikkat: Az önce aldığınız 'e-Devlet şifreniz güncellenmiştir, tıklayın' "
        "mesajı resmi bir kaynaktan gelmiyor. Bu tür linklere tıklamayın, "
        "şifrenizi veya kodunuzu kimseyle paylaşmayın."
    )
