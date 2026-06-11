from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

PILIAPP_BASE  = "https://kr.piliapp.com/apple-emoji/search/?q="
TWEMOJI_CDN   = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{}.png"

# 한국어 키워드 → Twemoji 코드 폴백 (piliapp 실패 시)
_KO_TWEMOJI: dict[str, list[str]] = {
    "여름":  ["2600",  "1f31e", "1f3d6"],
    "태양":  ["2600",  "1f31e"],
    "겨울":  ["2744",  "26c4",  "1f9ca"],
    "봄":    ["1f338", "1f33a"],
    "가을":  ["1f342", "1f343"],
    "하트":  ["2764",  "1f495", "1f49c"],
    "별":    ["2b50",  "2728",  "1f31f"],
    "불꽃":  ["1f525", "2728"],
    "할인":  ["1f4b0", "1f3f7"],
    "sale":  ["1f4b0", "2728"],
    "세일":  ["1f4b0", "2728"],
    "쿠폰":  ["1f3f7", "2728"],
    "무료":  ["1f381", "2728"],
    "쇼핑":  ["1f6cd", "1f4b3"],
    "패션":  ["1f457", "2728"],
    "뷰티":  ["1f484", "1f338"],
    "스킨":  ["1f9f4", "2728"],
    "신상":  ["1f195", "2728"],
    "한정":  ["23f0",  "1f525"],
}
_DEFAULT_CODES = ["2728", "1f31f", "2b50"]   # ✨ 🌟 ⭐


def _twemoji_candidates(keywords: str) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for kw in [k.strip().lower() for k in keywords.replace(",", " ").split() if k.strip()]:
        codes = _KO_TWEMOJI.get(kw, [])
        for code in codes:
            if code not in seen:
                seen.add(code)
                results.append({
                    "name": kw,
                    "char": "",
                    "img_url": TWEMOJI_CDN.format(code),
                    "keyword": kw,
                })
    if not results:
        for code in _DEFAULT_CODES:
            results.append({
                "name": "sparkle",
                "char": "✨",
                "img_url": TWEMOJI_CDN.format(code),
                "keyword": "",
            })
    return results


def fetch_emoji_candidates(keywords: str) -> list[dict]:
    results: list[dict] = []
    for kw in [k.strip() for k in keywords.replace(",", " ").split() if k.strip()]:
        try:
            url = PILIAPP_BASE + requests.utils.quote(kw)
            resp = requests.get(url, timeout=8,
                                headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("li.emoji-item")[:5]:
                char    = item.get("data-emoji", "")
                name    = item.get("title", "")
                img_tag = item.select_one("img")
                img_url = img_tag["src"] if img_tag and img_tag.get("src") else ""
                if char:
                    results.append({
                        "name": name, "char": char,
                        "img_url": img_url, "keyword": kw,
                    })
        except Exception:
            pass

    # piliapp 실패 시 Twemoji CDN 폴백
    if not results:
        results = _twemoji_candidates(keywords)

    return results


def pick_emoji_with_claude(
    candidates: list[dict],
    main_copy: str, sub_copy: str,
    api_key: str, count: int = 2,
) -> list[dict]:
    if not candidates:
        return []
    if not api_key:
        return candidates[:count]
    try:
        import anthropic
        candidate_str = "\n".join(
            f"{i+1}. {c['char']} ({c['name']}) — 키워드: {c['keyword']}"
            for i, c in enumerate(candidates)
        )
        prompt = (
            f"카카오 비즈보드 광고 소재에 어울리는 이모티콘 {count}개를 골라 번호만 쉼표로 답해주세요.\n"
            f"메인카피: {main_copy}\n서브카피: {sub_copy}\n후보:\n{candidate_str}"
        )
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        indices = [int(x.strip()) - 1 for x in text.split(",") if x.strip().isdigit()]
        return [candidates[i] for i in indices if 0 <= i < len(candidates)]
    except Exception:
        return candidates[:count]


def fetch_emoji_png(img_url: str) -> bytes | None:
    if not img_url:
        return None
    try:
        resp = requests.get(img_url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None


def recommend_color_with_claude(
    main_copy: str, sub_copy: str, api_key: str
) -> str:
    if not api_key:
        return "#CC0000"
    try:
        import anthropic
        prompt = (
            f"카카오 비즈보드 뱃지/강조 텍스트 색상을 추천해주세요.\n"
            f"메인카피: {main_copy}\n서브카피: {sub_copy}\n"
            f"조건: 무채색 금지, 선명한 색상, HEX만 답변. 예: #E8272A"
        )
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        match = re.search(r"#[0-9A-Fa-f]{6}", msg.content[0].text)
        if match:
            return match.group(0)
    except Exception:
        pass
    return "#CC0000"
