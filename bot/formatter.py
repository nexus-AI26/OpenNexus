import re

MARKDOWN_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!\\"


def escape_md2(text: str) -> str:
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


def format_response(text: str) -> str:
    lines = text.split("\n")
    result: list[str] = []
    in_code_block = False

    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        formatted = _format_inline(line)
        result.append(formatted)

    return "\n".join(result)


def _format_inline(line: str) -> str:
    parts: list[str] = []
    i = 0
    text = line

    while i < len(text):
        if text[i] == "`" and i + 1 < len(text):
            end = text.find("`", i + 1)
            if end != -1:
                parts.append("`" + text[i + 1 : end] + "`")
                i = end + 1
                continue

        if text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                inner = escape_md2(text[i + 2 : end])
                parts.append(f"*{inner}*")
                i = end + 2
                continue

        parts.append(escape_md2(text[i]))
        i += 1

    return "".join(parts)


def split_message(text: str, max_len: int = 4096) -> list[str]:
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    lines = text.split("\n")
    current: list[str] = []
    current_len = 0
    in_code_block = False
    code_block_header = ""

    for line in lines:
        line_len = len(line) + 1

        if line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_block_header = line
            else:
                in_code_block = False

        if current_len + line_len > max_len:
            if in_code_block and not line.startswith("```"):
                current.append("```")
                chunks.append("\n".join(current))
                current = [code_block_header, line]
                current_len = len(code_block_header) + 1 + line_len
            else:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks
