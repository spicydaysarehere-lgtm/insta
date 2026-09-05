import subprocess
from pathlib import Path
import cv2


def run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result


def probe_duration(path):
    return float(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ]).stdout.strip())


def frame_analysis(path, sample_fps=2):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("Unable to open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps / sample_fps))
    previous = None
    data = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step:
            i += 1
            continue
        small = cv2.resize(frame, (320, 180))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        motion = 0 if previous is None else float(cv2.absdiff(gray, previous).mean()) / 255
        edges = cv2.Canny(gray, 70, 150)
        data.append({
            "t": i / fps,
            "motion": motion,
            "edges": float((edges > 0).mean()),
            "brightness": float(gray.mean()) / 255,
        })
        previous = gray
        i += 1
    cap.release()
    if not data:
        raise RuntimeError("No frames sampled")
    return data


def audio_analysis(path, duration):
    out = []
    start = 0.0
    while start < duration:
        length = min(2.0, duration - start)
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", str(start), "-t", str(length), "-i", str(path),
            "-af", "volumedetect", "-f", "null", "-"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        mean = maxv = -60.0
        for line in result.stderr.splitlines():
            if line.strip().startswith("mean_volume:"):
                try:
                    mean = float(line.split(":", 1)[1].replace("dB", "").strip())
                except ValueError:
                    pass
            if line.strip().startswith("max_volume:"):
                try:
                    maxv = float(line.split(":", 1)[1].replace("dB", "").strip())
                except ValueError:
                    pass
        out.append({"t": start + length / 2, "mean": mean, "max": maxv})
        start += 2.0
    return out


def _norm(v, lo, hi):
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def _avg(frames, a, b, key):
    values = [x[key] for x in frames if a <= x["t"] <= b]
    return sum(values) / len(values) if values else 0.0


def find_best_moment(path, min_seconds=15, max_seconds=45):
    duration = probe_duration(path)
    if duration <= min_seconds:
        return 0.0, duration, 100.0

    frames = frame_analysis(path)
    audio = audio_analysis(path, duration)
    means = [x["mean"] for x in audio] or [-60]
    maxes = [x["max"] for x in audio] or [-60]

    def sound_score(t):
        item = min(audio, key=lambda x: abs(x["t"] - t))
        return 0.55 * _norm(item["mean"], min(means), max(means)) + 0.45 * _norm(item["max"], min(maxes), max(maxes))

    lengths = sorted(set([
        min_seconds,
        min(20, max_seconds, duration),
        min(25, max_seconds, duration),
        min(30, max_seconds, duration),
        min(35, max_seconds, duration),
        min(max_seconds, duration),
    ]))

    candidates = []
    for length in lengths:
        if length < min_seconds:
            continue
        start = 0.0
        while start + length <= duration + 0.01:
            end = min(duration, start + length)
            motion = min(1, _avg(frames, start, end, "motion") / 0.18)
            edges = min(1, _avg(frames, start, end, "edges") / 0.20)
            bright = min(1, _avg(frames, start, end, "brightness") / 0.45)
            score = 40 * motion + 35 * sound_score((start + end) / 2) + 20 * edges + 5 * bright
            candidates.append((score, start, end))
            start += max(3.0, length * 0.35)

    if not candidates:
        return 0.0, min(duration, max_seconds), 0.0

    score, start, end = max(candidates)
    return start, end - start, round(score, 2)


def render_reel(source, output, start, length):
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(source),
        "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "medium",
        "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(output)
    ])
