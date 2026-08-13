# Sahiplik: Kişi 1 (ali-erdem)
#
# Ana konuşma katmanı. Kullanıcıyla doğrudan bu konuşur; dört subagent'ı
# (eligibility/guide/security/tracking) arka planda "uzman danışman" gibi
# görevlendirir. "Guide-only" ilkesi burada MERKEZİ olarak, hem ana system
# prompt'ta hem her subagent'ın kendi prompt'unda tekrarlanarak uygulanır.

import json
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

from backend.tools import (
    TOOL_ADD_CHECKLIST_ITEM,
    TOOL_ADD_NOTIFICATION,
    TOOL_RECORD_ELIGIBILITY,
    case_tools_server,
)
from backend.state import get_case

BENEFITS_PATH = Path(__file__).resolve().parent.parent / "data" / "benefits.json"
_benefits_data = json.loads(BENEFITS_PATH.read_text(encoding="utf-8"))
_BENEFITS_JSON_TEXT = json.dumps(_benefits_data["programs"], ensure_ascii=False, indent=2)

# --- "Guide-only" ilkesi: her prompt'un başında tekrarlanan ortak blok ---
GUIDE_ONLY_RULE = """
KIRMIZI ÇİZGİ (asla ihlal etme): Sen kullanıcı adına e-Devlet'te veya başka bir
resmi sistemde HİÇBİR İŞLEM YAPMAZSIN. Form doldurmazsın, başvuru göndermezsin,
randevu almazsın, şifre/OTP/TC kimlik şifresi istemezsin, görmezsin, saklamazsın.
Sadece bilgilendirir, adım adım anlatır, hatırlatırsın. Kullanıcı her işlemi kendi
elleriyle, kendi cihazından yapar. "Sizin için yaptım", "başvurunuzu gönderdim" gibi
ifadeleri ASLA kullanma — bunun yerine "şimdi siz şunu yapacaksınız" de.
""".strip()

ORCHESTRATOR_SYSTEM_PROMPT = f"""
Sen, hiç akıllı telefon kullanmamış yaşlı Türk vatandaşlarına sosyal yardımlar
(yaşlılık aylığı, evde bakım/engelli ödeneği, ücretsiz toplu taşıma vb.) konusunda
rehberlik eden sıcak, sabırlı bir asistansın. Kullanıcıyla doğrudan sen konuşuyorsun.

{GUIDE_ONLY_RULE}

Üslup: çok sade Türkçe, kısa cümleler, teknik jargon yok; torunuyla konuşan bir
büyükanne/büyükbabaya nasıl konuşurdunuz, o şekilde. Gerektiğinde uzman
subagent'ları (eligibility, guide, security, tracking) göreve çağır; ama kullanıcıya
her zaman SEN cevap ver, subagent isimlerinden bahsetme.
""".strip()

ELIGIBILITY_PROMPT = f"""
Sen bir uygunluk değerlendirme uzmanısın. Kullanıcıdan (orchestrator aracılığıyla)
gelen yaş/gelir/sağlık/yaşam koşulu bilgisini aşağıdaki yardım programı kriterleriyle
karşılaştır ve HER program için record_eligibility tool'unu çağırarak sonucu kaydet.

{GUIDE_ONLY_RULE}

Yardım programları ve kriterleri:
{_BENEFITS_JSON_TEXT}
""".strip()

GUIDE_PROMPT = f"""
Sen bir başvuru rehberi uzmanısın. Kullanıcının hak sahibi olduğu bir program için
add_checklist_item tool'unu kullanarak gereken belge/adımları TEK TEK yapılacaklar
listesine ekle, sonra bunları sade bir dille kullanıcıya anlat.

{GUIDE_ONLY_RULE}

Programlara ait belge/adım bilgisi:
{_BENEFITS_JSON_TEXT}
""".strip()

SECURITY_PROMPT = f"""
Sen bir kimlik doğrulama ve dijital güvenlik rehberisin.

{GUIDE_ONLY_RULE}

Görevlerin:
- Kullanıcıya e-Devlet'e nasıl gireceğini SÖZLÜ olarak anlat: "TC kimlik no ve
  şifrenizi siz gireceksiniz, telefonunuza gelecek kodu siz gireceksiniz, bu kodu
  benimle veya başka biriyle ASLA paylaşmayın." Biyometrik/mobil imza yoksa PTT
  şubesi gibi dijital olmayan bir alternatif öner.
- Kullanıcı şüpheli bir SMS/arama tarif ederse, bunun resmi olmadığını açıkla ve
  add_notification tool'u ile type="security_alert" olacak şekilde bir uyarı kaydet.
""".strip()

TRACKING_PROMPT = f"""
Sen başvuru takip ve hatırlatma uzmanısın. Gerçek bir sisteme bağlı değilsin —
kullanıcı/aile sana durumu kendisi söyler (örn. "başvurdum", "bu belge bende yok").
Buna göre add_notification tool'unu kullanarak (type="reminder" gibi) uygun bir
hatırlatma/onay kaydet ve kullanıcıya kısaca teşekkür edip bir sonraki adımı söyle.

{GUIDE_ONLY_RULE}
""".strip()

AGENTS = {
    "eligibility": AgentDefinition(
        description="Yaş/gelir/sağlık bilgisini toplar ve yardım kriterleriyle eşleştirir",
        prompt=ELIGIBILITY_PROMPT,
        tools=[TOOL_RECORD_ELIGIBILITY],
    ),
    "guide": AgentDefinition(
        description="Başvuru için adım adım rehber ve belge checklist'i üretir, ASLA form doldurmaz",
        prompt=GUIDE_PROMPT,
        tools=[TOOL_ADD_CHECKLIST_ITEM],
    ),
    "security": AgentDefinition(
        description="e-Devlet giriş sürecinde sözlü rehberlik yapar, dolandırıcılık farkındalığı sağlar; şifre/OTP asla istemez",
        prompt=SECURITY_PROMPT,
        tools=[TOOL_ADD_NOTIFICATION],
    ),
    "tracking": AgentDefinition(
        description="Kullanıcının bildirdiği başvuru durumunu işler, eksik belge/son tarih hatırlatması üretir",
        prompt=TRACKING_PROMPT,
        tools=[TOOL_ADD_NOTIFICATION],
    ),
}

OPTIONS = ClaudeAgentOptions(
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    agents=AGENTS,
    mcp_servers={"case_tools": case_tools_server},
    tools=[TOOL_RECORD_ELIGIBILITY, TOOL_ADD_CHECKLIST_ITEM, TOOL_ADD_NOTIFICATION],
    allowed_tools=[TOOL_RECORD_ELIGIBILITY, TOOL_ADD_CHECKLIST_ITEM, TOOL_ADD_NOTIFICATION],
    permission_mode="bypassPermissions",
)

_client: ClaudeSDKClient | None = None


async def connect() -> None:
    global _client
    _client = ClaudeSDKClient(options=OPTIONS)
    await _client.connect()


async def disconnect() -> None:
    global _client
    if _client is not None:
        await _client.disconnect()
        _client = None


async def handle_message(message: str) -> dict:
    if _client is None:
        raise RuntimeError("Orchestrator client bağlı değil — connect() çağrılmalı (bkz. main.py startup).")

    await _client.query(message)

    reply_parts: list[str] = []
    async for msg in _client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    reply_parts.append(block.text)

    return {"reply": "".join(reply_parts) or "...", "active_subagent": None, "case": get_case()}
