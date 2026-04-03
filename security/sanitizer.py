import re


INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?prior\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"new\s+role\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"override\s+(system|your)\s+(prompt|instructions|role)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|your)", re.IGNORECASE),
    re.compile(r"pretend\s+you\s+(are|were)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+)?(are|were)\s+a", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"<\|im_start\|>system", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
]


def sanitize_input(text: str) -> str:
    sanitized = text
    for pattern in INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED]", sanitized)
    return sanitized


def contains_injection(text: str) -> bool:
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def is_command_allowed(command: str, allowed_commands: list[str]) -> bool:
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return False
    base_cmd = cmd_parts[0].split("/")[-1].split("\\")[-1]
    return base_cmd in allowed_commands


def is_destructive(command: str, patterns: list[str]) -> bool:
    cmd_lower = command.lower()
    for pattern in patterns:
        if pattern in cmd_lower:
            return True
    return False


def log_exec(command: str, user_id: int, log_path: str) -> None:
    import datetime
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    line = f"[{timestamp}] user={user_id} cmd={command}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)
