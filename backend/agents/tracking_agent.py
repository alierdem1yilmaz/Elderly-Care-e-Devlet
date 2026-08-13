# Subagent C — Takip & Proaktif Bildirim
#
# Serbest konuşma mantığı artık backend/agents/orchestrator.py içinde AgentDefinition
# olarak tanımlı (TRACKING_PROMPT + add_notification tool'u, bkz. backend/tools.py).
#
# Aşağıdaki sabit metin SADECE demo günü "scripted senaryo" butonu için kullanılır
# (bkz. backend/main.py: /scenario/missing-document) — canlı demoda LLM'in o an ne
# söyleyeceğine güvenmemek için bilerek sabit tutuldu.

MISSING_DOCUMENT_MESSAGE = (
    "Hatırlatma: Nüfus cüzdanı fotokopisi başvuru için hâlâ eksik görünüyor. "
    "Bir an önce temin etmenizi öneririm."
)
