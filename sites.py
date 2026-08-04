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


def today_tomorrow_kst():
    today = datetime.now(KST).date()
    return today.isoformat(), (today + timedelta(days=1)).isoformat()


def fetch_yeogi(name: str, place_id: int, dong_code: str):
    """Returns (found: bool, price: int|None, badges: list[str])."""
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


def fetch_yanolja(name: str, place_id: int):
    """Returns (found: bool, price: int|None, badges: list[str])."""
    url = f"https://nol.yanolja.com/stay/domestic/{place_id}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text

    if str(place_id) not in html:
        return False, None, []

    badges = []
    for key in ("benefitBadges", "badgeList", "rateBadges"):
        for m in re.finditer(rf'\\"{key}\\":\[(.*?)\]', html):
            for label_m in re.finditer(r'\\"label\\":\\"([^"\\]+)\\"', m.group(1)):
                badges.append(label_m.group(1))

    price = None
    rate_m = re.search(r'\\"rate\\":\\"([\d,]+)\\"', html)
    if rate_m:
        price = int(rate_m.group(1).replace(",", ""))

    return True, price, badges
