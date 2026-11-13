"""Measure scheduling throughput with a fixed synthetic async-latency workload."""

import argparse
import asyncio
import json
import statistics
import time

from agentprobe.adapters import CallableAgent
from agentprobe.demo_agents import demo_spec, good_agent
from agentprobe.judge import Judge
from agentprobe.mock import MockProvider
from agentprobe.runner import run_suite
from agentprobe.scenarios import generate_suite


async def measure(args):
    spec = demo_spec()
    suite = await generate_suite(spec, MockProvider(), per_persona=args.per_persona, seed=42)

    async def delayed_agent(messages):
        await asyncio.sleep(args.latency_ms / 1000)
        return good_agent(messages)

    timings = {}
    for concurrency in [1, args.concurrency]:
        observations = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            run = await run_suite(
                spec,
                suite,
                CallableAgent(delayed_agent, "synthetic-latency"),
                Judge(MockProvider()),
                concurrency=concurrency,
                timeout=60,
            )
            if any(conversation.error for conversation in run.conversations):
                raise RuntimeError("Benchmark encountered execution errors")
            observations.append(time.perf_counter() - started)
        timings[str(concurrency)] = {
            "seconds": observations,
            "median_seconds": statistics.median(observations),
        }
    print(
        json.dumps(
            {
                "workload": "synthetic sleep per target reply; not real LLM throughput",
                "seed": 42,
                "conversations": len(suite.scenarios),
                "turns_per_conversation": 3,
                "latency_ms": args.latency_ms,
                "repeats": args.repeats,
                "timings": timings,
                "speedup": timings["1"]["median_seconds"]
                / timings[str(args.concurrency)]["median_seconds"],
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-persona", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--latency-ms", type=float, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.concurrency <= 1 or args.latency_ms < 0 or args.repeats < 1:
        parser.error(
            "concurrency must exceed 1, latency must be nonnegative, repeats must be positive"
        )
    asyncio.run(measure(args))


if __name__ == "__main__":
    main()
