"""对话/聊天 API"""
import uuid
from fastapi import APIRouter, Request, HTTPException, Query
from services.db_service import db

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _resolve_chat_model() -> str:
    """从已启用的提供商中选第一个可用的模型"""
    from app_config.encryption import ConfigEncryption
    from app_config.providers import PROVIDERS, PROVIDER_ORDER
    from app_config.settings import CONFIG_DIR
    from services.llm_service import _get_model_string

    enc = ConfigEncryption(CONFIG_DIR)
    cfg = enc.load_config()
    for pk in PROVIDER_ORDER:
        saved = cfg.get(pk, {})
        if saved.get("enabled") and saved.get("api_key"):
            models = saved.get("models") or PROVIDERS[pk].get("models", [])
            if models:
                return _get_model_string(pk, models[0])
    return "openai/gpt-4o-mini"


@router.get("/conversations")
async def list_conversations():
    return {"conversations": db.list_conversations()}


@router.post("/conversations")
async def create_conversation(req: Request):
    body = await req.json()
    title = body.get("title", "新对话")
    model = body.get("model", "")
    system_prompt = body.get("system_prompt", "")
    task_type = body.get("task_type", "pentest")
    conv = db.create_conversation(title=title, model=model,
                                   system_prompt=system_prompt, task_type=task_type)
    return conv


@router.get("/conversations/{cid}")
async def get_conversation(cid: str):
    conv = db.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "对话不存在")
    messages = db.get_messages(cid)
    return {"conversation": conv, "messages": messages}


@router.delete("/conversations/{cid}")
async def delete_conversation(cid: str):
    conn = db._get_conn()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
    conn.commit()
    return {"ok": True}


@router.post("/conversations/{cid}/messages")
async def send_message(cid: str, req: Request):
    body = await req.json()
    content = body.get("content", "")
    role = body.get("role", "user")
    if not content:
        raise HTTPException(400, "内容不能为空")
    db.add_message(cid, role, content)
    conv = db.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "对话不存在")

    use_agent = body.get("use_agent", False)
    # 支持前端传递模型选择
    model_str = body.get("model", "") or conv.get("model", "")
    if not model_str:
        model_str = _resolve_chat_model()

    if not use_agent:
        return {"ok": True, "message": "消息已记录"}

    # 直接 LLM 对话（不走 OODA 循环）
    from services.llm_client import acompletion
    history = db.get_messages(cid, limit=20)
    msgs = [{"role": "system", "content": "你是 Stopen AI 助手，帮助用户进行渗透测试和网络安全分析。回复简洁专业。"}]
    for m in history:
        msgs.append({"role": m["role"], "content": m["content"]})

    try:
        # 获取 API key
        from app_config.encryption import ConfigEncryption
        from app_config.settings import CONFIG_DIR
        enc = ConfigEncryption(CONFIG_DIR)
        cfg = enc.load_config()
        provider_key = model_str.split("/")[0] if "/" in model_str else "openai"
        saved = cfg.get(provider_key, {})
        api_key = saved.get("api_key", "")
        if not api_key:
            return {"assistant": "[错误] 未配置 API Key，请在「配置」页面设置", "use_agent": True}

        llm_kwargs = {"api_key": api_key}
        from app_config.providers import PROVIDERS
        info = PROVIDERS.get(provider_key, {})
        if info.get("base_url") and not info.get("is_native", True):
            llm_kwargs["api_base"] = saved.get("base_url") or info["base_url"]

        resp = await acompletion(model=model_str, messages=msgs, **llm_kwargs)
        reply = resp.choices[0].message.content or ""
        db.add_message(cid, "assistant", reply[:5000])
        return {"assistant": reply[:5000], "use_agent": True}
    except Exception as e:
        error_msg = f"[错误] {e}"
        return {"assistant": error_msg, "use_agent": True, "error": str(e)}


def _resolve_chat_model() -> str:
    """从已启用的提供商中选第一个可用的模型"""
    from app_config.encryption import ConfigEncryption
    from app_config.providers import PROVIDERS, PROVIDER_ORDER
    from app_config.settings import CONFIG_DIR
    from services.llm_service import _get_model_string

    enc = ConfigEncryption(CONFIG_DIR)
    cfg = enc.load_config()
    for pk in PROVIDER_ORDER:
        saved = cfg.get(pk, {})
        if saved.get("enabled") and saved.get("api_key"):
            models = saved.get("models") or PROVIDERS[pk].get("models", [])
            if models:
                return _get_model_string(pk, models[0])
    return "openai/gpt-4o-mini"
