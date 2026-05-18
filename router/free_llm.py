import os, json, asyncio, httpx, hashlib, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

PROVIDERS = {
    "groq": {"url":"https://api.groq.com/openai/v1/chat/completions","key":os.getenv("GROQ_API_KEY"),"model":"llama-3.3-70b-versatile","limit":14000,"auth":"bearer"},
    "groq2":{"url":"https://api.groq.com/openai/v1/chat/completions","key":os.getenv("GROQ_API_KEY_2"),"model":"llama-3.3-70b-versatile","limit":14000,"auth":"bearer"},
    "cerebras":{"url":"https://api.cerebras.ai/v1/chat/completions","key":os.getenv("CEREBRAS_API_KEY"),"model":"llama-3.3-70b","limit":2000,"auth":"bearer"},
    "sambanova":{"url":"https://api.sambanova.ai/v1/chat/completions","key":os.getenv("SAMBANOVA_API_KEY"),"model":"Meta-Llama-3.1-405B-Instruct","limit":900,"auth":"bearer"},
    "gemini":{"url":"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions","key":os.getenv("GEMINI_API_KEY"),"model":"gemini-2.5-flash","limit":1500,"auth":"bearer"},
    "openrouter":{"url":"https://openrouter.ai/api/v1/chat/completions","key":os.getenv("OPENROUTER_API_KEY"),"model":"meta-llama/llama-3.3-70b-instruct:free","limit":200,"auth":"bearer"},
    "nvidia":{"url":"https://integrate.api.nvidia.com/v1/chat/completions","key":os.getenv("NVIDIA_API_KEY"),"model":"meta/llama-3.3-70b-instruct","limit":1000,"auth":"bearer"},
    "mistral":{"url":"https://api.mistral.ai/v1/chat/completions","key":os.getenv("MISTRAL_API_KEY"),"model":"mistral-small-latest","limit":1000,"auth":"bearer"},
    "ollama":{"url":f"{os.getenv('OLLAMA_BASE_URL','http://localhost:11434')}/v1/chat/completions","key":"ollama","model":os.getenv("OLLAMA_MODEL","mistral"),"limit":999999,"local":True,"auth":"bearer"},
    "pollinations":{"url":"https://text.pollinations.ai/openai","key":"","model":"openai","limit":999999,"auth":"none"},
    "github_models":{"url":"https://models.inference.ai.azure.com/chat/completions","key":os.getenv("GITHUB_TOKEN"),"model":"gpt-4o-mini","limit":150,"auth":"bearer"},
    "glm":{"url":"https://open.bigmodel.cn/api/paas/v4/chat/completions","key":os.getenv("ZHIPU_API_KEY"),"model":"glm-4.7-flash","limit":1000,"auth":"bearer"},
    "cloudflare":{"url":f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('CLOUDFLARE_ACCOUNT_ID')}/ai/run/@cf/meta/llama-3.3-70b-instruct","key":os.getenv("CLOUDFLARE_API_KEY"),"model":"@cf/meta/llama-3.3-70b-instruct","limit":10000,"auth":"cloudflare"},
    "electronhub":{"url":"https://api.electronhub.ai/v1/chat/completions","key":os.getenv("ELECTRONHUB_API_KEY"),"model":"gpt-4o","limit":500,"auth":"bearer"},
    "llm7":{"url":"https://api.llm7.io/v1/chat/completions","key":os.getenv("LLM7_API_KEY",""),"model":"deepseek-v3","limit":2000,"auth":"bearer"},
    "cohere":{"url":"https://api.cohere.com/v2/chat","key":os.getenv("COHERE_API_KEY"),"model":"command-r-plus","limit":1000,"auth":"cohere"},
}

USAGE = {p:0 for p in PROVIDERS}
_CACHE = {}
_CACHE_KEYS = []
CACHE_SIZE = 200

TASK_ROUTES = {
    "fast":      ["groq","groq2","cerebras","gemini","mistral","llm7","electronhub","github_models","glm","ollama"],
    "heavy":     ["sambanova","gemini","nvidia","groq","openrouter","github_models","cloudflare","ollama"],
    "code":      ["groq","mistral","gemini","nvidia","llm7","ollama"],
    "reasoning": ["sambanova","gemini","nvidia","groq","github_models","cloudflare","ollama"],
    "fallback":  ["pollinations","llm7","openrouter","mistral","nvidia","gemini","ollama"],
    "vision":    ["gemini","github_models","pollinations","electronhub","llm7","ollama"],
}

