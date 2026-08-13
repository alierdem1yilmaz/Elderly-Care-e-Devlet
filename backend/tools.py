# Sahiplik: Kişi 1 (ali-erdem) — Case-file'a yazma yetkisi olan tek yer burası.
# Subagent'lar kullanıcı için DIŞARIDA (e-Devlet vb.) hiçbir eylem yapmaz;
# bu tool'lar sadece KENDİ vaka dosyamıza (uygulama içi state) yazar.

import json

from claude_agent_sdk import tool, create_sdk_mcp_server

from backend import state
from backend.agents import guide_agent


@tool(
    "record_eligibility",
    "Bir yardım programı için uygunluk değerlendirmesini vaka dosyasına kaydeder.",
    {"program": str, "eligible": bool, "reason": str},
)
async def record_eligibility(args: dict) -> dict:
    current = [e for e in state.get_case()["eligibility"] if e["program"] != args["program"]]
    current.append({"program": args["program"], "eligible": args["eligible"], "reason": args["reason"]})
    state.set_eligibility(current)
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
    payload = {"required_documents": documents, "guide_text": guide_text}
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


@tool(
    "add_checklist_item",
    "Kullanıcının kendisinin hazırlaması/yapması gereken bir belge ya da adımı "
    "yapılacaklar listesine ekler. Bu bir talimat/hatırlatmadır, sistem bu işlemi "
    "kullanıcı adına yapmaz.",
    {"item": str},
)
async def add_checklist_item(args: dict) -> dict:
    current = state.get_case()["checklist"]
    current.append({"item": args["item"], "done": False})
    state.set_checklist(current)
    return {"content": [{"type": "text", "text": "Yapılacaklar listesine eklendi."}]}


@tool(
    "add_notification",
    "Aile üyesi panelinde görünecek bir bildirim/hatırlatma ekler "
    "(örn. eksik belge, yaklaşan son tarih, güvenlik uyarısı).",
    {"type": str, "message": str},
)
async def add_notification_tool(args: dict) -> dict:
    state.add_notification(args["type"], args["message"])
    return {"content": [{"type": "text", "text": "Bildirim eklendi."}]}


case_tools_server = create_sdk_mcp_server(
    name="case_tools",
    tools=[record_eligibility, get_program_guide, add_checklist_item, add_notification_tool],
)

# create_sdk_mcp_server ile tanımlanan tool'lara SDK içinde bu isimle erişilir:
# mcp__case_tools__record_eligibility, mcp__case_tools__get_program_guide,
# mcp__case_tools__add_checklist_item, mcp__case_tools__add_notification
TOOL_RECORD_ELIGIBILITY = "mcp__case_tools__record_eligibility"
TOOL_GET_PROGRAM_GUIDE = "mcp__case_tools__get_program_guide"
TOOL_ADD_CHECKLIST_ITEM = "mcp__case_tools__add_checklist_item"
TOOL_ADD_NOTIFICATION = "mcp__case_tools__add_notification"
