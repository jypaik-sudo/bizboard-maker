"""ABLY 비즈보드 소재 제작기"""
from __future__ import annotations
import io, uuid, zipfile, copy, hashlib, json, os, datetime

import streamlit as st
from core.generator import generate_png, MAIN_PT, SUB_PT
from core.removebg import remove_background
from core.emoji import fetch_emoji_candidates, pick_emoji_with_claude, fetch_emoji_png, recommend_color_with_claude


@st.cache_data(ttl=86400)
def _fetch_em(url: str) -> bytes | None:
    from core.emoji import fetch_emoji_png
    return fetch_emoji_png(url)

st.set_page_config(page_title="ABLY 비즈보드 소재 제작기", page_icon="🗂️", layout="wide")

st.markdown("""
<style>
/* ── 기본 ── */
[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important}
[data-testid="stAppViewContainer"]{
    background-color:#EFEFEF!important;
    background-image:
        radial-gradient(ellipse 60% 50% at 0% 0%,rgba(180,160,230,.38) 0%,transparent 70%),
        radial-gradient(ellipse 55% 45% at 100% 100%,rgba(170,145,225,.32) 0%,transparent 70%)!important;
}
[data-testid="stMainBlockContainer"]{max-width:1520px!important;padding:16px 28px 40px!important}
[data-testid="stMain"]{padding-top:0!important}

/* ── 헤더 ── */
.topbar{display:flex;align-items:center;gap:14px;padding:18px 0 12px;margin-bottom:4px}
.ably-badge{display:inline-flex;align-items:center;justify-content:center;
    background:#FFDE00;padding:0 16px;border-radius:8px;height:44px;
    font-size:16px;font-weight:900;color:#1a1a1a;letter-spacing:.8px;
    box-shadow:0 1px 4px rgba(0,0,0,.15);flex-shrink:0}
.topbar-title{font-size:26px;font-weight:800;color:#1a1a1a;letter-spacing:-.5px;margin:0}

/* ── 버튼 줄바꿈 방지 (전역) ── */
button{white-space:nowrap!important}
button p, button span, button div{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}

/* ── 포맷 버튼 (컬럼 안) ── */
div[data-testid="column"] button{
    border-radius:18px!important;
    padding:4px 6px!important;
    font-size:12px!important;font-weight:500!important;
    border:1.5px solid #E0E0E0!important;
    background:white!important;color:#555!important;
    min-height:30px!important;height:30px!important;
    line-height:1!important;
    white-space:nowrap!important;overflow:hidden!important;
}
div[data-testid="column"] button p{white-space:nowrap!important;overflow:hidden!important;font-size:12px!important}
div[data-testid="column"] button:hover{border-color:#9B76E8!important;color:#3A1D96!important;background:white!important}
div[data-testid="column"] button[kind="primary"]{
    background:#3A1D96!important;border-color:#3A1D96!important;
    color:white!important;font-weight:700!important}

/* ── 소재명 input / 소재생성 버튼 높이 맞춤 ── */
[data-testid="stTextInput"] input{height:42px!important;font-size:14px!important}
[data-testid="stTextInput"] label{font-size:11px!important;color:#888!important;margin-bottom:2px!important}

/* 소재명 행 버튼들 높이 고정 — text input이 있는 행에만 적용 (포맷 선택 행 제외) */
div[data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) > div:nth-child(n+2) button{
    height:42px!important;min-height:42px!important;
    margin-top:22px;
    border-radius:8px!important;
    font-size:13px!important;font-weight:700!important;
    padding:0 12px!important;
}

/* ── 섹션 라벨 ── */
.sec{font-size:11px;font-weight:800;color:#3A1D96;letter-spacing:.04em;margin:12px 0 4px;display:block}
hr.s{border:none;border-top:1px solid #EEEEEE!important;margin:10px 0!important}

/* ── 좌측 패널 배경 ── */
[data-testid="stVerticalBlockBorderWrapper"]:has(.left-marker){
    background:rgba(255,255,255,.78)!important;
    border-radius:12px!important;
    border:1px solid rgba(255,255,255,.95)!important;
    box-shadow:0 1px 5px rgba(58,29,150,.07)!important;
}
/* ── 우측 패널 배경 ── */
[data-testid="stVerticalBlockBorderWrapper"]:has(.right-marker){
    background:rgba(255,255,255,.45)!important;
    border-radius:12px!important;
    border:1px solid rgba(0,0,0,.07)!important;
}

/* ── 미리보기 플레이스홀더 ── */
.ph{height:160px;background:#f5f5f5;border-radius:8px;
    display:flex;align-items:center;justify-content:center;
    color:#bbb;font-size:13px;border:1.5px dashed #ddd;margin-bottom:10px}

/* ── expander ── */
details summary{font-size:13px!important;font-weight:600!important}

/* ── 전체 생성 버튼 ── */
[data-testid="stMainBlockContainer"] > div > div > [data-testid="stButton"]:last-of-type button[kind="primary"]{
    height:50px!important;font-size:15px!important;border-radius:10px!important}

/* ── 업로드 박스 높이 강제 통일 ── */
[data-testid="stFileUploaderDropzone"]{
    height:100px!important;min-height:100px!important;max-height:100px!important;
    overflow:hidden!important;box-sizing:border-box!important}
[data-testid="stFileUploaderDropzoneInstructions"]{font-size:12px!important}
[data-testid="stFileUploader"]{min-height:130px!important;margin-top:6px!important;margin-bottom:6px!important}
[data-testid="stFileUploader"] label{font-size:12px!important;margin-bottom:4px!important;color:#555!important}

/* ── number_input 스타일 ── */
[data-testid="stNumberInput"] label{
    font-size:10px!important;color:#AAA!important;
    font-weight:600!important;letter-spacing:.03em!important;
    margin-bottom:2px!important}
[data-testid="stNumberInput"] input{
    text-align:center!important;font-size:13px!important;
    font-weight:700!important;color:#3A1D96!important;
    background:#F8F6FF!important;border:1px solid #E8E0FF!important;
    border-radius:8px!important;padding:4px 2px!important}

/* number_input 래퍼 — 버튼이 잘리지 않도록 세로 여백 확보 */
[data-testid="stNumberInput"] > div,
[data-testid="stNumberInput"] > div > div{
    display:flex!important;align-items:center!important;
    flex-wrap:nowrap!important;gap:2px!important;
    padding-top:5px!important;padding-bottom:5px!important}
[data-testid="stNumberInput"] input{
    flex:1!important;min-width:0!important}
/* +/- 버튼 — 정사각형 고정, 모서리 둥근 형태 */
[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInputStepUp"]{
    flex:0 0 30px!important;
    width:30px!important;height:30px!important;
    min-width:30px!important;min-height:30px!important;
    max-width:30px!important;max-height:30px!important;
    background:#3A1D96!important;
    border:none!important;border-radius:8px!important;
    padding:0!important;cursor:pointer!important;
    position:relative!important;overflow:visible!important;
    align-self:center!important;flex-shrink:0!important}
[data-testid="stNumberInputStepDown"]{margin-right:1px!important}
/* SVG 숨기기 */
[data-testid="stNumberInputStepDown"] svg,
[data-testid="stNumberInputStepUp"] svg{display:none!important}
/* +/- 기호 */
[data-testid="stNumberInputStepDown"]::before,
[data-testid="stNumberInputStepUp"]::before{content:""!important}
[data-testid="stNumberInputStepDown"]::after,
[data-testid="stNumberInputStepUp"]::after{
    display:block!important;position:absolute!important;
    top:0!important;left:0!important;right:0!important;bottom:0!important;
    text-align:center!important;line-height:30px!important;
    font-size:17px!important;font-weight:700!important;
    color:#fff!important;pointer-events:none!important;font-family:sans-serif!important}
[data-testid="stNumberInputStepDown"]::after{content:"−"!important}
[data-testid="stNumberInputStepUp"]::after{content:"+"!important}
[data-testid="stNumberInputStepDown"]:hover,
[data-testid="stNumberInputStepUp"]:hover{background:#5533CC!important}

/* ── 포맷 버튼 그룹 간격 축소 ── */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] button){
    gap:6px!important}
</style>
""", unsafe_allow_html=True)

