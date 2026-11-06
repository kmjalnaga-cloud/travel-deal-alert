import json
import os
import sys
from pathlib import Path

from notify import send_telegram
from sites import fetch_campnic, fetch_yeogi, fetch_yanolja

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / "state.json"

SITE_LABELS = {"yeogi": "여기어때", "yanolja": "야놀자"}

# State key holding the last seen price per place/site/window.
PRICES_KEY = "__prices__"

# Stored in state for dated windows so "became bookable" is diffed like a badge.
OPEN = "__open__"

# State key holding per-room status for camp reservation pages.
CAMP_KEY = "__camp__"


def check_campnic(place: dict, state: dict, drop_percent: float) -> list[tuple[str, str]]:
    """Per-room watch of a camp reservation page for each date in place["dates"].

    Alerts, one message per date: rooms that just became bookable, price drops
    on rooms that stay bookable, and 시설할인 that newly appears.
    """
    cfg = place["campnic"]
    store_all = state.setdefault(CAMP_KEY, {})
    messages = []

    for window in place.get("dates", []):
        check_in, check_out = window["checkIn"], window["checkOut"]
        try:
            rooms = fetch_campnic(
                cfg["url"], cfg.get("groupKey", 2), check_in, check_out, cfg["rooms"]
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {place['name']} {window['label']} 조회 실패: {exc}", file=sys.stderr)
            continue

        store = store_all.setdefault(f"{place['name']}|{window['label']}", {})
        opened, dropped, discounted = [], [], []

        for room in rooms:
            prev = store.get(room["name"])
            was_open = bool(prev and prev["open"])

            if room["available"]:
                if not was_open:
                    opened.append(room)
                else:
                    if room["price"] < prev["price"]:
                        pct = (prev["price"] - room["price"]) / prev["price"] * 100
                        if pct >= drop_percent:
                            dropped.append((room, prev["price"], pct))
                    if room["discount"] and not prev.get("discount"):
                        discounted.append(room)

            store[room["name"]] = {
                "open": room["available"],
                # Keep the last bookable price while sold out, to compare on reopen.
                "price": room["price"] if room["available"] else (prev or room)["price"],
                "discount": room["discount"] if room["available"] else 0,
            }

        if not (opened or dropped or discounted):
            continue

        lines = [f"[판타스틱 캠프닉] {window['label']} ({check_in}~{check_out})"]
        if opened:
            lines.append("예약 가능해졌어요: " + _camp_rooms_text(opened))
        for room, old, pct in dropped:
            lines.append(
                f"가격 하락: {_camp_short(room['name'])} {old:,}원 → {room['price']:,}원 (-{pct:.0f}%)"
            )
        if discounted:
            lines.append(
                "시설할인: "
                + ", ".join(f"{_camp_short(r['name'])} {r['discount']:,}원" for r in discounted)
            )
        messages.append((check_in, "\n".join(lines)))

    return messages


def _camp_short(name: str) -> str:
    """'카라반 02 (8.5평)' -> '카라반 02'; '글램핑01' -> '글램핑01'."""
    return name.split("(")[0].strip()


def _camp_rooms_text(rooms: list[dict]) -> str:
    """Group same-price rooms: '글램핑 01·02 150,000원, 카라반 02 190,000원(시설할인 10,000원)'."""
    groups: dict[tuple, list[str]] = {}
    for r in rooms:
        short = _camp_short(r["name"])
        family = short.rstrip("0123456789 ").strip() or short
        number = short[len(family):].strip()
        groups.setdefault((family, r["price"], r["discount"]), []).append(number or short)
    parts = []
    for (family, price, discount), numbers in groups.items():
        text = f"{family} {'·'.join(numbers)} {price:,}원"
        if discount:
            text += f"(시설할인 {discount:,}원)"
        parts.append(text)
    return ", ".join(parts)


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def check_place(
    place: dict,
    state: dict,
    keywords: list[str] | None = None,
    drop_percent: float = 5,
) -> list[tuple[str, str]]:
    """Returns (check-in date, alert message) pairs for this place.

    Tonight's stay has an empty date so it sorts first; main() orders all
    messages by this date.

    Checks tonight's stay unless place["checkTonight"] is false; each entry in
    place["dates"] adds a window that also alerts when its dates become
    bookable. A place with "enabled": false is skipped entirely. Badges are
    alerted only when they contain one of `keywords` (all badges if None), and
    a price drop of at least `drop_percent` vs. the last seen price is alerted
    too.
    """
    messages = []
    if not place.get("enabled", True):
        return messages
    if "campnic" in place:
        return check_campnic(place, state, drop_percent)
    prices = state.setdefault(PRICES_KEY, {})
    windows = ([{}] if place.get("checkTonight", True) else []) + place.get("dates", [])

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

            if keywords is not None:
                badges = [b for b in badges if any(k in b for k in keywords)]
            if window_label:
                # Promo text on dates that can't be booked isn't actionable.
                badges = list(badges) + [OPEN] if price else []

            matched = sorted(set(badges))
            previous = set(state.get(state_key, []))
            new_items = [b for b in matched if b not in previous]

            prev_price = prices.get(state_key)
            dropped = None
            if price and prev_price and price < prev_price:
                pct = (prev_price - price) / prev_price * 100
                if pct >= drop_percent:
                    dropped = (prev_price, pct)
            if price:
                prices[state_key] = price

            if new_items or dropped:
                title = f"[{label}] {place['name']}"
                if window_label:
                    title += f" · {window_label} ({check_in}~{check_out})"
                lines = [title]
                if OPEN in new_items:
                    lines.append("예약 가능해졌어요")
                new_badges = [b for b in new_items if b != OPEN]
                if new_badges:
                    lines.append(f"배지: {', '.join(new_badges)}")
                if dropped:
                    lines.append(
                        f"가격: {price:,}원 (이전 {dropped[0]:,}원, -{dropped[1]:.0f}%)"
                    )
                else:
                    lines.append(f"가격: {price:,}원~" if price else "가격 정보 없음")
                messages.append((check_in or "", "\n".join(lines)))

            state[state_key] = matched

    return messages


def main():
    config = load_json(CONFIG_PATH, {"places": []})
    state = load_json(STATE_PATH, {})

    all_messages = []
    for place in config["places"]:
        all_messages.extend(
            check_place(
                place,
                state,
                config.get("keywords"),
                config.get("priceDropPercent", 5),
            )
        )

    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if all_messages:
        # Stable sort: same date keeps place order, then 여기어때 before 야놀자.
        all_messages.sort(key=lambda m: m[0])
        text = "🏨 특가 알림\n\n" + "\n\n".join(m[1] for m in all_messages)
        if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
            send_telegram(text)
        else:
            print("[dry-run] TELEGRAM_BOT_TOKEN/CHAT_ID 미설정, 전송 생략", file=sys.stderr)
        print(text)
    else:
        print("새로운 특가 없음")


if __name__ == "__main__":
    main()
