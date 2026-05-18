import os, asyncio, hashlib, json
from datetime import datetime

MEMORY_DIR  = "./data/memory"
SKILLS_DIR  = "./data/skills"
WORKSPACE   = "./workspace"

async def _get_sb():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key or "xxxx" in url: return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except: return None

def _checksum(content): return hashlib.sha256(content.encode()).hexdigest()[:16]

async def restore_on_startup():
    sb = await _get_sb()
    if not sb: return
    try:
        rows = sb.table("cloud_memory").select("key,content,checksum").execute()
        restored = 0
        for row in rows.data or []:
            key, content = row["key"], row["content"]
            if key.startswith("workspace/"):   path = f"{WORKSPACE}/{key.replace('workspace/','')}"
            elif key.startswith("skills/"):    path = f"{SKILLS_DIR}/{key.replace('skills/','')}"; os.makedirs(SKILLS_DIR, exist_ok=True)
            elif key.startswith("memory/"):    path = f"{MEMORY_DIR}/{key.replace('memory/','')}"; os.makedirs(MEMORY_DIR, exist_ok=True)
            else: continue
            if not os.path.exists(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path,"w") as f: f.write(content)
                restored += 1
        print(f"[CLOUD] Restored {restored} files")
    except Exception as e: print(f"[CLOUD] Restore error: {e}")

def _upsert(sb, key, content, existing_checksum):
    new_cs = _checksum(content)
    if existing_checksum == new_cs: return False
    try:
        sb.table("cloud_memory").upsert({"key":key,"content":content[:60000],"checksum":new_cs,"updated_at":datetime.utcnow().isoformat()}).execute()
        sb.table("cloud_memory_log").insert({"key":key,"checksum":new_cs,"length":len(content),"logged_at":datetime.utcnow().isoformat()}).execute()
        return True
    except Exception as e: print(f"[CLOUD] Upsert error: {e}"); return False

async def sync_to_cloud():
    sb = await _get_sb()
    if not sb: return
    try:
        existing = {r["key"]:r["checksum"] for r in (sb.table("cloud_memory").select("key,checksum").execute().data or [])}
    except: existing = {}
    synced = 0
    for fname in os.listdir(WORKSPACE):
        if not fname.endswith(".md"): continue
        path = f"{WORKSPACE}/{fname}"
        content = open(path).read()
        key = f"workspace/{fname}"
        if _upsert(sb, key, content, existing.get(key)): synced += 1
    if os.path.exists(SKILLS_DIR):
        for fname in os.listdir(SKILLS_DIR):
            if not fname.endswith(".md") or fname.startswith("."): continue
            path = f"{SKILLS_DIR}/{fname}"
            content = open(path).read()
            key = f"skills/{fname}"
            if _upsert(sb, key, content, existing.get(key)): synced += 1
    if os.path.exists(MEMORY_DIR):
        for fname in os.listdir(MEMORY_DIR):
            if not fname.endswith(".md"): continue
            path = f"{MEMORY_DIR}/{fname}"
            content = open(path).read()
            key = f"memory/{fname}"
            if _upsert(sb, key, content, existing.get(key)): synced += 1
    print(f"[CLOUD] Synced {synced} files")

async def cloud_sync_loop():
    await restore_on_startup()
    while True:
        await asyncio.sleep(30*60)
        await sync_to_cloud()

async def flush_on_shutdown():
    print("[CLOUD] Shutdown flush")
    await sync_to_cloud()
