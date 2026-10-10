import json
import logging
from collections.abc import Callable
from typing import Protocol

from openai import OpenAI

from sensei.domain.models import PullRequest, ReviewContext, ReviewResult
from sensei.infrastructure.config import RepositoryToolConfig
from sensei.integrations.tools import ToolRunner

logger = logging.getLogger(__name__)


class ReviewEngine(Protocol):
    def review(
        self,
        pull_request: PullRequest,
        diff: str,
        context: ReviewContext,
        action_prompt: str,
        tools: list[RepositoryToolConfig],
        action_sink: Callable[[str, dict], None],
    ) -> ReviewResult: ...


def _review_format() -> dict:
    return {
        "format": {
            "type": "json_schema",
            "name": "pull_request_review",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "summary": {"type": "string"},
                    "findings": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["risk", "confidence", "summary", "findings"],
            },
        }
    }


class OpenAIReviewEngine:
    def __init__(self, settings, tool_runner: ToolRunner):
        self.model = settings.llm_model
        self.prompt_cache_key = settings.prompt_cache_key
        self.max_tool_calls = settings.max_tool_calls
        self.tool_runner = tool_runner
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.llm_base_url, max_retries=0)

    def review(
        self,
        pull_request: PullRequest,
        diff: str,
        context: ReviewContext,
        action_prompt: str,
        tools: list[RepositoryToolConfig],
        action_sink: Callable[[str, dict], None],
    ) -> ReviewResult:
        try:
            tool_definitions = self.tool_runner.definitions(tools)
            cache_key = f"{self.prompt_cache_key}:{context.project}:{context.version}"
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "developer",
                        "content": (
                            f"{action_prompt}\n\nRepository context for {context.project}:\n{context.context}\n\n"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Review pull request #{pull_request.number} in "
                            f"{pull_request.owner}/{pull_request.repository}.\n\n"
                            f"Title: {pull_request.title}\n"
                            f"Author: {pull_request.author}\n"
                            f"Head branch: {pull_request.head_ref}\n"
                            f"Labels: {', '.join(pull_request.labels)}\n\n"
                            f"Head SHA: {pull_request.head_sha}\n\n"
                            f"Diff:\n{diff}"
                        ),
                    },
                ],
                text=_review_format(),
                tools=tool_definitions,
                prompt_cache_key=cache_key,
                store=True,
            )
            action_sink("llm_response", {"response_id": response.id, "stage": "initial"})
            for _ in range(self.max_tool_calls):
                calls = [item for item in response.output if item.type == "function_call"]
                if not calls:
                    break
                outputs = []
                configured = {tool.name: tool for tool in tools}
                for call in calls:
                    tool = configured.get(call.name)
                    try:
                        arguments = json.loads(call.arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": call.arguments}
                    if tool is None:
                        result = {"error": f"tool not configured: {call.name}"}
                    elif "raw" in arguments:
                        result = {"error": "tool arguments are not valid JSON"}
                    else:
                        result = self.tool_runner.run(tool, arguments)
                    output = self.tool_runner.output(result)
                    action_sink(
                        "tool_call",
                        {
                            "call_id": call.call_id,
                            "tool": call.name,
                            "arguments": arguments,
                            "output": output,
                        },
                    )
                    outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": output,
                        }
                    )
                response = self.client.responses.create(
                    model=self.model,
                    previous_response_id=response.id,
                    input=outputs,
                    text=_review_format(),
                    tools=tool_definitions,
                    prompt_cache_key=cache_key,
                    store=True,
                )
                action_sink("llm_response", {"response_id": response.id, "stage": "tool_follow_up"})
            else:
                return ReviewResult(
                    risk="high",
                    confidence="low",
                    summary="The review exceeded its tool-call limit; merge is blocked.",
                    findings=["The model did not return a final review within the configured tool-call limit."],
                )
            result = ReviewResult.model_validate_json(response.output_text)
        except Exception as exc:
            logger.warning(
                "LLM review failed repository=%s number=%s error=%s",
                pull_request.repository,
                pull_request.number,
                type(exc).__name__,
            )
            return ReviewResult(
                risk="high",
                confidence="low",
                summary="The review could not be completed; merge is blocked.",
                findings=["LLM review failed before a valid decision was returned."],
            )
        logger.info(
            "review completed repository=%s number=%s risk=%s confidence=%s",
            pull_request.repository,
            pull_request.number,
            result.risk,
            result.confidence,
        )
        return result

    def close(self) -> None:
        if self.client:
            self.client.close()
