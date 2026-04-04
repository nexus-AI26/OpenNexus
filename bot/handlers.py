import asyncio
import io
import json
import logging
import time
import re
from dataclasses import dataclass, field
from typing import Any

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, SKILLS_DIR, LOGS_DIR, augment_system_prompt
from bot.formatter import format_response, split_message
from bot.middleware import create_access_checker, create_sanitize_middleware
from providers import get_provider
from providers.base import BaseProvider
from skills.manager import SkillManager
from skills.generator import SkillGenerator
from security.sanitizer import is_command_allowed, is_destructive, log_exec
from tools.search import web_search

logger = logging.getLogger("opennexus.bot.handlers")

user_contexts: dict[int, list[dict[str, str]]] = {}
user_providers: dict[int, tuple[str, str]] = {}
user_system_prompts: dict[int, str] = {}
user_raw_mode: dict[int, bool] = {}
user_websearch_enabled: dict[int, bool] = {}


@dataclass
class GenerationControl:
    stop_requested: bool = False
    pending_notes: list[str] = field(default_factory=list)


user_gen_control: dict[int, GenerationControl] = {}

_config: Config | None = None
_skill_manager: SkillManager | None = None
_skill_generator: SkillGenerator | None = None

SUPPORTED_FILE_EXTENSIONS = {".txt", ".py", ".sh", ".md", ".json", ".log"}


def _get_config() -> Config:
    assert _config is not None
    return _config


def _get_provider_for_user(user_id: int) -> tuple[BaseProvider, str]:
    config = _get_config()
    if user_id in user_providers:
        prov_name, model = user_providers[user_id]
    else:
        prov_name = config.default_provider
        model = config.providers.get(prov_name, {}).get("default_model", "")

    provider_cfg = config.providers.get(prov_name, {})
    provider = get_provider(prov_name, provider_cfg)
    return provider, model


def _get_system_prompt(user_id: int) -> str:
    config = _get_config()
    return user_system_prompts.get(user_id, config.system_prompt)


def _get_gen_control(user_id: int) -> GenerationControl:
    if user_id not in user_gen_control:
        user_gen_control[user_id] = GenerationControl()
    return user_gen_control[user_id]


def request_generation_stop(user_id: int) -> None:
    _get_gen_control(user_id).stop_requested = True


def enqueue_generation_note(user_id: int, note: str) -> None:
    n = (note or "").strip()
    if n:
        _get_gen_control(user_id).pending_notes.append(n)


