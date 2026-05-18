import os, asyncio, signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

def verify_admin(request: Request):
    key = request.headers.get("X-Admin-Key")
    if not key or key != ADMIN_PASSWORD:
        raise HTTPException(403, "Admin access required")

@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.startup_check import run_startup_checks
    ok = await run_startup_checks()
    if not ok:
        raise RuntimeError("Startup checks failed")

    from memory.cloud_sync import restore_on_startup
    await restore_on_startup()

    from router.free_llm import reset_daily_usage
    from heartbeat.heartbeat import run_heartbeat
    from skills.skill_manager import run_curator
    from core.dreaming import dream_loop
    from core.curiosity import curiosity_loop
    from core.self_improver import self_improve_loop
    from core.plugin_manager import load_all, watch_plugins
    from memory.cloud_sync import cloud_sync_loop

    load_all()

    tasks = [
        asyncio.create_task(reset_daily_usage()),
        asyncio.create_task(run_heartbeat()),
        asyncio.create_task(dream_loop()),
        asyncio.create_task(curiosity_loop()),
        asyncio.create_task(self_improve_loop()),
        asyncio.create_task(watch_plugins()),
        asyncio.create_task(cloud_sync_loop()),
        asyncio.create_task(run_curator()),
    ]
    print("✅ NexusMind v2.3 — all systems active")
    yield
    from memory.cloud_sync import flush_on_shutdown
    await flush_on_shutdown()
    for t in tasks:
        t.cancel()

app = FastAPI(title="NexusMind", version="2.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

import os as _os
dashboard_path = _os.path.join(_os.path.dirname(__file__), "dashboard")
app.mount("/dashboard", StaticFiles(directory=dashboard_path, html=True), name="dashboard")

class Attachment(BaseModel):
    name: str
    data: str
    type: str = "image"

class TaskRequest(BaseModel):
    goal: str
    task_type: str = "research"
    attachments: list[Attachment] = []

class MessagePayload(BaseModel):
    message: str
    user_id: str = "default"
    attachments: list[Attachment] = []

from security.rate_limiter import rate_limit

@app.get("/")
async def root():
    from router.free_llm import remaining_budget
    return {
        "status": "NexusMind v2.3",
        "budget": remaining_budget(),
        "dashboard": "/dashboard",
    }

@app.get("/health")
async def health():
    from router.free_llm import remaining_budget
    return {"status": "ok", "llm_budget_left": remaining_budget()}

@app.post("/run", dependencies=[Depends(rate_limit)])
async def run_task(payload: TaskRequest):
    if not payload.goal.strip():
        raise HTTPException(400, "Goal empty")
    from agents.crew_orchestrator import run_crew
    from core.dreaming import mark_active
    mark_active()
    images = [a.data for a in payload.attachments if a.type == "image"]
    text_parts = []
    for a in payload.attachments:
        if a.type != "image":
            try:
                import base64
                if a.data.startswith("data:"):
                    header, data = a.data.split(",", 1)
                    decoded = base64.b64decode(data).decode("utf-8", errors="ignore")
                    text_parts.append(f"[File: {a.name}]\n{decoded[:3000]}")
                else:
                    text_parts.append(f"[File: {a.name}]\n{a.data[:3000]}")
            except: pass
    goal = payload.goal
    if text_parts:
        goal += "\n\n" + "\n".join(text_parts)
    result = await run_crew(goal, payload.task_type, images=images if images else None)
    return {"goal": payload.goal, "result": result, "task_type": payload.task_type}

@app.post("/message", dependencies=[Depends(rate_limit)])
async def handle_message(payload: MessagePayload):
    from memory.hermes_memory import hermes_memory
    from agents.crew_orchestrator import run_crew
    from core.dreaming import mark_active
    hermes_memory.session.add("user", payload.message)
    mark_active()
    images = [a.data for a in payload.attachments if a.type == "image"]
    text_parts = []
    for a in payload.attachments:
        if a.type != "image":
            try:
                import base64
                if a.data.startswith("data:"):
                    header, data = a.data.split(",", 1)
                    decoded = base64.b64decode(data).decode("utf-8", errors="ignore")
                    text_parts.append(f"[File: {a.name}]\n{decoded[:3000]}")
                else:
                    text_parts.append(f"[File: {a.name}]\n{a.data[:3000]}")
            except: pass
    combined = payload.message
    if text_parts:
        combined += "\n\n" + "\n".join(text_parts)
    t = combined.lower()
    if any(w in t for w in ["code","write","fix","debug","script"]):
        tt = "code"
    elif any(w in t for w in ["bitcoin","crypto","eth","price","defi"]):
        tt = "crypto"
    elif any(w in t for w in ["analyze","trend","compare","data"]):
        tt = "analysis"
    elif any(w in t for w in ["why","reason","think","solve"]):
        tt = "heavy"
    else:
        tt = "research"
    result = await run_crew(combined, tt, images=images if images else None)
    reply = result[:3800] + "…" if len(result) > 3800 else result
    return {"reply": reply, "task_type": tt, "user_id": payload.user_id}

@app.post("/memory/recall")
async def recall_memory(query: dict):
    from memory.hermes_memory import hermes_memory
    q = query.get("query","")
    facts = hermes_memory.facts.search(q)
    skills = hermes_memory.skills.search(q)
    return {"facts": facts, "skills": skills}

@app.post("/dream/now")
async def trigger_dream():
    from core.dreaming import _dream_memory, _dream_skills, _dream_insights
    await _dream_memory()
    await _dream_skills()
    await _dream_insights()
    return {"status": "dream complete"}

@app.post("/synthesize")
async def synthesize():
    from agents.crew_orchestrator import run_crew
    goal = ("Synthesize all memory and skills. Provide key insights, patterns, and recommendations.")
    result = await run_crew(goal, task_type="heavy")
    return {"synthesis": result}

@app.post("/synthesize/cross-domain")
async def cross_domain(payload: dict):
    domains = payload.get("domains", [])
    from agents.crew_orchestrator import run_crew
    if domains:
        goal = f"Fuse insights from: {', '.join(domains)}. Generate novel hypotheses."
    else:
        goal = "Detect knowledge domains, then fuse them to generate novel theories."
    result = await run_crew(goal, task_type="heavy")
    return {"synthesis": result}

@app.post("/dream-and-synthesize")
async def dream_and_synthesize():
    from core.dreaming import _dream_memory, _dream_skills, _dream_insights
    from agents.crew_orchestrator import run_crew
    dream_out = {}
    try:
        await _dream_memory(); dream_out["memory"] = "Consolidated"
    except Exception as e: dream_out["memory"] = str(e)
    try:
        await _dream_skills(); dream_out["skills"] = "Deduplicated"
    except Exception as e: dream_out["skills"] = str(e)
    try:
        await _dream_insights(); dream_out["insights"] = "Extracted"
    except Exception as e: dream_out["insights"] = str(e)
    try:
        synthesis = await run_crew("Synthesize all knowledge", task_type="heavy")
    except Exception as e: synthesis = str(e)
    return {"dream": dream_out, "synthesis": synthesis}

from core.code_executor import execute_python

@app.post("/code/execute")
async def exec_code(request: Request):
    body = await request.json()
    code = body.get("code","")
    if not code: raise HTTPException(400,"No code")
    output = execute_python(code, mode="sandbox")
    return {"output": output}

@app.post("/code/execute/unlocked")
async def exec_code_unlocked(request: Request, _ = Depends(verify_admin)):
    body = await request.json()
    code = body.get("code","")
    output = execute_python(code, mode="unlocked")
    return {"output": output}

@app.post("/restart")
async def restart(request: Request, _ = Depends(verify_admin)):
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "restarting"}

