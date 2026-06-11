from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup


PILIAPP_BASE = "https://kr.piliapp.com/apple-emoji/search/?q="


def fetch_emoji_candidates(keywords: str) -> list:
    results = []
    for kw in [k.strip() for k in keywords.replace(",", " ").split() if k.strip()]:
        try:
            url = PILIAPP_BASE + requests.utils.quote(kw)
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("li.emoji-item")[:5]:
                char = item.get("data-emoji", "")
                name = item.get("title", "")
                img = item.select_one("img")
                img_url = img["src"] if img and img.get("src") else ""
                if char:
                    results.append({"name": name, "char": char, "img_url": img_url, "keyword": kw})
        except Exception:
            pass
    return results


def pick_emoji_with_claude(candidates: list, main_copy: str, sub_copy: str, api_key: str, count: int = 2) -> list:
    if not candidates or not api_key:
        return candidates[:count]
    try:
        import anthropic  # lazy — optional dependency
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


def fetch_emoji_png(img_url: str) -> bytes:
    if not img_url:
        return None
    try:
        resp = requests.get(img_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None


def recommend_color_with_claude(main_copy: str, sub_copy: str, api_key: str) -> str:
    if not api_key:
        return "#CC0000"
    try:
        import anthropic  # lazy — optional dependency
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
