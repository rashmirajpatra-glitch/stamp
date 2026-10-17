from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import uvicorn

from stamp_agent.config import load_rules, load_settings
from stamp_agent.demo import run_demo
from stamp_agent.pipeline import StampIntelligencePipeline, build_sarvam_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def _build_pipeline(config_path: str | None = None, force_mock: bool = False) -> StampIntelligencePipeline:
    settings = load_settings()
    if force_mock:
        settings.sarvam_use_mock = True
    rules = load_rules(config_path)
    client = build_sarvam_client(settings)
    return StampIntelligencePipeline(settings=settings, rules=rules, sarvam_client=client)


def _handle_analyze(args: argparse.Namespace) -> int:
    pipeline = _build_pipeline(config_path=args.config, force_mock=args.mock)
    result = pipeline.analyze(args.image, output_dir=args.out)

    payload = result.report.to_dict()
    payload["report_path"] = str(result.report_path)
    payload["email_sent"] = result.email_sent

    print(json.dumps(payload, indent=2))
    logger.info("Analysis completed. JSON report written to %s", result.report_path)
    return 0


def _handle_serve(args: argparse.Namespace) -> int:
    uvicorn.run("stamp_agent.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _handle_demo(args: argparse.Namespace) -> int:
    summary = run_demo(output_dir=args.out)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sarvam AI Stamp Intelligence Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze a JPG/PNG document image")
    analyze.add_argument("image", type=str, help="Path to input image (JPG/PNG)")
    analyze.add_argument("--config", type=str, default=None, help="Path to YAML rules config")
    analyze.add_argument("--out", type=str, default=None, help="Directory to write JSON report")
    analyze.add_argument("--mock", action="store_true", help="Force mock Sarvam client")
    analyze.set_defaults(func=_handle_analyze)

    serve = subparsers.add_parser("serve", help="Run FastAPI server")
    serve.add_argument("--host", type=str, default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=_handle_serve)

    demo = subparsers.add_parser("demo", help="Run local mock demo end-to-end")
    demo.add_argument("--out", type=str, default=None, help="Directory to write demo report")
    demo.set_defaults(func=_handle_demo)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    raise SystemExit(exit_code)
