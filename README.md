# vedit

Video encoding utilities.

## booper.py

Encodes a video to 480p HEVC using VAAPI hardware acceleration.

```
python booper.py <input_file>
```

- Scales to 480px height (width auto-calculated to preserve aspect ratio) if the source is taller than 480px; skips scaling otherwise — works correctly for both landscape and vertical video
- Caps FPS to 30 if the source exceeds 30fps
- Output is saved alongside the source file:
  - `_boop_30fps.mp4` — encoded with FPS cap applied
  - `_boop.mp4` — encoded without FPS cap
- Audio is stripped from the output
- Will not overwrite an existing output file

**Requires:** `ffmpeg`, `ffprobe`, and a VAAPI-capable GPU at `/dev/dri/renderD128`
