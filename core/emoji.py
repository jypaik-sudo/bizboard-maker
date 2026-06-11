from __future__ import annotations
import re
import requests

# Apple iOS emoji CDN (emoji-datasource-apple npm 패키지)
APPLE_CDN = "https://cdn.jsdelivr.net/npm/emoji-datasource-apple@15.1.2/img/apple/64/{}.png"

def _url(code: str) -> str:
    return APPLE_CDN.format(code.upper())

# 카테고리별 전체 이모티콘 카탈로그
EMOJI_CATALOG: dict[str, list[str]] = {
    "✨ 효과/기호":    ["2728","2B50","1F31F","1F4AB","1F4A5","1F525","1F4AF","2714","2757","2665","2666","1F49E","1F4A0"],
    "😊 표정":         ["1F600","1F603","1F604","1F60A","1F970","1F929","1F973","1F60D","1F618","1F917","1F914","1F44D","1F44F","1F64C","1F9E1","1F499","1F49A","1F49B","1F496"],
    "🌸 꽃/식물":      ["1F338","1F33A","1F33B","1F337","1F339","1F340","1F341","1F342","1F343","1F331","1F332","1F333","1F334","1F335","1FAB7","1FAB8"],
    "☀️ 날씨/자연":    ["2600","1F31E","1F327","2614","2744","26C4","1F308","1F32C","1F319","1F315","1F30A","1F4A7","26A1","1F30B","1F30C"],
    "🍓 음식/음료":    ["1F34B","1F353","1F351","1F352","1F347","1F349","1F34D","1F345","1F382","1F370","1F369","1F36A","1F36B","1F36C","2615","1F9CB","1F964","1F366","1F367","1F368","1F355","1F354","1F32D"],
    "👗 패션/의류":    ["1F457","1F455","1F454","1F456","1F459","1F45A","1F45F","1F460","1F461","1F462","1F9E5","1F9E6","1F9E2","1F9E3","1F9E4","1F9E7","1F9E8","1FA70","1FA71","1FA72","1FA73"],
    "👜 가방/악세서리": ["1F45C","1F45B","1F45D","1F6CD","1F48D","1F48E","231A","1F576","1F511","1F381","1F9F3","1F392","1F9F2"],
    "💄 뷰티/스킨케어": ["1F484","1F485","1F48B","1F9F4","1F9F3","1F9F5","1F338","1F9E8","1F9FC","1FA78","1F6C1","1F6C0","1FAE7"],
    "💼 직장/업무":    ["1F4BC","1F454","1F4BB","1F5A5","1F4C4","1F4DD","1F4CB","1F3E2","1F511","1F4D3","1F4D6","1F4C5","1F4CA","1F4CC","1F4CE","1F4CF","1F4D0","1FAA4"],
    "💰 쇼핑/혜택":    ["1F6CD","1F4B0","1F4B8","1F4B3","1F3F7","1F195","1F196","1F197","23F0","1F525","1F4AF","1F389","1F38A","1F381","1F380"],
    "🐶 동물":         ["1F436","1F431","1F43B","1F430","1F427","1F984","1F43C","1F996","1F43E","1F415","1F408","1F407","1F439","1F43F","1F98A","1F98B","1F994","1F987","1F989"],
    "🏋️ 스포츠/활동":  ["1F4AA","1F3C3","1F3CB","1F6B4","1F3CA","1F9D8","1F93A","1F3C5","26BD","26F0","1F6B6","1F9D7","1F6A4","1F3C4","26F9"],
    "✈️ 여행/장소":    ["1F30D","1F3D6","1F3D5","1F6EB","1F697","1F682","1F5FC","1F3EF","26FA","1F30F","1F391","1F3A0","1F3A1","1F3A2","1F3AA"],
    "🏠 홈/리빙":      ["1F3E0","1F33C","1F56F","1F331","1F4A1","1F6CB","1F6BF","1F9FA","1F9F9","1FAB4","1F9F8","1F397","1FAA4","1F9F6","1F9F7"],
    "🎉 기념/파티":    ["1F389","1F38A","1F38B","1F38D","1F38E","1F388","1F382","1F370","1F381","1F4E6","1F942","1F943","1F941","1F3B6","1F3A4","1F3A7","1F3B8"],
    "🌙 밤/달":        ["1F319","1F315","1F316","1F317","1F318","2B50","1F4AB","1F303","1F304","1F305","1F307","1F306"],
    "❤️ 하트/사랑":    ["2764","1F495","1F496","1F497","1F498","1F499","1F49A","1F49B","1F49C","1F49D","1F49E","1F90D","1F90E","1F9E1","1FA77","1FAF6"],
}

