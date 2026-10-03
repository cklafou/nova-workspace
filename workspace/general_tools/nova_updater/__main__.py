# @nova: Command line for the model updater: check, search, inventory, plan, install and training bundles, for testing and for agents.
"""python -m nova_updater <command> [options]

  check [--force]                       newest dense 27-32B models vs what Nova runs
  status                                last check, remembered decisions, pending install
  search QUERY [--source S] [--author A] [--min-b N] [--max-b N] [--dense] [--gguf] [--license L]
  candidate MODEL_ID [--source S]       GGUF builds, quants and projectors for one model
  inventory                             installed models, projectors and LoRAs (reads models/)
  plan MODEL_ID [--quant Q] [--gguf-repo R] [--replace PATH ...] [--no-activate] [--lora none|keep]
  install PLAN_ID --yes                 download + switch (applies at next model start from the CLI)
  train-bundle --base REPO --data FILE [FILE ...] [--preset personality|specialist] [--name N]
"""
from __future__ import annotations

import argparse
import json
import sys

from . import catalog, check, install, inventory, jobs, plan, train


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nova_updater", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check"); p.add_argument("--force", action="store_true")
    sub.add_parser("status")
    p = sub.add_parser("search"); p.add_argument("query", nargs="?", default="")
    p.add_argument("--source", default="huggingface"); p.add_argument("--author")
    p.add_argument("--min-b", type=float); p.add_argument("--max-b", type=float)
    p.add_argument("--dense", action="store_true"); p.add_argument("--gguf", action="store_true")
    p.add_argument("--license"); p.add_argument("--limit", type=int, default=25)
    p = sub.add_parser("candidate"); p.add_argument("model_id"); p.add_argument("--source", default="huggingface")
    sub.add_parser("inventory")
    p = sub.add_parser("plan"); p.add_argument("model_id"); p.add_argument("--source", default="huggingface")
    p.add_argument("--quant"); p.add_argument("--gguf-repo"); p.add_argument("--replace", nargs="*", default=[])
    p.add_argument("--no-activate", action="store_true"); p.add_argument("--lora", default="none")
    p = sub.add_parser("install"); p.add_argument("plan_id"); p.add_argument("--yes", action="store_true")
    p = sub.add_parser("train-bundle"); p.add_argument("--base", required=True)
    p.add_argument("--data", nargs="+", required=True); p.add_argument("--preset", default="personality")
    p.add_argument("--name")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "check":
            _print(check.run_check(force=args.force))
        elif args.cmd == "status":
            _print(check.status())
        elif args.cmd == "search":
            src = catalog.source(args.source)
            hits = src.search(q=args.query, author=args.author, gguf=args.gguf, limit=max(args.limit, 50))
            hits = catalog.filter_hits(hits, min_b=args.min_b, max_b=args.max_b, dense_only=args.dense,
                                       licenses=[args.license] if args.license else None)
            _print([h.to_dict() for h in catalog.sort_hits(hits)[: args.limit]])
        elif args.cmd == "candidate":
            _print(plan.describe_candidate(args.source, args.model_id))
        elif args.cmd == "inventory":
            _print(inventory.scan())
        elif args.cmd == "plan":
            _print(plan.build({"source": args.source, "model_id": args.model_id, "quant": args.quant,
                               "gguf_repo": args.gguf_repo, "replace": args.replace,
                               "activate": not args.no_activate, "lora": {"mode": args.lora}}))
        elif args.cmd == "install":
            job = install.start(args.plan_id, confirm=args.yes)
            while job.state in ("queued", "running"):
                import time
                time.sleep(2)
                info = job.to_dict(1)
                print(f"\r{info['step'][:70]:70s} {info['percent'] or 0:5.1f}%", end="", flush=True)
            print()
            _print(job.to_dict())
            return 0 if job.state == "succeeded" else 1
        elif args.cmd == "train-bundle":
            spec = train.prepare_spec({"base_model_id": args.base, "data_files": args.data,
                                       "preset": args.preset, "output_name": args.name, "runner": "export"})
            _print(train.export(spec))
    except (ValueError, RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
