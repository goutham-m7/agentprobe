"""Versioned, strict data contracts shared by adapters, runners and reports."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Criterion = Literal["task_success", "policy_adherence", "hallucination", "tone", "tool_misuse"]
CRITERIA: tuple[Criterion, ...] = (
    "task_success",
    "policy_adherence",
    "hallucination",
    "tone",
    "tool_misuse",
)
Persona = Literal[
    "confused", "angry", "multilingual", "prompt-injector", "edge-case-seeker", "goal-switcher"
]
PERSONAS: tuple[Persona, ...] = (
    "confused",
    "angry",
    "multilingual",
    "prompt-injector",
    "edge-case-seeker",
    "goal-switcher",
)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Tool(Model):
    name: Text
    description: Text
    parameters: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})


class AgentSpec(Model):
    name: Text
    purpose: Text
    policies: list[Text] = Field(min_length=1)
    facts: list[Text] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_tools(self):
        if len({tool.name for tool in self.tools}) != len(self.tools):
            raise ValueError("Tool names must be unique")
        return self

    @property
    def fingerprint(self) -> str:
        data = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode()).hexdigest()


class Branch(Model):
    after_turn: int = Field(ge=1, le=10, strict=True)
    contains: Text
    next_turn: int = Field(ge=2, le=10, strict=True)


class Scenario(Model):
    id: Text
    persona: Persona
    objective: Text
    turns: list[Text] = Field(min_length=1, max_length=10)
    branches: list[Branch] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def forward_branches(self):
        if any(
            not branch.after_turn < branch.next_turn <= len(self.turns) for branch in self.branches
        ):
            raise ValueError("Branch destinations must be forward and within the plan")
        return self

    def following_turn(self, after_turn: int, reply: str) -> int:
        for branch in self.branches:
            if branch.after_turn == after_turn and branch.contains.casefold() in reply.casefold():
                return branch.next_turn
        return after_turn + 1


class Suite(Model):
    format_version: Literal[1] = 1
    spec_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    seed: int
    scenarios: list[Scenario] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({scenario.id for scenario in self.scenarios}) != len(self.scenarios):
            raise ValueError("Scenario IDs must be unique")
        return self


class ToolCall(Model):
    id: Text
    name: Text
    arguments: dict


class Message(Model):
    role: Literal["system", "user", "assistant"]
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)


class Reply(Model):
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)

    @model_validator(mode="after")
    def has_output(self):
        if not self.content.strip() and not self.tool_calls:
            raise ValueError("Agent reply must contain text or tool calls")
        return self


class Judgment(Model):
    passed: bool = Field(strict=True)
    reason: Text
    evidence: Text


class Grades(Model):
    scores: dict[Criterion, Judgment]

    @model_validator(mode="after")
    def complete_rubric(self):
        if set(self.scores) != set(CRITERIA):
            raise ValueError("Judge must return exactly all five rubric criteria")
        return self


class Conversation(Model):
    scenario_id: Text
    messages: list[Message]
    grades: Grades | None
    error: str | None
    duration_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def outcome(self):
        if (self.grades is None) == (self.error is None):
            raise ValueError("Conversation must have either grades or an error")
        return self


class Run(Model):
    format_version: Literal[1] = 1
    id: Text
    agent: Text
    judge: Text
    created_at: Text
    spec: AgentSpec
    suite: Suite
    conversations: list[Conversation]
    duration_seconds: float = Field(ge=0)
    concurrency: int = Field(ge=1)

    @model_validator(mode="after")
    def consistent(self):
        if self.spec.fingerprint != self.suite.spec_fingerprint:
            raise ValueError("Run spec and suite fingerprint differ")
        actual = [item.scenario_id for item in self.conversations]
        expected = [item.id for item in self.suite.scenarios]
        if actual != expected:
            raise ValueError("Run must contain every suite scenario in order")
        return self
