#!/usr/bin/env python3
import os
import subprocess
import sys
import time
import json
from pathlib import Path

VAAPI_DEVICE = "/dev/dri/renderD128"


def get_video_info(input_path: str) -> tuple[float | None, int | None, float | None]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", "-select_streams", "v:0", input_path],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        stream = data["streams"][0]
        height = int(stream["height"])
        num, den = stream.get("r_frame_rate", "0/1").split("/")
        fps = float(num) / float(den) if float(den) else None
        return duration, height, fps
    except Exception:
        return None, None, None


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def draw_bar(fraction: float, width: int = 28) -> str:
    filled = int(fraction * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def encode_480p(input_path: str) -> None:
    src = Path(input_path).resolve()
    if not src.exists():
        print(f"File not found: {src}")
        sys.exit(1)

    total, src_height, src_fps = get_video_info(str(src))

    cap_fps = src_fps is not None and src_fps > 30
    suffix = "_boop_30fps.mp4" if cap_fps else "_boop.mp4"
    out = src.with_name(src.stem + suffix)
    if out.exists():
        print(f"Error: output file already exists — aborting without changes.")
        print(f"  Source : {src}")
        print(f"  Conflict: {out}")
        print(f"  Remove or rename the existing file to re-encode.")
        sys.exit(1)

    filters = []
    if cap_fps:
        filters.append("fps=30")
    filters.append("format=nv12,hwupload")
    if src_height is None or src_height > 480:
        filters.append("scale_vaapi=-2:480")
    vf = ",".join(filters)

    cmd = [
        "ffmpeg",
        "-vaapi_device", VAAPI_DEVICE,
        "-i", str(src),
        "-vf", vf,
        "-c:v", "hevc_vaapi",
        "-qp", "24",
        "-an",
        "-progress", "pipe:1",
        "-nostats",
        str(out),
    ]

    print(f"Encoding: {src.name}  →  {out.name}")
    if total:
        print(f"Duration: {fmt_time(total)}")
    if src_height is not None and src_height <= 480:
        print(f"Source height {src_height}px ≤ 480 — skipping scale")
    if cap_fps and src_fps is not None:
        print(f"Source FPS {src_fps:.2f} → capped at 30")
    print()

    start = time.time()
    chunk: dict[str, str] = {}

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, bufsize=1)

    for line in proc.stdout:
        key, _, val = line.strip().partition("=")
        chunk[key] = val.strip()

        if key != "progress":
            continue

        elapsed = time.time() - start
        raw = chunk.get("out_time_us", "0")
        pos = int(raw) / 1_000_000 if raw not in ("", "N/A") else 0.0
        fps = float(chunk.get("fps", 0) or 0)
        speed = chunk.get("speed", "?x")
        chunk = {}

        if total and total > 0:
            frac = min(pos / total, 1.0)
            eta = (elapsed / frac - elapsed) if frac > 0.001 else 0
            status = (
                f"\r{draw_bar(frac)} {frac*100:5.1f}%  "
                f"{fmt_time(pos)}/{fmt_time(total)}  "
                f"elapsed {fmt_time(elapsed)}  ETA {fmt_time(eta)}  "
                f"{fps:.0f}fps  {speed}"
            )
        else:
            status = (
                f"\rEncoded {fmt_time(pos)}  "
                f"elapsed {fmt_time(elapsed)}  "
                f"{fps:.0f}fps  {speed}"
            )

        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80
        print(status[:cols], end="", flush=True)

    proc.wait()
    print()

    elapsed = time.time() - start
    if proc.returncode == 0:
        size_mb = out.stat().st_size / 1_048_576
        print(f"\nDone in {fmt_time(elapsed)}  ({size_mb:.1f} MB)  →  {out}")
    else:
        print(f"\nffmpeg exited with code {proc.returncode}")
        sys.exit(proc.returncode)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        sys.exit(1)
    encode_480p(sys.argv[1])
