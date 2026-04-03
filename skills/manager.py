import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SkillManager:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        self._skills.clear()
        for path in self.skills_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                skill_id = data.get("id", path.stem)
                self._skills[skill_id] = data
            except (json.JSONDecodeError, OSError):
                continue

    def reload(self) -> None:
        self._load_all()

    def list_skills(self) -> list[dict[str, Any]]:
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        return self._skills.get(skill_id)

    def delete_skill(self, skill_id: str) -> bool:
        if skill_id not in self._skills:
            return False
        file_path = self.skills_dir / f"{skill_id}.json"
        if file_path.exists():
            file_path.unlink()
        del self._skills[skill_id]
        return True

    def save_skill(self, skill: dict[str, Any]) -> str:
        skill_id = skill.get("id") or str(uuid.uuid4())
        skill["id"] = skill_id
        file_path = self.skills_dir / f"{skill_id}.json"
        file_path.write_text(
            json.dumps(skill, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._skills[skill_id] = skill
        return skill_id

    def match_skills(self, user_input: str) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        input_lower = user_input.lower()
        for skill in self._skills.values():
            keywords = skill.get("trigger_keywords", [])
            for keyword in keywords:
                if keyword.lower() in input_lower:
                    skill["use_count"] = skill.get("use_count", 0) + 1
                    self.save_skill(skill)
                    matched.append(skill)
                    break
        return matched

    def build_skill_injection(self, user_input: str) -> str:
        matched = self.match_skills(user_input)
        if not matched:
            return ""
        injections = [
            s.get("system_prompt_injection", "") for s in matched if s.get("system_prompt_injection")
        ]
        if not injections:
            return ""
        return "\n\n---\n[Auto-loaded skills]\n" + "\n\n".join(injections)

    @staticmethod
    def create_skill_template(
        name: str,
        description: str,
        keywords: list[str],
        injection: str,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "trigger_keywords": keywords,
            "system_prompt_injection": injection,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "auto-generated",
            "use_count": 0,
        }
