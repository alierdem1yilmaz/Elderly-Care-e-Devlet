# Sahiplik: Kişi 1 (ali-erdem)
#
# Ana konuşma katmanı. Kullanıcıyla doğrudan bu konuşur; dört subagent'ı
# (eligibility/guide/security/tracking) arka planda "uzman danışman" gibi
# görevlendirir. "Guide-only" ilkesi burada MERKEZİ olarak, hem ana system
# prompt'ta hem her subagent'ın kendi prompt'unda tekrarlanarak uygulanır.

import json
import logging
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    HookContext,
    HookMatcher,
    SubagentStartHookInput,
    TaskStartedMessage,
    TaskUpdatedMessage,
    TERMINAL_TASK_STATUSES,
    TextBlock,
)

logger = logging.getLogger(__name__)

from backend.tools import (
    TOOL_ADD_CHECKLIST_ITEM,
    TOOL_ADD_NOTIFICATION,
    TOOL_GET_PROGRAM_GUIDE,
    TOOL_RECORD_ELIGIBILITY,
    TOOL_SET_ROADMAP,
    build_case_tools,
)
from backend.state import get_case

BENEFITS_PATH = Path(__file__).resolve().parent.parent / "data" / "benefits.json"
_benefits_data = json.loads(BENEFITS_PATH.read_text(encoding="utf-8"))
_BENEFITS_JSON_TEXT = json.dumps(_benefits_data["programs"], ensure_ascii=False, indent=2)
_PROGRAM_ID_NAME_LIST = "\n".join(
    f'- id="{p["id"]}" → {p["name"]}' for p in _benefits_data["programs"]
)

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

