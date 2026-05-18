import os, re
from datetime import datetime

WORKSPACE = "./workspace"
SKILLS_DIR = "./data/skills"
MEMORY_FILE = f"{WORKSPACE}/MEMORY.md"

os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(SKILLS_DIR, exist_ok=True)

class SessionContext:
    def __init__(self, max_turns=20):
        self.turns = []
        self.max_turns = max_turns
    def add(self, role, content):
        self.turns.append({"role":role,"content":content})
        if len(self.turns) > self.max_turns: self.turns.pop(0)
    def get(self): return list(self.turns)
    def clear(self): self.turns = []

class PersistentMemory:
    def read(self):
        if not os.path.exists(MEMORY_FILE): return ""
        return open(MEMORY_FILE).read()
    def append_fact(self, fact):
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        with open(MEMORY_FILE,"a") as f: f.write(f"\n- [{ts}] {fact.strip()}")
    def safe_write(self, new_content):
        original = self.read()
        if not original:
            with open(MEMORY_FILE,"w") as f: f.write(new_content); return True
        if len(new_content.strip()) < max(100, len(original)*0.2):
            print("[MEM] Rejected short write")
            return False
        backup = MEMORY_FILE.replace(".md", f"_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.md")
        with open(backup,"w") as f: f.write(original)
        with open(MEMORY_FILE,"w") as f: f.write(new_content)
        return True
    def search(self, query, limit=5):
        if not os.path.exists(MEMORY_FILE): return []
        keywords = [w.lower() for w in query.split() if len(w)>3]
        hits = []
        for line in open(MEMORY_FILE).readlines():
            score = sum(1 for kw in keywords if kw in line.lower())
            if score: hits.append((score, line.strip()))
        hits.sort(reverse=True)
        return [h[1] for h in hits[:limit]]
    def write_daily_log(self, task, result):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_path = f"./data/memory/{today}.md"
        os.makedirs("./data/memory", exist_ok=True)
        with open(log_path,"a") as f:
            f.write(f"\n## [{datetime.utcnow().strftime('%H:%M')}] Task\n**Goal:** {task[:200]}\n**Result:** {result[:400]}\n")

class SkillLibrary:
    def write(self, task, result, score):
        if score < 0.7: return None
        os.makedirs(SKILLS_DIR, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]", "_", task[:50].lower()).strip("_")
        path = f"{SKILLS_DIR}/{slug}.md"
        content = f"# Skill: {task[:100]}\n\n## When to use\n{task}\n\n## Approach that worked\n{result[:1000]}\n\n## Score\n{score:.2f}\n"
        with open(path,"w") as f: f.write(content)
        return path
    def search(self, query, limit=3):
        if not os.path.exists(SKILLS_DIR): return []
        keywords = [w.lower() for w in query.split() if len(w)>3]
        hits = []
        for fname in os.listdir(SKILLS_DIR):
            if not fname.endswith(".md") or fname.startswith("."): continue
            content = open(f"{SKILLS_DIR}/{fname}").read()
            score = sum(1 for kw in keywords if kw in content.lower())
            if score: hits.append((score, content[:500]))
        hits.sort(reverse=True)
        return [h[1] for h in hits[:limit]]
    def curate(self):
        pass

class HermesMemory:
    def __init__(self):
        self.session = SessionContext()
        self.facts = PersistentMemory()
        self.skills = SkillLibrary()
    def get_context(self, task):
        return {
            "session_turns": self.session.get()[-8:],
            "memory_facts": self.facts.search(task),
            "skills": self.skills.search(task),
            "soul": self._read("SOUL.md"),
            "agents_rules": self._read("AGENTS.md"),
        }
    def after_task(self, task, result, success, score):
        self.session.add("assistant", result[:300])
        if success: self.facts.append_fact(f"Completed: {task[:80]} | Score: {score:.2f}")
        self.facts.write_daily_log(task, result)
        if success: self.skills.write(task, result, score)
    def _read(self, filename):
        path = f"{WORKSPACE}/{filename}"
        return open(path).read()[:2000] if os.path.exists(path) else ""

hermes_memory = HermesMemory()
