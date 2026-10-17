from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from stamp_agent.models import AnalysisReport


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_") or "document"


def write_json_report(report: AnalysisReport, output_dir: str | Path) -> Path:
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = _slugify(Path(report.input_file).stem)
    path = out_dir / f"{stem}_{ts}.json"

    with path.open("w", encoding="utf-8") as handle:
        json.dump(report.to_dict(), handle, indent=2)

    return path
