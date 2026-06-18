"""ALTEREGO OS — Planner.

Decomposes a mission into a flat list of tasks (V1: no DAG, just ordered steps).
V2 will produce a real DAG with dependencies.

The Planner uses the LLM plugin to break down the objective, given the list
of available capabilities from the CapabilityRegistry.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel

from alterego.kernel.base import Mission
from alterego.kernel.capability_registry import CapabilityRegistry


class Task(BaseModel):
    """A single step in a mission plan."""
    step: int
    description: str
    capability: str  # e.g. "github", "llm.chat"
    method: str = ""  # e.g. "clone", "chat"
    params: dict[str, Any] = {}


class Planner:
    """Plans missions by decomposing objectives into tasks.

    V1.1 strategy:
      1. Ask the LLM to produce a JSON plan using the available capabilities.
      2. Strict JSON parsing with markdown fence stripping.
      3. Fallback to single llm.chat task if LLM fails or produces invalid JSON.
    """

    PLANNER_PROMPT = """You are a JSON-only task planner. You decompose user requests into executable task sequences. You NEVER explain, NEVER use markdown, NEVER write prose. You output ONLY a JSON object.

Available capabilities and their methods:
{capabilities}

Method reference:
- filesystem: read(path), write(path, content), append(path, content), list(path), glob(pattern, path), exists(path), mkdir(path), copy(src, dest), move(src, dest), delete(path), info(path)
- llm.chat: chat(user, system)
- github: clone(repo, dest), list_repos(owner, limit), get_repo_info(repo), create_issue(repo, title, body), create_pull_request(repo, title, head, base, body), list_commits(repo, limit)
- docker: ps(all), logs(container, tail), restart(container), stop(container), start(container), build(path, tag), exec(container, cmd), stats(container)
- ssh: exec(host, user, command, port, key_path), scp_put(host, user, local, remote), scp_get(host, user, remote, local), health_check(host, user, port, key_path)
- browser: open(url), click(selector), fill(selector, value), screenshot(path, full_page), scrape(selector), evaluate(script)
- database.sql: query(sql, args), execute(sql, args)
- database.nosql: find(collection, filter, limit), find_one(collection, filter), insert(collection, document), update(collection, filter, set), delete(collection, filter), count(collection, filter)
- email: send(to, subject, body, html)
- telegram: send_message(chat_id, text, parse_mode), send_document(chat_id, document_path)

You MUST respond with ONLY this JSON structure and nothing else:
{{"tasks":[{{"step":1,"description":"short description","capability":"capability_name","method":"method_name","params":{{"key":"value"}}}}]}}

Rules:
- ONLY output JSON. No text before or after. No markdown fences.
- Use ONLY the capabilities listed above.
- Use concrete parameter values (no placeholders).
- Maximum 5 tasks.
- For simple greetings/questions: ONE task with capability="llm.chat", method="chat".
- For file operations: use "filesystem" capability with concrete paths.
- End with an llm.chat task to respond to the user."""

    # Suffix appended to the user message to force JSON output
    JSON_SUFFIX = """

Respond with ONLY the JSON task plan. No explanation. No markdown. Start with { and end with }."""

    def __init__(self, capability_registry: CapabilityRegistry, llm_plugin: Any) -> None:
        self.capability_registry = capability_registry
        self.llm_plugin = llm_plugin

    async def plan(self, mission: Mission) -> list[Task]:
        """Produce a list of tasks for the given mission."""
        caps_description = self.capability_registry.describe() or "(no capabilities registered)"
        prompt = self.PLANNER_PROMPT.format(capabilities=caps_description)
        user_msg = mission.objective + self.JSON_SUFFIX

        logger.info(f"planning mission {mission.id}: {mission.objective[:80]}")

        # Use LLM plugin to produce the plan
        try:
            raw = await self.llm_plugin.call("chat", {
                "system": prompt,
                "user": user_msg,
                "temperature": 0.1,  # very low temperature for structured output
            })
        except Exception as e:
            logger.error(f"planner LLM call failed: {e}")
            return self._fallback(mission.objective)

        # Parse the JSON plan
        plan = self._parse_plan(raw)
        if not plan:
            logger.warning("planner produced empty/invalid plan; fallback to direct LLM")
            return self._fallback(mission.objective)

        return plan

    def _fallback(self, objective: str) -> list[Task]:
        """Fallback: single LLM task that answers directly."""
        return [Task(
            step=1,
            description="Answer the user directly",
            capability="llm.chat",
            method="chat",
            params={"system": "You are ALTEREGO, a digital brain and personal assistant. Be helpful and concise.", "user": objective},
        )]

    def _parse_plan(self, raw: Any) -> Optional[list[Task]]:
        """Parse the LLM output into a list of Task. Returns None on failure.

        Handles multiple response formats:
        - {"content": '{"tasks": [...]}'}  (LLM plugin wraps in content)
        - {"content": "```json\\n{...}\\n```"}  (markdown-fenced JSON)
        - {"tasks": [...]}                 (direct dict)
        - '{"tasks": [...]}'               (raw JSON string)
        - '```json\\n{...}\\n```'           (markdown-fenced string)
        """
        # Step 1: Extract content string from possible wrapper
        content_str: Optional[str] = None
        tasks_data: Optional[list] = None

        if isinstance(raw, dict):
            if "tasks" in raw:
                tasks_data = raw["tasks"]
            elif "content" in raw:
                content = raw["content"]
                if isinstance(content, str):
                    content_str = content
                elif isinstance(content, dict) and "tasks" in content:
                    tasks_data = content["tasks"]
                else:
                    return None
            else:
                return None
        elif isinstance(raw, str):
            content_str = raw
        else:
            return None

        # Step 2: If we have a string, strip markdown fences and parse JSON
        if content_str is not None and tasks_data is None:
            # Strip markdown code fences (```json ... ``` or ``` ... ```)
            content_str = content_str.strip()
            fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
            fence_match = re.search(fence_pattern, content_str, re.DOTALL)
            if fence_match:
                content_str = fence_match.group(1).strip()

            # Try direct JSON parse
            try:
                parsed = json.loads(content_str)
                tasks_data = parsed.get("tasks", [])
            except json.JSONDecodeError:
                # Try to extract JSON object from the string
                start = content_str.find("{")
                end = content_str.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(content_str[start:end])
                        tasks_data = parsed.get("tasks", [])
                    except json.JSONDecodeError:
                        # Last resort: try to find "tasks" array directly
                        try:
                            tasks_match = re.search(r'"tasks"\s*:\s*\[', content_str)
                            if tasks_match:
                                arr_start = tasks_match.end() - 1
                                # Find matching closing bracket
                                depth = 0
                                for i in range(arr_start, len(content_str)):
                                    if content_str[i] == '[':
                                        depth += 1
                                    elif content_str[i] == ']':
                                        depth -= 1
                                        if depth == 0:
                                            tasks_json = content_str[arr_start:i+1]
                                            tasks_data = json.loads(tasks_json)
                                            break
                        except (json.JSONDecodeError, Exception):
                            return None
                        if tasks_data is None:
                            return None
                else:
                    return None

        if not tasks_data:
            return None

        # Step 3: Convert to Task objects
        tasks = []
        for i, t in enumerate(tasks_data, start=1):
            try:
                if not isinstance(t, dict):
                    continue
                tasks.append(Task(
                    step=t.get("step", i),
                    description=t.get("description", ""),
                    capability=t.get("capability", "llm.chat"),
                    method=t.get("method", ""),
                    params=t.get("params", {}),
                ))
            except Exception as e:
                logger.warning(f"failed to parse task {i}: {e}")
        return tasks if tasks else None
