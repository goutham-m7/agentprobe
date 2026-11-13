"""CLI composition root: environment reads, provider lifetime and exit semantics."""

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import httpx
from pydantic import ValidationError

from agentprobe import __version__
from agentprobe.adapters import CallableAgent, HttpAgent, load_callable
from agentprobe.artifacts import read_run, write_run
from agentprobe.calibration import LabelSet, calibrate
from agentprobe.comparison import compare
from agentprobe.demo_agents import broken_agent, demo_spec, good_agent
from agentprobe.judge import Judge
from agentprobe.labelling import label_run
from agentprobe.mock import MockProvider
from agentprobe.models import Suite
from agentprobe.providers import OpenAIProvider, ProviderError
from agentprobe.reports import comparison_html, comparison_markdown, page, summarize
from agentprobe.runner import run_suite
from agentprobe.scenarios import generate_suite
from agentprobe.spec import load_spec


def default_directory(prefix: str) -> Path:
    return Path(".agentprobe") / f"{prefix}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"


def new_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)


def provider_options(parser):
    parser.add_argument(
        "--provider",
        choices=["mock", "openai"],
        default="mock",
        help="mock only supports the bundled Harbor demo contract",
    )
    parser.add_argument("--base-url", help="OpenAI-compatible base URL (or AGENTPROBE_BASE_URL)")
    parser.add_argument("--model", help="Judge/generator model (or AGENTPROBE_MODEL)")
    parser.add_argument(
        "--key-env",
        default="AGENTPROBE_API_KEY",
        help="Environment variable holding judge/generator key",
    )
    parser.add_argument("--retries", type=int, default=2, help="Judge/generator retries, 0..5")
    parser.add_argument("--input-price", type=float, help="USD per million input tokens")
    parser.add_argument("--output-price", type=float, help="USD per million output tokens")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="agentprobe",
        description="CI for AI agents: adversarial conversations, calibrated judges and paired regression checks.",
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run the complete offline good-vs-broken demonstration")
    demo.add_argument("--out", type=Path)
    demo.add_argument("--per-persona", type=int, default=4)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--samples", type=int, default=10000)
    demo.add_argument("--concurrency", type=int, default=6)
    generate = commands.add_parser(
        "generate", help="Generate and save a reusable adversarial suite"
    )
    generate.add_argument("spec", type=Path)
    generate.add_argument("--out", type=Path, required=True)
    generate.add_argument("--per-persona", type=int, default=4)
    generate.add_argument("--seed", type=int, default=42)
    provider_options(generate)
    run = commands.add_parser("run", help="Run a trusted Python callable or sandbox HTTP agent")
    run.add_argument("spec", type=Path)
    target = run.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--callable", dest="callable_target", help="Trusted module:function; receives list[Message]"
    )
    target.add_argument("--endpoint", help="OpenAI-compatible target chat endpoint or base URL")
    run.add_argument("--target-model")
    run.add_argument("--agent-key-env", default="AGENTPROBE_AGENT_KEY")
    run.add_argument("--target-input-price", type=float)
    run.add_argument("--target-output-price", type=float)
    run.add_argument("--suite", type=Path)
    run.add_argument("--out", type=Path)
    run.add_argument("--concurrency", type=int, default=6)
    run.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="Whole conversation including judgment, in seconds",
    )
    run.add_argument("--per-persona", type=int, default=4)
    run.add_argument("--seed", type=int, default=42)
    provider_options(run)
    diff = commands.add_parser("diff", help="Compare matched run folders or run.json files")
    diff.add_argument("baseline", type=Path)
    diff.add_argument("candidate", type=Path)
    diff.add_argument(
        "--out", type=Path, help="New directory for diff.json, report.html and summary.md"
    )
    diff.add_argument("--samples", type=int, default=10000)
    diff.add_argument("--seed", type=int, default=42)
    diff.add_argument("--fail-on-regression", action="store_true")
    calibration = commands.add_parser(
        "calibrate",
        help="Measure judge agreement against human or explicit synthetic reference labels",
    )
    calibration.add_argument("labels", type=Path)
    calibration.add_argument("--out", type=Path, required=True)
    calibration.add_argument("--concurrency", type=int, default=6)
    calibration.add_argument("--timeout", type=float, default=60)
    provider_options(calibration)
    label = commands.add_parser("label", help="Blindly annotate complete run transcripts")
    label.add_argument("run", type=Path)
    label.add_argument("--labeler", required=True)
    label.add_argument("--out", type=Path, required=True)
    return root


