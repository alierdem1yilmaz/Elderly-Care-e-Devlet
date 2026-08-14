# Sahiplik: Kişi 1 (ali-erdem) — Case-file'a yazma yetkisi olan tek yer burası.
# Subagent'lar kullanıcı için DIŞARIDA (e-Devlet vb.) hiçbir eylem yapmaz;
# bu tool'lar sadece KENDİ vaka dosyamıza (uygulama içi state) yazar.
#
# Tool'lar artık bir case_id'ye kapatılmış (closure) şekilde üretiliyor —
# birden fazla aile/yaşlı aynı anda konuşabildiği için (bkz. orchestrator.py'nin
# case_id başına ayrı client kurması), her oturumun kendi tool sunucusu olmalı,
# yoksa bir ailenin verisi başka birininkine yazılabilirdi.

import json

from claude_agent_sdk import tool, create_sdk_mcp_server

from backend import state
from backend.agents import guide_agent

# create_sdk_mcp_server ile tanımlanan tool'lara SDK içinde bu isimle erişilir
# (sunucu adı "case_tools" olduğu sürece, hangi case_id'ye kapatıldığından
# BAĞIMSIZ olarak aynı isimler kullanılır — bu yüzden AgentDefinition'lardaki
# `tools=[...]` referansları case_id'den bağımsız, sabit kalabiliyor).
TOOL_RECORD_ELIGIBILITY = "mcp__case_tools__record_eligibility"
TOOL_GET_PROGRAM_GUIDE = "mcp__case_tools__get_program_guide"
TOOL_ADD_CHECKLIST_ITEM = "mcp__case_tools__add_checklist_item"
TOOL_ADD_NOTIFICATION = "mcp__case_tools__add_notification"
TOOL_SET_ROADMAP = "mcp__case_tools__set_roadmap"


def build_case_tools(case_id: str):
    """Belirli bir case_id'ye kapatılmış (closure) tool'larla yeni bir MCP
    sunucusu üretir. Her case/oturum için bir kere çağrılır (bkz.
    orchestrator.py::_build_options)."""

    @tool(
        "record_eligibility",
        "Bir yardım programı için uygunluk değerlendirmesini vaka dosyasına kaydeder.",
        {"program": str, "eligible": bool, "reason": str},
    )
    async def record_eligibility(args: dict) -> dict:
        current = [e for e in state.get_case(case_id)["eligibility"] if e["program"] != args["program"]]
        current.append({"program": args["program"], "eligible": args["eligible"], "reason": args["reason"]})
        state.set_eligibility(case_id, current)
        return {"content": [{"type": "text", "text": "Uygunluk sonucu kaydedildi."}]}

    @tool(
        "get_program_guide",
        "Bir yardım programının DOĞRULANMIŞ belge listesini ve başvuru adımlarını "
        "benefits.json'dan deterministik olarak döner (halüsinasyon riski yok). "
        "Checklist'e belge eklemeden veya adımları anlatmadan ÖNCE mutlaka bu tool'u "
        "çağır; belge isimlerini kendi hafızandan uydurma, dönen required_documents "
        "listesini birebir kullan.",
        {"program": str},
    )
    async def get_program_guide(args: dict) -> dict:
        program = args["program"]
        documents = [item["item"] for item in guide_agent.build_checklist(program)]
        guide_text = guide_agent.build_steps(program)
        roadmap = guide_agent.build_roadmap(program)
        payload = {
            "required_documents": documents,
            "guide_text": guide_text,
            "steps": roadmap["steps"] if roadmap else [],
            "administered_by": roadmap["administered_by"] if roadmap else None,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}

    @tool(
        "set_roadmap",
        "Kullanıcı arayüzünde KALICI, numaralı adım kartları olarak gösterilecek "
        "bir yol haritası kaydeder. get_program_guide'dan aldığın 'steps' listesini "
        "DEĞİŞTİRMEDEN, birebir buraya da geç — sadece sohbette anlatmak yeterli "
        "değil, kullanıcı bunu daha sonra tekrar bakabileceği bir kart olarak görmeli.",
        {"program": str, "steps": list[str], "administered_by": str},
    )
    async def set_roadmap(args: dict) -> dict:
        state.set_roadmap(case_id, args["program"], args["steps"], args.get("administered_by"))
        return {"content": [{"type": "text", "text": "Yol haritası kaydedildi."}]}

    @tool(
        "add_checklist_item",
        "Kullanıcının kendisinin hazırlaması/yapması gereken bir belge ya da adımı "
        "yapılacaklar listesine ekler. Bu bir talimat/hatırlatmadır, sistem bu işlemi "
        "kullanıcı adına yapmaz.",
        {"item": str},
    )
    async def add_checklist_item(args: dict) -> dict:
        current = state.get_case(case_id)["checklist"]
        current.append({"item": args["item"], "done": False})
        state.set_checklist(case_id, current)
        return {"content": [{"type": "text", "text": "Yapılacaklar listesine eklendi."}]}

    @tool(
        "add_notification",
        "Aile üyesi panelinde görünecek bir bildirim/hatırlatma ekler "
        "(örn. eksik belge, yaklaşan son tarih, güvenlik uyarısı).",
        {"type": str, "message": str},
    )
    async def add_notification_tool(args: dict) -> dict:
        state.add_notification(case_id, args["type"], args["message"])
        return {"content": [{"type": "text", "text": "Bildirim eklendi."}]}

    return create_sdk_mcp_server(
        name="case_tools",
        tools=[record_eligibility, get_program_guide, set_roadmap, add_checklist_item, add_notification_tool],
    )
