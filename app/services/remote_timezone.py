"""Resolve maintenance regions to IANA zones without fixed UTC offsets."""

import re

import pytz

ALIASES = {
    "东京": "Asia/Tokyo",
    "大阪": "Asia/Tokyo",
    "日本": "Asia/Tokyo",
    "首尔": "Asia/Seoul",
    "韩国": "Asia/Seoul",
    "新加坡": "Asia/Singapore",
    "sg": "Asia/Singapore",
    "纽约": "America/New_York",
    "nyc": "America/New_York",
    "洛杉矶": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "法兰克福": "Europe/Berlin",
    "frankfurt": "Europe/Berlin",
    "德国": "Europe/Berlin",
    "伦敦": "Europe/London",
    "英国": "Europe/London",
    "香港": "Asia/Hong_Kong",
    "台湾": "Asia/Taipei",
    "台北": "Asia/Taipei",
    "北京": "Asia/Shanghai",
    "上海": "Asia/Shanghai",
    "广州": "Asia/Shanghai",
    "china": "Asia/Shanghai",
    "cn": "Asia/Shanghai",
    "中国内地": "Asia/Shanghai",
    "japan": "Asia/Tokyo",
    "osaka": "Asia/Tokyo",
    "germany": "Europe/Berlin",
    "united kingdom": "Europe/London",
    "uk": "Europe/London",
    "深圳": "Asia/Shanghai",
    "中国": "Asia/Shanghai",
    "中国大陆": "Asia/Shanghai",
    "悉尼": "Australia/Sydney",
    "墨尔本": "Australia/Melbourne",
}
CITY_ZONES = {zone.rsplit("/", 1)[-1].replace("_", " ").casefold(): zone for zone in pytz.common_timezones}


def region_timezone(region: str) -> str | None:
    parts = re.split(r"\s*[/／>|,，·]\s*", (region or "").strip())
    for part in reversed(parts):
        key = part.strip().replace("_", " ").casefold()
        if key in ALIASES:
            return ALIASES[key]
        if key in CITY_ZONES:
            return CITY_ZONES[key]
        zones = pytz.country_timezones.get(part.upper(), [])
        if len(zones) == 1:
            return zones[0]
    return None
