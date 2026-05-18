import os, asyncio
from crewai import Agent, Task, Crew, Process
from langchain_community.tools import DuckDuckGoSearchRun
from crewai.tools import tool
from memory.hermes_memory import hermes_memory
from router.free_llm import complete

# Standard configuration
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS","90"))

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

def _run_crew_sync(goal, task_type):
    # Dynamic Agent Initialization to solve Pydantic/LLM validation loops
    key = os.getenv("GROQ_API_KEY")
    # Passing the string directly is the most stable way for CrewAI Agents
    llm_config = f"groq/llama-3.3-70b-versatile"
    
    # 1. Researcher
    researcher = Agent(
        role="Research Specialist", goal="Find accurate info",
        backstory="Expert analyst", tools=[web_search, recall_memory], 
        llm=llm_config, verbose=True, memory=True, max_iter=5
    )
    # 2. Coder
    coder = Agent(
        role="Code Specialist", goal="Write clean Python",
        backstory="Senior engineer", tools=[recall_memory, run_python], 
        llm=llm_config, verbose=True, memory=True, max_iter=5
    )
    # 3. Analyst
    analyst = Agent(
        role="Data Analyst", goal="Find patterns",
        backstory="Statistical expert", tools=[recall_memory, run_python, tool_list_devices, tool_file_read],
        llm=llm_config, verbose=True, memory=True, max_iter=5
    )
    # 4. Critic
    critic = Agent(
        role="Quality Critic", goal="Identify flaws", backstory="Demanding reviewer", tools=[], 
        llm=llm_config, verbose=True, max_iter=3
    )
    # 5. Crypto
    crypto_agent = Agent(
        role="Crypto Specialist", goal="Analyze crypto",
        backstory="Blockchain expert", tools=[web_search, get_crypto_price, recall_memory], 
        llm=llm_config, verbose=True, memory=True, max_iter=5
    )
    # 6. Automator
    automator = Agent(
        role="Device Automator", goal="Control devices",
        backstory="Automation expert", tools=[tool_list_devices, tool_shell, tool_file_read, tool_file_write, tool_screenshot, tool_notify, recall_memory],
        llm=llm_config, verbose=True, memory=True, max_iter=5
    )

    agent_map = {
        "research": [researcher, critic],
        "code": [coder, critic],
        "analysis": [analyst, critic],
        "crypto": [crypto_agent, analyst, critic],
        "heavy": [researcher, analyst, critic],
        "full": [researcher, coder, analyst, critic],
        "device": [automator, critic],
        "automate": [automator, analyst, critic],
    }

    ctx = hermes_memory.get_context(goal)
    hint = ""
    if ctx["skills"]: hint += "\nRelevant skills:\n" + "\n---\n".join(ctx["skills"][:2])
    if ctx["memory_facts"]: hint += "\nRelevant memory:\n" + "\n".join(ctx["memory_facts"][:3])
    
    enriched = goal + hint
    agents = agent_map.get(task_type, agent_map["research"])
    
    task = Task(description=enriched, expected_output="Comprehensive answer", agent=agents[0])
    crew = Crew(agents=agents, tasks=[task], process=Process.sequential, verbose=True)
    
    result = str(crew.kickoff())
    hermes_memory.after_task(goal, result, True, 0.8)
    return result

async def run_crew(goal, task_type="research", images=None):
    if not os.getenv("GROQ_API_KEY") or "xxxx" in os.getenv("GROQ_API_KEY", ""):
        return "❌ CONFIGURATION ERROR: GROQ_API_KEY is missing or invalid in Space Secrets."

    if images:
        try:
            desc = await complete(
                messages=[{"role":"user","content":"Describe this image in detail."}],
                task_type="vision", max_tokens=500, images=[images[0]]
            )
            goal = f"{goal}\n\n[Image description]: {desc}"
        except: pass

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_crew_sync, goal, task_type),
            timeout=AGENT_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        return f"[TIMEOUT] Task exceeded {AGENT_TIMEOUT}s"
    except Exception as e:
        import traceback
        print(f"CRITICAL CREW ERROR: {traceback.format_exc()}")
        return f"[ERROR] {str(e)[:500]}"
