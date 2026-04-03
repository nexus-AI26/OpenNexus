import re
from pathlib import Path

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:sk|pk)-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
    re.compile(r"xox[bpsar]-[0-9a-zA-Z-]{10,}"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
]


def scan_directory(directory: Path, config_filename: str = "config.toml") -> list[str]:
    warnings: list[str] = []
    if not directory.exists():
        return warnings

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name == config_filename:
            continue
        if file_path.suffix in (".json", ".toml", ".yaml", ".yml", ".env", ".txt", ".md", ".log"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue
            for pattern in SECRET_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    warnings.append(
                        f"Potential secret found in {file_path}: "
                        f"pattern '{pattern.pattern}' matched {len(matches)} time(s)"
                    )
    return warnings


def check_hardcoded_keys(source_dir: Path) -> list[str]:
    warnings: list[str] = []
    key_patterns = [
        re.compile(r'api_key\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']'),
        re.compile(r'token\s*=\s*["\'][a-zA-Z0-9_:-]{20,}["\']'),
    ]
    for py_file in source_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for pattern in key_patterns:
            matches = pattern.findall(content)
            if matches:
                warnings.append(
                    f"Possible hardcoded key in {py_file}: "
                    f"{len(matches)} suspicious assignment(s)"
                )
    return warnings
