import json
import logging
from typing import Any, AsyncGenerator

from providers.base import BaseProvider
from skills.manager import SkillManager

logger = logging.getLogger("opennexus.skills.generator")

SKILL_GEN_PROMPT = (
    "You are a skill generator for OpenNexus, an AI assistant built for developers and "
    "ethical hackers. Based on the following user task, generate a reusable skill JSON "
    "object that will help handle similar tasks more effectively in the future. Output "
    "only valid JSON matching the schema. No markdown, no explanation, just raw JSON.\n"
    "Schema:\n"
    "{\n"
    '  "name": "string",\n'
    '  "description": "string",\n'
    '  "trigger_keywords": ["array", "of", "strings"],\n'
    '  "system_prompt_injection": "string"\n'
    "}\n"
    "Task: {task}"
)

RECURRING_THRESHOLD = 3


class SkillGenerator:
    def __init__(self, skill_manager: SkillManager) -> None:
        self.skill_manager = skill_manager
        self._task_counts: dict[str, int] = {}

    def record_task(self, task_summary: str) -> bool:
        key = task_summary.lower().strip()[:120]
        self._task_counts[key] = self._task_counts.get(key, 0) + 1
        return self._task_counts[key] >= RECURRING_THRESHOLD

    def should_generate(self, user_input: str) -> bool:
        existing = self.skill_manager.match_skills(user_input)
        if existing:
            return False
        task_key = user_input.lower().strip()[:120]
        return self._task_counts.get(task_key, 0) >= RECURRING_THRESHOLD

    async def generate_skill(
        self,
        task: str,
        provider: BaseProvider,
        model: str | None = None,
    ) -> dict[str, Any] | None:
        prompt = SKILL_GEN_PROMPT.format(task=task)
        messages = [{"role": "user", "content": prompt}]

        full_response = ""
        try:
            gen: AsyncGenerator[str, None] = provider.complete(
                messages=messages,
                model=model,
                system=None,
                stream=False,
            )
            async for chunk in gen:
                full_response += chunk
        except Exception as e:
            logger.error("Skill generation failed: %s", e)
            return None

        full_response = full_response.strip()
        if full_response.startswith("```"):
            lines = full_response.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            full_response = "\n".join(lines)

        try:
            skill_data = json.loads(full_response)
        except json.JSONDecodeError:
            logger.error("Skill generation returned invalid JSON: %s", full_response[:200])
            return None

        required_keys = {"name", "description", "trigger_keywords", "system_prompt_injection"}
        if not required_keys.issubset(skill_data.keys()):
            logger.error("Skill JSON missing required keys: %s", skill_data.keys())
            return None

        skill = SkillManager.create_skill_template(
            name=skill_data["name"],
            description=skill_data["description"],
            keywords=skill_data["trigger_keywords"],
            injection=skill_data["system_prompt_injection"],
        )
        self.skill_manager.save_skill(skill)
        logger.info("Auto-generated skill: %s (%s)", skill["name"], skill["id"])
        return skill
