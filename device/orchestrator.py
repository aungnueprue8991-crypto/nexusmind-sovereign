import json, hmac, hashlib, time, asyncio, os
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

_connected_devices = {}
_pending_commands = {}

def sign_request(payload, secret):
    body = json.dumps(payload, sort_keys=True).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

async def handle_device_ws(websocket: WebSocket, secret: str):
    await websocket.accept()
    device_name = None
    try:
        async for raw in websocket.iter_text():
            try: msg = json.loads(raw)
            except: continue
            msg_type = msg.get("type","")
            if msg_type == "register":
                sig = msg.pop("signature","")
                expected = sign_request(msg, secret)
                if sig != expected:
                    await websocket.send(json.dumps({"type":"error","error":"Invalid signature"}))
                    continue
                device_name = msg["device_name"]
                _connected_devices[device_name] = {
                    "ws":websocket,"capabilities":msg.get("capabilities",[]),
                    "device_type":msg.get("device_type","unknown"),
                    "last_seen":datetime.utcnow(),"connected_at":datetime.utcnow()
                }
                print(f"[ORCH] Device registered: {device_name}")
                await websocket.send(json.dumps({"type":"registered","device_name":device_name}))
            elif msg_type.endswith("_result") or msg_type in ("pong","error"):
                cmd_id = msg.get("command_id","")
                if cmd_id in _pending_commands:
                    _pending_commands[cmd_id].set_result(msg)
                    del _pending_commands[cmd_id]
            if device_name and device_name in _connected_devices:
                _connected_devices[device_name]["last_seen"] = datetime.utcnow()
    except WebSocketDisconnect:
        pass
    finally:
        if device_name and device_name in _connected_devices:
            del _connected_devices[device_name]

async def send_command(device_name, command, secret, timeout=30):
    if device_name not in _connected_devices:
        return {"error": f"Device '{device_name}' not connected"}
    device = _connected_devices[device_name]
    cmd_id = f"cmd_{int(time.time())}"
    command["command_id"] = cmd_id
    command["signature"] = sign_request(command, secret)
    future = asyncio.get_event_loop().create_future()
    _pending_commands[cmd_id] = future
    try:
        await device["ws"].send_text(json.dumps(command))
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        _pending_commands.pop(cmd_id, None)
        return {"error": "Command timeout"}

def list_devices():
    return [{"name":n,"device_type":d["device_type"],"capabilities":d["capabilities"],"last_seen":d["last_seen"].isoformat()} for n,d in _connected_devices.items()]
