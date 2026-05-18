import os, ast, asyncio, importlib.util, sqlite3
from datetime import datetime

PLUGINS_DIR = "./plugins"
PLUGIN_DB   = "./data/sqlite/plugins.db"
os.makedirs(PLUGINS_DIR, exist_ok=True)

BANNED_IMPORTS = {"os","subprocess","sys","socket","shutil","pathlib","ctypes","multiprocessing","importlib","pickle","marshal","exec","eval","__import__","compile"}
_loaded_plugins = {}
_plugin_tools = {}

def _init_db():
    conn = sqlite3.connect(PLUGIN_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS plugin_allowlist (name TEXT PRIMARY KEY, status TEXT DEFAULT 'pending', loaded_at TEXT, hash TEXT)")
    conn.commit(); conn.close()
_init_db()

def _ast_check(source):
    violations = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e: return [str(e)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if name.split(".")[0] in BANNED_IMPORTS: violations.append(f"Banned import: {name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec","eval","compile","__import__"}:
            violations.append(f"Banned call: {node.func.id}()")
    return violations

def register_tool(name, func, description=""):
    _plugin_tools[name] = func

def _load_plugin(path):
    name = os.path.basename(path).replace(".py","")
    source = open(path).read()
    violations = _ast_check(source)
    if violations:
        print(f"[PLUGIN] {name} blocked: {violations}")
        return False
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        module.register_tool = register_tool
        spec.loader.exec_module(module)
        _loaded_plugins[name] = module
        return True
    except Exception as e:
        print(f"[PLUGIN] Error {name}: {e}")
        return False

def load_all():
    for fname in os.listdir(PLUGINS_DIR):
        if fname.endswith(".py") and not fname.startswith("_"):
            _load_plugin(f"{PLUGINS_DIR}/{fname}")

async def watch_plugins():
    seen = {}
    while True:
        await asyncio.sleep(10)
        for fname in os.listdir(PLUGINS_DIR):
            if not fname.endswith(".py") or fname.startswith("_"): continue
            path = f"{PLUGINS_DIR}/{fname}"
            mtime = os.path.getmtime(path)
            name = fname.replace(".py","")
            if path not in seen or seen[path] != mtime:
                seen[path] = mtime
                if name in _loaded_plugins: del _loaded_plugins[name]
                _load_plugin(path)
