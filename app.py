"""ABLY 비즈보드 소재 제작기 — 투컬럼 에디터 + 세션 저장"""
from __future__ import annotations
import io, uuid, zipfile, copy, hashlib, json, os, datetime

import streamlit as st
from core.generator import generate_png, MAIN_PT, SUB_PT
from core.removebg import remove_background
from core.emoji import fetch_emoji_candidates, pick_emoji_with_claude, fetch_emoji_png, recommend_color_with_claude

st.set_page_config(page_title="ABLY 비즈보드 소재 제작기", page_icon="🗂️", layout="wide")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none!important}
[data-testid="stAppViewContainer"]{
    background-color:#EFEFEF!important;
    background-image:radial-gradient(ellipse 60% 50% at 0% 0%,rgba(180,160,230,.38) 0%,transparent 70%),
                     radial-gradient(ellipse 55% 45% at 100% 100%,rgba(170,145,225,.32) 0%,transparent 70%)!important;
    min-height:100vh}
[data-testid="stMainBlockContainer"]{max-width:1280px;padding:16px 20px 40px}
[data-testid="stMain"]{padding-top:0!important}
.topbar{display:flex;align-items:center;gap:14px;padding:20px 4px 10px;margin-bottom:16px}
.ably-badge{display:inline-flex;align-items:center;justify-content:center;background:#FFDE00;
    padding:0 14px;border-radius:8px;height:44px;font-size:16px;font-weight:900;color:#1a1a1a;
    letter-spacing:.8px;box-shadow:0 1px 4px rgba(0,0,0,.15);flex-shrink:0}
