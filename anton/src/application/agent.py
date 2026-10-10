import copy
import json
import logging
from dataclasses import dataclass
from typing import Any

from domain.diagnosis import Diagnosis
from domain.enums import ConfidenceLevel, DiagnosisStatus, RiskLevel
from hive_common.logging import log_payload
from infrastructure.config import Settings
from integrations.github import GitHubApp
from integrations.prometheus import query_prometheus
from integrations.prompts import PromptStore
from integrations.shell import run_shell
from openai import OpenAI
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def _diagnosis_text_format() -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "diagnosis",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "status": {"type": "string", "enum": [status.value for status in DiagnosisStatus]},
                    "incident": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "confidence": {"type": "string", "enum": [level.value for level in ConfidenceLevel]},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "proposed_files": {"type": "array", "items": {"type": "string"}},
                    "risk": {"type": "string", "enum": [level.value for level in RiskLevel]},
                    "validation": {"type": "array", "items": {"type": "string"}},
                    "rollback": {"type": "string"},
                    "post_merge_checks": {"type": "array", "items": {"type": "string"}},
                    "proposed_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "file_path": {"type": "string"},
                                "content": {"type": "string"},
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                            },
                            "required": ["file_path", "content", "title", "body"],
                        },
                    },
                    "manual_actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string"},
                                "command": {"type": "string"},
                                "reason": {"type": "string"},
                                "validation": {"type": "string"},
                            },
                            "required": ["title", "command", "reason", "validation"],
                        },
                    },
                },
                "required": [
                    "status",
                    "incident",
                    "hypothesis",
                    "confidence",
                    "evidence",
                    "proposed_files",
                    "risk",
                    "validation",
                    "rollback",
                    "post_merge_checks",
                    "proposed_changes",
                    "manual_actions",
                ],
            },
        }
    }


@dataclass
class AgentSession:
    client: OpenAI
    base_response_id: str
    tools: list[dict[str, Any]]

    def close(self) -> None:
        self.client.close()


def boot(settings: Settings, system_prompt: str) -> AgentSession:
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.llm_base_url, max_retries=0)
    tools = copy.deepcopy(settings.llm_tools)
    response = client.responses.create(
        model=settings.llm_model,
        input=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": "Runtime initialized. Wait for an alert investigation request."},
        ],
        tools=tools,
        prompt_cache_key=settings.prompt_cache_key,
        store=True,
    )
    return AgentSession(client=client, base_response_id=response.id, tools=tools)


def _dispatch(settings: Settings, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "run_shell":
        return run_shell(
            **arguments,
            cwd=str(settings.repo_path),
            allowed_binaries=settings.shell_allowed_binaries,
            denied_patterns=settings.shell_denied_patterns,
        )
    if name == "query_prometheus":
        return query_prometheus(settings.prometheus_url, **arguments)
    if name == "github_read":
        github = GitHubApp(settings)
        try:
            return github.read(**arguments)
        finally:
            github.close()
    raise ValueError(f"Unknown client-side tool: {name}")


def diagnose(
    settings: Settings,
    question: str,
    prompt_store: PromptStore,
    session: AgentSession,
    alert_id: str = "unknown",
    replay_prompt: str | None = None,
) -> Diagnosis:
    action_prompt = prompt_store.action("investigate")
    if replay_prompt:
        action_prompt = (
            f"{action_prompt}\n\n{prompt_store.action('replay').replace('{{operator_prompt}}', replay_prompt)}"
        )
    prompt = f"Question: {question}\n\n" + action_prompt
    logger.info("agent.step input alert_id=%s step=llm_prompt input=%s", alert_id, log_payload(prompt))
    response = session.client.responses.create(
        model=settings.llm_model,
        previous_response_id=session.base_response_id,
        input=prompt,
        tools=session.tools,
        text=_diagnosis_text_format(),
        prompt_cache_key=settings.prompt_cache_key,
        store=True,
    )
    logger.info(
        "agent.step output alert_id=%s step=llm_prompt output_types=%s",
        alert_id,
        [item.type for item in response.output],
    )
    for _ in range(settings.max_tool_calls):
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            break
        outputs = []
        for call in calls:
            arguments = json.loads(call.arguments)
            logger.info(
                "agent.step input alert_id=%s step=tool tool=%s arguments=%s",
                alert_id,
                call.name,
                log_payload(arguments),
            )
            try:
                action_prompt = prompt_store.action(call.name)
                result = _dispatch(settings, call.name, arguments)
                result = {"action_guidance": action_prompt, "result": result}
            except Exception as exc:
                result = {"error": f"read-only tool failed: {type(exc).__name__}: {str(exc)[:500]}"}
            logger.info(
                "agent.step output alert_id=%s step=tool tool=%s result=%s",
                alert_id,
                call.name,
                log_payload(result, settings.max_tool_output_bytes),
            )
            encoded = json.dumps(result, default=str)
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": encoded[: settings.max_tool_output_bytes],
                }
            )
        response = session.client.responses.create(
            model=settings.llm_model,
            previous_response_id=response.id,
            input=outputs,
            tools=session.tools,
            text=_diagnosis_text_format(),
            prompt_cache_key=settings.prompt_cache_key,
            store=True,
        )
        logger.info(
            "agent.step output alert_id=%s step=llm_tool_followup output_types=%s",
            alert_id,
            [item.type for item in response.output],
        )
    else:
        raise RuntimeError("Anton investigation exceeded ANTON_MAX_TOOL_CALLS")
    raw = response.output_text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        diagnosis = Diagnosis.model_validate_json(raw)
        logger.info(
            "agent.step output alert_id=%s step=diagnosis result=%s", alert_id, log_payload(diagnosis.model_dump())
        )
        return diagnosis
    except ValidationError as exc:
        issues = [
            {"location": ".".join(str(part) for part in error["loc"]), "type": error["type"], "message": error["msg"]}
            for error in exc.errors()
        ]
        logger.warning("model returned an invalid diagnosis response issues=%s", log_payload(issues))
        return Diagnosis(
            status=DiagnosisStatus.BLOCKED,
            incident="invalid diagnosis response",
            hypothesis="The model response did not match the diagnosis contract.",
            evidence=["Diagnosis output validation failed before a fix was proposed."],
            validation=["No validation was run because the diagnosis was invalid."],
            rollback="No change was proposed.",
        )
    except (TypeError, ValueError) as exc:
        logger.warning("model returned an unreadable diagnosis response error=%s", type(exc).__name__)
        return Diagnosis(
            status=DiagnosisStatus.BLOCKED,
            incident="invalid diagnosis response",
            hypothesis="The model response did not match the diagnosis contract.",
            evidence=["Diagnosis output validation failed before a fix was proposed."],
            validation=["No validation was run because the diagnosis was invalid."],
            rollback="No change was proposed.",
        )
