import os
import sys
import asyncio

# Add current directory and the nexusmind directory to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "nexusmind"))

# Manually load .env since we're running from the root
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), "nexusmind", ".env"))

from router.free_llm import _pick_provider, PROVIDERS, USAGE

async def run_diagnostic():
    print("--- NexusMind Routing Diagnostic ---")
    
    # Simulate a key for Gemini for testing
    if not PROVIDERS["gemini"]["key"]:
        PROVIDERS["gemini"]["key"] = "SIMULATED_KEY_FOR_TEST"
    
    # Test cases for routing
    tasks = ["fast", "heavy", "code", "vision", "reasoning"]
    
    for task in tasks:
        provider = _pick_provider(task)
        if provider:
            p_info = PROVIDERS[provider]
            print(f"[SUCCESS] Task '{task}' routed to: {provider} ({p_info['model']})")
        else:
            print(f"[FAILURE] Task '{task}' found no available providers.")

    print("\n--- Provider Availability Check (Simulated) ---")
    available_count = 0
    for name, p in PROVIDERS.items():
        has_key = p.get("local") or (p.get("auth") == "none") or (p.get("key") and p["key"] != "")
        status = "READY" if has_key else "MISSING_KEY"
        if has_key: available_count += 1
        print(f"[{status}] {name:<15} | Model: {p['model']}")
    
    print(f"\nSummary: {available_count}/{len(PROVIDERS)} providers configured.")

if __name__ == '__main__':
    asyncio.run(run_diagnostic())
