#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "examples" / "oracle_staging" / "fixtures" / "minimal_penny_stock_bot.py"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_staging_rehearsal"
EXPORTER_MODULE = ROOT / "examples" / "oracle_sidecar" / "patch_drafts" / "ai_council_signal_exporter_module.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a local staging copy for Oracle export hook rehearsal.")
    parser.add_argument("--source-bot", default=str(DEFAULT_SOURCE), help="Read-only source bot file.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Local staging output directory.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = prepare_staging(Path(args.source_bot), Path(args.output))
    except Exception as exc:
        result = {
            "status": "failed",
            "detail": str(exc),
            "order_execution_allowed": False,
        }
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0


def prepare_staging(source_bot: Path, output_dir: Path) -> dict[str, Any]:
    source = source_bot.expanduser()
    output = output_dir.expanduser()
    if not source.exists():
        raise FileNotFoundError(f"source bot not found: {source}")
    output.mkdir(parents=True, exist_ok=True)
    outbox = output / "outbox"
    state = output / "state"
    modules = output / "modules"
    for directory in (outbox, state, modules):
        directory.mkdir(parents=True, exist_ok=True)

    staging_bot = output / "penny_stock_bot.py"
    shutil.copy2(source, staging_bot)
    exporter_copy = modules / "ai_council_signal_exporter_module.py"
    shutil.copy2(EXPORTER_MODULE, exporter_copy)

    manifest = {
        "status": "prepared",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_bot": str(source),
        "source_sha256": sha256_file(source),
        "staging_bot": str(staging_bot),
        "staging_sha256": sha256_file(staging_bot),
        "exporter_module": str(exporter_copy),
        "outbox_dir": str(outbox),
        "state_dir": str(state),
        "source_modified": sha256_file(source) != sha256_file(staging_bot),
        "oracle_server_contacted": False,
        "order_execution_allowed": False,
        "simulation_only": True,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        **manifest,
        "manifest_path": str(manifest_path),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
