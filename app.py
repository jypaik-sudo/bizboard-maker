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

/* 소재명 행 버튼들 높이 고정 (소재 생성, 삭제) */
div[data-testid="stHorizontalBlock"] > div:nth-child(n+2) button{
    height:42px!important;min-height:42px!important;
    margin-top:22px;  /* label 높이 보정 */
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
    "기본": ["가운데 오브젝트","텍스트강조","할인율뱃지","서브텍스트강조"],
    "믹스": ["[믹스] 텍스트강조","[믹스] 할인율뱃지"],
    "로고": ["[로고] 가운데+텍스트","[로고] 가운데+뱃지","[로고] 우측+텍스트","[로고] 우측+뱃지"],
}
# 버튼 표시 라벨 — 한 줄 유지
FMT_LABELS = {
    "가운데 오브젝트":      "오브젝트",
    "텍스트강조":           "텍스트강조",
    "할인율뱃지":           "할인율뱃지",
    "서브텍스트강조":       "서브강조",
    "[믹스] 텍스트강조":    "텍스트강조",
    "[믹스] 할인율뱃지":    "할인율뱃지",
    "[로고] 가운데+텍스트": "가운데+텍스트",
    "[로고] 가운데+뱃지":   "가운데+뱃지",
    "[로고] 우측+텍스트":   "우측+텍스트",
    "[로고] 우측+뱃지":     "우측+뱃지",
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
    saved = _load(sid)
    st.session_state.creatives = [_merge(s) for s in saved] if saved else [_new()]

# ── 포맷 선택 ─────────────────────────────────────────────────────────────────
def _set_fmt(cid, fmt):
    for cr in st.session_state.creatives:
        if cr["id"] == cid: cr["format"] = fmt; break

def _fmt_selector(cid, current):
    for group, fmts in FORMATS.items():
        st.markdown(
            f"<span style='font-size:10px;font-weight:800;color:#AAA;"
            f"text-transform:uppercase;letter-spacing:.06em'>{group}</span>",
            unsafe_allow_html=True)
        cols = st.columns(4)
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
        return generate_png({
            "format":        c["format"],
            "main_copy":     c["main_copy"],
            "sub_copy":      c["sub_copy"],
            "sub_right":     c.get("sub_right",""),
            "emphasis_text": c["emphasis_text"],
            "emphasis_color":c["emphasis_color"],
            "emphasis_type": EMPHASIS_TYPE.get(c["format"],"none"),
            "product_images":c["product_images"],
            "brand_logo":    c.get("brand_logo"),
            "emoji_images":  emoji_images,
            "emoji_items":   final_emoji_items,
            "adjustments":   c.get("adjustments",{}),
        }, logo)
    except Exception as e:
        st.error(str(e)); return None

def _warn_guide(adj):
    # main_size/sub_size는 number_input min/max_value로 이미 제한 → 경고 불필요
    if abs(adj.get("text_dx",0)) > GUIDE["text_dx_limit"] or abs(adj.get("text_dy",0)) > GUIDE["text_dy_limit"]:
        st.warning("⚠️ 텍스트 위치가 안전 영역 밖입니다.")
    if abs(adj.get("obj_dx",0)) > GUIDE["obj_dx_limit"] or abs(adj.get("obj_dy",0)) > GUIDE["obj_dy_limit"]:
        st.warning("⚠️ 오브젝트 위치가 안전 영역 밖입니다.")

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
        del_clicked = hc3.button("🗑", key=f"del_{cid}", use_container_width=True)

        if gen_clicked:
            with st.spinner("생성 중…"):
                r = _do_gen(c, logo)
                if r: c["result_png"] = r

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
                    c["main_copy"] = st.text_input(
                        "메인카피(좌) Bold", value=c["main_copy"],
                        placeholder="예: 쫀득 말랑 착화감", key=f"main_{cid}")
                    c["sub_copy"]  = st.text_input(
                        "메인카피(우) Bold", value=c["sub_copy"],
                        placeholder="예: 착화감 최고", key=f"sub_{cid}")
                    c["sub_right"] = st.text_input(
                        "서브카피 Regular", value=c.get("sub_right",""),
                        placeholder="예: 무료배송 + SALE", key=f"subr_{cid}")
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
                    st.caption("레퍼런스 (선택)")
                    rf = st.file_uploader("ref", type=["png","jpg","jpeg","webp"],
                                           key=f"ref_{cid}", label_visibility="collapsed")
                    if rf: c["reference_image"] = rf.getvalue()
                with ci2:
                    st.caption("상품 이미지 ✱  1~3장 · 자동 누끼")
                    prods = st.file_uploader(
                        "prod", type=["png","jpg","jpeg","webp"],
                        accept_multiple_files=True, key=f"prod_{cid}",
                        label_visibility="collapsed")
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
                    ca, cb = st.columns(2)
                    adj["main_size"] = ca.number_input(
                        "메인카피 (pt)", min_value=39, max_value=51,
                        value=max(39, min(51, adj.get("main_size", MAIN_PT))), key=f"ms_{cid}")
                    adj["sub_size"]  = cb.number_input(
                        "서브카피 (pt)", min_value=39, max_value=51,
                        value=max(39, min(51, adj.get("sub_size",  SUB_PT))),  key=f"ss_{cid}")

                    st.caption("텍스트 블록 이동")
                    cc, cd = st.columns(2)
                    adj["text_dx"] = cc.slider("← X →", -200, 200, adj.get("text_dx",0), key=f"tdx_{cid}")
                    adj["text_dy"] = cd.slider("↑ Y ↓", -80, 80, adj.get("text_dy",0), key=f"tdy_{cid}")

                    st.caption("오브젝트 이동·기울기")
                    ce, cf, crot = st.columns(3)
                    adj["obj_dx"]       = ce.slider("← X →",  -160, 160, adj.get("obj_dx",0),       key=f"odx_{cid}")
                    adj["obj_dy"]       = cf.slider("↑ Y ↓",   -80,  80, adj.get("obj_dy",0),       key=f"ody_{cid}")
                    adj["obj_rotation"] = crot.slider("기울기°", -30,  30, adj.get("obj_rotation",0), key=f"orot_{cid}")

                    _warn_guide(adj)

                # adj 변경 감지 → 자동 재생성
                adj_hash = hashlib.md5(json.dumps(adj, sort_keys=True).encode()).hexdigest()
                if c.get("result_png") and c.get("_adj_hash") != adj_hash:
                    c["_adj_hash"] = adj_hash
                    with st.spinner("업데이트 중…"):
                        r = _do_gen(c, logo)
                        if r: c["result_png"] = r

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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w") as zf:
        for i,c in enumerate(done):
            zf.writestr(f"{c['name'] or f'creative_{i+1}'}.png", c["result_png"])
    buf.seek(0)
    st.download_button(
        f"⬇ 전체 ZIP ({len(done)}개)", data=buf,
        file_name="bizboard.zip", mime="application/zip", use_container_width=True)

_save(sid)
