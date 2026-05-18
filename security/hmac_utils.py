import os, hmac, hashlib, json, time
from dotenv import load_dotenv
load_dotenv()
SECRET = os.getenv("INTERNAL_HMAC_SECRET","change-me").encode()

def sign_request(payload: dict | bytes):
    if isinstance(payload, dict):
        body = json.dumps(payload, sort_keys=True).encode()
    else:
        body = payload
    sig = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return body, f"sha256={sig}"

def verify_signature(body: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

async def signed_post(url: str, payload: dict, timeout=60) -> dict:
    import httpx
    body, sig = sign_request(payload)
    async with httpx.AsyncClient(timeout=timeout) as c:
        resp = await c.post(url, content=body, headers={
            "Content-Type":"application/json",
            "X-Nexus-Signature":sig,
            "X-Timestamp":str(int(time.time())),
        })
        return resp.json()
