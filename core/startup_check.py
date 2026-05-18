import os, asyncio
from dotenv import load_dotenv
load_dotenv()

async def run_startup_checks() -> bool:
    results = {}
    llm_keys = {"GROQ_API_KEY":os.getenv("GROQ_API_KEY"),"GEMINI_API_KEY":os.getenv("GEMINI_API_KEY")}
    llm_ok = any(v and "xxxx" not in v for v in llm_keys.values())
    results["LLM providers"] = "✓ OK" if llm_ok else "⚠ WARNING"
    secret = os.getenv("INTERNAL_HMAC_SECRET","change-me")
    results["HMAC secret"] = "✓ OK" if secret!="change-me" else "⚠ WARNING"
    for f in ["SOUL.md","AGENTS.md","MEMORY.md"]:
        path = f"./workspace/{f}"
        if not os.path.exists(path):
            with open(path,"w") as fh: fh.write(f"# {f.replace('.md','')}\n")
    print("\n=== STARTUP CHECK ===")
    for comp, status in results.items(): print(f"  {comp:<22} {status}")
    return True