# 한국어 키워드 → Apple emoji hex 코드
_KO_TWEMOJI: dict[str, list[str]] = {
    "여름":       ["2600",  "1F31E", "1F3D6"],
    "태양":       ["2600",  "1F31E"],
    "겨울":       ["2744",  "26C4",  "1F9CA"],
    "봄":         ["1F338", "1F33A"],
    "가을":       ["1F342", "1F343"],
    "비":         ["1F327", "2614"],
    "눈":         ["2744",  "1F328"],
    "바람":       ["1F32C", "1F343"],
    "달":         ["1F319", "1F315"],
    "밤":         ["1F319", "2728"],
    "구름":       ["2601",  "26C5"],
    "무지개":     ["1F308", "2728"],
    "직장인":     ["1F4BC", "1F454"],
    "야근":       ["1F319", "1F4BC"],
    "아근":       ["1F319", "1F4BC"],
    "컴퓨터":     ["1F4BB", "1F5A5"],
    "노트북":     ["1F4BB", "2728"],
    "문서":       ["1F4C4", "1F4DD"],
    "회사":       ["1F3E2", "1F4BC"],
    "업무":       ["1F4BC", "1F4CB"],
    "오피스":     ["1F3E2", "1F4BC"],
    "키링":       ["1F511", "2728"],
    "선물":       ["1F381", "2728"],
    "파우치":     ["1F45C", "2728"],
    "다이어리":   ["1F4D3", "1F4DD"],
    "메모":       ["1F4DD", "2728"],
    "하트":       ["2764",  "1F495"],
    "사랑":       ["2764",  "1F495"],
    "행복":       ["1F60A", "1F31F"],
    "귀여운":     ["1F436", "2728"],
    "귀여워":     ["1F436", "2728"],
    "별":         ["2B50",  "2728"],
    "반짝":       ["2728",  "1F31F"],
    "파이팅":     ["1F4AA", "1F525"],
    "응원":       ["1F389", "1F4AA"],
    "파티":       ["1F389", "1F38A"],
    "레몬":       ["1F34B", "1F9C3"],
    "토마토":     ["1F345"],
    "딸기":       ["1F353"],
    "복숭아":     ["1F351", "1F338"],
    "수박":       ["1F349", "2600"],
    "포도":       ["1F347"],
    "파인애플":   ["1F34D", "2600"],
    "체리":       ["1F352"],
    "커피":       ["2615",  "1F9CB"],
    "케이크":     ["1F382", "1F370"],
    "쇼핑":       ["1F6CD", "1F4B3"],
    "패션":       ["1F457", "2728"],
    "옷":         ["1F457", "1F455"],
    "가방":       ["1F45C", "1F6CD"],
    "신발":       ["1F45F", "1F460"],
    "구두":       ["1F460", "2728"],
    "악세서리":   ["2728",  "1F48E"],
    "주얼리":     ["1F48E", "2728"],
    "반지":       ["1F48D", "2728"],
    "시계":       ["231A",  "2728"],
    "선글라스":   ["1F576", "2600"],
    "모자":       ["1F9E2", "2728"],
    "뷰티":       ["1F484", "1F338"],
    "스킨케어":   ["1F9F4", "2728"],
    "스킨":       ["1F9F4", "2728"],
    "립스틱":     ["1F484", "1F48B"],
    "립":         ["1F484", "1F48B"],
    "향수":       ["1F9F4", "1F338"],
    "크림":       ["1F9F4", "1F338"],
    "네일":       ["1F485", "2728"],
    "할인":       ["1F4B0", "1F3F7"],
    "sale":       ["1F4B0", "2728"],
    "세일":       ["1F4B0", "2728"],
    "쿠폰":       ["1F3F7", "2728"],
    "무료":       ["1F381", "2728"],
    "혜택":       ["1F4B0", "2728"],
    "신상":       ["1F195", "2728"],
    "한정":       ["23F0",  "1F525"],
    "특가":       ["1F4B8", "1F525"],
    "이벤트":     ["1F389", "2728"],
    "여행":       ["1F30D", "1F9F3"],
    "캠핑":       ["1F3D5", "1F525"],
    "헬스":       ["1F4AA", "1F3CB"],
    "운동":       ["1F3C3", "1F4AA"],
    "강아지":     ["1F436", "1F9E1"],
    "고양이":     ["1F431", "2728"],
    "크리스마스":  ["1F384", "2744"],
    "새해":       ["1F386", "1F389"],
    "꽃":         ["1F338", "1F33C"],
    "폰케이스":   ["1F4F1", "2728"],
    "이어폰":     ["1F3A7", "1F4FB"],
    "음악":       ["1F3B5", "1F3A7"],
}