async def _check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    checker = create_access_checker(_get_config())
    return await checker(update, context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    text = (
        "🔷 *OpenNexus* — AI assistant for developers and ethical hackers\\.\n\n"
        "Available commands:\n"
        "/clear — Clear conversation context\n"
        "/model <provider> <model> — Switch AI model\n"
        "/skills — List auto\\-generated skills\n"
        "/skill show <id> — Show skill details\n"
        "/skill delete <id> — Delete a skill\n"
        "/export — Export conversation as Markdown\n"
        "/system — Show current system prompt\n"
        "/system set <text> — Override system prompt\n"
        "/tokens — Approximate token count\n"
        "/raw — Toggle raw API response mode\n"
        "/stop — Stop the current reply while it is generating\n"
        "/wait <text> — Send a note during generation \\(continues the reply\\)\n"
        "/help — Full command reference"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="MarkdownV2")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    user_contexts.pop(user_id, None)
    if update.message:
        await update.message.reply_text("Conversation cleared.")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    args = context.args or []

    if len(args) < 2:
        config = _get_config()
        current = user_providers.get(user_id, (config.default_provider, ""))
        if update.message:
            await update.message.reply_text(
                f"Current: {current[0]} / {current[1]}\n"
                f"Usage: /model <provider> <model>\n"
                f"Providers: anthropic, openai, openrouter, groq, ollama, custom"
            )
        return

    provider_name = args[0].lower()
    model_name = args[1]

    valid_providers = {"anthropic", "openai", "openrouter", "groq", "ollama", "custom"}
    if provider_name not in valid_providers:
        if update.message:
            await update.message.reply_text(
                f"Unknown provider: {provider_name}\n"
                f"Available: {', '.join(sorted(valid_providers))}"
            )
        return

    user_providers[user_id] = (provider_name, model_name)
    if update.message:
        await update.message.reply_text(f"Switched to {provider_name} / {model_name}")


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    assert _skill_manager is not None
    skills = _skill_manager.list_skills()
    if not skills:
        if update.message:
            await update.message.reply_text("No skills stored yet.")
        return

    lines = ["📚 *Skills:*\n"]
    for s in skills:
        lines.append(f"• `{s['id'][:8]}` — {s['name']} (used {s.get('use_count', 0)}x)")

    if update.message:
        await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_skill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    assert _skill_manager is not None
    args = context.args or []

    if len(args) < 2:
        if update.message:
            await update.message.reply_text("Usage: /skill show <id> or /skill delete <id>")
        return

    action = args[0].lower()
    skill_id_prefix = args[1]

    all_skills = _skill_manager.list_skills()
    matched_skill = None
    for s in all_skills:
        if s["id"].startswith(skill_id_prefix):
            matched_skill = s
            break

    if not matched_skill:
        if update.message:
            await update.message.reply_text(f"No skill found matching ID prefix: {skill_id_prefix}")
        return

    if action == "show":
        text = f"```json\n{json.dumps(matched_skill, indent=2)}\n```"
        if update.message:
            await update.message.reply_text(text, parse_mode="MarkdownV2")
    elif action == "delete":
        _skill_manager.delete_skill(matched_skill["id"])
        if update.message:
            await update.message.reply_text(f"Deleted skill: {matched_skill['name']}")
    else:
        if update.message:
            await update.message.reply_text("Usage: /skill show <id> or /skill delete <id>")


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    history = user_contexts.get(user_id, [])

    if not history:
        if update.message:
            await update.message.reply_text("No conversation to export.")
        return

    md_lines = ["# OpenNexus Conversation Export\n"]
    for msg in history:
        role = msg["role"].upper()
        content = msg["content"]
        md_lines.append(f"## {role}\n\n{content}\n")

    content_str = "\n".join(md_lines)
    buf = io.BytesIO(content_str.encode("utf-8"))
    buf.name = "conversation.md"

    if update.message:
        await update.message.reply_document(document=buf, filename="conversation.md")


async def cmd_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    args = context.args or []

    if not args:
        prompt = _get_system_prompt(user_id)
        if update.message:
            await update.message.reply_text(f"Current system prompt:\n\n{prompt}")
        return

    if args[0].lower() == "set" and len(args) > 1:
        text = update.message.text if update.message else ""
        new_prompt = text.split("/system set ", 1)[-1].strip()
        user_system_prompts[user_id] = augment_system_prompt(new_prompt)
        if update.message:
            await update.message.reply_text("System prompt updated for this session.")
    else:
        prompt = _get_system_prompt(user_id)
        if update.message:
            await update.message.reply_text(f"Current system prompt:\n\n{prompt}")


async def cmd_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    history = user_contexts.get(user_id, [])
    total_chars = sum(len(m["content"]) for m in history)
    approx_tokens = total_chars // 4
    if update.message:
        await update.message.reply_text(
            f"Context: {len(history)} messages, ~{total_chars} chars, ~{approx_tokens} tokens"
        )


async def cmd_raw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    current = user_raw_mode.get(user_id, False)
    user_raw_mode[user_id] = not current
    state = "ON" if not current else "OFF"
    if update.message:
        await update.message.reply_text(f"Raw mode: {state}")


async def cmd_websearch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    args = context.args or []
    if not args:
        state = "ON" if user_websearch_enabled.get(user_id, True) else "OFF"
        if update.message:
            await update.message.reply_text(f"Auto-websearch is currently {state}.")
        return

    val = args[0].lower()
    if val in ("on", "true", "yes"):
        user_websearch_enabled[user_id] = True
    elif val in ("off", "false", "no"):
        user_websearch_enabled[user_id] = False

    state = "ON" if user_websearch_enabled.get(user_id, True) else "OFF"
    if update.message:
        await update.message.reply_text(f"Auto-websearch is now {state}.")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    query = " ".join(context.args or [])
    if not query:
        if update.message:
            await update.message.reply_text("Usage: /search <query>")
        return

    if update.message:
        msg = await update.message.reply_text(f"Searching web for '{query}'...")
        results = await web_search(query)
        if not results:
            await msg.edit_text("No results found.")
            return

        lines = []
        for i, r in enumerate(results, 1):
            title = r['title'].replace("`", "")
            url = r['url'].replace("`", "")
            snippet = r['snippet'].replace("`", "")
            lines.append(f"{i}. {title} | {url}\n{snippet}")
        text = "```\n" + "\n\n".join(lines) + "\n```"
        await msg.edit_text(text, parse_mode="MarkdownV2")


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    config = _get_config()
    user_id = update.effective_user.id
    if user_id != config.owner_id:
        if update.message:
            await update.message.reply_text("Access denied. Owner only.")
        return

    command = " ".join(context.args or [])
    if not command:
        if update.message:
            await update.message.reply_text("Usage: /run <shell command>")
        return

    await _execute_shell_and_reply(update, command)


async def _execute_shell_and_reply(update: Update, command: str, bypass_allowlist: bool = False) -> str:
    config = _get_config()
    user_id = update.effective_user.id 
    if not bypass_allowlist and not is_command_allowed(command, config.allowed_commands):
        if update.message:
            await update.message.reply_text("Command not in allowlist.")
        return ""
    if is_destructive(command, config.destructive_patterns):
        if update.message:
            await update.message.reply_text("Destructive command pattern detected and blocked.")
        return ""

    log_exec(command, user_id, str(LOGS_DIR / "exec.log"))

    msg = None
    if update.message:
        msg = await update.message.reply_text("⚙️ Executing...")

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

        out = stdout.decode('utf-8', errors='replace').strip()
        err = stderr.decode('utf-8', errors='replace').strip()
        result = ""
        if out: result += out + "\n"
        if err: result += err + "\n"
        if not result: result = "(no output)"

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        result = "Command timed out after 10 seconds."
    except Exception as e:
        result = f"Error executing command: {e}"

    if msg:
        try:
            res_md = result.replace("`", "'")[:3900]
            await msg.edit_text(f"```text\n$ {command}\n{res_md}\n```", parse_mode="MarkdownV2")
        except Exception:
            pass

    return result


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    config = _get_config()
    user_id = update.effective_user.id 
    if user_id != config.owner_id:
        if update.message:
            await update.message.reply_text("Owner only.")
        return

    args = context.args or []
    if not args:
        if update.message:
            await update.message.reply_text("Usage: /adduser <telegram_id>")
        return

    try:
        new_id = int(args[0])
    except ValueError:
        if update.message:
            await update.message.reply_text("Invalid ID. Must be numeric.")
        return

    if new_id not in config.allowed_users:
        config.allowed_users.append(new_id)
        config.save_whitelist()

    if update.message:
        await update.message.reply_text(f"User {new_id} added to whitelist.")


async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    config = _get_config()
    user_id = update.effective_user.id 
    if user_id != config.owner_id:
        if update.message:
            await update.message.reply_text("Owner only.")
        return

    args = context.args or []
    if not args:
        if update.message:
            await update.message.reply_text("Usage: /removeuser <telegram_id>")
        return

    try:
        rm_id = int(args[0])
    except ValueError:
        if update.message:
            await update.message.reply_text("Invalid ID. Must be numeric.")
        return

    if rm_id == config.owner_id:
        if update.message:
            await update.message.reply_text("Cannot remove the owner.")
        return

    if rm_id in config.allowed_users:
        config.allowed_users.remove(rm_id)
        config.save_whitelist()

    if update.message:
        await update.message.reply_text(f"User {rm_id} removed from whitelist.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    user_id = update.effective_user.id
    _get_gen_control(user_id).stop_requested = True
    if update.message:
        await update.message.reply_text("Stopping current reply…")


async def cmd_wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    args = context.args or []
    note = " ".join(args).strip()
    if not note:
        if update.message:
            await update.message.reply_text(
                "Usage: /wait <message>\n"
                "Sends a note while the bot is generating; it will continue and use your guidance."
            )
        return
    user_id = update.effective_user.id
    _get_gen_control(user_id).pending_notes.append(note)
    if update.message:
        await update.message.reply_text("Noted — I'll work that into the rest of the reply.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    text = (
        "🔷 *OpenNexus Command Reference*\n\n"
        "`/start` — Greeting and command list\n"
        "`/clear` — Clear conversation context\n"
        "`/model <provider> <model>` — Switch AI provider and model\n"
        "`/skills` — List all locally stored skills\n"
        "`/skill show <id>` — Show a skill's full JSON\n"
        "`/skill delete <id>` — Delete a skill\n"
        "`/export` — Export conversation as \\.md file\n"
        "`/system` — Show current system prompt\n"
        "`/system set <text>` — Override system prompt\n"
        "`/tokens` — Show approximate token count\n"
        "`/raw` — Toggle raw API response mode\n"
        "`/stop` — Stop the current reply mid\\-generation\n"
        "`/wait <text>` — Note during generation; bot continues with your guidance\n"
        "`/adduser <id>` — Owner: add user to whitelist\n"
        "`/removeuser <id>` — Owner: remove user from whitelist\n"
        "`/help` — This message"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="MarkdownV2")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return

    if not update.message or not update.message.document:
        return

    doc = update.message.document
    file_name = doc.file_name or "unknown"
    ext = "." + file_name.rsplit(".", 1)[-1] if "." in file_name else ""

    if ext not in SUPPORTED_FILE_EXTENSIONS:
        await update.message.reply_text(
            f"Unsupported file type: {ext}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_FILE_EXTENSIONS))}"
        )
        return

    file = await doc.get_file()
    data = await file.download_as_bytearray()
    text_content = data.decode("utf-8", errors="replace")

    user_id = update.effective_user.id
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    user_contexts[user_id].append({
        "role": "user",
        "content": f"[File uploaded: {file_name}]\n\n{text_content}",
    })

    caption = update.message.caption
    if caption:
        sanitizer = create_sanitize_middleware(_get_config())
        sanitized = await sanitizer(update, context)
        await _process_message(update, context, sanitized or caption)
    else:
        await update.message.reply_text(f"Ingested `{file_name}` ({len(text_content)} chars) into context.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check(update, context):
        return
    if not update.message or not update.message.text:
        return

    sanitizer = create_sanitize_middleware(_get_config())
    sanitized = await sanitizer(update, context)
    if sanitized is None:
        return

    await _process_message(update, context, sanitized)


async def _process_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> None:
    assert _skill_manager is not None
    assert _skill_generator is not None
    user_id = update.effective_user.id 
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    if not any(m["content"] == text and m["role"] == "user" for m in user_contexts[user_id][-1:]):
        user_contexts[user_id].append({"role": "user", "content": text})

    ctrl = _get_gen_control(user_id)
    ctrl.stop_requested = False
    while ctrl.pending_notes:
        note = ctrl.pending_notes.pop(0)
        user_contexts[user_id].append({
            "role": "system",
            "content": "[User note:]\n" + note,
        })

    base_prompt = _get_system_prompt(user_id)
    system_prompt = (
        base_prompt +
        "\n\nIf you need to execute a shell command to fulfill the request, output exactly `<execute>the command</execute>`. "
        "Wait for the system result before continuing. DO NOT hallucinate command outputs."
    )

    skill_injection = _skill_manager.build_skill_injection(text, system_prompt)
    if skill_injection:
        system_prompt += skill_injection

    provider, model = _get_provider_for_user(user_id)

    assert update.message is not None

    max_turns = 5
    for turn in range(max_turns):
        await context.bot.send_chat_action(
            chat_id=update.message.chat_id,
            action=constants.ChatAction.TYPING,
        )

        try:
            sent_message = None
            last_edit_time = 0.0
            chunk_count = 0
            typing_refresh = 0
            turn_segments: list[str] = []
            stopped = False

            while True:
                current_stream = ""
                chunk_count = 0
                typing_refresh = 0
                restart_stream = False

                async for chunk in provider.complete(
                    messages=user_contexts[user_id],
                    model=model,
                    system=system_prompt,
                    stream=True,
                ):
                    current_stream += chunk
                    chunk_count += 1
                    typing_refresh += 1

                    if ctrl.stop_requested:
                        ctrl.stop_requested = False
                        stopped = True
                        break

                    if ctrl.pending_notes:
                        if current_stream.strip():
                            user_contexts[user_id].append({
                                "role": "assistant",
                                "content": current_stream,
                            })
                            turn_segments.append(current_stream)
                        while ctrl.pending_notes:
                            note = ctrl.pending_notes.pop(0)
                            user_contexts[user_id].append({
                                "role": "system",
                                "content": (
                                    "[User interjection while you were replying — continue and apply this:]\n"
                                    + note
                                ),
                            })
                        restart_stream = True
                        break

                    if typing_refresh >= 18:
                        typing_refresh = 0
                        try:
                            await context.bot.send_chat_action(
                                chat_id=update.message.chat_id,
                                action=constants.ChatAction.TYPING,
                            )
                        except Exception:
                            pass

                    now = time.time()
                    display_text = "".join(turn_segments) + current_stream

                    if sent_message is None and display_text.strip():
                        try:
                            sent_message = await update.message.reply_text(display_text)
                            last_edit_time = now
                        except Exception:
                            pass
                        continue

                    should_update = (
                        sent_message is not None
                        and display_text.strip()
                        and ((now - last_edit_time >= 0.07) or (chunk_count >= 3))
                    )

                    if should_update:
                        try:
                            await sent_message.edit_text(display_text)
                            last_edit_time = now
                            chunk_count = 0
                        except Exception:
                            pass

                if stopped:
                    agg = "".join(turn_segments) + current_stream
                    if current_stream.strip():
                        user_contexts[user_id].append({
                            "role": "assistant",
                            "content": current_stream + "\n\n[Generation stopped by user.]",
                        })
                    elif turn_segments:
                        user_contexts[user_id].append({
                            "role": "system",
                            "content": "[User stopped generation.]",
                        })
                    tail = "(Stopped by user.)"
                    show = (agg + "\n\n" + tail) if agg.strip() else tail
                    chunks = split_message(show)
                    if sent_message:
                        try:
                            await sent_message.edit_text(chunks[0])
                        except Exception:
                            pass
                    else:
                        sent_message = await update.message.reply_text(chunks[0])
                    for extra in chunks[1:]:
                        await update.message.reply_text(extra)
                    break

                if restart_stream:
                    continue

                if current_stream.strip():
                    user_contexts[user_id].append({
                        "role": "assistant",
                        "content": current_stream,
                    })
                    turn_segments.append(current_stream)

                display_text = "".join(turn_segments)
                if display_text.strip():
                    chunks = split_message(display_text)
                    if sent_message:
                        try:
                            await sent_message.edit_text(chunks[0])
                        except Exception:
                            pass
                    else:
                        sent_message = await update.message.reply_text(chunks[0])
                    for extra in chunks[1:]:
                        await update.message.reply_text(extra)
                else:
                    if sent_message:
                        await sent_message.edit_text("(empty response)")
                    else:
                        await update.message.reply_text("(empty response)")

                break

            if stopped:
                break

            full_response = "".join(turn_segments)
            match = re.search(r'<execute>(.*?)</execute>', full_response, re.DOTALL)
            if match and user_id == _get_config().owner_id:
                cmd = match.group(1).strip()
                await update.message.reply_text(f"🛠 *Executing:* `{cmd}`", parse_mode="MarkdownV2")

                output = await _execute_shell_and_reply(update, cmd, bypass_allowlist=True)
                sys_msg = f"[SYSTEM COMMAND EXECUTION RESULT: {cmd}]\n{output}"
                user_contexts[user_id].append({"role": "system", "content": sys_msg})

                if not output:
                    await update.message.reply_text("_Command produced no output_", parse_mode="MarkdownV2")
            else:
                break

        except Exception as e:
            error_msg = f"Error ({provider.name}): {e}"
            logger.error(error_msg)
            if update.message:
                await update.message.reply_text(error_msg)
            break

    _skill_generator.record_task(text)
    if _skill_generator.should_generate(text):
        skill = await _skill_generator.generate_skill(text, provider, model)
        if skill:
            await update.message.reply_text(
                f"🧠 Auto-generated skill: *{skill['name']}*",
                parse_mode="MarkdownV2",
            )


def setup_bot(config: Config) -> Application:
    global _config, _skill_manager, _skill_generator
    _config = config
    _skill_manager = SkillManager(SKILLS_DIR)
    _skill_generator = SkillGenerator(_skill_manager)

    app = Application.builder().token(config.bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("skill", cmd_skill))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("websearch", cmd_websearch))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("system", cmd_system))
    app.add_handler(CommandHandler("tokens", cmd_tokens))
    app.add_handler(CommandHandler("raw", cmd_raw))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("wait", cmd_wait))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("removeuser", cmd_removeuser))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
