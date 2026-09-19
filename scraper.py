import json
import os
import sys
from pathlib import Path

from notify import send_telegram
from sites import fetch_yeogi, fetch_yanolja

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / "state.json"

SITE_LABELS = {"yeogi": "여기어때", "yanolja": "야놀자"}

# Stored in state for dated windows so "became bookable" is diffed like a badge.
OPEN = "__open__"


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def check_place(place: dict, state: dict) -> list[str]:
    """Returns a list of alert messages for this place.

    Always checks tonight's stay; each entry in place["dates"] adds a window
    that also alerts when its dates become bookable.
    """
    messages = []
    windows = [{}] + place.get("dates", [])

    for window in windows:
        window_label = window.get("label")
        check_in, check_out = window.get("checkIn"), window.get("checkOut")

        for site, label in SITE_LABELS.items():
            site_cfg = place.get(site)
            if not site_cfg:
                continue

            state_key = f"{place['name']}|{site}"
            if window_label:
                state_key += f"|{window_label}"

            try:
                if site == "yeogi":
                    found, price, badges = fetch_yeogi(
                        place["name"], site_cfg["id"], site_cfg["dong_code"],
                        check_in, check_out,
                    )
                else:
                    found, price, badges = fetch_yanolja(
                        place["name"], site_cfg["id"], check_in, check_out
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {label} {place['name']} 조회 실패: {exc}", file=sys.stderr)
                continue

            if not found:
                continue

            if window_label:
                # Promo text on dates that can't be booked isn't actionable.
                badges = list(badges) + [OPEN] if price else []

            matched = sorted(set(badges))
            previous = set(state.get(state_key, []))
            new_items = [b for b in matched if b not in previous]

            if new_items:
                title = f"[{label}] {place['name']}"
                if window_label:
                    title += f" · {window_label} ({check_in}~{check_out})"
                lines = [title]
                if OPEN in new_items:
                    lines.append("예약 가능해졌어요")
                new_badges = [b for b in new_items if b != OPEN]
                if new_badges:
                    lines.append(f"배지: {', '.join(new_badges)}")
                lines.append(f"가격: {price:,}원~" if price else "가격 정보 없음")
                messages.append("\n".join(lines))

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