_DEFAULT_CODES = ["2728", "1F31F", "2B50"]


def _twemoji_candidates(keywords: str) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for kw in [k.strip().lower() for k in keywords.replace(",", " ").split() if k.strip()]:
        codes = _KO_TWEMOJI.get(kw, [])
        for code in codes:
            if code not in seen:
                seen.add(code)
                results.append({"name": kw, "char": "", "img_url": _url(code), "keyword": kw, "code": code})
    if not results:
        for code in _DEFAULT_CODES:
            results.append({"name": "sparkle", "char": "✨", "img_url": _url(code), "keyword": "", "code": code})
    return results


def fetch_emoji_candidates(keywords: str) -> list[dict]:
    return _twemoji_candidates(keywords)


def get_catalog_candidates(category: str | None = None) -> list[dict]:
    """카탈로그 전체 또는 특정 카테고리 이모티콘 반환"""
    cats = {category: EMOJI_CATALOG[category]} if (category and category in EMOJI_CATALOG) else EMOJI_CATALOG
    result = []
    for cat, codes in cats.items():
        for code in codes:
            result.append({"name": cat, "char": "", "img_url": _url(code), "keyword": cat, "code": code})
    return result


def pick_emoji_with_claude(candidates, main_copy, sub_copy, api_key, count=2):
    if not candidates: return []
    if not api_key: return candidates[:count]
    try:
        import anthropic
        cstr = "\n".join(f"{i+1}. ({c['name']}) 키워드:{c['keyword']}" for i, c in enumerate(candidates))
        prompt = (f"카카오 비즈보드에 어울리는 이모티콘 {count}개를 골라 번호만 쉼표로 답해주세요.\n"
                  f"메인카피:{main_copy}\n서브카피:{sub_copy}\n후보:\n{cstr}")
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=50,
                                     messages=[{"role":"user","content":prompt}])
        indices = [int(x.strip())-1 for x in msg.content[0].text.split(",") if x.strip().isdigit()]
        return [candidates[i] for i in indices if 0<=i<len(candidates)]
    except Exception:
        return candidates[:count]


def fetch_emoji_png(img_url: str) -> bytes | None:
    if not img_url: return None
    try:
        resp = requests.get(img_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200: return resp.content
    except Exception: pass
    return None


def recommend_color_with_claude(main_copy, sub_copy, api_key):
    if not api_key: return "#CC0000"
    try:
        import anthropic, re as _re
        prompt = (f"카카오 비즈보드 강조색을 추천해주세요.\n메인:{main_copy}\n서브:{sub_copy}\n"
                  f"조건: 무채색 금지, 선명한 색상, HEX만 답변. 예:#E8272A")
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=20,
                                     messages=[{"role":"user","content":prompt}])
        m = _re.search(r"#[0-9A-Fa-f]{6}", msg.content[0].text)
        if m: return m.group(0)
    except Exception: pass
    return "#CC0000"
