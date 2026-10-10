import json
import os
import subprocess

from sensei.infrastructure.config import RepositoryToolConfig


class ToolRunner:
    def __init__(self, settings):
        self.timeout_seconds = settings.command_timeout_seconds
        self.max_output_bytes = settings.max_tool_output_bytes

    @staticmethod
    def definitions(tools: list[RepositoryToolConfig]) -> list[dict]:
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "strict": True,
            }
            for tool in tools
        ]

    def run(self, tool: RepositoryToolConfig, arguments: dict) -> dict[str, object]:
        args = arguments.get("args", [])
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            return {"error": "tool args must be a list of strings"}
        try:
            result = subprocess.run(
                [tool.command, *args],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            output = result.stdout[: self.max_output_bytes]
            return {"exit_code": result.returncode, "output": output}
        except subprocess.TimeoutExpired:
            return {"error": f"{tool.name} timed out"}
        except OSError as exc:
            return {"error": f"{tool.name} could not run: {type(exc).__name__}"}

    @staticmethod
    def output(result: dict[str, object]) -> str:
        return json.dumps(result, default=str)
