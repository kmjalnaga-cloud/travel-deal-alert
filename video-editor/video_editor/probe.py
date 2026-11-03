"""ffprobe로 미디어 파일 정보를 읽는다."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    width: int | None
    height: int | None
    fps: Fraction | None
    sample_rate: int | None
    duration: float | None
    video_codec: str | None
    audio_codec: str | None

    @property
    def has_video(self) -> bool:
        return self.width is not None

    @property
    def has_audio(self) -> bool:
        return self.sample_rate is not None


def _parse_rate(value: str | None) -> Fraction | None:
    if not value or value in ("0/0", "0"):
        return None
    try:
        rate = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


def parse_probe_json(path: Path, data: dict) -> MediaInfo:
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = None
    raw = (data.get("format") or {}).get("duration")
    if raw is not None:
        try:
            duration = float(raw)
        except ValueError:
            pass

    sample_rate = None
    if audio and audio.get("sample_rate"):
        sample_rate = int(audio["sample_rate"])

    return MediaInfo(
        path=path,
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        fps=(_parse_rate(video.get("avg_frame_rate")) or _parse_rate(video.get("r_frame_rate")))
        if video
        else None,
        sample_rate=sample_rate,
        duration=duration,
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
    )


def probe(path: str | Path, ffprobe: str = "ffprobe") -> MediaInfo:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {path}")
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", str(path)],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("ffprobe를 찾을 수 없습니다. ffmpeg를 설치해 주세요.") from None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"미디어 파일을 읽을 수 없습니다: {path}\n{e.stderr.strip()}") from None
    return parse_probe_json(path, json.loads(result.stdout))
