import os, asyncio
from crewai import Agent, Task, Crew, Process, LLM
from langchain_community.tools import DuckDuckGoSearchRun
from crewai.tools import tool
from memory.hermes_memory import hermes_memory
from router.free_llm import complete

AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS","90"))

def _make_llm():
    key = os.getenv("GROQ_API_KEY")
    if not key or "xxxx" in key:
        print("⚠ WARNING: GROQ_API_KEY is missing.")
        return None
    # Using the native CrewAI LLM wrapper to resolve Pydantic validation errors
    return LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=key,
        temperature=0.7,
        timeout=60
    )

llm = _make_llm()

@tool("Web Search")
def web_search(query: str) -> str:
    """Useful to search the internet for current events, news, and real-time information."""
    try: return DuckDuckGoSearchRun().run(query)
    except: return "Search failed"

@tool("Memory Recall")
def recall_memory(query: str) -> str:
    """Retrieves relevant facts and skills from the agent's long-term persistent memory based on the query."""
    mem = hermes_memory.facts.search(query)
    sk = hermes_memory.skills.search(query)
    return "\n".join(mem+sk) or "No memories"

@tool("Crypto Price")
def get_crypto_price(coin: str) -> str:
    """Fetches the current market price and 24h change for a specific cryptocurrency (e.g., 'bitcoin', 'ethereum')."""
    import httpx
    try:
        resp = httpx.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids":coin,"vs_currencies":"usd","include_24hr_change":"true"}, timeout=10)
        return str(resp.json())
    except: return "Failed"

@tool("Run Python Code")
def run_python(code_and_mode: str) -> str:
    """Executes Python code. Format: 'sandbox' or 'unlocked' on the first line, then the code. Default is sandbox."""
    lines = code_and_mode.split("\n",1)
    if len(lines)==2 and lines[0].strip() in ("sandbox","unlocked"):
        mode = lines[0].strip()
        code = lines[1]
    else:
        mode = "sandbox"
        code = code_and_mode
    from core.code_executor import execute_python
    return execute_python(code, mode)

from device.agent_tools import tool_list_devices, tool_shell, tool_file_read, tool_file_write, tool_screenshot, tool_notify

researcher = Agent(role="Research Specialist", goal="Find accurate info",
                   backstory="Expert analyst", tools=[web_search, recall_memory], llm=llm, verbose=True, memory=True, max_iter=5)
coder = Agent(role="Code Specialist", goal="Write clean Python",
              backstory="Senior engineer", tools=[recall_memory, run_python], llm=llm, verbose=True, memory=True, max_iter=5)
analyst = Agent(role="Data Analyst", goal="Find patterns",
                backstory="Statistical expert", tools=[recall_memory, run_python, tool_list_devices, tool_file_read],
                llm=llm, verbose=True, memory=True, max_iter=5)
critic = Agent(role="Quality Critic", goal="Identify flaws", backstory="Demanding reviewer", tools=[], llm=llm, verbose=True, max_iter=3)
crypto_agent = Agent(role="Crypto Specialist", goal="Analyze crypto",
                     backstory="Blockchain expert", tools=[web_search, get_crypto_price, recall_memory], llm=llm, verbose=True, memory=True, max_iter=5)
automator = Agent(role="Device Automator", goal="Control devices",
                  backstory="Automation expert", tools=[tool_list_devices, tool_shell, tool_file_read, tool_file_write, tool_screenshot, tool_notify, recall_memory],
                  llm=llm, verbose=True, memory=True, max_iter=5)

AGENT_MAP = {
    "research": [researcher, critic],
    "code": [coder, critic],
    "analysis": [analyst, critic],
    "crypto": [crypto_agent, analyst, critic],
    "heavy": [researcher, analyst, critic],
    "full": [researcher, coder, analyst, critic],
    "device": [automator, critic],
    "automate": [automator, analyst, critic],
}

def _run_crew_sync(goal, task_type):
    ctx = hermes_memory.get_context(goal)
    hint = ""
    if ctx["skills"]: hint += "\nRelevant skills:\n" + "\n---\n".join(ctx["skills"][:2])
    if ctx["memory_facts"]: hint += "\nRelevant memory:\n" + "\n".join(ctx["memory_facts"][:3])
    enriched = goal + hint
    agents = AGENT_MAP.get(task_type, AGENT_MAP["research"])
    task = Task(description=enriched, expected_output="Comprehensive answer", agent=agents[0])
    crew = Crew(agents=agents, tasks=[task], process=Process.sequential, verbose=True)
    result = str(crew.kickoff())
    hermes_memory.after_task(goal, result, True, 0.8)
    return result

async def run_crew(goal, task_type="research", images=None):
    # Explicit check for API Key
    if not os.getenv("GROQ_API_KEY") or "xxxx" in os.getenv("GROQ_API_KEY", ""):
        return "❌ CONFIGURATION ERROR: GROQ_API_KEY is missing or invalid in your Space Secrets. Please add your key from console.groq.com to the Hugging Face Settings tab."

    if images:
        try:
            desc = await complete(
                messages=[{"role":"user","content":"Describe this image in detail."}],
                task_type="vision", max_tokens=500, images=[images[0]]
            )
            goal = f"{goal}\n\n[Image description]: {desc}"
        except: pass

    try:
        # Re-initialize LLM in case it was None at startup
        global llm
        if llm is None:
            llm = _make_llm()
            if llm is None: return "❌ LLM Initialization Failed. Check GROQ_API_KEY."

        result = await asyncio.wait_for(
            asyncio.to_thread(_run_crew_sync, goal, task_type),
            timeout=AGENT_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        msg = f"[TIMEOUT] Task exceeded {AGENT_TIMEOUT}s"
        hermes_memory.after_task(goal, msg, False, 0.1)
        return msg
    except Exception as e:
        import traceback
        print(f"DEBUG: {traceback.format_exc()}")
        msg = f"[ERROR] {str(e)[:200]}"
        hermes_memory.after_task(goal, msg, False, 0.0)
        return msg
