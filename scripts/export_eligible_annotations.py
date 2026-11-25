"""Export pending TRACE-UpdateSet gold for eligible train and validation cases."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from trace_mem.data.updateset import annotation_packet, read_release
from trace_mem.training import _inputs, eligible_case


def export(dataset: Path, output: Path) -> dict:
    root = Path("data").resolve()
    path = output.resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Write annotation packets under ignored data/")
    rows, manifest = read_release(dataset)
    pending = [row for row in rows
               if row["split"] in ("train", "validation")
               and row["gold"] is None and eligible_case(_inputs(row))]
    packet = annotation_packet(pending)
    content = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in packet)
    with path.open("xb") as file:
        file.write(content)
    return {
        "counts": dict(Counter(row["split"] for row in pending)),
        "rows": len(packet),
        "packet_sha256": hashlib.sha256(content).hexdigest(),
        "dataset_sha256": manifest["files"]["cases.jsonl"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.dataset, args.output), sort_keys=True))
