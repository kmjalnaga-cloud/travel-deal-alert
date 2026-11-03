"""EditSpec + 원본 정보로 ffmpeg 명령줄을 만든다 (실행은 하지 않음)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from .options import EditSpec, Resolution
from .probe import MediaInfo

SUPPORTED_EXTENSIONS = (".mp4", ".mov", ".mkv")


class NoChangesError(ValueError):
    """요청한 값이 이미 원본과 같아서 할 작업이 없을 때."""


def resolve_size(src_w: int, src_h: int, res: Resolution) -> tuple[int, int]:
    """한쪽만 지정된 경우 원본 비율로 나머지를 계산한다 (짝수로 반올림)."""
    if res.width and res.height:
        return res.width, res.height

    def even(x: float) -> int:
        return max(2, 2 * round(x / 2))

    if res.height:
        return even(src_w * res.height / src_h), res.height
    return res.width, even(src_h * res.width / src_w)


def _scale_filter(res: Resolution, fit: str) -> str:
    w, h = res.width, res.height
    if not (w and h):  # 한쪽만 지정: ffmpeg가 비율 유지 + 짝수 보정(-2)
        return f"scale={w or -2}:{h or -2}"
    if fit == "stretch":
        return f"scale={w}:{h}"
    if fit == "cover":  # 꽉 채우고 넘치는 부분은 잘라냄
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    # contain: 비율 유지, 남는 부분은 검은 여백
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")


def _fmt_fps(fps: Fraction) -> str:
    return str(fps.numerator) if fps.denominator == 1 else f"{fps.numerator}/{fps.denominator}"


def build_command(
    src: MediaInfo,
    dst: str | Path,
    spec: EditSpec,
    *,
    overwrite: bool = False,
    crf: int = 18,
    preset: str = "medium",
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """변경이 필요한 스트림만 재인코딩하고, 나머지는 복사(copy)한다."""
    dst = Path(dst)
    if dst.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 출력 형식입니다: {dst.suffix!r} (지원: {', '.join(SUPPORTED_EXTENSIONS)})")
    if dst.resolve() == src.path.resolve():
        raise ValueError("입력과 출력 파일이 같습니다. 다른 이름을 지정해 주세요.")
    if not src.has_video and not src.has_audio:
        raise ValueError("영상/오디오 스트림이 없는 파일입니다.")

    vf: list[str] = []
    if src.has_video:
        # fps를 먼저 줄이면 scale 할 프레임 수가 줄어 더 빠르다
        if spec.fps is not None and spec.fps != src.fps:
            vf.append(f"fps={_fmt_fps(spec.fps)}")
        if spec.resolution is not None:
            target = resolve_size(src.width, src.height, spec.resolution)
            if target != (src.width, src.height):
                vf.append(_scale_filter(spec.resolution, spec.fit))
                vf.append("setsar=1")
    encode_audio = (
        src.has_audio and spec.sample_rate is not None and spec.sample_rate != src.sample_rate
    )
    if not vf and not encode_audio:
        raise NoChangesError("요청한 설정이 원본과 이미 같습니다. 변경할 내용이 없습니다.")

    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-stats",
           "-y" if overwrite else "-n", "-i", str(src.path)]
    if vf:
        cmd += ["-vf", ",".join(vf),
                "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p"]
    elif src.has_video:
        cmd += ["-c:v", "copy"]
    if encode_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", str(spec.sample_rate)]
    elif src.has_audio:
        cmd += ["-c:a", "copy"]
    if dst.suffix.lower() in (".mp4", ".mov"):
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(dst))
    return cmd
