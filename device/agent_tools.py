from crewai.tools import tool
from device.orchestrator import send_command, list_devices
import os, asyncio

SECRET = os.getenv("INTERNAL_HMAC_SECRET","change-me")

@tool("Device List")
def tool_list_devices(dummy: str="") -> str:
    """Lists all currently connected mobile devices and their capabilities."""
    devices = list_devices()
    if not devices: return "No devices connected."
    return "\n".join(f"- {d['name']} ({d['device_type']}): {', '.join(d['capabilities'])}" for d in devices)

@tool("Shell Command")
def tool_shell(device_and_cmd: str) -> str:
    """Executes a shell command on a specific device. Format: 'device_name: command'."""
    parts = device_and_cmd.split(": ",1)
    if len(parts)!=2: return "Format: device_name: command"
    device, cmd = parts
    result = asyncio.run(send_command(device, {"type":"shell","command":cmd}, SECRET))
    return result.get("stdout","") or result.get("stderr","") or result.get("error","")

@tool("File Read")
def tool_file_read(args: str) -> str:
    """Reads the content of a file from a connected device. Format: 'device_name: /absolute/path'."""
    parts = args.split(": ",1)
    if len(parts)!=2: return "Format: device_name: /path"
    device, path = parts
    result = asyncio.run(send_command(device, {"type":"file_read","path":path}, SECRET))
    return result.get("content","") or result.get("error","")

@tool("File Write")
def tool_file_write(args: str) -> str:
    """Writes content to a file on a connected device. Format: 'device_name: /path ||| content'."""
    parts = args.split(": ",1)
    if len(parts)!=2: return "Format: device_name: /path ||| content"
    device, rest = parts
    path_content = rest.split(" ||| ",1)
    if len(path_content)!=2: return "Format error"
    path, content = path_content
    result = asyncio.run(send_command(device, {"type":"file_write","path":path,"content":content}, SECRET))
    return result.get("success","") or result.get("error","")

@tool("Take Screenshot")
def tool_screenshot(device_name: str) -> str:
    """Captures a screenshot of the specified connected device."""
    result = asyncio.run(send_command(device_name.strip(), {"type":"screenshot"}, SECRET, timeout=15))
    return f"[Screenshot: {len(result.get('screenshot_base64',''))} chars]" if "screenshot_base64" in result else result.get("error","")

@tool("Send Notification")
def tool_notify(args: str) -> str:
    """Sends a push notification to a connected device. Format: 'device_name: title ||| message'."""
    parts = args.split(": ",1)
    if len(parts)!=2: return "Format: device_name: title ||| message"
    device, rest = parts
    title_msg = rest.split(" ||| ",1)
    if len(title_msg)!=2: return "Format error"
    title, message = title_msg
    result = asyncio.run(send_command(device, {"type":"notification","title":title,"message":message}, SECRET))
    return "Notification sent" if result.get("sent") else result.get("error","")