# ── 세션 저장 ─────────────────────────────────────────────────────────────────
SESS_DIR = "sessions"
os.makedirs(SESS_DIR, exist_ok=True)
_SKIP = {"product_images","brand_logo","result_png","_prod_hashes",
         "_brand_logo_hash","reference_image","emoji_candidate_pngs"}

def _sess_path(sid):
    return os.path.join(SESS_DIR, f"{datetime.date.today().isoformat()}_{sid}.json")

def _save(sid):
    try:
        with open(_sess_path(sid),"w",encoding="utf-8") as f:
            json.dump([{k:v for k,v in c.items() if k not in _SKIP}
                       for c in st.session_state.creatives], f, ensure_ascii=False)
    except Exception: pass

def _load(sid):
    try:
        p = _sess_path(sid)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: pass
    return None

# ── 에셋 & 시크릿 ─────────────────────────────────────────────────────────────
@st.cache_resource
def _logo():
    with open("assets/logo.png","rb") as f: return f.read()

def _secret(k):
    try: return st.secrets[k]
    except: return ""

REMOVEBG_KEY  = _secret("REMOVEBG_API_KEY")
ANTHROPIC_KEY = _secret("ANTHROPIC_API_KEY")

# ── 포맷 정의 ─────────────────────────────────────────────────────────────────
FORMATS = {
    "기본":   ["텍스트강조","할인율뱃지","서브텍스트강조"],
    "가운데": ["[믹스] 텍스트강조","[믹스] 할인율뱃지","가운데 오브젝트"],
    "로고":   ["[로고] 우측+텍스트","[로고] 우측+뱃지","[로고] 가운데+텍스트","[로고] 가운데+뱃지"],
}
# 버튼 표시 라벨 — 한 줄 유지
FMT_LABELS = {
    "텍스트강조":           "텍스트강조",
    "할인율뱃지":           "할인율뱃지",
    "서브텍스트강조":       "서브강조",
    "가운데 오브젝트":      "기본",
    "[믹스] 텍스트강조":    "텍스트강조",
    "[믹스] 할인율뱃지":    "할인율뱃지",
    "[로고] 우측+텍스트":   "기본+텍스트",
    "[로고] 우측+뱃지":     "기본+뱃지",
    "[로고] 가운데+텍스트": "가운데+텍스트",
    "[로고] 가운데+뱃지":   "가운데+뱃지",
}
EMPHASIS_TYPE = {
    "텍스트강조":"text","서브텍스트강조":"text",
    "[믹스] 텍스트강조":"text","[로고] 가운데+텍스트":"text","[로고] 우측+텍스트":"text",
    "할인율뱃지":"badge","[믹스] 할인율뱃지":"badge",
    "[로고] 가운데+뱃지":"badge","[로고] 우측+뱃지":"badge",
}
HAS_EMPHASIS = set(EMPHASIS_TYPE.keys())
THREE_FIELD_FMTS = {
    "가운데 오브젝트","[믹스] 텍스트강조","[믹스] 할인율뱃지",
    "[로고] 가운데+텍스트","[로고] 가운데+뱃지",
}
LOGO_FMTS = {
    "[로고] 가운데+텍스트","[로고] 가운데+뱃지",
    "[로고] 우측+텍스트","[로고] 우측+뱃지",
}
GUIDE = dict(
    main_size_min=39, main_size_max=51,
    sub_size_min=39,  sub_size_max=51,
    text_dx_limit=200, text_dy_limit=80,
    obj_dx_limit=160,  obj_dy_limit=80,
)