.topbar-title{font-size:26px;font-weight:800;color:#1a1a1a;letter-spacing:-.5px;line-height:44px;margin:0}
.preview-placeholder{height:130px;background:#f0f0f0;border-radius:8px;
    display:flex;align-items:center;justify-content:center;color:#aaa;font-size:13px}
div[data-testid="column"] button{border-radius:20px!important;padding:4px 13px!important;
    font-size:12px!important;font-weight:500!important;border:1.5px solid #E0E0E0!important;
    background:white!important;color:#555!important;white-space:nowrap!important;
    min-height:32px!important;height:auto!important;line-height:1.4!important}
div[data-testid="column"] button:hover{border-color:#9B76E8!important;color:#3A1D96!important}
div[data-testid="column"] button[kind="primary"]{background:#3A1D96!important;
    border-color:#3A1D96!important;color:white!important;font-weight:700!important}
div[data-testid="stTextInput"] input{font-size:13px!important}
div[data-testid="stTextInput"] label{font-size:11px!important;color:#777!important}
details summary{font-size:13px!important;font-weight:600!important}
hr{margin:10px 0!important}
</style>
""", unsafe_allow_html=True)

# ── Session persistence ────────────────────────────────────────────────────────
SESS_DIR = "sessions"
os.makedirs(SESS_DIR, exist_ok=True)

_SKIP_KEYS = {"product_images","brand_logo","result_png","emoji_candidate_pngs",
              "_prod_hashes","_brand_logo_hash","reference_image"}

def _sess_path(sid: str) -> str:
    today = datetime.date.today().isoformat()
    return os.path.join(SESS_DIR, f"{today}_{sid}.json")

def _save_session(sid: str) -> None:
    try:
        data = [{k:v for k,v in c.items() if k not in _SKIP_KEYS}
                for c in st.session_state.creatives]
        with open(_sess_path(sid), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _load_session(sid: str) -> list | None:
    try:
        p = _sess_path(sid)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

# ── Assets & secrets ──────────────────────────────────────────────────────────
@st.cache_resource
def _logo() -> bytes:
    with open("assets/logo.png","rb") as f: return f.read()

def _secret(k):
    try: return st.secrets[k]
    except: return ""

REMOVEBG_KEY  = _secret("REMOVEBG_API_KEY")
ANTHROPIC_KEY = _secret("ANTHROPIC_API_KEY")

# ── Format definitions ─────────────────────────────────────────────────────────
FORMATS = {
    "기본": ["가운데 오브젝트","텍스트강조","할인율뱃지","서브텍스트강조"],
    "믹스": ["[믹스] 텍스트강조","[믹스] 할인율뱃지"],
    "로고": ["[로고] 가운데+텍스트","[로고] 가운데+뱃지","[로고] 우측+텍스트","[로고] 우측+뱃지"],
}
EMPHASIS_TYPE = {
    "텍스트강조":"text","서브텍스트강조":"text",
    "[믹스] 텍스트강조":"text","[로고] 가운데+텍스트":"text","[로고] 우측+텍스트":"text",
    "할인율뱃지":"badge","[믹스] 할인율뱃지":"badge",
    "[로고] 가운데+뱃지":"badge","[로고] 우측+뱃지":"badge",
}
HAS_EMPHASIS  = set(EMPHASIS_TYPE.keys())
EMPHASIS_Q    = {"text":"강조 텍스트","badge":"뱃지 텍스트"}
THREE_FIELD_FMTS = {
    "가운데 오브젝트","[믹스] 텍스트강조","[믹스] 할인율뱃지",
    "[로고] 가운데+텍스트","[로고] 가운데+뱃지",
}
LOGO_FMTS = {
    "[로고] 가운데+텍스트","[로고] 가운데+뱃지",
    "[로고] 우측+텍스트","[로고] 우측+뱃지",
}

GUIDE = dict(
    main_size_min=28, main_size_max=62,
    sub_size_min=18,  sub_size_max=50,
    text_dx_limit=200, text_dy_limit=100,
    obj_dx_limit=160,  obj_dy_limit=80,
)

# ── Creative defaults ──────────────────────────────────────────────────────────
def _new() -> dict:
    return dict(
        id=str(uuid.uuid4())[:8], name="", format="가운데 오브젝트",
        main_copy="", sub_copy="", sub_right="", emphasis_text="",
        emphasis_color="#CC0000", use_recommend=True,
        product_images=[], brand_logo=None, reference_image=None,
        object_type="단독", use_emoji=False, emoji_keywords="",
        emoji_candidates=[], emoji_selected=[],
        adjustments={}, result_png=None,
    )

def _merge(saved: dict) -> dict:
    base = _new()
    base.update({k:v for k,v in saved.items() if k in base and k not in _SKIP_KEYS})
    return base

# ── Session init ───────────────────────────────────────────────────────────────
if "sid" not in st.session_state:
    params = st.query_params
    st.session_state.sid = params.get("sid", str(uuid.uuid4())[:8])
    st.query_params["sid"] = st.session_state.sid

sid = st.session_state.sid

if "creatives" not in st.session_state:
    saved = _load_session(sid)
    st.session_state.creatives = [_merge(s) for s in saved] if saved else [_new()]

# ── Format selector ────────────────────────────────────────────────────────────
_MAX_BTNS = max(len(v) for v in FORMATS.values())

def _set_fmt(cid, fmt):
    for cr in st.session_state.creatives:
        if cr["id"] == cid:
            cr["format"] = fmt; break

def _fmt_selector(cid, current):
    for group, fmts in FORMATS.items():
        shorts = [f.replace("[믹스] ","").replace("[로고] ","") for f in fmts]
        cols = st.columns([0.7]+[1.8]*_MAX_BTNS)
        cols[0].markdown(f"<div style='font-size:12px;font-weight:700;color:#888;padding-top:6px'>{group}</div>",
                         unsafe_allow_html=True)
        for col,fmt,lbl in zip(cols[1:len(fmts)+1],fmts,shorts):
            col.button(lbl, key=f"fmt_{cid}_{fmt}",
                       type="primary" if fmt==current else "secondary",
                       use_container_width=True, on_click=_set_fmt, args=(cid,fmt))

# ── Generate helper ────────────────────────────────────────────────────────────
def _do_generate(c: dict, logo: bytes) -> bytes | None:
    try:
        if c.get("use_recommend") and ANTHROPIC_KEY and c["format"] in HAS_EMPHASIS:
            c["emphasis_color"] = recommend_color_with_claude(c["main_copy"],c["sub_copy"],ANTHROPIC_KEY)
        emoji_images = []
        if c.get("use_emoji"):
            kw = c.get("emoji_keywords","") or (c["main_copy"]+" "+c["sub_copy"])
            if not c.get("emoji_candidates"):
                c["emoji_candidates"] = fetch_emoji_candidates(kw)
            cands = c["emoji_candidates"]
            sel_urls = c.get("emoji_selected",[])
            if sel_urls:
                chosen = [cd for cd in cands if cd["img_url"] in sel_urls]
            else:
                chosen = pick_emoji_with_claude(cands,c["main_copy"],c["sub_copy"],ANTHROPIC_KEY)
            emoji_images = [b for e in chosen if (b:=fetch_emoji_png(e.get("img_url","")))]
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
            "adjustments":   c.get("adjustments",{}),
        }, logo)
    except Exception as e:
        st.error(str(e)); return None

# ── Guide validation ───────────────────────────────────────────────────────────
def _warn_guide(adj: dict) -> None:
    ms = adj.get("main_size", MAIN_PT)
    ss = adj.get("sub_size",  SUB_PT)
    if ms < GUIDE["main_size_min"] or ms > GUIDE["main_size_max"]:
        st.warning(f"⚠️ 가이드 이탈: 메인 폰트 {ms}px (허용 {GUIDE['main_size_min']}–{GUIDE['main_size_max']}px)")
    if ss < GUIDE["sub_size_min"] or ss > GUIDE["sub_size_max"]:
        st.warning(f"⚠️ 가이드 이탈: 서브 폰트 {ss}px (허용 {GUIDE['sub_size_min']}–{GUIDE['sub_size_max']}px)")
    if abs(adj.get("text_dx",0)) > GUIDE["text_dx_limit"] or abs(adj.get("text_dy",0)) > GUIDE["text_dy_limit"]:
        st.warning("⚠️ 가이드 이탈: 텍스트 위치가 안전 영역 밖입니다.")
    if abs(adj.get("obj_dx",0)) > GUIDE["obj_dx_limit"] or abs(adj.get("obj_dy",0)) > GUIDE["obj_dy_limit"]:
        st.warning("⚠️ 가이드 이탈: 오브젝트 위치가 안전 영역 밖입니다.")

# ── Left column: form ──────────────────────────────────────────────────────────
def _form(idx: int, c: dict) -> None:
    cid = c["id"]
    fmt = c["format"]
    em_type = EMPHASIS_TYPE.get(fmt,"none")

    c["name"] = st.text_input("소재명", value=c["name"],
                               placeholder="예: 에잇세컨즈_믹스", key=f"name_{cid}")
    st.markdown("**포맷 선택**")
    _fmt_selector(cid, fmt)
    st.divider()

    st.markdown("**카피**")
    if fmt in THREE_FIELD_FMTS:
        c["main_copy"] = st.text_input("메인카피(좌) Bold", value=c["main_copy"],
                                        placeholder="예: 쫀득 말랑 착화감", key=f"main_{cid}")
        c["sub_copy"]  = st.text_input("메인카피(우) Bold", value=c["sub_copy"],
                                        placeholder="예: 착화감 최고", key=f"sub_{cid}")
        c["sub_right"] = st.text_input("서브카피 Regular",  value=c.get("sub_right",""),
                                        placeholder="예: 무료배송 + SALE", key=f"subr_{cid}")
    else:
        c["main_copy"] = st.text_input("메인카피 Bold", value=c["main_copy"],
                                        placeholder="예: 지금이 딱 좋아", key=f"main_{cid}")
        c["sub_copy"]  = st.text_input("서브카피 Regular", value=c["sub_copy"],
                                        placeholder="예: 무료배송 + SALE", key=f"sub_{cid}")

    if fmt in HAS_EMPHASIS:
        _ref = c.get("sub_right","") if fmt in THREE_FIELD_FMTS else c["sub_copy"]
        c["emphasis_text"] = st.text_input(
            EMPHASIS_Q[em_type], value=c["emphasis_text"],
            placeholder="예: 무료배송 / 75%", key=f"em_{cid}")
        if c["emphasis_text"] and _ref and c["emphasis_text"] not in _ref:
            st.error(f"'{c['emphasis_text']}'가 서브카피에 없어요.")
        cr, cc = st.columns(2)
        c["use_recommend"] = cr.checkbox("AI 색상 추천", value=c.get("use_recommend",True), key=f"rec_{cid}")
        if not c["use_recommend"]:
            c["emphasis_color"] = cc.color_picker("강조 색상", value=c.get("emphasis_color","#CC0000"), key=f"clr_{cid}")

    st.divider()
    st.markdown("**오브젝트 이미지**")

    if fmt in LOGO_FMTS:
        st.caption("브랜드 로고 ✱")
        lf = st.file_uploader("브랜드 로고", type=["png","jpg","jpeg","webp"],
                               key=f"blogo_{cid}", label_visibility="collapsed")
        if lf:
            raw = lf.getvalue(); h = hashlib.md5(raw).hexdigest()
            if h != c.get("_brand_logo_hash"):
                with st.spinner("누끼 처리…"):
                    c["brand_logo"] = remove_background(raw, REMOVEBG_KEY)
                c["_brand_logo_hash"] = h

    cl, cp = st.columns(2)
    with cl:
        st.caption("레퍼런스 (선택)")
        rf = st.file_uploader("레퍼런스", type=["png","jpg","jpeg","webp"],
                               key=f"ref_{cid}", label_visibility="collapsed")
        if rf: c["reference_image"] = rf.getvalue()
    with cp:
        st.caption("상품 이미지 ✱ (1~3장)")
        prods = st.file_uploader("상품 이미지", type=["png","jpg","jpeg","webp"],
                                  accept_multiple_files=True, key=f"prod_{cid}",
                                  label_visibility="collapsed")
        if prods:
            raws = [f.getvalue() for f in prods[:3]]
            hs = [hashlib.md5(b).hexdigest() for b in raws]
            if hs != c.get("_prod_hashes"):
                with st.spinner("누끼 처리…"):
                    c["product_images"] = [remove_background(b, REMOVEBG_KEY) for b in raws]
                c["_prod_hashes"] = hs

    c["object_type"] = st.radio("배치 타입",["단독","카테고리","믹스(코디)"], horizontal=True,
                                  index=["단독","카테고리","믹스(코디)"].index(c.get("object_type","단독")),
                                  key=f"otype_{cid}")
    st.divider()

    c["use_emoji"] = st.toggle("이모티콘 추가", value=c.get("use_emoji",False), key=f"emoji_{cid}")
    if c["use_emoji"]:
        prev_kw = c.get("emoji_keywords","")
        c["emoji_keywords"] = st.text_input(
            "이모티콘 키워드", value=prev_kw,
            placeholder="예: 직장인, 컴퓨터 · 공란이면 카피 기반 자동", key=f"ekw_{cid}")
        if c["emoji_keywords"] != prev_kw:
            c["emoji_candidates"] = []  # keyword 바뀌면 후보 초기화

    st.divider()
    bc1, bc2, _ = st.columns([1.5,1.5,5])
    if bc1.button("🗑 삭제", key=f"del_{cid}"):
        st.session_state.creatives = [x for x in st.session_state.creatives if x["id"]!=cid]
        st.rerun()
    if bc2.button("📋 복제", key=f"dup_{cid}"):
        nc = copy.deepcopy(c); nc["id"] = str(uuid.uuid4())[:8]
        nc["name"] = c["name"]+"_복사"; nc["result_png"] = None
        i = next(i for i,x in enumerate(st.session_state.creatives) if x["id"]==cid)
        st.session_state.creatives.insert(i+1, nc); st.rerun()

# ── Right column: preview + controls ──────────────────────────────────────────
def _preview(idx: int, c: dict, logo: bytes) -> None:
    cid = c["id"]
    adj = c.setdefault("adjustments",{})

    # Generate button
    if st.button("▶ 소재 생성", type="primary", key=f"gen_{cid}", use_container_width=True):
        with st.spinner("생성 중…"):
            result = _do_generate(c, logo)
            if result:
                c["result_png"] = result

    # Preview
    if c.get("result_png"):
        st.image(c["result_png"], use_container_width=True)
        st.download_button("⬇ PNG 저장", data=c["result_png"],
                           file_name=f"{c['name'] or f'creative_{idx+1}'}.png",
                           mime="image/png", key=f"dl_{cid}")
    else:
        st.markdown('<div class="preview-placeholder">▶ 소재 생성을 눌러주세요</div>',
                    unsafe_allow_html=True)

    # ── Adjustments ──────────────────────────────────────────────────────────
    with st.expander("📐 위치·크기 조정", expanded=False):
        st.caption("**텍스트 폰트 크기 (px)**")
        ca, cb = st.columns(2)
        adj["main_size"] = ca.number_input("메인카피", 20, 70,
                                            adj.get("main_size", MAIN_PT), key=f"ms_{cid}")
        adj["sub_size"]  = cb.number_input("서브카피", 14, 55,
                                            adj.get("sub_size",  SUB_PT),  key=f"ss_{cid}")

        st.caption("**텍스트 블록 이동 (px)**")
        cc, cd = st.columns(2)
        adj["text_dx"] = cc.slider("← X →", -200, 200, adj.get("text_dx",0), key=f"tdx_{cid}")
        adj["text_dy"] = cd.slider("↑ Y ↓", -100, 100, adj.get("text_dy",0), key=f"tdy_{cid}")

        st.caption("**오브젝트 이동 (px)**")
        ce, cf = st.columns(2)
        adj["obj_dx"] = ce.slider("← X →", -160, 160, adj.get("obj_dx",0), key=f"odx_{cid}")
        adj["obj_dy"] = cf.slider("↑ Y ↓", -80,  80,  adj.get("obj_dy",0), key=f"ody_{cid}")

        st.caption("**이모티콘**")
        cg, ch = st.columns(2)
        adj["em_size"] = cg.slider("크기 (px)", 24, 90, adj.get("em_size",52), key=f"ems_{cid}")
        adj["em_hue"]  = ch.slider("색조 (°)", -180, 180, int(adj.get("em_hue",0)), key=f"emh_{cid}")

        _warn_guide(adj)

        if st.button("🔄 조정 반영", key=f"apply_{cid}", use_container_width=True):
            with st.spinner("재생성 중…"):
                result = _do_generate(c, logo)
                if result: c["result_png"] = result
            st.rerun()

    # ── Emoji picker ─────────────────────────────────────────────────────────
    if c.get("use_emoji"):
        with st.expander("😀 이모티콘 선택", expanded=False):
            kw = c.get("emoji_keywords","") or (c["main_copy"]+" "+c["sub_copy"])
            if not c.get("emoji_candidates"):
                c["emoji_candidates"] = fetch_emoji_candidates(kw)

            cands = c.get("emoji_candidates",[])
            sel_urls = set(c.get("emoji_selected",[]))

            if cands:
                st.caption(f"키워드 '{kw}' 기반 후보 (최대 2개 선택)")
                per_row = 5
                for i in range(0, len(cands), per_row):
                    chunk = cands[i:i+per_row]
                    cols = st.columns(len(chunk))
                    for j, cand in enumerate(chunk):
                        with cols[j]:
                            png = fetch_emoji_png(cand["img_url"])
                            if png:
                                st.image(png, width=44)
                            url = cand["img_url"]
                            is_sel = url in sel_urls
                            if st.button("✓" if is_sel else "＋",
                                         key=f"epick_{cid}_{i+j}",
                                         type="primary" if is_sel else "secondary"):
                                if is_sel:
                                    c["emoji_selected"] = [u for u in c.get("emoji_selected",[]) if u!=url]
                                else:
                                    cur = c.get("emoji_selected",[])
                                    c["emoji_selected"] = (cur[1:]+[url]) if len(cur)>=2 else cur+[url]
                                c["emoji_candidates"] = cands
                                st.rerun()
            else:
                st.caption("키워드를 입력하면 이모티콘 후보가 표시됩니다.")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="topbar">'
    '<span class="ably-badge">ABLY</span>'
    '<span class="topbar-title">비즈보드 소재 제작기</span>'
    '</div>',
    unsafe_allow_html=True)

logo_bytes = _logo()

# ── Render each creative ───────────────────────────────────────────────────────
for i, c in enumerate(st.session_state.creatives):
    label = f"소재 {i+1}" + (f" — {c['name']}" if c["name"] else "")
    with st.expander(label, expanded=True):
        col_l, col_r = st.columns([5, 6])
        with col_l:
            _form(i, c)
        with col_r:
            _preview(i, c, logo_bytes)

st.write("")

if st.button("＋ 소재 추가", use_container_width=True):
    st.session_state.creatives.append(_new()); st.rerun()

st.write("")

# ── Generate all ───────────────────────────────────────────────────────────────
if st.button("▶ 전체 소재 생성", type="primary", use_container_width=True):
    with st.spinner("전체 생성 중…"):
        for c in st.session_state.creatives:
            result = _do_generate(c, logo_bytes)
            if result: c["result_png"] = result
    st.success(f"✅ {len(st.session_state.creatives)}개 완료!")
    st.rerun()

# ── ZIP download ───────────────────────────────────────────────────────────────
done = [c for c in st.session_state.creatives if c.get("result_png")]
if done:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w") as zf:
        for i,c in enumerate(done):
            zf.writestr(f"{c['name'] or f'creative_{i+1}'}.png", c["result_png"])
    buf.seek(0)
    st.download_button(f"⬇ 전체 ZIP ({len(done)}개)", data=buf,
                       file_name="bizboard.zip", mime="application/zip",
                       use_container_width=True)

# ── Auto-save ──────────────────────────────────────────────────────────────────
_save_session(sid)
