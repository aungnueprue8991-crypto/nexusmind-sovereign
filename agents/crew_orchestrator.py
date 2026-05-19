import os, asyncio
from crewai import Agent, Task, Crew, Process, LLM
from langchain_community.tools import DuckDuckGoSearchRun
from crewai.tools import tool
from memory.hermes_memory import hermes_memory
from router.free_llm import complete

# Core Settings
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS","120"))

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
    """Executes Python code. Format: 'sandbox' or 'unlocked' on the first line, then the code."""
    lines = code_and_mode.split("\n",1)
    if len(lines)==2 and lines[0].strip() in ("sandbox","unlocked"):
        mode = lines[0].strip(); code = lines[1]
    else:
        mode = "sandbox"; code = code_and_mode
    from core.code_executor import execute_python
    return execute_python(code, mode)

from device.agent_tools import tool_list_devices, tool_shell, tool_file_read, tool_file_write, tool_screenshot, tool_notify

def _run_crew_sync(goal, task_type):
    # Initialize the LLM wrapper fresh for every task
    nexus_llm = LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.7
    )
    
    # Define Agents
    researcher = Agent(role="Research Specialist", goal="Find accurate info", backstory="Expert analyst", 
                       tools=[web_search, recall_memory], llm=nexus_llm, verbose=True, memory=True)
    coder = Agent(role="Code Specialist", goal="Write clean Python", backstory="Senior engineer", 
                  tools=[recall_memory, run_python], llm=nexus_llm, verbose=True, memory=True)
    analyst = Agent(role="Data Analyst", goal="Find patterns", backstory="Statistical expert", 
                    tools=[recall_memory, run_python, tool_list_devices], llm=nexus_llm, verbose=True, memory=True)
    critic = Agent(role="Quality Critic", goal="Identify flaws", backstory="Demanding reviewer", 
                   tools=[], llm=nexus_llm, verbose=True)
    crypto = Agent(role="Crypto Specialist", goal="Analyze crypto", backstory="Blockchain expert", 
                   tools=[web_search, get_crypto_price], llm=nexus_llm, verbose=True, memory=True)
    automator = Agent(role="Device Automator", goal="Control devices", backstory="Automation expert", 
                      tools=[tool_list_devices, tool_shell, tool_screenshot, tool_notify], llm=nexus_llm, verbose=True, memory=True)

    agent_map = {
        "research": [researcher, critic],
        "code": [coder, critic],
        "analysis": [analyst, critic],
        "crypto": [crypto, analyst, critic],
        "heavy": [researcher, analyst, critic],
        "full": [researcher, coder, analyst, critic],
        "device": [automator, critic],
        "automate": [automator, analyst, critic],
    }

    ctx = hermes_memory.get_context(goal)
    hint = ""
    if ctx["skills"]: hint += "\nSkills:\n" + "\n---\n".join(ctx["skills"][:2])
    if ctx["memory_facts"]: hint += "\nMemory:\n" + "\n".join(ctx["memory_facts"][:3])
    
    task = Task(description=goal + hint, expected_output="Detailed final response", agent=agent_map.get(task_type, [researcher])[0])
    crew = Crew(agents=agent_map.get(task_type, [researcher, critic]), tasks=[task], process=Process.sequential, verbose=True)
    
    result = str(crew.kickoff())
    hermes_memory.after_task(goal, result, True, 0.8)
    return result

async def run_crew(goal, task_type="research", images=None):
    if not os.getenv("GROQ_API_KEY"):
        return "❌ Missing GROQ_API_KEY."

    if images:
        try:
            desc = await complete(messages=[{"role":"user","content":"Describe image."}], task_type="vision", images=[images[0]])
            goal = f"{goal}\n\n[Image]: {desc}"
        except: pass

    try:
        return await asyncio.wait_for(asyncio.to_thread(_run_crew_sync, goal, task_type), timeout=AGENT_TIMEOUT)
    except Exception as e:
        return f"⚠️ SYSTEM ERROR: {str(e)}"
