import sys
import base64
from pathlib import Path


def encode_file(in_path: Path):
    # Standard Base‑64 with newline every 76 characters (RFC 2045)
    data = in_path.read_bytes()
    return base64.encodebytes(data).decode("ascii").strip()


if __name__ == "__main__":
    argv = sys.argv[1:]
    if len(argv) != 1:
        sys.stderr.write(f"b64 need exactly one input: {argv}\n")
        sys.exit(1)
    in_path = Path(argv[0])
    if not in_path.is_file():
        sys.stderr.write(f"file not found: {in_path}\n")
        sys.exit(1)
    b64 = encode_file(in_path)
    sys.stdout.write(b64)
    sys.stdout.flush()