"""간단한 동영상 편집 라이브러리 (ffmpeg 래퍼).

지원 기능: 해상도 변경, 프레임레이트 변경, 오디오 샘플레이트 변경.
"""

from .commands import NoChangesError, build_command
from .options import EditSpec, Resolution, parse_fps, parse_resolution
from .probe import MediaInfo, probe

__all__ = [
    "EditSpec",
    "MediaInfo",
    "NoChangesError",
    "Resolution",
    "build_command",
    "parse_fps",
    "parse_resolution",
    "probe",
]
