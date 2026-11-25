import json
from pathlib import Path

PROJECTS_FILE = Path("projects.json")

class ProjectManager:
    """Mengelola pemetaan nama project ke project ID / URL Flow."""
    def __init__(self, filepath: Path = PROJECTS_FILE):
        self.filepath = filepath
        self.projects = self._load()

    def _load(self) -> dict:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.projects, f, indent=2, ensure_ascii=False)

    def register_project(self, project_id: str, name: str, account_id: str = ""):
        self.projects[name] = {
            "id": project_id,
            "name": name,
            "account_id": account_id
        }
        self._save()

    def get_project(self, name: str) -> dict | None:
        return self.projects.get(name)

    def list_projects(self) -> dict:
        return self.projects
