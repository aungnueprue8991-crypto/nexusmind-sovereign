import asyncio
async def run_heartbeat():
    while True:
        await asyncio.sleep(600)
