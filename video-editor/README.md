# video-editor

ffmpeg 기반의 간단한 동영상 변환 도구. 외부 Python 패키지 없이 표준 라이브러리만 사용합니다.

## 기능

| 기능 | 옵션 | 예시 |
|---|---|---|
| 해상도 변경 | `-r, --resolution` | `1280x720`, `720p`(세로 기준), `1280x`(가로만), `x480`(세로만), `4k` |
| 프레임레이트 변경 | `-f, --fps` | `30`, `29.97`, `30000/1001` |
| 오디오 샘플레이트 변경 | `-s, --sample-rate` | `44100`, `48000`, `44.1k` |

- 바꿀 필요가 없는 스트림은 **재인코딩 없이 복사**합니다. (예: 샘플레이트만 바꾸면 영상은 그대로 복사)
- 한쪽만 지정하면 원본 비율을 유지하고, 가로·세로를 둘 다 지정했는데 비율이 다르면 `--fit`으로 처리 방식을 고릅니다.
  `contain`(기본, 검은 여백) / `cover`(꽉 채우고 잘라냄) / `stretch`(늘임)
- 요청한 값이 이미 원본과 같으면 아무것도 하지 않고 종료 코드 1을 반환합니다.

## 요구사항

ffmpeg / ffprobe (PATH에 있어야 함), Python 3.10+

## 사용법

```bash
cd video-editor
python -m video_editor info input.mp4
python -m video_editor convert input.mp4 -r 720p -f 30 -s 44100 -o output.mp4
python -m video_editor convert input.mp4 -r 1080x1080 --fit cover -y   # 정사각형으로 잘라내기
python -m video_editor convert input.mp4 -f 24 --dry-run               # ffmpeg 명령만 출력
```

출력 파일을 지정하지 않으면 `<이름>_edited.<확장자>`로 저장되며, 이미 있으면 `-y` 없이는 덮어쓰지 않습니다.

## 제한 사항

- 출력 형식: `.mp4`, `.mov`, `.mkv` (H.264 + AAC)
- 영상 1개·오디오 1개 스트림만 처리합니다 (자막, 추가 오디오 트랙은 버려짐).
- 해상도는 H.264 요구사항에 따라 짝수만 허용합니다.

## 구조

```
video_editor/
  probe.py     ffprobe로 원본 정보 읽기 (MediaInfo)
  options.py   입력 파싱 + EditSpec (해상도/FPS/샘플레이트)
  commands.py  EditSpec -> ffmpeg 명령줄 생성 (실행 안 함, 테스트 쉬움)
  cli.py       argparse CLI
```

GUI 등을 붙일 때는 `probe()` → `build_command()` → `subprocess.run()` 흐름을 그대로 재사용하면 됩니다.

## 테스트

```bash
python -m unittest discover -s tests -t .
```
