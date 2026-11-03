"""사용자 입력(해상도/FPS/샘플레이트) 파싱과 편집 명세."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

FIT_MODES = ("contain", "cover", "stretch")

# 별칭 -> 세로 픽셀 (가로는 원본 비율에 맞춰 자동 계산). "NNNp"는 숫자 그대로 세로 픽셀.
RESOLUTION_ALIASES = {"4k": 2160, "uhd": 2160, "fhd": 1080, "hd": 720}


@dataclass(frozen=True)
class Resolution:
    """width/height 중 None인 쪽은 원본 비율로 자동 계산한다."""

    width: int | None
    height: int | None

    def __post_init__(self) -> None:
        if self.width is None and self.height is None:
            raise ValueError("해상도에는 가로 또는 세로가 필요합니다.")
        for name, v in (("가로", self.width), ("세로", self.height)):
            if v is not None and (v <= 0 or v % 2):
                raise ValueError(f"{name} 값은 2 이상의 짝수여야 합니다 (H.264 요구사항): {v}")


def parse_resolution(text: str) -> Resolution:
    """'1280x720', '1280x'(가로만), 'x720'(세로만), '720p'(세로 기준), '4k' 형식을 받는다."""
    s = text.strip().lower()
    if s in RESOLUTION_ALIASES:
        return Resolution(None, RESOLUTION_ALIASES[s])
    m = re.fullmatch(r"(\d+)p", s)
    if m:
        return Resolution(None, int(m.group(1)))
    m = re.fullmatch(r"(\d*)[x×](\d*)", s)
    if m and (m.group(1) or m.group(2)):
        return Resolution(int(m.group(1)) if m.group(1) else None,
                          int(m.group(2)) if m.group(2) else None)
    raise ValueError(f"해상도 형식이 올바르지 않습니다: {text!r} (예: 1280x720, 720p, x480)")


def parse_fps(text: str) -> Fraction:
    """'30', '29.97', '30000/1001' 형식을 받는다."""
    try:
        fps = Fraction(text.strip())
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"프레임레이트 형식이 올바르지 않습니다: {text!r}") from None
    if not 0 < fps <= 240:
        raise ValueError(f"프레임레이트는 0 초과 240 이하여야 합니다: {text!r}")
    return fps


def parse_sample_rate(text: str) -> int:
    """'48000' 또는 '44.1k' 형식을 받는다."""
    s = text.strip().lower()
    try:
        rate = round(float(s[:-1]) * 1000) if s.endswith("k") else int(s)
    except ValueError:
        raise ValueError(f"샘플레이트 형식이 올바르지 않습니다: {text!r} (예: 44100, 48k)") from None
    if not 8000 <= rate <= 192000:
        raise ValueError(f"샘플레이트는 8000~192000 Hz 범위여야 합니다: {text!r}")
    return rate


@dataclass(frozen=True)
class EditSpec:
    resolution: Resolution | None = None
    fps: Fraction | None = None
    sample_rate: int | None = None
    fit: str = "contain"  # 가로·세로를 모두 지정했을 때 비율이 다른 경우의 처리 방식

    def __post_init__(self) -> None:
        if self.fit not in FIT_MODES:
            raise ValueError(f"fit은 {FIT_MODES} 중 하나여야 합니다: {self.fit!r}")

    @property
    def is_empty(self) -> bool:
        return self.resolution is None and self.fps is None and self.sample_rate is None
