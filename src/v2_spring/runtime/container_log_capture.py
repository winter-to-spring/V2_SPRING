from __future__ import annotations

import argparse
import json
import subprocess
import sys
from threading import Thread
from pathlib import Path


class BoundedStreamCapture:
    def __init__(self, *, head_bytes: int, tail_bytes: int, max_bytes: int) -> None:
        self.head_bytes = head_bytes
        self.tail_bytes = tail_bytes
        self.max_bytes = max_bytes
        self.total_bytes = 0
        self._full_preview = bytearray()
        self._head = bytearray()
        self._tail = bytearray()

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.total_bytes += len(chunk)
        remaining_preview = self.max_bytes - len(self._full_preview)
        if remaining_preview > 0:
            self._full_preview.extend(chunk[:remaining_preview])
        remaining_head = self.head_bytes - len(self._head)
        if remaining_head > 0:
            self._head.extend(chunk[:remaining_head])
        combined_tail = self._tail + chunk
        if len(combined_tail) > self.tail_bytes:
            combined_tail = combined_tail[-self.tail_bytes :]
        self._tail = combined_tail

    def render(self) -> tuple[str, int, bool]:
        if self.total_bytes <= self.max_bytes:
            return self._full_preview.decode("utf-8", errors="replace").rstrip(), self.total_bytes, False
        omitted_bytes = max(self.total_bytes - (self.head_bytes + self.tail_bytes), 0)
        head_text = self._head.decode("utf-8", errors="replace").rstrip()
        tail_text = self._tail.decode("utf-8", errors="replace").rstrip()
        preview = f"{head_text}\n\n... [truncated {omitted_bytes} bytes] ...\n\n{tail_text}".strip()
        return preview, self.total_bytes, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="container-log-capture",
        description="Execute the worker entrypoint and persist bounded diagnostics.",
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--head-bytes", type=int, required=True)
    parser.add_argument("--tail-bytes", type=int, required=True)
    parser.add_argument("--max-bytes", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stdout_capture = BoundedStreamCapture(
        head_bytes=args.head_bytes,
        tail_bytes=args.tail_bytes,
        max_bytes=args.max_bytes,
    )
    stderr_capture = BoundedStreamCapture(
        head_bytes=args.head_bytes,
        tail_bytes=args.tail_bytes,
        max_bytes=args.max_bytes,
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "/opt/v2/isolated_worker_entry.py",
            "--workspace",
            args.workspace,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout_thread = Thread(target=_consume_stream, args=(process.stdout, stdout_capture), daemon=True)
    stderr_thread = Thread(target=_consume_stream, args=(process.stderr, stderr_capture), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    return_code = process.wait()
    stdout_thread.join()
    stderr_thread.join()

    stdout_preview, stdout_bytes, stdout_truncated = stdout_capture.render()
    stderr_preview, stderr_bytes, stderr_truncated = stderr_capture.render()
    (output_dir / "stdout.preview.txt").write_text(stdout_preview, encoding="utf-8")
    (output_dir / "stderr.preview.txt").write_text(stderr_preview, encoding="utf-8")
    (output_dir / "capture_meta.json").write_text(
        json.dumps(
            {
                "stdout_bytes": stdout_bytes,
                "stderr_bytes": stderr_bytes,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return return_code


def _consume_stream(stream, capture: BoundedStreamCapture) -> None:
    if stream is None:
        return
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        capture.feed(chunk)
    stream.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
