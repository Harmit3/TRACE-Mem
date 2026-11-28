"""Package only tracked files from an explicit TRACE-Mem commit."""

from argparse import ArgumentParser
from hashlib import file_digest
from pathlib import Path, PurePosixPath
import subprocess


VERSION = "1.0.0-rc.1"


def safe_path(name):
    path = PurePosixPath(name.casefold())
    return (
        path.parts[0] not in {"data", "results", "third_party", ".git"}
        and (not path.name.startswith(".env") or path.name == ".env.example")
        and path.suffix not in {".gguf", ".safetensors", ".pth", ".pt", ".bin",
                                ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".zip"}
        and not any(marker in path.name for marker in (".sqlite-", ".sqlite3-", ".db-"))
    )


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="Committed Git revision to package")
    parser.add_argument("output", type=Path, help="New ZIP file")
    parser.add_argument("--version", choices=(VERSION, "1.0.0", "1.1.0"), default=VERSION,
                        help="Archive directory version (does not create a release or tag)")
    args = parser.parse_args()
    if args.output.exists() or args.output.suffix.lower() != ".zip":
        parser.error("Output must be a new .zip file")
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", args.revision + "^{commit}"], text=True
    ).strip()
    entries = subprocess.check_output(["git", "ls-tree", "-rz", revision]).split(b"\0")
    for entry in filter(None, entries):
        metadata, raw_path = entry.split(b"\t", 1)
        if not metadata.startswith((b"100644 blob ", b"100755 blob ")) or not safe_path(raw_path.decode("utf-8")):
            parser.error("Committed tree contains a disallowed file type or path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "archive", "--format=zip", f"--prefix=TRACE-Mem-{args.version}/",
                    f"--output={args.output.resolve()}", revision], check=True)
    with args.output.open("rb") as file:
        print(f"{revision} | {args.output.stat().st_size} bytes | SHA-256 {file_digest(file, 'sha256').hexdigest()}")


if __name__ == "__main__":
    main()