from device.orchestrator import handle_device_ws, list_devices, send_command

@app.websocket("/device/ws/{device_name}")
async def device_ws(websocket: WebSocket, device_name: str):
    secret = os.getenv("INTERNAL_HMAC_SECRET","change-me")
    await handle_device_ws(websocket, secret)

@app.get("/device/list")
async def devices():
    return {"devices": list_devices()}

@app.post("/device/command")
async def device_cmd(payload: dict):
    secret = os.getenv("INTERNAL_HMAC_SECRET","change-me")
    return await send_command(payload["device_name"], payload["command"], secret, payload.get("timeout",30))

import re as _re
@app.get("/skills/list")
async def list_skills():
    skills_dir = "./data/skills"
    if not os.path.exists(skills_dir): return {"skills":[]}
    items = []
    for f in os.listdir(skills_dir):
        if f.endswith(".md") and not f.startswith("."):
            with open(os.path.join(skills_dir, f)) as fp: title = fp.readline().strip().replace("# Skill: ","")
            items.append({"name": f, "title": title})
    return {"skills": items}

@app.post("/skills/create")
async def create_skill(payload: dict):
    name = payload.get("name","").strip()
    content = payload.get("content","")
    if not name or not content: raise HTTPException(400,"Name and content required")
    slug = _re.sub(r"[^a-z0-9_]", "_", name.lower())[:50]
    path = f"./data/skills/{slug}.md"
    os.makedirs("./data/skills", exist_ok=True)
    with open(path,"w") as f: f.write(content)
    return {"status":"created","path":path}

from core.plugin_manager import _load_plugin

@app.post("/plugins/upload")
async def plugin_upload(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"): raise HTTPException(400,"Only .py allowed")
    import aiofiles
    path = f"./plugins/{file.filename}"
    os.makedirs("./plugins", exist_ok=True)
    async with aiofiles.open(path,"wb") as f: await f.write(await file.read())
    success = _load_plugin(path)
    return {"status":"loaded" if success else "failed","filename":file.filename}

@app.get("/plugins")
async def list_plugins():
    from core.plugin_manager import _loaded_plugins, _plugin_tools
    return {"plugins": list(_loaded_plugins.keys()), "tools": list(_plugin_tools.keys())}

@app.get("/stats")
async def stats():
    from router.free_llm import USAGE, PROVIDERS, remaining_budget
    from memory.hermes_memory import hermes_memory
    return {
        "llm_usage": {k: {"used":USAGE[k],"limit":PROVIDERS[k]["limit"],"pct":round(USAGE[k]/PROVIDERS[k]["limit"]*100,1)} for k in USAGE},
        "budget_remaining": remaining_budget(),
        "memory_size": len(hermes_memory.facts.read())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("DASHBOARD_PORT","7860")))
