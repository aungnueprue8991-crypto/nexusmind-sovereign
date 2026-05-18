import os, json, asyncio
from datetime import datetime
from router.free_llm import complete

MEMORY_FILE = "./workspace/MEMORY.md"
SKILLS_DIR  = "./data/skills"
DREAMS_LOG  = "./data/dreams"
IDLE_SECONDS = 300
os.makedirs(DREAMS_LOG, exist_ok=True)

_last_task_time = datetime.utcnow()

def mark_active():
    global _last_task_time
    _last_task_time = datetime.utcnow()

def _idle_seconds():
    return (datetime.utcnow() - _last_task_time).total_seconds()

async def _dream_memory():
    from memory.hermes_memory import hermes_memory
    if not os.path.exists(MEMORY_FILE): return
    raw = open(MEMORY_FILE).read()
    if len(raw) < 200: return
    result = await complete(
        messages=[{"role":"user","content":f"Consolidate this memory. Remove duplicates, keep unique facts. Output bullet points.\n{raw[:4000]}"}],
        task_type="fast", max_tokens=2000, use_cache=False)
    hermes_memory.facts.safe_write(f"# NexusMind Memory\n\n{result.strip()}\n")

async def _dream_skills():
    if not os.path.exists(SKILLS_DIR): return
    files = [f for f in os.listdir(SKILLS_DIR) if f.endswith(".md")]
    if len(files) < 3: return
    titles = {}
    for fname in files:
        first_line = open(f"{SKILLS_DIR}/{fname}").readline().strip()
        titles[fname] = first_line.replace("# Skill: ", "")
    titles_str = "\n".join(f"{k}: {v}" for k,v in titles.items())
    result = await complete(
        messages=[{"role":"user","content":f"Identify duplicate skills. Output JSON array of objects with 'keep' and 'archive'.\n{titles_str}"}],
        task_type="fast", max_tokens=500)
    try:
        import re, json
        m = re.search(r"\[.*\]", result, re.DOTALL)
        if not m: return
        groups = json.loads(m.group())
        archive = f"{SKILLS_DIR}/.archive"
        os.makedirs(archive, exist_ok=True)
        for group in groups:
            for fname in group.get("archive", []):
                src = f"{SKILLS_DIR}/{fname}"
                if os.path.exists(src): os.rename(src, f"{archive}/{fname}")
    except: pass

async def _dream_insights():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_path = f"./data/memory/{today}.md"
    if not os.path.exists(log_path): return
    log = open(log_path).read()
    existing = open(MEMORY_FILE).read() if os.path.exists(MEMORY_FILE) else ""
    result = await complete(
        messages=[{"role":"user","content":f"Extract 1-3 new insights not in memory.\nLog:\n{log[:3000]}\nExisting:\n{existing[:1000]}"}],
        task_type="fast", max_tokens=300)
    if "(nothing new)" in result.lower(): return
    with open(MEMORY_FILE,"a") as f:
        f.write(f"\n\n## Insights [{today}]\n{result.strip()}\n")

async def dream_loop():
    print("[DREAM] Loop started")
    while True:
        await asyncio.sleep(60)
        if _idle_seconds() < IDLE_SECONDS: continue
        print(f"[DREAM] Idle — dreaming")
        try:
            await _dream_memory()
            await _dream_skills()
            await _dream_insights()
        except Exception as e: print(f"[DREAM] Error: {e}")
        mark_active()
