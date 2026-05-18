import asyncio
from memory.hermes_memory import hermes_memory

async def run_curator():
    while True:
        await asyncio.sleep(3600)
        hermes_memory.skills.curate()