def _default_adj(fmt: str) -> dict:
    """포맷에 따른 기본 adj — 소재 생성 클릭 시 항상 이 값으로 리셋."""
    base = dict(
        main_size=MAIN_PT, sub_size=SUB_PT,
        logo_size=40,
        obj_dx=0, obj_dy=0, obj_scale=100, obj_rotation=0,
        text_dx=0, left_dx=0, right_dx=0,
    )
    # 우측 오브젝트 포맷: ABLY 로고(x≈878~979, y≈24~45) 침범 방지
    # 오브젝트 박스가 넓으므로 x를 약간 좌측으로 당겨 로고 영역과 겹침 최소화
    if fmt not in THREE_FIELD_FMTS and fmt not in ("가운데 오브젝트",):
        base["obj_dx"] = -20   # 기본 우측 박스에서 살짝 좌이동 → 로고 영역 여백 확보
    return base


def _new():
    return dict(id=str(uuid.uuid4())[:8],name="",format="가운데 오브젝트",
                main_copy="",sub_copy="",sub_right="",emphasis_text="",
                emphasis_color="#CC0000",use_recommend=True,
                product_images=[],brand_logo=None,reference_image=None,
                object_type="단독",use_emoji=False,emoji_keywords="",
                emoji_candidates=[],emoji_selected=[],emoji_items=[],
                adjustments={},result_png=None)

def _merge(s):
    b=_new(); b.update({k:v for k,v in s.items() if k in b and k not in _SKIP}); return b

# ── 세션 초기화 ───────────────────────────────────────────────────────────────
if "sid" not in st.session_state:
    st.session_state.sid = st.query_params.get("sid", str(uuid.uuid4())[:8])
    st.query_params["sid"] = st.session_state.sid
sid = st.session_state.sid

if "creatives" not in st.session_state:
    st.session_state.creatives = [_new()]

# ── 포맷 선택 ─────────────────────────────────────────────────────────────────
def _set_fmt(cid, fmt):
    for cr in st.session_state.creatives:
        if cr["id"] == cid: cr["format"] = fmt; break

def _fmt_selector(cid, current):
    # 모든 그룹 st.columns(4) 고정 → 그룹 간 버튼 위치 완벽 정렬
    # CSS 버그 수정 후 (stHorizontalBlock:has(stTextInput) 로 스코핑) 정상 정렬됨
    for gi, (group, fmts) in enumerate(FORMATS.items()):
        if gi > 0:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='font-size:10px;font-weight:800;color:#BBBBBB;"
            f"text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px'>{group}</div>",
            unsafe_allow_html=True)
        cols = st.columns(4, gap="small")  # CSS로 추가 축소
        for i, fmt in enumerate(fmts):
            cols[i].button(
                FMT_LABELS.get(fmt, fmt),
                key=f"fmt_{cid}_{fmt}",
                type="primary" if fmt == current else "secondary",
                use_container_width=True,
                on_click=_set_fmt, args=(cid, fmt),
            )

# ── 생성 로직 ─────────────────────────────────────────────────────────────────
def _do_gen(c, logo):
    try:
        if c.get("use_recommend") and ANTHROPIC_KEY and c["format"] in HAS_EMPHASIS:
            c["emphasis_color"] = recommend_color_with_claude(
                c["main_copy"], c["sub_copy"], ANTHROPIC_KEY)
        # emoji_items 변환 (bytes 추가)
        final_emoji_items = []
        for item in c.get("emoji_items", []):
            b = _fetch_em(item["url"])
            if b:
                final_emoji_items.append({
                    "bytes": b,
                    "size": item.get("size", 52),
                    "hue": item.get("hue", 0),
                    "rotation": item.get("rotation", 0),
                })
        emoji_images = [it["bytes"] for it in final_emoji_items]  # 기존 호환용
        # emoji_items 없으면 기존 방식 폴백
        if not final_emoji_items and c.get("use_emoji"):
            kw = c.get("emoji_keywords","") or (c["main_copy"]+" "+c["sub_copy"])
            if not c.get("emoji_candidates"):
                c["emoji_candidates"] = fetch_emoji_candidates(kw)
            cands = c["emoji_candidates"]
            sel = c.get("emoji_selected",[])
            chosen = ([cd for cd in cands if cd["img_url"] in sel] if sel
                      else pick_emoji_with_claude(cands,c["main_copy"],c["sub_copy"],ANTHROPIC_KEY))
            emoji_images = [b for e in chosen if (b := fetch_emoji_png(e.get("img_url","")))]
        prod_imgs = c.get("product_images") or []
        if not prod_imgs:
            st.warning("⚠️ 상품 이미지가 없습니다. 오브젝트 없이 생성합니다.")
        return generate_png({
            "format":        c["format"],
            "main_copy":     c["main_copy"],
            "sub_copy":      c["sub_copy"],
            "sub_right":     c.get("sub_right",""),
            "emphasis_text": c["emphasis_text"],
            "emphasis_color":c["emphasis_color"],
            "emphasis_type": EMPHASIS_TYPE.get(c["format"],"none"),
            "product_images":prod_imgs,
            "brand_logo":    c.get("brand_logo"),
            "emoji_images":  emoji_images,
            "emoji_items":   final_emoji_items,
            "adjustments":   c.get("adjustments",{}),
        }, logo)
    except Exception as e:
        import traceback
        st.error(f"생성 오류: {e}\n{traceback.format_exc()}"); return None

