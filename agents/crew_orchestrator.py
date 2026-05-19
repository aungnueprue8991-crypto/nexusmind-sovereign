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
    # Initialize the LLM wrapper fresh for every task to avoid stale state
    # This LLM class is specific to CrewAI and handles Pydantic validation internally
    nexus_llm = LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.7
    )
    
    # Define Agents with explicit LLM configuration
    researcher = Agent(
        role="Research Specialist", 
        goal="Find accurate info", 
        backstory="Expert analyst with years of experience in data synthesis.", 
        tools=[web_search, recall_memory], 
        llm=nexus_llm, 
        verbose=True, 
        memory=True
    )
    
    coder = Agent(
        role="Code Specialist", 
        goal="Write clean, efficient Python code", 
        backstory="Senior software engineer specializing in automation and systems integration.", 
        tools=[recall_memory, run_python], 
        llm=nexus_llm, 
        verbose=True, 
        memory=True
    )
    
    analyst = Agent(
        role="Data Analyst", 
        goal="Analyze complex datasets and find patterns", 
        backstory="Statistical expert with a knack for identifying trends and insights.", 
        tools=[recall_memory, run_python, tool_list_devices], 
        llm=nexus_llm, 
        verbose=True, 
        memory=True
    )
    
    critic = Agent(
        role="Quality Critic", 
        goal="Review output for accuracy and flaws", 
        backstory="A demanding reviewer who ensures every response is production-grade.", 
        tools=[], 
        llm=nexus_llm, 
        verbose=True
    )
    
    crypto = Agent(
        role="Crypto Specialist", 
        goal="Monitor and analyze cryptocurrency markets", 
        backstory="Blockchain expert with deep knowledge of DeFi and market cycles.", 
        tools=[web_search, get_crypto_price], 
        llm=nexus_llm, 
        verbose=True, 
        memory=True
    )
    
    automator = Agent(
        role="Device Automator", 
        goal="Control and orchestrate mobile devices", 
        backstory="Automation expert specialized in remote device management and testing.", 
        tools=[tool_list_devices, tool_shell, tool_screenshot, tool_notify], 
        llm=nexus_llm, 
        verbose=True, 
        memory=True
    )

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
    if ctx["skills"]: hint += "\n\nRelevant Skills:\n" + "\n---\n".join(ctx["skills"][:2])
    if ctx["memory_facts"]: hint += "\n\nRelevant Memory:\n" + "\n".join(ctx["memory_facts"][:3])
    
    task_description = goal + hint
    agents = agent_map.get(task_type, [researcher, critic])
    
    task = Task(
        description=task_description, 
        expected_output="A comprehensive and detailed final response.", 
        agent=agents[0]
    )
    
    crew = Crew(
        agents=agents, 
        tasks=[task], 
        process=Process.sequential, 
        verbose=True
    )
    
    result = str(crew.kickoff())
    hermes_memory.after_task(goal, result, True, 0.8)
    return result

async def run_crew(goal, task_type="research", images=None):
    if not os.getenv("GROQ_API_KEY"):
        return "❌ CONFIGURATION ERROR: GROQ_API_KEY is missing."

    if images:
        try:
            desc = await complete(messages=[{"role":"user","content":"Describe this image."}], task_type="vision", images=[images[0]])
            goal = f"{goal}\n\n[Context from Image]: {desc}"
        except Exception as e:
            print(f"Vision error: {e}")

    try:
        # Run in a separate thread to avoid blocking the event loop
        return await asyncio.wait_for(
            asyncio.to_thread(_run_crew_sync, goal, task_type), 
            timeout=AGENT_TIMEOUT
        )
    except asyncio.TimeoutError:
        return f"⏰ TIMEOUT: Task exceeded {AGENT_TIMEOUT} seconds."
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"CRITICAL ERROR:\n{err_msg}")
        return f"⚠️ SYSTEM ERROR: {str(e)}"