def _cache_key(messages, system=""):
    raw = system + str(messages)
    return hashlib.md5(raw.encode()).hexdigest()

def _cache_get(key):
    return _CACHE.get(key)

def _cache_set(key, value):
    if key not in _CACHE:
        _CACHE_KEYS.append(key)
        if len(_CACHE_KEYS) > CACHE_SIZE:
            _CACHE.pop(_CACHE_KEYS.pop(0), None)
    _CACHE[key] = value

def _pick_provider(task_type="fast"):
    order = TASK_ROUTES.get(task_type, TASK_ROUTES["fast"])
    for name in order:
        p = PROVIDERS[name]
        has_key = p.get("local") or (p.get("auth") == "none") or (p.get("key") and p["key"]!="")
        if has_key and USAGE[name] < p["limit"] - 5:
            return name
    return None

async def complete(messages, system="", max_tokens=1000, task_type="fast", temperature=0.7, use_cache=True, images=None):
    ck = _cache_key(messages, system)
    if use_cache and (cached := _cache_get(ck)) and not images:
        return cached

    if images:
        task_type = "vision"

    name = _pick_provider(task_type)
    if not name:
        return "[SYSTEM] All providers at capacity. Try after midnight UTC."

    p = PROVIDERS[name]
    USAGE[name] += 1

    payload_messages = []
    if system:
        payload_messages.append({"role":"system","content":system})

    if images and messages:
        last_msg = messages[-1].copy()
        if isinstance(last_msg.get("content"), str):
            parts = [{"type":"text","text":last_msg["content"]}]
            for img in images:
                parts.append({"type":"image_url","image_url":{"url":img,"detail":"auto"}})
            last_msg["content"] = parts
            payload_messages.extend(messages[:-1])
            payload_messages.append(last_msg)
        else:
            payload_messages.extend(messages)
    else:
        payload_messages.extend(messages)

    auth = p.get("auth","bearer")
    headers = {"Content-Type":"application/json"}
    if auth == "bearer": headers["Authorization"] = f"Bearer {p['key']}"
    elif auth == "cloudflare": headers["Authorization"] = f"Bearer {p['key']}"
    elif auth == "cohere": headers["Authorization"] = f"Bearer {p['key']}"; headers["Cohere-Version"] = "2022-12-06"

    if name == "cloudflare":
        body = {"messages": payload_messages, "max_tokens": max_tokens, "temperature": temperature}
    elif name == "cohere":
        body = {"model": p["model"], "messages": payload_messages, "max_tokens": max_tokens, "temperature": temperature}
    else:
        body = {"model": p["model"], "messages": payload_messages, "max_tokens": max_tokens, "temperature": temperature}

    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(p["url"], headers=headers, json=body)
            data = resp.json()

        if name == "cloudflare":
            content = data.get("result",{}).get("response","") or data.get("errors",[{}])[0].get("message","error")
        elif name == "cohere":
            content = data.get("text","") or data.get("message","error")
        else:
            if "choices" not in data:
                USAGE[name] = p["limit"]
                return await complete(messages, system, max_tokens, "fallback", temperature, use_cache, images=images)
            content = data["choices"][0]["message"]["content"]
        print(f"[LLM] ✓ {name} ({USAGE[name]}/{p['limit']})")
        _cache_set(ck, content)
        return content
    except Exception as e:
        print(f"[LLM] {name} error: {e}")
        USAGE[name] = p["limit"]
        return await complete(messages, system, max_tokens, "fallback", temperature, use_cache, images=images)

def remaining_budget():
    return sum(max(0, PROVIDERS[k]["limit"] - USAGE[k]) for k in USAGE)

async def reset_daily_usage():
    while True:
        now = datetime.utcnow()
        secs = (23 - now.hour)*3600 + (59 - now.minute)*60 + (60 - now.second)
        await asyncio.sleep(secs + 1)
        for k in USAGE: USAGE[k] = 0
        print("[LLM] Daily reset")
        await asyncio.sleep(62)