def _warn_guide(adj):
    pass  # 화살표 버튼이 하드 min/max 로 제한 → 경고 불필요

# ── 조정값 변경 콜백 ──────────────────────────────────────────────────────────
def _do_adj(cid, key, delta, lo, hi):
    for cr in st.session_state.creatives:
        if cr["id"] == cid:
            a = cr.setdefault("adjustments", {})
            a[key] = max(lo, min(hi, a.get(key, 0) + delta))
            break

def _do_adj_both(cid, key1, key2, delta, lo, hi):
    """두 키를 항상 같은 값으로 동기화 (메인카피 좌·우 폰트 동일 고정용)"""
    for cr in st.session_state.creatives:
        if cr["id"] == cid:
            a = cr.setdefault("adjustments", {})
            v = max(lo, min(hi, a.get(key1, lo + (hi-lo)//2) + delta))
            a[key1] = v; a[key2] = v
            break

# ── number_input 스테퍼 ───────────────────────────────────────────────────────
def _adj_stepper(col, cid, adj, key, label, lo, hi, step, unit="px", default=0):
    val = max(lo, min(hi, adj.get(key, default)))
    lbl = f"{label} ({unit})" if unit != "px" else label
    with col:
        new_val = st.number_input(
            lbl,
            min_value=lo, max_value=hi,
            value=val, step=step,
            key=f"ni_{key}_{cid}",
            format="%d",
        )
    adj[key] = int(new_val)


# ── 간격 경고 계산 ────────────────────────────────────────────────────────────
def _gap_warning(fmt, adj):
    """오브젝트↔카피 간격 33px 미만 시 (True, 메시지) 반환."""
    from core.generator import ZONES
    _FMTMAP = {
        "가운데 오브젝트": "가운데 오브젝트",
        "[믹스] 텍스트강조": "믹스 텍스트강조",
        "[믹스] 할인율뱃지": "믹스 할인율뱃지",
        "[로고] 가운데+텍스트": "로고 가운데+텍스트",
        "[로고] 가운데+뱃지": "로고 가운데+뱃지",
        "텍스트강조": "텍스트강조",
        "할인율뱃지": "할인율뱃지",
        "서브텍스트강조": "서브텍스트강조",
        "[로고] 우측+텍스트": "로고 우측+텍스트",
        "[로고] 우측+뱃지": "로고 우측+뱃지",
    }
    key = _FMTMAP.get(fmt, fmt)
    zone = ZONES.get(key)
    if not zone:
        return False, ""
    obj_box, text_x, lw, right_x, _rw = zone
    if not obj_box:
        return False, ""

    scale  = adj.get("obj_scale", 100) / 100.0
    obj_dx = adj.get("obj_dx", 0)
    cx = (obj_box[0] + obj_box[2]) // 2
    hw = int((obj_box[2] - obj_box[0]) * scale / 2)
    obj_left  = cx - hw + obj_dx
    obj_right = cx + hw + obj_dx
    MIN = 33

    if fmt in THREE_FIELD_FMTS:
        # 우측 텍스트와 오브젝트 오른쪽 경계
        if right_x is not None:
            gap = (right_x + adj.get("right_dx", 0)) - obj_right
            if gap < MIN:
                return True, f"오브젝트↔메인카피(우) 간격 {gap}px — 최소 {MIN}px 필요"
        # 좌측 텍스트와 오브젝트 왼쪽 경계
        if text_x is not None:
            text_right_est = text_x + adj.get("left_dx", 0) + lw
            gap = obj_left - text_right_est
            if gap < MIN:
                return True, f"메인카피(좌)↔오브젝트 간격 {gap}px — 최소 {MIN}px 필요"
    else:
        # 오브젝트가 우측, 텍스트가 좌측
        text_dx = adj.get("text_dx", 0)
        if text_x is not None:
            text_right_est = text_x + text_dx + 380
            gap = obj_left - text_right_est
            if gap < MIN:
                return True, f"텍스트↔오브젝트 간격 {gap}px — 최소 {MIN}px 필요"

    # 캔버스 좌·우측 여백 48px
    if obj_left < 48:
        return True, f"오브젝트 좌측 여백 {obj_left}px — 최소 48px 필요"
    if obj_right > 981:
        return True, f"오브젝트 우측 여백 {1029 - obj_right}px — 최소 48px 필요"

    return False, ""

# ── 카드 렌더 ─────────────────────────────────────────────────────────────────
def _card(idx, c, logo):
    cid = c["id"]
    fmt = c["format"]
    em_type = EMPHASIS_TYPE.get(fmt, "none")
    adj = c.setdefault("adjustments", {})
    label = f"소재 {idx+1}" + (f"  —  {c['name']}" if c["name"] else "")

    with st.expander(label, expanded=True):

        # ── 헤더 행: 소재명 / 소재생성 / 삭제 ──────────────────────────────
        hc1, hc2, hc3 = st.columns([5, 2, 1])
        c["name"] = hc1.text_input(
            "소재명", value=c["name"],
            placeholder="예: 에잇세컨즈_믹스",
            key=f"name_{cid}")
        gen_clicked = hc2.button(
            "▶ 소재 생성", key=f"gen_{cid}",
            type="primary", use_container_width=True)
        del_clicked = hc3.button("삭제", key=f"del_{cid}", use_container_width=True)

        if gen_clicked:
            # 소재 생성 시 항상 adj 초기화 → 포맷 기본 위치로 리셋
            c["adjustments"] = _default_adj(fmt)
            with st.spinner("생성 중…"):
                r = _do_gen(c, logo)
                if r: c["result_png"] = r
            st.rerun()  # adj 리셋이 스테퍼에 반영되도록

        if del_clicked:
            st.session_state.creatives = [x for x in st.session_state.creatives if x["id"] != cid]
            st.rerun()

        st.divider()

        # ── 본문 2열: 좌(폼) / 우(미리보기+조정) ────────────────────────────
        col_l, col_r = st.columns([10, 11], gap="large")

        # ── 좌측 폼 ─────────────────────────────────────────────────────────
        with col_l:
            with st.container(border=True):
                st.markdown('<span class="left-marker"></span>', unsafe_allow_html=True)

                # 포맷
                st.markdown('<span class="sec">포맷 선택</span>', unsafe_allow_html=True)
                _fmt_selector(cid, fmt)
                st.markdown('<hr class="s">', unsafe_allow_html=True)

                # 카피
                st.markdown('<span class="sec">카피</span>', unsafe_allow_html=True)
                if fmt in THREE_FIELD_FMTS:
                    # 로고 가운데 포맷: 메인카피(좌)는 로고가 대체 → 입력란 숨김
                    if fmt not in LOGO_FMTS:
                        c["main_copy"] = st.text_input(
                            "메인카피(좌) Bold", value=c["main_copy"],
                            placeholder="예: 쫀득 말랑 착화감", key=f"main_{cid}")
                    c["sub_copy"]  = st.text_input(
                        "메인카피(우) Bold", value=c["sub_copy"],
                        placeholder="예: 착화감 최고", key=f"sub_{cid}")
                    c["sub_right"] = st.text_input(
                        "서브카피 Regular", value=c.get("sub_right",""),
                        placeholder="예: 무료배송 + SALE", key=f"subr_{cid}")
                elif fmt in LOGO_FMTS:
                    # 로고 우측 포맷: 메인카피는 로고가 대체 → 서브카피만
                    c["sub_copy"] = st.text_input(
                        "서브카피 Regular", value=c["sub_copy"],
                        placeholder="예: 무료배송 + SALE", key=f"sub_{cid}")
                else:
                    c["main_copy"] = st.text_input(
                        "메인카피 Bold", value=c["main_copy"],
                        placeholder="예: 지금이 딱 좋아", key=f"main_{cid}")
                    c["sub_copy"]  = st.text_input(
                        "서브카피 Regular", value=c["sub_copy"],
                        placeholder="예: 무료배송 + SALE", key=f"sub_{cid}")

                if fmt in HAS_EMPHASIS:
                    _ref = c.get("sub_right","") if fmt in THREE_FIELD_FMTS else c["sub_copy"]
                    q_label = "강조 텍스트" if em_type == "text" else "뱃지 텍스트"
                    c["emphasis_text"] = st.text_input(
                        q_label, value=c["emphasis_text"],
                        placeholder="예: 무료배송 / 75%", key=f"em_{cid}")
                    if c["emphasis_text"] and _ref and c["emphasis_text"] not in _ref:
                        st.error(f"'{c['emphasis_text']}'가 서브카피에 없어요.")
                    cr_, cc_ = st.columns(2)
                    c["use_recommend"] = cr_.checkbox(
                        "AI 색상 추천", value=c.get("use_recommend",True), key=f"rec_{cid}")
                    if not c["use_recommend"]:
                        c["emphasis_color"] = cc_.color_picker(
                            "강조 색상", value=c.get("emphasis_color","#CC0000"), key=f"clr_{cid}")

                st.markdown('<hr class="s">', unsafe_allow_html=True)

                # 이미지
                st.markdown('<span class="sec">오브젝트 이미지</span>', unsafe_allow_html=True)
                if fmt in LOGO_FMTS:
                    st.caption("브랜드 로고 ✱ (자동 누끼)")
                    lf = st.file_uploader("브랜드 로고", type=["png","jpg","jpeg","webp"],
                                           key=f"blogo_{cid}", label_visibility="collapsed")
                    if lf:
                        raw = lf.getvalue(); h = hashlib.md5(raw).hexdigest()
                        if h != c.get("_brand_logo_hash"):
                            with st.spinner("누끼 처리…"):
                                c["brand_logo"] = remove_background(raw, REMOVEBG_KEY)
                            c["_brand_logo_hash"] = h

                ci1, ci2 = st.columns(2)
                with ci1:
                    rf = st.file_uploader("레퍼런스 (선택)", type=["png","jpg","jpeg","webp"],
                                           key=f"ref_{cid}")
                    if rf: c["reference_image"] = rf.getvalue()
                with ci2:
                    prods = st.file_uploader(
                        "상품 이미지 ✱  1~3장 · 자동 누끼", type=["png","jpg","jpeg","webp"],
                        accept_multiple_files=True, key=f"prod_{cid}")
                    if prods:
                        raws = [f.getvalue() for f in prods[:3]]
                        hs = [hashlib.md5(b).hexdigest() for b in raws]
                        if hs != c.get("_prod_hashes"):
                            with st.spinner("누끼 처리…"):
                                c["product_images"] = [remove_background(b, REMOVEBG_KEY) for b in raws]
                            c["_prod_hashes"] = hs

                c["object_type"] = st.radio(
                    "배치 타입", ["단독","카테고리","믹스(코디)"], horizontal=True,
                    index=["단독","카테고리","믹스(코디)"].index(c.get("object_type","단독")),
                    key=f"otype_{cid}")

                st.markdown('<hr class="s">', unsafe_allow_html=True)

                # 이모티콘 + 복제
                ec1, ec2 = st.columns([3,1])
                c["use_emoji"] = ec1.toggle(
                    "이모티콘 추가", value=c.get("use_emoji",False), key=f"emoji_{cid}")
                ec2.button("📋 복제", key=f"dup_{cid}", use_container_width=True,
                           on_click=lambda: _dup(cid))
                if c["use_emoji"]:
                    prev_kw = c.get("emoji_keywords","")
                    c["emoji_keywords"] = st.text_input(
                        "이모티콘 키워드", value=prev_kw,
                        placeholder="예: 직장인, 컴퓨터 · 공란이면 카피 기반 자동",
                        key=f"ekw_{cid}")
                    if c["emoji_keywords"] != prev_kw:
                        c["emoji_candidates"] = []

        # ── 우측 미리보기 + 조정 ────────────────────────────────────────────
        with col_r:
            with st.container(border=True):
                st.markdown('<span class="right-marker"></span>', unsafe_allow_html=True)

                # 미리보기 자리 예약
                preview_slot = st.empty()
                dl_slot = st.empty()

                # 조정 패널
                with st.expander("📐 위치·크기 조정", expanded=bool(c.get("result_png"))):

                    # ── 폰트·로고 크기 ───────────────────────────────────
                    if fmt in LOGO_FMTS and fmt not in THREE_FIELD_FMTS:
                        # 기본+텍스트 / 기본+뱃지: 로고 사이즈 + 서브카피
                        st.caption("크기 조정  ·  로고 35~45px / 서브카피 39~51pt")
                        la, lb = st.columns(2)
                        ls_new = la.number_input(
                            "로고 사이즈 (px)", min_value=35, max_value=45,
                            value=max(35, min(45, adj.get("logo_size", 40))),
                            step=1, key=f"ni_ls_{cid}", format="%d",
                        )
                        adj["logo_size"] = int(ls_new)
                        ss_new = lb.number_input(
                            "서브카피 (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, adj.get("sub_size", SUB_PT))),
                            step=1, key=f"ni_ss_{cid}", format="%d",
                        )
                        adj["sub_size"] = int(ss_new)

                    elif fmt in LOGO_FMTS and fmt in THREE_FIELD_FMTS:
                        # 가운데+텍스트 / 가운데+뱃지: 로고 + 메인카피(우) + 서브카피
                        st.caption("크기 조정  ·  로고 35~45px / 메인카피(우)·서브카피 39~51pt")
                        la, lb, lc = st.columns(3)
                        ls_new = la.number_input(
                            "로고 (px)", min_value=35, max_value=45,
                            value=max(35, min(45, adj.get("logo_size", 40))),
                            step=1, key=f"ni_ls_{cid}", format="%d",
                        )
                        adj["logo_size"] = int(ls_new)
                        ms_new = lb.number_input(
                            "메인카피(우) (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, adj.get("main_size", MAIN_PT))),
                            step=1, key=f"ni_ms_{cid}", format="%d",
                        )
                        adj["main_size"] = int(ms_new)
                        ss_new = lc.number_input(
                            "서브카피 (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, adj.get("sub_size", SUB_PT))),
                            step=1, key=f"ni_ss_{cid}", format="%d",
                        )
                        adj["sub_size"] = int(ss_new)

                    elif fmt in THREE_FIELD_FMTS:
                        st.caption("카피 폰트 (pt)  ·  메인(좌·우) 항상 동일 / 서브 별도")
                        fa, fb = st.columns(2)
                        ms_new = fa.number_input(
                            "메인카피 39~51 (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, adj.get("main_size", MAIN_PT))),
                            step=1, key=f"ni_ms_{cid}", format="%d",
                        )
                        adj["main_size"] = int(ms_new)
                        _ss_init = adj.get("sub_size", SUB_PT)
                        if _ss_init == adj["main_size"] and "sub_size_set" not in adj:
                            _ss_init = SUB_PT
                        ss_new = fb.number_input(
                            "서브카피 39~51 (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, _ss_init)),
                            step=1, key=f"ni_ss_{cid}", format="%d",
                        )
                        adj["sub_size"] = int(ss_new)
                        adj["sub_size_set"] = True
                    else:
                        st.caption("폰트 크기  39~51 pt")
                        fa, fb = st.columns(2)
                        ms_new = fa.number_input(
                            "메인카피 (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, adj.get("main_size", MAIN_PT))),
                            step=1, key=f"ni_ms_{cid}", format="%d",
                        )
                        adj["main_size"] = int(ms_new)
                        ss_new = fb.number_input(
                            "서브카피 (pt)", min_value=39, max_value=51,
                            value=max(39, min(51, adj.get("sub_size", SUB_PT))),
                            step=1, key=f"ni_ss_{cid}", format="%d",
                        )
                        adj["sub_size"] = int(ss_new)

                    st.markdown('<hr class="s">', unsafe_allow_html=True)

                    # ── 텍스트 X 이동 ─────────────────────────────────────
                    # Y축 이동 없음 — 자동 수직 중앙 정렬 / 메인↔서브 간격 20px 고정
                    if fmt in THREE_FIELD_FMTS:
                        # 오브젝트 가운데: 좌카피(우방향+) / 우카피(좌방향-)
                        st.caption("카피 X 이동  ·  4px 단위  ·  좌측 48px·우측 48px 여백 보호")
                        tx1, tx2 = st.columns(2)
                        # 메인(좌): base x=48, +방향(→)으로만 이동 → 최대 obj 33px 전까지
                        _adj_stepper(tx1, cid, adj, "left_dx",  "메인(좌) →",    0, 100, 4)
                        # 메인(우): base x=698, -방향(←)으로만 이동 → 우측 여백 48px 보호
                        _adj_stepper(tx2, cid, adj, "right_dx", "← 메인(우)", -100,   0, 4)
                    else:
                        # 오브젝트 우측: 메인+서브 함께 이동
                        st.caption("텍스트 X 이동  ·  4px 단위  ·  좌측 48px 여백 보호")
                        _tc1, _tc2 = st.columns([1, 1])
                        _adj_stepper(_tc1, cid, adj, "text_dx", "→ X →", 0, 100, 4)

                    st.markdown('<hr class="s">', unsafe_allow_html=True)

                    # ── 오브젝트 이동·크기·기울기 ─────────────────────────
                    st.caption("오브젝트  ·  4px / 5% / 1° 단위")
                    oa, ob, oc, od = st.columns(4)
                    _adj_stepper(oa, cid, adj, "obj_dx",       "← X →", -150,  80, 4)
                    _adj_stepper(ob, cid, adj, "obj_dy",       "↑ Y ↓",  -40,  40, 4)
                    _adj_stepper(oc, cid, adj, "obj_scale",    "크기",    70, 130, 5, "%", default=100)
                    _adj_stepper(od, cid, adj, "obj_rotation", "기울기", -30,  30, 1, "°")

                    # ── 간격 경고 ─────────────────────────────────────────
                    has_warn, warn_msg = _gap_warning(fmt, adj)
                    if has_warn:
                        st.warning(f"⚠️ {warn_msg}", icon=None)

                # 위치·크기 조정 후 "적용" 버튼으로만 재생성
                if c.get("result_png"):
                    adj_hash = hashlib.md5(json.dumps(adj, sort_keys=True).encode()).hexdigest()
                    if c.get("_adj_hash") != adj_hash:
                        if st.button("🔄 조정 적용", key=f"apply_adj_{cid}", use_container_width=True):
                            c["_adj_hash"] = adj_hash
                            with st.spinner("업데이트 중…"):
                                r = _do_gen(c, logo)
                                if r: c["result_png"] = r
                            st.rerun()

                # preview_slot에 최종 이미지 채우기
                if c.get("result_png"):
                    preview_slot.image(c["result_png"], use_container_width=True)
                    dl_slot.download_button(
                        "⬇ PNG 저장", data=c["result_png"],
                        file_name=f"{c['name'] or f'creative_{idx+1}'}.png",
                        mime="image/png", key=f"dl_{cid}",
                        use_container_width=True)
                else:
                    preview_slot.markdown('<div class="ph">▶ 소재 생성을 눌러주세요</div>',
                                          unsafe_allow_html=True)

                # 이모티콘 픽커
                if c.get("use_emoji"):
                    if "emoji_items" not in c:
                        c["emoji_items"] = []

                    with st.expander("😀 이모티콘 선택 · 세부 설정"):
                        kw = c.get("emoji_keywords","") or (c["main_copy"]+" "+c["sub_copy"])

                        # ── 섹션 A: 추천 이모티콘 ──────────────────────────────
                        st.markdown("**🎯 추천 이모티콘**")
                        if not c.get("emoji_candidates"):
                            c["emoji_candidates"] = fetch_emoji_candidates(kw)
                        cands = c.get("emoji_candidates", [])
                        sel_urls = {it["url"] for it in c["emoji_items"]}

                        if cands:
                            per = 6
                            for ri in range(0, min(len(cands), 12), per):
                                chunk = cands[ri:ri+per]
                                pcols = st.columns(len(chunk))
                                for j, cand in enumerate(chunk):
                                    with pcols[j]:
                                        png = _fetch_em(cand["img_url"])
                                        if png: st.image(png, width=44)
                                        url = cand["img_url"]
                                        is_sel = url in sel_urls
                                        if st.button("✓" if is_sel else "＋", key=f"ep_{cid}_{ri+j}",
                                                     type="primary" if is_sel else "secondary"):
                                            if is_sel:
                                                c["emoji_items"] = [it for it in c["emoji_items"] if it["url"]!=url]
                                            else:
                                                if len(c["emoji_items"]) < 3:
                                                    c["emoji_items"].append({"url":url,"size":52,"hue":0,"rotation":0})
                                                else:
                                                    c["emoji_items"] = c["emoji_items"][1:]+[{"url":url,"size":52,"hue":0,"rotation":0}]
                                            c["emoji_candidates"] = cands
                                            st.rerun()

                        # ── 섹션 B: 전체 카탈로그 ───────────────────────────────
                        st.markdown("**📦 전체 이모티콘**")
                        from core.emoji import get_catalog_candidates, EMOJI_CATALOG
                        cat_names = list(EMOJI_CATALOG.keys())
                        sel_cat = st.selectbox("카테고리", cat_names, key=f"ecat_{cid}")
                        cat_cands = get_catalog_candidates(sel_cat)
                        sel_urls2 = {it["url"] for it in c["emoji_items"]}
                        per2 = 8
                        for ri2 in range(0, len(cat_cands), per2):
                            chunk2 = cat_cands[ri2:ri2+per2]
                            pcols2 = st.columns(len(chunk2))
                            for j2, cand2 in enumerate(chunk2):
                                with pcols2[j2]:
                                    png2 = _fetch_em(cand2["img_url"])
                                    if png2: st.image(png2, width=40)
                                    url2 = cand2["img_url"]
                                    is_sel2 = url2 in sel_urls2
                                    if st.button("✓" if is_sel2 else "＋", key=f"ec_{cid}_{ri2+j2}",
                                                 type="primary" if is_sel2 else "secondary"):
                                        if is_sel2:
                                            c["emoji_items"] = [it for it in c["emoji_items"] if it["url"]!=url2]
                                        else:
                                            if len(c["emoji_items"]) < 3:
                                                c["emoji_items"].append({"url":url2,"size":52,"hue":0,"rotation":0})
                                            else:
                                                c["emoji_items"] = c["emoji_items"][1:]+[{"url":url2,"size":52,"hue":0,"rotation":0}]
                                        st.rerun()

                        # ── 섹션 C: 선택된 이모티콘 개별 설정 ────────────────
                        if c["emoji_items"]:
                            st.markdown("**⚙️ 선택된 이모티콘 개별 설정**")
                            for ei, item in enumerate(c["emoji_items"]):
                                png_item = _fetch_em(item["url"])
                                ic1, ic2, ic3, ic4, ic5 = st.columns([1, 2, 2, 2, 1])
                                if png_item: ic1.image(png_item, width=36)
                                item["size"]     = ic2.number_input(f"크기{ei+1}", 20, 90, item.get("size",52),   key=f"eis_{cid}_{ei}")
                                item["rotation"] = ic3.slider(f"기울기{ei+1}°", -45, 45, item.get("rotation",0), key=f"eir_{cid}_{ei}")
                                item["hue"]      = ic4.slider(f"색조{ei+1}°", -180, 180, item.get("hue",0),      key=f"eih_{cid}_{ei}")
                                if ic5.button("✕", key=f"eid_{cid}_{ei}"):
                                    c["emoji_items"].pop(ei); st.rerun()


def _dup(cid):
    for i, x in enumerate(st.session_state.creatives):
        if x["id"] == cid:
            nc = copy.deepcopy(x)
            nc["id"] = str(uuid.uuid4())[:8]
            nc["name"] = x["name"]+"_복사"
            nc["result_png"] = None
            st.session_state.creatives.insert(i+1, nc)
            break


# ── 헤더 ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="topbar">'
    '<span class="ably-badge">ABLY</span>'
    '<span class="topbar-title">비즈보드 소재 제작기</span>'
    '</div>',
    unsafe_allow_html=True)

logo_bytes = _logo()

# ── 소재 목록 ─────────────────────────────────────────────────────────────────
for i, c in enumerate(st.session_state.creatives):
    _card(i, c, logo_bytes)

st.write("")

if st.button("＋ 소재 추가", use_container_width=True):
    st.session_state.creatives.append(_new()); st.rerun()

st.write("")

if st.button("▶ 전체 소재 생성", type="primary", use_container_width=True):
    with st.spinner("전체 생성 중…"):
        for c in st.session_state.creatives:
            r = _do_gen(c, logo_bytes)
            if r: c["result_png"] = r
    st.success(f"✅ {len(st.session_state.creatives)}개 완료!")
    st.rerun()

done = [c for c in st.session_state.creatives if c.get("result_png")]
if done:
    @st.cache_data(show_spinner=False)
    def _make_zip(keys: tuple, pngs: tuple) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, data in zip(keys, pngs):
                zf.writestr(f"{name}.png", data)
        return buf.getvalue()

    _keys = tuple(c["name"] or f"creative_{i+1}" for i, c in enumerate(done))
    _pngs = tuple(c["result_png"] for c in done)
    zip_bytes = _make_zip(_keys, _pngs)
    st.download_button(
        f"⬇ 전체 ZIP ({len(done)}개)", data=zip_bytes,
        file_name="bizboard.zip", mime="application/zip", use_container_width=True)

_save(sid)
