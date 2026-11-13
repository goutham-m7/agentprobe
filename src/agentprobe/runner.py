"""Bounded multi-turn execution. Failures remain visible and are never scored."""

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime

from agentprobe.adapters import Agent
from agentprobe.judge import Judge
from agentprobe.models import AgentSpec, Conversation, Message, Run, Scenario, Suite


async def run_suite(
    spec: AgentSpec, suite: Suite, agent: Agent, judge: Judge, *, concurrency: int, timeout: float
) -> Run:
    if not 1 <= concurrency <= 256 or timeout <= 0:
        raise ValueError("concurrency must be 1..256 and timeout must be positive")
    if spec.fingerprint != suite.spec_fingerprint:
        raise ValueError("Spec fingerprint does not match suite")
    semaphore = asyncio.Semaphore(concurrency)
    started = time.perf_counter()
    system = (
        "You are the agent described by this contract. Follow its purpose, facts, policies and tool constraints.\n"
        + json.dumps(spec.model_dump(), ensure_ascii=False)
    )

    async def execute(scenario: Scenario) -> Conversation:
        async with semaphore:
            began = time.perf_counter()
            messages = [Message(role="system", content=system)]
            grades = None
            error = None
            try:
                async with asyncio.timeout(timeout):
                    for turn in scenario.turns:
                        messages.append(Message(role="user", content=turn))
                        reply = await agent.respond(
                            [message.model_copy(deep=True) for message in messages], spec.tools
                        )
                        messages.append(
                            Message(
                                role="assistant", content=reply.content, tool_calls=reply.tool_calls
                            )
                        )
                        if reply.tool_calls:
                            # No fake tool results and no unsafe tool execution.
                            break
                    grades = await judge.score(spec, messages, scenario.objective)
            except TimeoutError:
                error = "Conversation timed out"
            except Exception as exc:
                # Exception messages may contain API credentials or private URLs.
                error = f"Agent or judge failed ({type(exc).__name__})"
            return Conversation(
                scenario_id=scenario.id,
                messages=messages,
                grades=grades,
                error=error,
                duration_seconds=time.perf_counter() - began,
            )

    conversations = await asyncio.gather(*(execute(scenario) for scenario in suite.scenarios))
    return Run(
        id=uuid.uuid4().hex[:12],
        agent=agent.name,
        judge=judge.name,
        created_at=datetime.now(UTC).isoformat(),
        spec=spec.model_copy(deep=True),
        suite=suite.model_copy(deep=True),
        conversations=conversations,
        duration_seconds=time.perf_counter() - started,
        concurrency=concurrency,
    )
