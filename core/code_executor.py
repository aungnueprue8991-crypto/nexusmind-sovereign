import ast
import subprocess
import tempfile
import os
import sys

EXECUTION_TIMEOUT = 30
MAX_OUTPUT = 4000

# Strict list of allowed modules
ALLOWED_MODULES = {"math", "json", "re", "datetime", "time", "random", "statistics", "itertools", "collections", "hashlib", "base64"}

def _clean_env():
    """Returns a sanitized environment dictionary."""
    safe = {}
    # Keep only essential and non-sensitive variables
    for k in ("PATH", "LANG", "LC_ALL", "PYTHONPATH", "PYTHONUNBUFFERED", "TERM"):
        if k in os.environ:
            safe[k] = os.environ[k]
    safe["HOME"] = os.getenv("HOME", "/tmp")
    return safe

def validate_sandbox(code):
    """
    Performs a deep AST audit of the code.
    Blocks banned imports, sensitive attributes, and dangerous calls.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

    for node in ast.walk(tree):
        # Block banned imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
            for mod in modules:
                if mod and mod.split('.')[0] not in ALLOWED_MODULES:
                    return False, f"Banned import: {mod}"
        
        # Block dangerous calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "compile", "__import__", "open", "input", "getattr", "setattr", "delattr", "hasattr", "globals", "locals"}:
                    return False, f"Banned call: {node.func.id}()"
        
        # Block sensitive attribute access (e.g., __subclasses__, __globals__)
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return False, f"Banned attribute access: {node.attr}"
                
    return True, ""

def execute_python(code, mode="sandbox"):
    """
    Executes Python code in a subprocess.
    """
    if mode == "sandbox":
        ok, err = validate_sandbox(code)
        if not ok:
            return f"❌ Sandbox Violation: {err}"
        return _run_subprocess(code, is_sandbox=True)
    elif mode == "unlocked":
        # Unlocked mode still does a basic safety check to prevent accidental self-deletion
        if "os.remove" in code or "shutil.rmtree" in code or "os.system" in code:
            return "❌ Safety Block: Destructive commands detected in code."
        return _run_subprocess(code, is_sandbox=False)
    else:
        return "❌ Error: Invalid execution mode."

def _run_subprocess(code, is_sandbox=True):
    """
    Handles the actual process execution.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        if is_sandbox:
            # Wrap in a restricted environment
            wrapped_code = f"""
import sys
# Remove dangerous builtins
for b in ('open', 'eval', 'exec', 'compile', '__import__', 'input', 'getattr', 'setattr', 'delattr', 'help'):
    if hasattr(__builtins__, b):
        delattr(__builtins__, b)
if isinstance(__builtins__, dict):
    for b in ('open', 'eval', 'exec', 'compile', '__import__', 'input', 'getattr', 'setattr', 'delattr', 'help'):
        __builtins__.pop(b, None)

try:
{chr(10).join('    ' + line for line in code.splitlines())}
except Exception as e:
    print(f"Runtime Error: {{e}}", file=sys.stderr)
"""
            f.write(wrapped_code)
        else:
            f.write(code)
        tmp_path = f.name

    try:
        env = _clean_env()
        # Run with timeout and capture output
        process = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT,
            env=env,
            cwd=os.getcwd()
        )
        
        output = process.stdout
        if process.stderr:
            output += "\nSTDERR:\n" + process.stderr
            
        if not output.strip():
            if process.returncode == 0:
                output = "(Success: No output)"
            else:
                output = f"(Exit Code {process.returncode})"
                
        return output[:MAX_OUTPUT] + ("..." if len(output) > MAX_OUTPUT else "")
        
    except subprocess.TimeoutExpired:
        return "⏰ Error: Execution Timeout (30s)"
    except Exception as e:
        return f"❌ Execution Error: {e}"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
