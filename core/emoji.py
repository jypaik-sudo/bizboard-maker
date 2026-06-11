from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

PILIAPP_BASE = "https://kr.piliapp.com/apple-emoji/search/?q="
TWEMOJI_CDN  = "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{}.png"

# 한국어 키워드 → Twemoji hex 코드 (piliapp 스크래핑 실패 시 폴백)
_KO_TWEMOJI: dict[str, list[str]] = {
    # 날씨 / 자연
    "여름":     ["2600",  "1f31e", "1f3d6"],
    "태양":     ["2600",  "1f31e"],
    "겨울":     ["2744",  "26c4",  "1f9ca"],
    "봄":       ["1f338", "1f33a"],
    "가을":     ["1f342", "1f343"],
    "비":       ["1f327", "2614"],
    "눈":       ["2744",  "1f328"],
    "바람":     ["1f32c", "1f343"],
    "달":       ["1f319", "1f315"],
    "밤":       ["1f319", "2728"],
    "구름":     ["2601",  "26c5"],
    "무지개":   ["1f308", "2728"],

    # 직장 / 업무
    "직장인":   ["1f4bc", "1f454"],
    "야근":     ["1f319", "1f4bc"],
    "아근":     ["1f319", "1f4bc"],   # 야근 오타
    "컴퓨터":   ["1f4bb", "1f5a5"],
    "노트북":   ["1f4bb", "2728"],
    "문서":     ["1f4c4", "1f4dd"],
    "회사":     ["1f3e2", "1f4bc"],
    "업무":     ["1f4bc", "1f4cb"],
    "오피스":   ["1f3e2", "1f4bc"],
    "키링":     ["1f511", "2728"],
    "선물":     ["1f381", "2728"],
    "파우치":   ["1f45c", "2728"],
    "다이어리": ["1f4d3", "1f4dd"],
    "메모":     ["1f4dd", "2728"],

    # 감정 / 표현
    "하트":     ["2764",  "1f495"],
    "사랑":     ["2764",  "1f495"],
    "행복":     ["1f60a", "1f31f"],
    "귀여운":   ["1f436", "2728"],
    "귀여워":   ["1f436", "2728"],
    "별":       ["2b50",  "2728"],
    "반짝":     ["2728",  "1f31f"],
    "스파클":   ["2728",  "1f31f"],
    "파이팅":   ["1f4aa", "1f525"],
    "응원":     ["1f389", "1f4aa"],
    "파티":     ["1f389", "1f38a"],

    # 음식 / 음료
    "레몬":     ["1f34b", "1f9c3"],
    "토마토":   ["1f345"],
    "딸기":     ["1f353"],
    "복숭아":   ["1f351", "1f338"],
    "수박":     ["1f349", "2600"],
    "포도":     ["1f347"],
    "파인애플": ["1f34d", "2600"],
    "체리":     ["1f352"],
    "블루베리": ["1fad0"],
    "커피":     ["2615",  "1f9cb"],
    "음료":     ["1f964", "2615"],
    "케이크":   ["1f382", "1f370"],
    "아이스크림": ["1f366", "1f9c1"],
    "도넛":     ["1f369"],
    "쿠키":     ["1f36a"],
    "피자":     ["1f355"],

    # 패션 / 쇼핑
    "쇼핑":     ["1f6cd", "1f4b3"],
    "패션":     ["1f457", "2728"],
    "옷":       ["1f457", "1f455"],
    "가방":     ["1f45c", "1f6cd"],
    "신발":     ["1f45f", "1f460"],
    "구두":     ["1f460", "2728"],
    "샌들":     ["1f461", "2600"],
    "악세서리": ["2728",  "1f48e"],
    "주얼리":   ["1f48e", "2728"],
    "반지":     ["1f48d", "2728"],
    "목걸이":   ["1f4ff", "2728"],
    "시계":     ["231a",  "2728"],
    "선글라스": ["1f576", "2600"],
    "모자":     ["1f9e2", "2728"],
    "양말":     ["1f9e6"],

    # 뷰티 / 스킨케어
    "뷰티":     ["1f484", "1f338"],
    "스킨케어": ["1f9f4", "2728"],
    "스킨":     ["1f9f4", "2728"],
    "립스틱":   ["1f484", "1f48b"],
    "립":       ["1f484", "1f48b"],
    "향수":     ["1f9f4", "1f338"],
    "크림":     ["1f9f4", "1f338"],
    "마스크":   ["1f9f4", "1f338"],
    "팩":       ["1f9f4", "2728"],
    "아이섀도": ["1f484", "2728"],
    "네일":     ["1f485", "2728"],
    "매니큐어": ["1f485", "2728"],
    "쿠션":     ["1f484", "2728"],
    "파운데이션": ["1f484", "2728"],

    # 쇼핑 혜택
    "할인":     ["1f4b0", "1f3f7"],
    "sale":     ["1f4b0", "2728"],
    "세일":     ["1f4b0", "2728"],
    "쿠폰":     ["1f3f7", "2728"],
    "무료":     ["1f381", "2728"],
    "혜택":     ["1f4b0", "2728"],
    "신상":     ["1f195", "2728"],
    "한정":     ["23f0",  "1f525"],
    "특가":     ["1f4b8", "1f525"],
    "이벤트":   ["1f389", "2728"],

    # 스포츠 / 활동
    "여행":     ["1f30d", "1f9f3"],
    "캠핑":     ["1f3d5", "1f525"],
    "헬스":     ["1f4aa", "1f3cb"],
    "운동":     ["1f3c3", "1f4aa"],
    "스포츠":   ["1f3c5", "26bd"],
    "수영":     ["1f3ca", "1f30a"],
    "산책":     ["1f6b6", "1f33f"],
    "요가":     ["1f9d8", "1f33f"],
    "등산":     ["1f9d7", "26f0"],
    "자전거":   ["1f6b4", "1f31f"],

    # 홈 / 리빙
    "집":       ["1f3e0", "2728"],
    "홈":       ["1f3e0", "2728"],
    "인테리어": ["1f3e0", "1f33c"],
    "꽃":       ["1f338", "1f33c"],
    "식물":     ["1f331", "1f33f"],
    "캔들":     ["1f56f", "1f338"],

    # 기술 / 전자
    "폰":       ["1f4f1", "2728"],
    "폰케이스": ["1f4f1", "2728"],
    "이어폰":   ["1f3a7", "1f4fb"],
    "음악":     ["1f3b5", "1f3a7"],
    "게임":     ["1f3ae", "1f4bb"],
    "카메라":   ["1f4f7", "2728"],

    # 동물 / 캐릭터
    "강아지":   ["1f436", "1f9e1"],
    "고양이":   ["1f431", "2728"],
    "곰":       ["1f43b", "2728"],
    "토끼":     ["1f430", "1f338"],
    "펭귄":     ["1f427", "1f9ca"],
    "공룡":     ["1f996", "2728"],
    "유니콘":   ["1f984", "2728"],
    "팬더":     ["1f43c", "2728"],

    # 계절 / 행사
    "크리스마스": ["1f384", "2744"],
    "할로윈":   ["1f383", "1f987"],
    "새해":     ["1f386", "1f389"],
    "추석":     ["1f315", "1f338"],
    "발렌타인": ["2764",  "1f36b"],
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
                    "name":    kw,
                    "char":    "",
                    "img_url": TWEMOJI_CDN.format(code),
                    "keyword": kw,
                })
    if not results:
        for code in _DEFAULT_CODES:
            results.append({
                "name":    "sparkle",
                "char":    "✨",
                "img_url": TWEMOJI_CDN.format(code),
                "keyword": "",
            })
    return results


def fetch_emoji_candidates(keywords: str) -> list[dict]:
    results: list[dict] = []
    for kw in [k.strip() for k in keywords.replace(",", " ").split() if k.strip()]:
        try:
            url  = PILIAPP_BASE + requests.utils.quote(kw)
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
                        "name":    name,
                        "char":    char,
                        "img_url": img_url,
                        "keyword": kw,
                    })
        except Exception:
            pass

    # piliapp 실패 / 결과 없음 → Twemoji 폴백
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
    main_copy: str, sub_copy: str, api_key: str,
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