def make_provider(args, client):
    if args.provider == "mock":
        return MockProvider()
    model = args.model or os.environ.get("AGENTPROBE_MODEL", "")
    if not model:
        raise ValueError("Set --model or AGENTPROBE_MODEL for the real provider")
    base_url = args.base_url or os.environ.get("AGENTPROBE_BASE_URL", "https://api.openai.com/v1")
    return OpenAIProvider(
        client,
        base_url,
        os.environ.get(args.key_env, ""),
        model,
        retries=args.retries,
        input_price=args.input_price,
        output_price=args.output_price,
    )


def write_usage(path: Path, provider, agent=None) -> None:
    usage = {}
    if isinstance(provider, OpenAIProvider):
        usage["judge_generator"] = provider.accounting()
    if isinstance(agent, HttpAgent):
        usage["target"] = agent.provider.accounting()
    new_file(path, json.dumps(usage, indent=2) + "\n")


def calibration_text(result) -> str:
    label = "human labels" if result.label_source == "human" else "synthetic reference labels"
    lines = [
        f"## Judge agreement against {label}",
        "",
        f"{result.examples} transcripts · Judge: {result.judge}",
        "",
        "| Criterion | Agreement | Cohen's kappa | Reliability warnings |",
        "|---|---:|---:|---|",
    ]
    for key, metric in result.metrics.items():
        kappa = "undefined" if metric.kappa is None else f"{metric.kappa:.3f}"
        lines.append(
            f"| {key} | {metric.agreement:.1%} | {kappa} | {', '.join(metric.warnings) or 'none'} |"
        )
    if result.label_source == "synthetic_reference":
        lines += [
            "",
            "Synthetic references demonstrate calibration mechanics only. No human agreement or real-model reliability is claimed.",
        ]
    lines += [
        "",
        "Overall agreement pools rubric decisions; per-item warnings are the reliability gate.",
    ]
    return "\n".join(lines) + "\n"


