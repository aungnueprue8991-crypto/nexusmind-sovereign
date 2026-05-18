import os, asyncio
from datetime import datetime
from router.free_llm import complete, remaining_budget

CURIOSITY_LOG = "./data/curiosity"
MEMORY_FILE   = "./workspace/MEMORY.md"
MIN_BUDGET    = int(os.getenv("MIN_LLM_BUDGET_FOR_CURIOSITY","500"))
os.makedirs(CURIOSITY_LOG, exist_ok=True)

async def curiosity_loop():
    print("[CURIOSITY] Loop started")
    await asyncio.sleep(60*60*2)
    while True:
        budget = remaining_budget()
        if budget < MIN_BUDGET:
            print(f"[CURIOSITY] Skipping — budget {budget}")
            await asyncio.sleep(60*30)
            continue
        print(f"[CURIOSITY] Running — budget {budget}")
        try:
            memory = open(MEMORY_FILE).read() if os.path.exists(MEMORY_FILE) else ""
            questions = []
            result = await complete(
                messages=[{"role":"user","content":f"Review your memory and list 3 specific knowledge gaps.\nMemory:\n{memory[:2000]}"}],
                task_type="fast", max_tokens=300)
            for line in result.split("\n"):
                if line.strip() and line[0].isdigit() and "." in line:
                    q = line.split(".",1)[-1].strip()
                    if len(q)>10: questions.append(q)
            for q in questions[:3]:
                answer = await complete(
                    messages=[{"role":"user","content":q}],
                    system="Give a concise, factual answer.",
                    task_type="fast", max_tokens=400)
                ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                with open(f"{CURIOSITY_LOG}/{datetime.utcnow().strftime('%Y-%m-%d')}.md","a") as f:
                    f.write(f"\n## [{ts}] {q}\n{answer[:400]}\n")
                if os.path.exists(MEMORY_FILE):
                    with open(MEMORY_FILE,"a") as f:
                        f.write(f"\n- [CURIOUS {ts}] {q[:80]} → {answer[:120]}")
                await asyncio.sleep(5)
        except Exception as e: print(f"[CURIOSITY] Error: {e}")
        await asyncio.sleep(60*60*2)
