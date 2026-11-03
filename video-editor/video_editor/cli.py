"""명령줄 인터페이스: info / convert."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from .commands import NoChangesError, build_command
from .options import FIT_MODES, EditSpec, parse_fps, parse_resolution, parse_sample_rate
from .probe import MediaInfo, probe


def format_info(info: MediaInfo) -> str:
    lines = [f"파일: {info.path}"]
    if info.duration is not None:
        lines.append(f"길이: {info.duration:.2f}초")
    if info.has_video:
        fps = f"{float(info.fps):.3f}".rstrip("0").rstrip(".") if info.fps else "?"
        lines.append(f"영상: {info.width}x{info.height}, {fps} fps, {info.video_codec}")
    else:
        lines.append("영상: 없음")
    lines.append(f"오디오: {info.sample_rate} Hz, {info.audio_codec}" if info.has_audio else "오디오: 없음")
    return "\n".join(lines)


def _default_output(src: Path) -> Path:
    return src.with_name(f"{src.stem}_edited{src.suffix}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="video_editor", description="간단한 동영상 변환 도구 (ffmpeg 기반)")
    sub = p.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="파일의 해상도/FPS/샘플레이트 확인")
    info.add_argument("input", type=Path)

    c = sub.add_parser("convert", help="해상도 / 프레임레이트 / 오디오 샘플레이트 변경")
    c.add_argument("input", type=Path)
    c.add_argument("-o", "--output", type=Path, help="출력 파일 (기본: <이름>_edited.<확장자>)")
    c.add_argument("-r", "--resolution", help="예: 1280x720, 720p, 1280x(가로만), x480(세로만)")
    c.add_argument("-f", "--fps", help="예: 30, 29.97, 30000/1001")
    c.add_argument("-s", "--sample-rate", help="예: 44100, 48000, 44.1k")
    c.add_argument("--fit", choices=FIT_MODES, default="contain",
                   help="가로·세로를 모두 지정했을 때 비율이 다르면: contain=여백 추가(기본), cover=잘라내기, stretch=늘이기")
    c.add_argument("--crf", type=int, default=18, help="영상 품질 (낮을수록 고화질, 기본 18)")
    c.add_argument("--preset", default="medium", help="x264 인코딩 속도 프리셋 (기본 medium)")
    c.add_argument("-y", "--overwrite", action="store_true", help="출력 파일이 있으면 덮어쓰기")
    c.add_argument("--dry-run", action="store_true", help="실행하지 않고 ffmpeg 명령만 출력")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        info = probe(args.input)
        if args.command == "info":
            print(format_info(info))
            return 0

        if not (args.resolution or args.fps or args.sample_rate):
            parser.error("--resolution, --fps, --sample-rate 중 하나 이상을 지정해 주세요.")
        spec = EditSpec(
            resolution=parse_resolution(args.resolution) if args.resolution else None,
            fps=parse_fps(args.fps) if args.fps else None,
            sample_rate=parse_sample_rate(args.sample_rate) if args.sample_rate else None,
            fit=args.fit,
        )
        dst = args.output or _default_output(args.input)
        if dst.exists() and not args.overwrite and not args.dry_run:
            raise FileExistsError(f"출력 파일이 이미 있습니다: {dst} (-y 로 덮어쓰기)")
        cmd = build_command(info, dst, spec, overwrite=args.overwrite, crf=args.crf, preset=args.preset)
        if args.dry_run:
            print(shlex.join(cmd))
            return 0
        print(format_info(info), "\n→", dst, flush=True)
        subprocess.run(cmd, check=True)
        print("완료:", format_info(probe(dst)), sep="\n")
        return 0
    except NoChangesError as e:
        print(e, file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg 실패 (종료 코드 {e.returncode})", file=sys.stderr)
        return e.returncode or 1
    except (ValueError, RuntimeError, OSError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