Biçimlendirme: cevabın hem ekranda gösteriliyor hem sesli okunuyor, bu yüzden
ASLA markdown biçimlendirmesi kullanma — yıldız (**), hashtag (##), madde imi
sembolü (-, •, 🔹) yazma. Sıralama gerekiyorsa "Birincisi:", "Sonra:" gibi
sözle ya da gerçek satır sonlarıyla ayır; sadece düz, sıcak cümleler kur.

Bilgi toplama: eligibility uzmanını çağırmadan önce yaş, gelir durumu (düşük/orta/
yüksek beyan yeterli, kesin rakam şart değil), sağlık/engellilik durumu ve yaşam
koşulları hakkında TEK SEFERDE değil, sohbet havasında, birer birer sor. Kullanıcı
zaten bir bilgi verdiyse tekrar sorma. Elindeki bilgi bir programı değerlendirmeye
yetecek kadar var mı diye kendi kendine karar ver; yetiyorsa eligibility'yi çağır,
yetmiyorsa önce eksik bilgiyi sor.
""".strip()

ELIGIBILITY_PROMPT = f"""
Sen bir uygunluk değerlendirme uzmanısın. Kullanıcıdan (orchestrator aracılığıyla)
gelen yaş/gelir/sağlık/yaşam koşulu bilgisini aşağıdaki yardım programı kriterleriyle
karşılaştır ve HER program için record_eligibility tool'unu çağırarak sonucu kaydet.

Not: Kriterlerdeki "income_below_threshold" gibi alanlar şu an kesin bir rakam
içermiyor (taslak veri, gerçek eşik değerleri henüz eklenmedi). Kesin rakam yoksa
kullanıcının "düşük gelirliyim/geçinemiyorum" gibi kendi beyanını esas al; tahmin
uydurma. Belirsizlik varsa bunu `reason` alanında açıkça belirt (örn. "gelir beyanına
göre muhtemelen uygun, kesin gelir eşiği resmi kaynaktan teyit edilmeli") — reason
sonradan kullanıcıya "kesin sonuç değil, ön değerlendirme" diye aktarılacak.

{GUIDE_ONLY_RULE}

Yardım programları ve kriterleri:
{_BENEFITS_JSON_TEXT}
""".strip()

GUIDE_PROMPT = f"""
Sen bir başvuru rehberi uzmanısın. Görevin, kullanıcının hak sahibi olduğu bir
program için somut, takip edilebilir bir yol haritası çıkarmak. Sırasıyla:

1. ÖNCE get_program_guide tool'unu çağır (program parametresine aşağıdaki id'lerden
   birini gir). Bu tool sana benefits.json'dan DOĞRULANMIŞ, kesin belge listesini
   (required_documents), adımları (steps) ve kurumu (administered_by) döner.
2. set_roadmap tool'unu çağırarak dönen "steps" listesini VE "administered_by"yi
   DEĞİŞTİRMEDEN kaydet — bu, kullanıcının arayüzde göreceği kalıcı, numaralı adım
   kartıdır; sadece sohbette anlatmak yeterli değildir, çünkü sohbet kayar/unutulur.
3. Dönen required_documents listesindeki HER belgeyi TEK TEK, birebir metinle
   add_checklist_item ile yapılacaklar listesine ekle. Belge isimlerini kendi
   hafızandan ASLA uydurma veya kısaltma — tool'un döndüğü metni aynen kullan.
4. Son olarak guide_text'i sade, sıcak, KISA bir dille kullanıcıya özetle (kartta
   zaten yazılı olan adımları tek tek tekrar okuma, sadece "adımları hazırladım,
   Rehberim'de görebilirsiniz" gibi kısa bir yönlendirme yeterli).

{GUIDE_ONLY_RULE}

Programlar (get_program_guide çağırırken "program" parametresi için id kullan):
{_PROGRAM_ID_NAME_LIST}
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

# background=False: varsayılan davranışta SDK, alt görevleri arka planda
# çalıştırabiliyor — orchestrator'ın turu, subagent'ın tool çağrıları (ör.
# record_eligibility) HENÜZ TAMAMLANMADAN bitebiliyor. Bunu canlı Supabase
# testinde yakaladık: /chat cevabındaki "case" alanı boştu, ama hemen
# ardından GET /case doğru veriyi gösteriyordu — subagent arka planda
# tamamlanmıştı. background=False bunu senkron/bloklayıcı yapıp, /chat
# cevabı dönmeden ÖNCE subagent'ın gerçekten bitmesini garanti ediyor.
AGENTS = {
    "eligibility": AgentDefinition(
        description="Yaş/gelir/sağlık bilgisini toplar ve yardım kriterleriyle eşleştirir",
        prompt=ELIGIBILITY_PROMPT,
        tools=[TOOL_RECORD_ELIGIBILITY],
        background=False,
    ),
    "guide": AgentDefinition(
        description="Başvuru için adım adım rehber ve belge checklist'i üretir, ASLA form doldurmaz",
        prompt=GUIDE_PROMPT,
        tools=[TOOL_GET_PROGRAM_GUIDE, TOOL_SET_ROADMAP, TOOL_ADD_CHECKLIST_ITEM],
        background=False,
    ),
    "security": AgentDefinition(
        description="e-Devlet giriş sürecinde sözlü rehberlik yapar, dolandırıcılık farkındalığı sağlar; şifre/OTP asla istemez",
        prompt=SECURITY_PROMPT,
        tools=[TOOL_ADD_NOTIFICATION],
        background=False,
    ),
    "tracking": AgentDefinition(
        description="Kullanıcının bildirdiği başvuru durumunu işler, eksik belge/son tarih hatırlatması üretir",
        prompt=TRACKING_PROMPT,
        tools=[TOOL_ADD_NOTIFICATION],
        background=False,
    ),
}

# Artık TEK bir global client yok — her case_id (yaşlı profili) kendi
# ClaudeSDKClient'ına, kendi case_tools sunucusuna ve kendi konuşma geçmişine
# sahip. Böylece Electron'daki bir yaşlı, telefonla arayan başka bir yaşlı ve
# mobil uygulamadan bakan bir aile üyesi aynı anda birbirine karışmadan
# kullanılabiliyor.
_clients: dict[str, ClaudeSDKClient] = {}

# case_id -> bu case'in son /chat turunda çağrılan subagent'lar. SDK, alt-görev
# başladığında bunu SubagentStart hook'u ile bildiriyor.
_active_subagents: dict[str, list[str]] = {}


def _build_options(case_id: str) -> ClaudeAgentOptions:
    _active_subagents[case_id] = []

    async def _on_subagent_start(
        input_data: SubagentStartHookInput, tool_use_id: str | None, context: HookContext
    ) -> dict:
        _active_subagents[case_id].append(input_data["agent_type"])
        return {}

    def _on_stderr(line: str) -> None:
        # `claude` CLI alt süreci çökerse (ör. exit code 1), SDK'nın fırlattığı
        # hata mesajı sadece "Check stderr output for details" diyor, gerçek
        # sebebi içermiyor — o yüzden ham stderr'i burada kendimiz loglayıp
        # asıl sebebi (varsa) terminalde görünür kılıyoruz.
        logger.warning("claude CLI stderr (case=%s): %s", case_id, line)

    return ClaudeAgentOptions(
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        agents=AGENTS,
        mcp_servers={"case_tools": build_case_tools(case_id)},
        # Orkestratörün elinde SADECE "Task" olmalı (subagent çağırma aracı) —
        # case_tools'u burada da listelersek model genelde subagent'lara hiç
        # uğramadan doğrudan kendisi çağırıyor; bu da her subagent'ın kendi
        # promptunu/tool kısıtını (ör. security sadece add_notification görür)
        # anlamsız kılıyor. Gerçek case_tools tool'ları yalnızca her
        # AgentDefinition'ın kendi `tools=` listesinde tanımlı.
        tools=["Task"],
        allowed_tools=["Task"],
        permission_mode="bypassPermissions",
        hooks={"SubagentStart": [HookMatcher(hooks=[_on_subagent_start])]},
        stderr=_on_stderr,
    )


async def _get_or_create_client(case_id: str) -> ClaudeSDKClient:
    client = _clients.get(case_id)
    if client is None:
        client = ClaudeSDKClient(options=_build_options(case_id))
        await client.connect()
        _clients[case_id] = client
    return client


async def _evict_client(case_id: str) -> None:
    # Alt süreç (claude CLI) bir kere çökünce, o case_id için önbellekteki
    # client KALICI OLARAK bozuk kalıyordu — her sonraki mesaj, backend
    # yeniden başlatılana kadar aynı hatayı vermeye devam ediyordu (canlı
    # testte doğrulandı). Bozuk client'ı burada önbellekten atıp bir dahaki
    # mesajda sıfırdan, sağlıklı bir süreç kurulmasını sağlıyoruz.
    client = _clients.pop(case_id, None)
    if client is not None:
        try:
            await client.disconnect()
        except Exception:
            pass  # zaten çökmüş bir süreci kapatmaya çalışıyoruz, hata beklenir


async def disconnect_all() -> None:
    for client in _clients.values():
        await client.disconnect()
    _clients.clear()
    _active_subagents.clear()


async def _run_turn(case_id: str, message: str) -> dict:
    client = await _get_or_create_client(case_id)

    _active_subagents[case_id] = []
    await client.query(message)

    # ÖNEMLİ: SDK, subagent (Task) çağrılarını ARKA PLANDA çalıştırıyor —
    # orchestrator'ın turu (bir ResultMessage ile) subagent daha işini
    # bitirmeden kapanabiliyor; canlı testte orchestrator "kontrol ediyorum,
    # birazdan söylerim" deyip turu bitirirken, record_eligibility gibi tool
    # çağrıları henüz çalışmamış oluyordu. Arka plandaki görev bitince sonucu,
    # AYNI client üzerinde receive_response()'u TEKRAR çağırınca (yeni bir
    # query göndermeden) alıyoruz — bu yüzden aşağıda, başlayıp da henüz
    # tamamlanmamış görev kalmayana kadar receive_response()'u tekrar tekrar
    # okuyoruz. Böylece hem case state'i hem de kullanıcıya dönen cevap metni
    # (ör. "değerlendirmeyi tamamladım, işte sonuç...") eksiksiz oluyor.
    # Her _drain() çağrısı kendi metin parçalarını döner (biriktirmez) —
    # sadece EN SON turun metnini kullanıyoruz. Yoksa ilk turdaki "birazdan
    # söylerim" dolgu cümlesiyle, arka plandaki görev bitince gelen asıl/tam
    # cevap üst üste birleşip tekrarlı, uzun bir mesaj oluşuyordu.
    latest_reply_parts: list[str] = []
    pending_task_ids: set[str] = set()

    async def _drain(stream) -> list[str]:
        parts: list[str] = []
        async for msg in stream:
            if isinstance(msg, AssistantMessage):
                # parent_tool_use_id dolu olan mesajlar bir subagent'ın KENDİ
                # iç konuşmasına ait (ör. eligibility'nin kendi markdown'lu
                # özeti) — bunları kullanıcıya göstermiyoruz, sadece ana
                # orchestrator'ın (parent_tool_use_id=None) kendi metnini
                # topluyoruz; yoksa iki farklı üslupta iki cevap üst üste
                # biniyordu.
                if msg.parent_tool_use_id is not None:
                    continue
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
            elif isinstance(msg, TaskStartedMessage):
                pending_task_ids.add(msg.task_id)
            elif isinstance(msg, TaskUpdatedMessage) and msg.status in TERMINAL_TASK_STATUSES:
                pending_task_ids.discard(msg.task_id)
        return parts

    parts = await _drain(client.receive_response())
    if parts:
        latest_reply_parts = parts

    # Güvenlik amaçlı üst sınır: normalde 1-2 turda biter, sonsuz döngüye
    # girmemesi için makul bir tavan koyuyoruz.
    for _ in range(5):
        if not pending_task_ids:
            break
        parts = await _drain(client.receive_response())
        if parts:
            latest_reply_parts = parts

    reply_parts = latest_reply_parts

    # Bu turda birden fazla subagent çağrılmış olabilir; UI'da göstermek için
    # en son çağrılanı (cevaba en çok katkısı olan) esas alıyoruz.
    subagents_this_turn = _active_subagents.get(case_id, [])
    active_subagent = subagents_this_turn[-1] if subagents_this_turn else None

    return {"reply": "".join(reply_parts) or "...", "active_subagent": active_subagent, "case": get_case(case_id)}


async def handle_message(case_id: str, message: str) -> dict:
    try:
        return await _run_turn(case_id, message)
    except ClaudeSDKError:
        # `claude` CLI alt süreci bir sebeple çökmüş (ağ kesintisi, geçici bir
        # hata vb.) — önbellekteki bozuk client'ı atıp SIFIRDAN bir süreçle bir
        # kez daha deniyoruz. Böylece kullanıcı aynı hatayı tekrar tekrar
        # görüp backend'in yeniden başlatılmasını beklemek zorunda kalmıyor.
        logger.warning("Client çöktü (case=%s), sıfırdan bağlanıp tekrar deneniyor", case_id, exc_info=True)
        await _evict_client(case_id)
        return await _run_turn(case_id, message)
