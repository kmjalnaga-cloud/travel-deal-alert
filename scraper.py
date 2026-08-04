import json
import os
import sys
from pathlib import Path

from notify import send_telegram
from sites import fetch_yeogi, fetch_yanolja

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / "state.json"

SITE_LABELS = {"yeogi": "여기어때", "yanolja": "야놀자"}


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def check_place(place: dict, state: dict) -> list[str]:
    """Returns a list of alert messages for this place."""
    messages = []

    for site, label in SITE_LABELS.items():
        site_cfg = place.get(site)
        if not site_cfg:
            continue

        state_key = f"{place['name']}|{site}"
        try:
            if site == "yeogi":
                found, price, badges = fetch_yeogi(
                    place["name"], site_cfg["id"], site_cfg["dong_code"]
                )
            else:
                found, price, badges = fetch_yanolja(place["name"], site_cfg["id"])
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {label} {place['name']} 조회 실패: {exc}", file=sys.stderr)
            continue

        if not found:
            continue

        matched = sorted(set(badges))
        previous = set(state.get(state_key, []))
        new_badges = [b for b in matched if b not in previous]

        if new_badges:
            price_text = f"{price:,}원~" if price else "가격 정보 없음"
            messages.append(
                f"[{label}] {place['name']}\n"
                f"배지: {', '.join(new_badges)}\n"
                f"가격: {price_text}"
            )

        state[state_key] = matched

    return messages


def main():
    config = load_json(CONFIG_PATH, {"places": []})
    state = load_json(STATE_PATH, {})

    all_messages = []
    for place in config["places"]:
        all_messages.extend(check_place(place, state))

    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if all_messages:
        text = "🏨 특가 알림\n\n" + "\n\n".join(all_messages)
        if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
            send_telegram(text)
        else:
            print("[dry-run] TELEGRAM_BOT_TOKEN/CHAT_ID 미설정, 전송 생략", file=sys.stderr)
        print(text)
    else:
        print("새로운 특가 없음")


if __name__ == "__main__":
    main()
