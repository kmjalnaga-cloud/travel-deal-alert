import html as htmllib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

KST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


SOLD_OUT_RE = re.compile(
    r'\\"rate\\":\\"([\d,]+)\\",\\"nights\\":[^,]*,\\"averageRate\\":[^,]*,\\"soldOut\\":(true|false)'
)


def today_tomorrow_kst():
    today = datetime.now(KST).date()
    return today.isoformat(), (today + timedelta(days=1)).isoformat()


def fetch_yeogi(name: str, place_id: int, dong_code: str, check_in=None, check_out=None):
    """Returns (found: bool, price: int|None, badges: list[str]).

    price is None when the dates are not bookable (not open yet or sold out).
    """
    if not check_in or not check_out:
        check_in, check_out = today_tomorrow_kst()
    url = (
        "https://www.yeogi.com/domestic-accommodations"
        f"?keyword={quote(name)}&autoKeyword={quote(name)}"
        f"&checkIn={check_in}&checkOut={check_out}&personal=2"
        f"&dongCode={dong_code}&ano={place_id}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    match = NEXT_DATA_RE.search(resp.text)
    if not match:
        raise RuntimeError("__NEXT_DATA__ not found in yeogi response")
    data = json.loads(match.group(1))
    accommodations = data["props"]["pageProps"].get("accommodationsData", [])

    for acc in accommodations:
        if acc.get("meta", {}).get("id") != place_id:
            continue
        badges = []
        for promo in acc.get("promotions", []) or []:
            for b in promo.get("content", {}).get("badges", []) or []:
                if b.get("text"):
                    badges.append(b["text"])
        stay = acc.get("room", {}).get("stay", {}) or {}
        for b in stay.get("badges", []) or []:
            if b.get("text"):
                badges.append(b["text"])
        price = (stay.get("price") or {}).get("discountPrice")
        return True, price, badges

    return False, None, []


def fetch_yanolja(name: str, place_id: int, check_in=None, check_out=None):
    """Returns (found: bool, price: int|None, badges: list[str]).

    Without dates the site defaults to tonight. price is None when the dates
    are not bookable (not open yet or sold out).
    """
    url = f"https://nol.yanolja.com/stay/domestic/{place_id}"
    if check_in and check_out:
        url += f"?checkInDate={check_in}&checkOutDate={check_out}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    if str(place_id) not in html:
        return False, None, []

    # Sold-out rooms keep showing their price, so a price alone doesn't mean
    # bookable. Each rate plan is one chunk holding its price, soldOut flag
    # and badges; only chunks with soldOut=false count.
    badges = []
    prices = []
    for plan in html.split('\\"ratePlanId\\":')[1:]:
        sold_m = SOLD_OUT_RE.search(plan)
        if not sold_m or sold_m.group(2) == "true":
            continue
        prices.append(int(sold_m.group(1).replace(",", "")))
        for key in ("benefitBadges", "badgeList", "rateBadges"):
            for m in re.finditer(rf'\\"{key}\\":\[(.*?)\]', plan):
                for label_m in re.finditer(r'\\"label\\":\\"([^"\\]+)\\"', m.group(1)):
                    badges.append(label_m.group(1))

    return True, (min(prices) if prices else None), badges


def fetch_campnic(url: str, group_key: int, check_in: str, check_out: str, prefixes):
    """Rooms of a nowgo-based camp reservation page for one stay.

    Returns a list of dicts: name, available, price (what you pay, after any
    시설할인), discount (0 if none). Only rooms whose name starts with one of
    `prefixes` are kept. Raises if the page has no matching rooms, so a layout
    change or error page isn't mistaken for "everything is sold out".
    """
    resp = requests.get(
        url,
        params={"group_key": group_key, "s_dt": check_in, "e_dt": check_out, "sel": ""},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", resp.text, flags=re.S)
    lines = [
        re.sub(r"\s+", " ", ln).strip()
        for ln in htmllib.unescape(re.sub(r"<[^>]+>", "\n", text)).split("\n")
    ]
    lines = [ln for ln in lines if ln]

    starts = [i for i, ln in enumerate(lines) if "기준" in ln and "최대" in ln]
    rooms = []
    for n, i in enumerate(starts):
        name = lines[i - 1]
        if not name.startswith(tuple(prefixes)):
            continue
        end = starts[n + 1] - 1 if n + 1 < len(starts) else len(lines)
        block = lines[i:end]
        if "가격" not in block:
            continue
        seg = block[block.index("가격") + 1:][:8]
        status = next((x for x in seg if x in ("선택", "예약완료")), None)
        if status is None:
            continue
        nums = [
            int(x.replace(",", "").replace("원", ""))
            for x in seg[:seg.index(status)]
            if re.fullmatch(r"[\d,]+원?", x)
        ]
        if not nums:
            continue
        discount = nums[0] if "시설할인" in seg[:seg.index(status)] and len(nums) >= 3 else 0
        rooms.append(
            {
                "name": name,
                "available": status == "선택",
                "price": nums[-1],
                "discount": discount,
            }
        )
    if not rooms:
        raise RuntimeError("no matching camp rooms found on the page")
    return rooms