async def demo(args) -> int:
    directory = args.out or default_directory("demo")
    if directory.exists():
        raise FileExistsError(f"Refusing to overwrite {directory}; choose a new --out")
    spec = demo_spec()
    provider = MockProvider()
    suite = await generate_suite(spec, provider, per_persona=args.per_persona, seed=args.seed)
    good = await run_suite(
        spec,
        suite,
        CallableAgent(good_agent, "harbor:good-v1"),
        Judge(provider),
        concurrency=args.concurrency,
        timeout=10,
    )
    broken = await run_suite(
        spec,
        suite,
        CallableAgent(broken_agent, "harbor:broken-v2"),
        Judge(provider),
        concurrency=args.concurrency,
        timeout=10,
    )
    comparison = compare(good, broken, samples=args.samples, seed=args.seed)
    labels = LabelSet.model_validate_json(
        files("agentprobe").joinpath("data/reference-labels.json").read_text(encoding="utf-8")
    )
    calibration = await calibrate(labels, Judge(provider), concurrency=args.concurrency, timeout=10)
    directory.mkdir(parents=True)
    write_run(good, directory / "good")
    write_run(broken, directory / "broken")
    (directory / "suite.json").write_text(suite.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (directory / "diff.json").write_text(
        comparison.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (directory / "summary.md").write_text(comparison_markdown(comparison), encoding="utf-8")
    (directory / "index.html").write_text(
        comparison_html(comparison).replace(
            "<footer>",
            '<p><a href="good/report.html">Baseline conversation evidence</a> · <a href="broken/report.html">Candidate conversation evidence</a></p><footer>',
        ),
        encoding="utf-8",
    )
    (directory / "calibration.json").write_text(
        calibration.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (directory / "calibration.md").write_text(calibration_text(calibration), encoding="utf-8")
    print("agentprobe · offline regression demo")
    for name, result in [("Good", good), ("Broken", broken)]:
        summary = summarize(result)
        print(
            f"{name}: {summary['passed']}/{summary['total']} conversations passed ({summary['rate']:.1%}); {summary['errors']} errors"
        )
    print(f"Significant metric regressions: {', '.join(comparison.regressions)}")
    overall = comparison.metrics["overall"].interval
    print(
        f"Overall delta: {overall.delta * 100:+.1f} pp; 95% CI [{overall.ci_low * 100:+.1f}, {overall.ci_high * 100:+.1f}] pp"
    )
    metric = calibration.metrics["overall"]
    print(
        f"Judge agreement against synthetic reference labels: {metric.agreement:.1%}; kappa {metric.kappa:.3f} ({calibration.examples} transcripts)"
    )
    print(f"Reports: {directory}/index.html, summary.md, diff.json, calibration.json")
    return 0


async def execute(args) -> int:
    if args.out is not None and args.out.exists():
        raise FileExistsError(f"Refusing to overwrite {args.out}; choose a new --out")
    if args.command == "label":
        labels = label_run(read_run(args.run), args.labeler)
        new_file(args.out, labels.model_dump_json(indent=2) + "\n")
        print(f"Wrote {len(labels.examples)} annotated transcripts: {args.out}")
        return 0
    if args.command == "demo":
        return await demo(args)
    if args.command == "diff":
        result = compare(
            read_run(args.baseline), read_run(args.candidate), samples=args.samples, seed=args.seed
        )
        text = comparison_markdown(result)
        if args.out:
            args.out.mkdir(parents=True, exist_ok=False)
            (args.out / "diff.json").write_text(
                result.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            (args.out / "summary.md").write_text(text, encoding="utf-8")
            (args.out / "report.html").write_text(comparison_html(result), encoding="utf-8")
        print(text, end="")
        return int(args.fail_on_regression and bool(result.regressions))
    async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False) as client:
        provider = make_provider(args, client)
        if args.command == "calibrate":
            labels = LabelSet.model_validate_json(args.labels.read_text(encoding="utf-8"))
            result = await calibrate(
                labels, Judge(provider), concurrency=args.concurrency, timeout=args.timeout
            )
            args.out.mkdir(parents=True, exist_ok=False)
            (args.out / "calibration.json").write_text(
                result.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            text = calibration_text(result)
            (args.out / "summary.md").write_text(text, encoding="utf-8")
            from html import escape

            (args.out / "report.html").write_text(
                page(
                    "agentprobe — judge calibration",
                    "<header><h1>Judge calibration</h1></header><pre>" + escape(text) + "</pre>",
                ),
                encoding="utf-8",
            )
            print(text, end="")
            write_usage(args.out / "usage.json", provider)
            return 0
        spec = load_spec(args.spec)
        if args.command == "generate":
            suite = await generate_suite(
                spec, provider, per_persona=args.per_persona, seed=args.seed
            )
            new_file(args.out, suite.model_dump_json(indent=2) + "\n")
            write_usage(args.out.with_suffix(args.out.suffix + ".usage.json"), provider)
            print(f"Generated {len(suite.scenarios)} scenarios across six personas: {args.out}")
            return 0
        if args.callable_target:
            agent = load_callable(args.callable_target)
        else:
            if not args.target_model:
                raise ValueError("--target-model is required with --endpoint")
            agent = HttpAgent(
                OpenAIProvider(
                    client,
                    args.endpoint,
                    os.environ.get(args.agent_key_env, ""),
                    args.target_model,
                    input_price=args.target_input_price,
                    output_price=args.target_output_price,
                )
            )
        suite = (
            Suite.model_validate_json(args.suite.read_text(encoding="utf-8"))
            if args.suite
            else await generate_suite(spec, provider, per_persona=args.per_persona, seed=args.seed)
        )
        result = await run_suite(
            spec, suite, agent, Judge(provider), concurrency=args.concurrency, timeout=args.timeout
        )
        directory = args.out or default_directory("run")
        write_run(result, directory)
        write_usage(directory / "usage.json", provider, agent)
        summary = summarize(result)
        print(
            f"{summary['passed']}/{summary['total']} conversations passed; {summary['errors']} errors; reports: {directory}"
        )
        return 2 if summary["errors"] else 0


def main() -> int:
    args = parser().parse_args()
    try:
        return asyncio.run(execute(args))
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in exc.errors(include_input=False)
        )
        print(f"agentprobe: error: invalid data: {details}", file=sys.stderr)
        return 2
    except (ValueError, OSError, ProviderError, TimeoutError) as exc:
        print(f"agentprobe: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("agentprobe: interrupted", file=sys.stderr)
        return 130
