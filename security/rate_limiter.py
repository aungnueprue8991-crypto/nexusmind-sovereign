import time, os
from collections import defaultdict, deque
from fastapi import Request, HTTPException

LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE","10"))
WINDOW = 60
_windows: dict[str, deque] = defaultdict(deque)

def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd: return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def rate_limit(request: Request):
    ip = _get_ip(request)
    now = time.time()
    win = _windows[ip]
    while win and win[0] < now - WINDOW:
        win.popleft()
    if len(win) >= LIMIT:
        retry = int(WINDOW - (now - win[0]))
        raise HTTPException(429, detail=f"Rate limit. Retry after {retry}s", headers={"Retry-After":str(retry)})
    win.append(now)
    if len(_windows) > 10000:
        stale = [ip for ip,w in _windows.items() if not w or w[-1] < now - WINDOW*2]
        for ip in stale[:1000]: del _windows[ip]
