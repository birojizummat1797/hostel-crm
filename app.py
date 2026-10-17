import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta, timezone
from database import (
    db, init_db, IS_POSTGRES, XONALAR, BARCHA_XONALAR_ROYXATI, XONA_TOMON_MAP, MUDDATLAR,
    xona_sigimini_ol, xonadagi_band_joyni_hisobla, xona_jinsini_tekshir, narx_hisobla, id_yaratish,
    jurnalga_yozish, barcha_bazani_yuklash, chiroyli_kartochka, rangla_jadval,
    toshkent_vaqti, avto_checkout_tekshir, avto_kenglik_sozla, aqlli_sana_filtri_ui,
    xona_tozalik_ozgartir, barcha_xona_tozalik_ol
)
from tg_bot import tg_xabar_yubor
from ceo_panel import render_xarajatlar_va_smena, render_ceo_panel

st.set_page_config(page_title="Y.S.H. ERP | Yangi Sergeli Hostel", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'user_login' not in st.session_state:
    st.session_state.user_login = ""
if 'xodim_ismi' not in st.session_state:
    st.session_state.xodim_ismi = ""
if 'ui_tema' not in st.session_state:
    st.session_state.ui_tema = "🌙 Qorong'u (Dark UI)"

# =========================================================
# 100% ISHLAYDIGAN DARK / LIGHT MODE VA UI/UX DIZAYN DVIJOGI
# =========================================================
def mukammal_ui_ux_sozla(tema_nomi):
    if tema_nomi == "🌙 Qorong'u (Dark UI)":
        css = """
        <style>
        .block-container { padding-top: 1.8rem !important; padding-bottom: 3rem !important; }
        .stApp { background-color: #0b0d14 !important; color: #f8fafc !important; }
        section[data-testid="stSidebar"] { background-color: #111420 !important; border-right: 1px solid #1e2436 !important; }
        
        /* Barcha sarlavha, matn, caption va metric qiymatlarini 100% yorqin oq/och-kulrang qilish */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp label, .stApp p, .stApp li,
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] span,
        div[data-testid="stMarkdownContainer"] div {
            color: #f1f5f9 !important;
        }
        div[data-testid="stCaptionContainer"],
        div[data-testid="stCaptionContainer"] p,
        div[data-testid="stCaptionContainer"] span,
        section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] * {
            color: #cbd5e1 !important;
            opacity: 1 !important;
        }

        /* CEO Panel va Dashboarddagi st.metric raqamlari (41,000 UZS va h.k.) */
        div[data-testid="metric-container"],
        div[data-testid="stMetric"] {
            background-color: #151928 !important;
            border: 1px solid #2a314b !important;
            border-left: 5px solid #8b5cf6 !important;
            padding: 16px 20px !important;
            border-radius: 14px !important;
            box-shadow: 0 6px 18px rgba(0,0,0,0.35) !important;
        }
        div[data-testid="stMetricLabel"] *,
        div[data-testid="metric-container"] label * {
            color: #cbd5e1 !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] *,
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] * {
            color: #ffffff !important;
            font-weight: 800 !important;
        }

        /* st.info, st.success, st.warning, st.error ichidagi yozuvlar */
        div[data-testid="stAlert"] * {
            color: #f8fafc !important;
        }

        /* Chap menyu bo'limlarini alohida tugma-kartochka qilish va dumaloq radio belgini yashirish */
        section[data-testid="stSidebar"] div[role="radiogroup"] {
            gap: 8px !important;
            margin-top: 6px !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {
            padding: 10px 14px !important;
            border-radius: 10px !important;
            width: 100% !important;
            background-color: #171c2e !important;
            border: 1px solid #262e48 !important;
            transition: all 0.18s ease !important;
            cursor: pointer !important;
            margin: 0 !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            background-color: #212842 !important;
            border-color: #7c3aed !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
            font-size: 14px !important;
            font-weight: 600 !important;
            color: #e2e8f0 !important;
            margin: 0 !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
            border-color: #a78bfa !important;
            box-shadow: 0 4px 14px rgba(124,58,237,0.4) !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
            color: #ffffff !important;
        }

        /* Barcha tugmalar (Download, Oddiy, Primary) */
        .stButton > button, .stDownloadButton > button {
            background-color: #1e2436 !important;
            color: #ffffff !important;
            border: 1px solid #3b4461 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
        }
        .stButton > button *, .stDownloadButton > button * {
            color: #ffffff !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            background-color: #2a324b !important;
            border-color: #8b5cf6 !important;
        }
        button[kind="primary"], .stFormSubmitButton > button {
            background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
            border: none !important;
            color: #ffffff !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
        }
        button[kind="primary"] *, .stFormSubmitButton > button * {
            color: #ffffff !important;
        }

        /* Formalar va Expanderlar */
        .stForm, div[data-testid="stExpander"] {
            background-color: #141724 !important;
            border: 1px solid #262b40 !important;
            border-radius: 14px !important;
            padding: 14px !important;
        }

        /* Modal oyna (st.dialog — Yangi bron) */
        div[role="dialog"] {
            background-color: #141724 !important;
            color: #ffffff !important;
            border: 1px solid #3b4461 !important;
            border-radius: 16px !important;
        }
        div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3,
        div[role="dialog"] p, div[role="dialog"] label, div[role="dialog"] span,
        div[data-testid="stModal"] * {
            color: #f8fafc !important;
        }
        div[role="dialog"] input, .stApp input[type="text"], .stApp input[type="number"], .stApp input[type="password"] {
            color: #0f172a !important;
            background-color: #f8fafc !important;
            font-weight: 600 !important;
        }
        div[data-baseweb="select"] * {
            color: #0f172a !important;
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    else:
        css = """
        <style>
        .block-container { padding-top: 1.8rem !important; padding-bottom: 3rem !important; }
        .stApp { background-color: #f8fafc !important; color: #0f172a !important; }
        section[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0 !important; }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp label, .stApp p { color: #0f172a !important; }
        div[data-testid="stCaptionContainer"] * { color: #475569 !important; opacity: 1 !important; }
        div[data-testid="metric-container"], div[data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-left: 6px solid #4f46e5 !important;
            padding: 16px 20px !important;
            border-radius: 14px !important;
            box-shadow: 2px 4px 12px rgba(0,0,0,0.05) !important;
        }
        div[data-testid="stMetricLabel"] * { color: #475569 !important; font-weight: 600 !important; }
        div[data-testid="stMetricValue"] * { color: #0f172a !important; font-weight: 800 !important; }
        section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 8px !important; margin-top: 6px !important; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {
            padding: 10px 14px !important;
            border-radius: 10px !important;
            width: 100% !important;
            background-color: #f1f5f9 !important;
            border: 1px solid #cbd5e1 !important;
            cursor: pointer !important;
            margin: 0 !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none !important; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label p { font-size: 14px !important; font-weight: 600 !important; color: #0f172a !important; margin: 0 !important; }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
            border-color: #4f46e5 !important;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p { color: #ffffff !important; }
        .stButton > button, .stDownloadButton > button {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }
        button[kind="primary"], .stFormSubmitButton > button {
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
        }
        button[kind="primary"] *, .stFormSubmitButton > button * { color: #ffffff !important; }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

# =========================================================
# XONADAGI KROVAT / JOY O'RNINI ANIQLASH FUNKSIYALARI
# =========================================================
def xonadagi_band_krovatlar(xona_nomi, kirish_str, chiqish_str, exclude_mijoz_id=None):
    if exclude_mijoz_id:
        rows = db.fetchall(
            "SELECT mijoz, xona_turi, izoh FROM bronlar WHERE xona=? AND mijoz_id!=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?",
            (xona_nomi, exclude_mijoz_id, chiqish_str, kirish_str)
        )
    else:
        rows = db.fetchall(
            "SELECT mijoz, xona_turi, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?",
            (xona_nomi, chiqish_str, kirish_str)
        )
    band_map = {}
    for m_ism, x_tur, iz in rows:
        birikma = f"{x_tur or ''} {iz or ''}"
        topildi = re.findall(r'(\d)-joy', birikma)
        for j_raqam in topildi:
            band_map[int(j_raqam)] = m_ism
    return band_map

def krovat_nomini_ajrat(xona_turi_str, izoh_str=""):
    birikma = f"{xona_turi_str or ''} {izoh_str or ''}"
    m = re.search(r'\[🛏️ (.*?)\]', birikma)
    if m:
        return m.group(1)
    return ""

# ==========================================
# AVTO-LOGIN (REFRESHDA VA SANA BOSILGANDA CHIQIB KETMASLIK UCHUN)
# ==========================================
if not st.session_state.logged_in and "user" in st.query_params:
    saved_login = st.query_params["user"]
    user = db.fetchone("SELECT role, ism, login FROM xodimlar WHERE login=?", (saved_login,))
    if user:
        st.session_state.logged_in = True
        st.session_state.role = user[0]
        st.session_state.xodim_ismi = user[1] if user[1] else user[2].upper()
        st.session_state.user_login = user[2]

# ==========================================
# 1. LOGIN OYNASI
# ==========================================
if not st.session_state.logged_in:
    mukammal_ui_ux_sozla(st.session_state.ui_tema)
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🏨 Yangi Sergeli Hostel | Y.S.H. ERP</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            login_input = st.text_input("Login")
            parol_input = st.text_input("Parol", type="password")
            submit_login = st.form_submit_button("Tizimga kirish", use_container_width=True, type="primary")
            if submit_login:
                user = db.fetchone("SELECT role, ism, login FROM xodimlar WHERE login=? AND parol=?", (login_input.strip(), parol_input.strip()))
                if user:
                    st.session_state.logged_in = True
                    st.session_state.role = user[0]
                    st.session_state.xodim_ismi = user[1] if user[1] else user[2].upper()
                    st.session_state.user_login = user[2]
                    st.query_params["user"] = user[2]
                    jurnalga_yozish("Tizim", st.session_state.xodim_ismi, "Tizimga kirdi", "Ish faoliyati boshlandi")
                    st.rerun()
                else:
                    st.error("Noto'g'ri login yoki parol!")
    st.stop()

# ==========================================
# HAR SAFAR AVTO-CHECKOUTNI TEKSHIRISH (12:00)
# ==========================================
avto_checkout_tekshir()

# ==========================================
# 2. CHAP MENYU VA TEMA
# ==========================================
xodim_ismi = st.session_state.xodim_ismi
hozirgi_uz_vaqt = toshkent_vaqti()
bugungi_sana = hozirgi_uz_vaqt.strftime("%Y-%m-%d")
hozirgi_soat = hozirgi_uz_vaqt.hour

st.sidebar.title("🏨 Y.S.H. ERP")
st.sidebar.markdown(f"<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>👤 {xodim_ismi} ({st.session_state.role.upper()})</div>", unsafe_allow_html=True)

tanlangan_tema = st.sidebar.selectbox(
    "🎨 Interfeys temasi:",
    ["🌙 Qorong'u (Dark UI)", "☀️ Yorug' (Standart)"],
    index=0 if st.session_state.ui_tema == "🌙 Qorong'u (Dark UI)" else 1
)
st.session_state.ui_tema = tanlangan_tema
mukammal_ui_ux_sozla(tanlangan_tema)
is_dark = (tanlangan_tema == "🌙 Qorong'u (Dark UI)")

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:12px; font-weight:800; letter-spacing:1px; margin-bottom:6px;'>ASOSIY BO'LIMLAR</div>", unsafe_allow_html=True)

if st.session_state.role == "ceo":
    menyu_variantlar = [
        "🏠 Boshqaruv paneli",
        "📅 Timeline & Shaxmatka",
        "📝 Yangi Bron / Qabul",
        "👥 Bronlar va Mehmonlar",
        "🧹 Xona tozalash",
        "🛒 Kassa (POS Market)",
        "📦 Xizmatlar va Sklad",
        "💸 Xarajat va Smena",
        "👑 CEO va Hisobotlar",
        "⚙️ Sozlamalar"
    ]
else:
    menyu_variantlar = [
        "🏠 Boshqaruv paneli",
        "📅 Timeline & Shaxmatka",
        "📝 Yangi Bron / Qabul",
        "👥 Bronlar va Mehmonlar",
        "🧹 Xona tozalash",
        "🛒 Kassa (POS Market)",
        "📦 Xizmatlar va Sklad",
        "💸 Xarajat va Smena",
        "⚙️ Sozlamalar"
    ]

# Agar Timeline jadvalidagi sana ustiga bosilgan bo'lsa, avtomatik Timeline bo'limida qolish
default_nav_idx = 1 if "tl_date" in st.query_params else 0
sahifa = st.sidebar.radio("Bo'limni tanlang:", menyu_variantlar, index=default_nav_idx, label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🔍 Global CRM Davr Filtri")
g_bosh_sana, g_tugash_sana, g_davr_nomi = aqlli_sana_filtri_ui(joylashuv="sidebar", key_prefix="global")
st.sidebar.markdown(f"<div style='font-size:13px; font-weight:600; margin-top:4px;'>📌 Faol davr: <b>{g_davr_nomi}</b></div>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.download_button(
    label="💾 Barcha bazani yuklash (Excel)",
    data=barcha_bazani_yuklash(),
    file_name=f"Y.S.H._ERP_Full_Backup_{bugungi_sana}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
st.sidebar.write("")
if st.sidebar.button("🚪 Tizimdan chiqish", use_container_width=True):
    jurnalga_yozish("Tizim", xodim_ismi, "Tizimdan chiqdi", "Ish faoliyati yakunlandi")
    st.session_state.logged_in = False
    st.session_state.role = None
    st.query_params.clear()
    st.rerun()

# =========================================================
# YORDAMCHI FUNKSIYA: YANGI BRON FORMASI
# (KROVAT / JOY YO'NALISHI VA O'RNI + KELISH SOATI BILAN!)
# =========================================================
def render_qabul_formasi(form_key_suffix="main"):
    c_top1, c_top2 = st.columns([1.5, 1.5], gap="medium")
    with c_top1:
        tomon = st.radio(
            "📍 1. Avval qanotni (tomonni) tanlang:",
            ["Chap tomon", "O'rtadagi", "O'ng tomon"],
            horizontal=True,
            key=f"qanot_{form_key_suffix}"
        )
    xona_variantlar = []
    tozalik_map = barcha_xona_tozalik_ol()
    for x_nom, (sigim, _) in XONALAR[tomon].items():
        toza_belgi = " 🔴[Tozalash kk]" if tozalik_map.get(x_nom) == "Tozalash kerak" else ""
        if tomon == "O'rtadagi":
            tavsif = f"{x_nom} (2 kishilik - Bitta Dvuxspalniy){toza_belgi}"
        elif sigim == 2:
            tavsif = f"{x_nom} (2 kishilik - 2 ta alohida krovat){toza_belgi}"
        else:
            tavsif = f"{x_nom} ({sigim} kishilik){toza_belgi}"
        xona_variantlar.append(tavsif)

    with c_top2:
        tanlangan_xona_label = st.selectbox(
            f"🛏️ 2. Xona raqamini tanlang ({tomon}):",
            xona_variantlar,
            key=f"xona_sel_{form_key_suffix}"
        )

    tanlangan_xona_nom = tanlangan_xona_label.split(" (")[0].strip()
    tanlangan_xona_sigim = XONALAR[tomon][tanlangan_xona_nom][0]
    hozir_band_krovatlar = xonadagi_band_krovatlar(tanlangan_xona_nom, bugungi_sana, (hozirgi_uz_vaqt.date() + timedelta(days=1)).strftime("%Y-%m-%d"))

    with st.form(f"qabul_form_{form_key_suffix}", clear_on_submit=True, enter_to_submit=False):
        bron_turi = st.radio("📌 Ro'yxatdan o'tish turi:", ["Hozir qabul qilish (Kirish)", "Oldindan band qilish (Bron)"], horizontal=True)
        st.markdown("---")
        col1, col2, col3 = st.columns(3, gap="medium")
        with col1:
            mijoz_ism = st.text_input("👤 Mijoz F.I.O (Ism) *")
            mijoz_tel = st.text_input("📞 Telefon raqami (ixtiyoriy):", placeholder="+998 90 123 45 67")
            jinsi = st.radio("🚻 Jinsi", ["Erkak", "Ayol"], horizontal=True)
            toifa = st.selectbox("🪪 Mijoz toifasi", ["O'zbekiston fuqarosi", "Chet el fuqarosi", "Talaba (Student)"])
            
            ks1, ks2 = st.columns([1.3, 1])
            with ks1:
                kirish_sanasi = st.date_input("📅 Kelish sanasi *", toshkent_vaqti().date())
            with ks2:
                kirish_soati_input = st.text_input("🕒 Kelish soati *", value=toshkent_vaqti().strftime("%H:%M"))
            
        with col2:
            maks_odam = 2 if tomon == "O'rtadagi" else tanlangan_xona_sigim
            odam_soni = st.number_input(f"👥 Mehmonlar soni (1 - {maks_odam})", min_value=1, max_value=maks_odam, value=1)
            
            # BOSH BOSHQARUVCHI TALABI: KROVAT / JOY O'RNINI BELGILASH (DVUXSPALNIYDAN TASHQARI)
            if tomon != "O'rtadagi":
                joy_yonalish = st.radio(
                    "🧭 Krovat tartibi (Yo'nalish):",
                    ["➡️ Chapdan o'ngga", "⬅️ O'ngdan chapga"],
                    horizontal=True
                )
                krovat_opsiyalar = []
                default_krovat = []
                for j_i in range(1, tanlangan_xona_sigim + 1):
                    if j_i in hozir_band_krovatlar:
                        krovat_opsiyalar.append(f"{j_i}-joy (🔴 Band: {hozir_band_krovatlar[j_i]})")
                    else:
                        opt_str = f"{j_i}-joy (🟢 Bo'sh)"
                        krovat_opsiyalar.append(opt_str)
                        if len(default_krovat) < 1:
                            default_krovat.append(opt_str)
                tanlangan_krovatlar = st.multiselect(
                    f"🛏️ Mijoz yotadigan joyni tanlang ({tanlangan_xona_nom}):",
                    krovat_opsiyalar,
                    default=default_krovat
                )
            else:
                joy_yonalish = ""
                tanlangan_krovatlar = []
                st.info("🛌 O'rtadagi Lyuks xona: Bitta Dvuxspalniy (To'liq xona)")

            toliq_band_vikup = st.checkbox("🔒 Xonani to'liq band qilish (Vikup — to'liq xona narxida)")
            kunlar = st.number_input("🌙 Necha kecha yashaydi? (7+ kunga 10% chegirma)", min_value=1, max_value=365, value=1)

        with col3:
            maxsus_kunlik = st.number_input("⚙️ Bir kecha maxsus narxi (0 = Avto standart)", min_value=0, value=0, step=5000)
            tolangan = st.number_input("💵 Hozir to'lanayotgan summa (UZS):", min_value=0, value=0, step=10000)
            tolov_shakli = st.selectbox("💳 To'lov shakli", ["Naqd", "Karta", "Onlayn"])
            t_taf = st.selectbox("🏦 To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
            qoshimcha_izoh = st.text_input("📝 Qo'shimcha izoh (ixtiyoriy):", placeholder="Payme, kim orqali keldi va h.k.")

        st.write("")
        submit_qabul = st.form_submit_button("✅ BRON QILISH / BAZAGA SAQLASH", type="primary", use_container_width=True)

        if submit_qabul:
            if not mijoz_ism.strip():
                st.error("⚠️ Mijoz ismini kiriting!")
            else:
                xona = tanlangan_xona_nom
                xona_sigimi = tanlangan_xona_sigim
                bazaviy_tur = "Dvuxspalniy" if tomon == "O'rtadagi" else ("2 alohida krovat" if xona_sigimi == 2 else f"{xona_sigimi} kishilik")
                
                # Tanlangan krovat / joy nomini shakllantirish
                if tomon != "O'rtadagi" and not toliq_band_vikup:
                    yon_qisqa = "Chapdan" if "Chapdan" in joy_yonalish else "O'ngdan"
                    if tanlangan_krovatlar:
                        joy_raqamlar = ", ".join([k.split(" (")[0] for k in tanlangan_krovatlar])
                    else:
                        joy_raqamlar = "1-joy"
                    krovat_yorliq = f"{yon_qisqa} {joy_raqamlar}"
                elif toliq_band_vikup and tomon != "O'rtadagi":
                    krovat_yorliq = f"Barcha joylar (1-{xona_sigimi}-joy)"
                else:
                    krovat_yorliq = "Dvuxspalniy"

                xona_turi_matn = f"To'liq band ({bazaviy_tur}) [🛏️ {krovat_yorliq}]" if (toliq_band_vikup or tomon == "O'rtadagi") else f"{bazaviy_tur} [🛏️ {krovat_yorliq}]"
                
                chiqish_sanasi = kirish_sanasi + timedelta(days=kunlar)
                kirish_str = kirish_sanasi.strftime("%Y-%m-%d")
                chiqish_str = chiqish_sanasi.strftime("%Y-%m-%d")
                
                band = xonadagi_band_joyni_hisobla(xona, kirish_str, chiqish_str)
                bosh_joy = xona_sigimi - band
                kerakli_joy = xona_sigimi if toliq_band_vikup else odam_soni
                zid_jins = None if (toliq_band_vikup or tomon == "O'rtadagi") else xona_jinsini_tekshir(xona, kirish_str, chiqish_str, jinsi)
                
                if odam_soni > xona_sigimi:
                    st.error(f"⚠️ {xona} jami {xona_sigimi} kishilik! Siz {odam_soni} kishi kiritdingiz.")
                elif toliq_band_vikup and band > 0:
                    st.error(f"⚠️ {xona} ni to'liq band (Vikup) qilib bo'lmaydi, chunki tanlangan sanalarda xonada boshqa mijoz bor!")
                elif kerakli_joy > bosh_joy:
                    st.error(f"⚠️ Xatolik: {xona} da tanlangan sanalar uchun bo'sh joy yetarli emas (Bo'sh joy: {bosh_joy} ta)!")
                elif zid_jins:
                    st.error(f"🚻 Xatolik: {xona} da tanlangan sanalarda **{zid_jins}** mijoz(lar) joylashgan! Umumiy xonaga **{jinsi}** mijozni qo'shib bo'lmaydi.")
                else:
                    kunlik_stavka, standart_jami = narx_hisobla(tomon, xona, toifa, odam_soni, kunlar, toliq_xona=toliq_band_vikup)
                    if maxsus_kunlik > 0:
                        kunlik_stavka = maxsus_kunlik
                        yakuniy_narx = maxsus_kunlik * kunlar
                        maxsus_belgi = True
                    else:
                        yakuniy_narx = standart_jami
                        maxsus_belgi = False

                    if t_taf == "Boshqa" and qoshimcha_izoh.strip():
                        t_taf = f"Boshqa ({qoshimcha_izoh.strip()})"

                    qoldiq = yakuniy_narx - tolangan
                    holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"
                    yangi_id = id_yaratish(jinsi, kirish_sanasi, toifa)
                    saq_turi = 'Hozir kirish' if bron_turi == "Hozir qabul qilish (Kirish)" else 'Bron'
                    
                    uz_now = toshkent_vaqti()
                    hozirgi_sana = uz_now.strftime("%Y-%m-%d")
                    soat_str = kirish_soati_input.strip() if kirish_soati_input.strip() else uz_now.strftime("%H:%M")
                    kirish_vaqti_toliq = f"{kirish_str} ({soat_str})"
                    muddat_nomi = f"{kunlar} kun"

                    izoh_yakuniy = f"[🛏️ {krovat_yorliq}] {qoshimcha_izoh.strip()}".strip()
                    if toliq_band_vikup and "To'liq xona" not in izoh_yakuniy:
                        izoh_yakuniy = f"[🔒 To'liq xona vikup] {izoh_yakuniy}".strip()

                    db.execute("""
                        INSERT INTO bronlar (
                            mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar,
                            kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti,
                            holat, kirish_sanasi, chiqish_sanasi, bron_turi, izoh, telefon
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        yangi_id, jinsi, kirish_vaqti_toliq, tomon, xona, xona_turi_matn, mijoz_ism.strip(), toifa,
                        odam_soni, muddat_nomi, kunlar, kunlik_stavka, standart_jami, yakuniy_narx, tolangan, qoldiq,
                        tolov_shakli, t_taf, holat, kirish_str, chiqish_str, saq_turi, izoh_yakuniy,
                        mijoz_tel.strip()
                    ))
                    if saq_turi == "Hozir kirish":
                        xona_tozalik_ozgartir(xona, "Toza")
                    if tolangan > 0:
                        db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                   (hozirgi_sana, yangi_id, mijoz_ism.strip(), "Yotoq (Qabul)", tolangan, tolov_shakli, t_taf, xodim_ismi))
                    jurnalga_yozish(yangi_id, xodim_ismi, "Yangi " + saq_turi, f"Mijoz: {mijoz_ism} ({odam_soni} kishi), Xona: {xona} ({krovat_yorliq}), Kirish: {kirish_vaqti_toliq}, To'ladi: {tolangan:,.0f} ({t_taf})")
                    
                    tel_qator = f"📞 <b>Telefon:</b> {mijoz_tel.strip()}\n" if mijoz_tel.strip() else ""
                    tg_xabar_yubor(
                        f"Yangi {saq_turi}",
                        f"👤 <b>Mijoz:</b> {mijoz_ism} ({odam_soni} kishi | {jinsi})\n"
                        f"{tel_qator}"
                        f"🛏 <b>Xona va Joy:</b> {xona} — <b>{krovat_yorliq}</b> ({kunlar} kecha)\n"
                        f"🕒 <b>Kirish:</b> {kirish_vaqti_toliq} ➡️ <b>Chiqish:</b> {chiqish_str} 12:00\n"
                        f"💰 <b>Jami hisob:</b> {yakuniy_narx:,.0f} UZS\n"
                        f"✅ <b>To'ladi:</b> {tolangan:,.0f} UZS ({t_taf})\n"
                        f"⚠️ <b>Qoldiq qarz:</b> {max(0, qoldiq):,.0f} UZS",
                        xodim_ismi, muhim=maxsus_belgi
                    )
                    st.success(f"✅ Mijoz ({mijoz_ism}) {xona} ({krovat_yorliq}) ga muvaffaqiyatli joylashtirildi! Jami hisob: {yakuniy_narx:,.0f} UZS")
                    st.rerun()

if hasattr(st, "dialog"):
    @st.dialog("➕ Yangi bron / Mehmon qabul qilish", width="large")
    def yangi_bron_modal():
        render_qabul_formasi("modal")
else:
    def yangi_bron_modal():
        pass

# ====================================================
# SAHIFA 1: 🏠 BOSHQARUV PANELI (IXCHAM KIRISH-CHIQISHLAR BILAN!)
# ====================================================
if sahifa == "🏠 Boshqaruv paneli":
    hafta_kunlari_uz = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
    oy_nomlari_uz = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    bugun_matn = f"Bugun, {hozirgi_uz_vaqt.day}-{oy_nomlari_uz[hozirgi_uz_vaqt.month]}, {hafta_kunlari_uz[hozirgi_uz_vaqt.weekday()]}"

    st.markdown(f"<h2 style='margin-bottom: 0px;'>Boshqaruv paneli</h2><p style='margin-top: 4px; margin-bottom: 18px;'>{bugun_matn} &nbsp;|&nbsp; Moliya davri: <b>{g_davr_nomi}</b></p>", unsafe_allow_html=True)

    df_barcha = db.read_df("SELECT * FROM bronlar")
    df_savdolar = db.read_df("SELECT * FROM savdolar")
    df_tolovlar = db.read_df("SELECT * FROM tolovlar_tarixi")
    df_xarajat = db.read_df("SELECT * FROM xarajatlar")
    tozalik_map = barcha_xona_tozalik_ol()

    if 'tolagan_summa' in df_barcha.columns:
        df_barcha['tolagan_summa'] = df_barcha['tolagan_summa'].fillna(0)
    if 'qoldiq' in df_barcha.columns:
        df_barcha['qoldiq'] = df_barcha['qoldiq'].fillna(0)

    jami_xonalar_soni = 36
    faol_df = df_barcha[(df_barcha['holat'] != 'Chiqib ketgan') & (df_barcha['kirish_sanasi'] <= bugungi_sana) & (df_barcha['chiqish_sanasi'] > bugungi_sana)] if not df_barcha.empty else pd.DataFrame()
    band_xonalar_set = set(faol_df['xona'].unique()) if not faol_df.empty else set()
    band_xonalar_soni = len(band_xonalar_set)
    bandlik_foiz = int(round((band_xonalar_soni / jami_xonalar_soni) * 100))

    tozalash_kerak_soni = sum(1 for x, h in tozalik_map.items() if h == "Tozalash kerak" and x not in band_xonalar_set)
    bosh_toza_xonalar_soni = max(0, jami_xonalar_soni - band_xonalar_soni - tozalash_kerak_soni)

    bugungi_kirishlar_df = df_barcha[(df_barcha['kirish_sanasi'] == bugungi_sana) & (df_barcha['holat'] != 'Chiqib ketgan')] if not df_barcha.empty else pd.DataFrame()
    hali_kirmagan_soni = len(bugungi_kirishlar_df[bugungi_kirishlar_df['bron_turi'] == 'Bron']) if not bugungi_kirishlar_df.empty else 0

    bugungi_chiqishlar_df = df_barcha[df_barcha['chiqish_sanasi'] == bugungi_sana] if not df_barcha.empty else pd.DataFrame()
    hali_chiqmagan_soni = len(bugungi_chiqishlar_df[bugungi_chiqishlar_df['holat'] != 'Chiqib ketgan']) if not bugungi_chiqishlar_df.empty else 0

    bugungi_tushum_sum = df_tolovlar[df_tolovlar['sana'] == bugungi_sana]['summa'].fillna(0).sum() if not df_tolovlar.empty else 0

    card_bg = "#141724" if is_dark else "#ffffff"
    card_border = "#262b40" if is_dark else "#cbd5e1"
    text_main = "#ffffff" if is_dark else "#0f172a"
    text_sub = "#cbd5e1" if is_dark else "#475569"

    oc1, oc2, oc3, oc4 = st.columns(4, gap="medium")
    with oc1:
        st.markdown(
            f"<div style='background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); padding: 20px; border-radius: 16px; color: white; box-shadow: 0 8px 20px rgba(124,58,237,0.3);'>"
            f"<div style='font-size: 14px; color: white;'>Band xonalar</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: white; margin: 6px 0;'>{band_xonalar_soni} <span style='font-size: 20px; color: white; opacity: 0.85;'>/ {jami_xonalar_soni}</span></div>"
            f"<div style='font-size: 13px; color: white; margin-bottom: 8px;'>{bandlik_foiz}% bandlik</div>"
            f"<div style='background: rgba(255,255,255,0.25); height: 6px; border-radius: 4px; width: 100%;'>"
            f"<div style='background: #ffffff; height: 6px; border-radius: 4px; width: {bandlik_foiz}%;'></div></div></div>",
            unsafe_allow_html=True
        )
    with oc2:
        st.markdown(
            f"<div style='background: {card_bg}; border: 1px solid {card_border}; padding: 20px; border-radius: 16px;'>"
            f"<div style='font-size: 14px; color: {text_sub};'>Bugungi kirishlar</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: {text_main}; margin: 6px 0;'>{len(bugungi_kirishlar_df)}</div>"
            f"<div style='font-size: 13px; color: {text_sub};'>{hali_kirmagan_soni} tasi hali kirmagan (Bron)</div></div>",
            unsafe_allow_html=True
        )
    with oc3:
        st.markdown(
            f"<div style='background: {card_bg}; border: 1px solid {card_border}; padding: 20px; border-radius: 16px;'>"
            f"<div style='font-size: 14px; color: {text_sub};'>Bugungi chiqishlar</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: {text_main}; margin: 6px 0;'>{len(bugungi_chiqishlar_df)}</div>"
            f"<div style='font-size: 13px; color: {text_sub};'>{hali_chiqmagan_soni} tasi hali chiqmagan</div></div>",
            unsafe_allow_html=True
        )
    with oc4:
        st.markdown(
            f"<div style='background: {card_bg}; border: 1px solid {card_border}; padding: 20px; border-radius: 16px;'>"
            f"<div style='font-size: 14px; color: {text_sub};'>Bugungi tushum</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: {text_main}; margin: 6px 0;'>{bugungi_tushum_sum:,.0f} UZS</div>"
            f"<div style='font-size: 13px; color: {text_sub};'>bugun qabul qilingan to'lovlar</div></div>",
            unsafe_allow_html=True
        )

    st.write("")
    # 1-SKRINSHOT TUZATISHI: IXCHAM, NAFIS VA KAM JOY EGALLAYDIGAN KIRISH-CHIQISHLAR BLOKI!
    with st.container(border=True):
        st.markdown("##### 🛎️ Bugungi kirish va chiqishlar")
        faol_chiqishlar = bugungi_chiqishlar_df[bugungi_chiqishlar_df['holat'] != 'Chiqib ketgan'] if not bugungi_chiqishlar_df.empty else pd.DataFrame()
        if bugungi_kirishlar_df.empty and faol_chiqishlar.empty:
            st.caption("Bugun uchun rejalashtirilgan kirish yoki chiqishlar yo'q.")
        else:
            row_bg = "#191e30" if is_dark else "#f1f5f9"
            for _, k_row in bugungi_kirishlar_df.iterrows():
                joy_str = krovat_nomini_ajrat(k_row.get('xona_turi', ''), k_row.get('izoh', ''))
                joy_b = f" • 🛏️ {joy_str}" if joy_str else ""
                soat_k = str(k_row['sana']).split("(")[1].replace(")", "") if "(" in str(k_row.get('sana', '')) else "12:00"
                if k_row.get('bron_turi') == 'Bron':
                    ck1, ck2 = st.columns([5.5, 1.3])
                    ck1.markdown(
                        f"<div style='background:{row_bg}; padding:8px 14px; border-radius:10px; border-left:4px solid #f59e0b; font-size:13.5px;'>"
                        f"🟠 <b>{k_row['mijoz']}</b> ({k_row['odam_soni']} kishi) &nbsp;—&nbsp; <span style='opacity:0.85;'>Bron kelishi • <b>{k_row['xona']}</b>{joy_b}</span></div>",
                        unsafe_allow_html=True
                    )
                    if ck2.button("🔑 Check-in", key=f"dash_in_{k_row['mijoz_id']}", use_container_width=True):
                        db.execute("UPDATE bronlar SET bron_turi='Hozir kirish' WHERE mijoz_id=?", (k_row['mijoz_id'],))
                        jurnalga_yozish(k_row['mijoz_id'], xodim_ismi, "Check-in (Keldi)", f"Bron qilingan {k_row['mijoz']} ({k_row['xona']}) kelib joylashdi")
                        st.rerun()
                else:
                    st.markdown(
                        f"<div style='background:{row_bg}; padding:8px 14px; border-radius:10px; border-left:4px solid #22c55e; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center; font-size:13.5px;'>"
                        f"<div>🟢 <b>{k_row['mijoz']}</b> ({k_row['odam_soni']} kishi) &nbsp;—&nbsp; <span style='opacity:0.85;'>Kelish ({soat_k}) • <b>{k_row['xona']}</b>{joy_b}</span></div>"
                        f"<span style='background:rgba(34,197,94,0.18); color:#4ade80; border:1px solid #22c55e; padding:3px 12px; border-radius:20px; font-size:12px; font-weight:700;'>✔ Kirish qilingan</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

            for _, ch_row in faol_chiqishlar.iterrows():
                joy_str = krovat_nomini_ajrat(ch_row.get('xona_turi', ''), ch_row.get('izoh', ''))
                joy_b = f" • 🛏️ {joy_str}" if joy_str else ""
                qarz_b = f" | ⚠️ Qarz: {int(ch_row['qoldiq']):,} UZS" if ch_row['qoldiq'] > 0 else ""
                cc1, cc2 = st.columns([5.5, 1.3])
                cc1.markdown(
                    f"<div style='background:{row_bg}; padding:8px 14px; border-radius:10px; border-left:4px solid #eab308; font-size:13.5px;'>"
                    f"🟡 <b>{ch_row['mijoz']}</b> ({ch_row['odam_soni']} kishi{qarz_b}) &nbsp;—&nbsp; <span style='opacity:0.85;'>Ketish (12:00) • <b>{ch_row['xona']}</b>{joy_b}</span></div>",
                    unsafe_allow_html=True
                )
                if ch_row['qoldiq'] <= 0:
                    if cc2.button("🚪 Chiqarish", key=f"dash_out_{ch_row['mijoz_id']}", use_container_width=True):
                        db.execute("UPDATE bronlar SET holat='Chiqib ketgan' WHERE mijoz_id=?", (ch_row['mijoz_id'],))
                        xona_tozalik_ozgartir(ch_row['xona'], "Tozalash kerak")
                        jurnalga_yozish(ch_row['mijoz_id'], xodim_ismi, "Checkout", f"{ch_row['mijoz']} ({ch_row['xona']}) chiqib ketdi")
                        st.rerun()
                else:
                    cc2.markdown("<div style='text-align:center; padding:6px; background:rgba(239,68,68,0.2); border-radius:8px; color:#f87171; font-size:12px; font-weight:700;'>⚠️ Qarzdor</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("##### 🛏️ Bugungi xonalar holati")
        xh1, xh2, xh3 = st.columns(3, gap="medium")
        xh1.markdown(f"<div style='background:{card_bg}; border:1px solid {card_border}; padding:14px; border-radius:12px;'><div style='font-size:24px; font-weight:800; color:{text_main};'>{band_xonalar_soni}</div><div style='font-size:13px; color:#a78bfa; font-weight:600;'>● Band xonalar</div></div>", unsafe_allow_html=True)
        xh2.markdown(f"<div style='background:{card_bg}; border:1px solid {card_border}; padding:14px; border-radius:12px;'><div style='font-size:24px; font-weight:800; color:{text_main};'>{bosh_toza_xonalar_soni}</div><div style='font-size:13px; color:#4ade80; font-weight:600;'>● Bo'sh (Toza)</div></div>", unsafe_allow_html=True)
        xh3.markdown(f"<div style='background:{card_bg}; border:1px solid {card_border}; padding:14px; border-radius:12px;'><div style='font-size:24px; font-weight:800; color:{text_main};'>{tozalash_kerak_soni}</div><div style='font-size:13px; color:#f87171; font-weight:600;'>● Tozalash kerak</div></div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("##### 📊 Keyingi 7 kunlik bandlik")
        kun_qisqa = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
        bar_cols = st.columns(7)
        lbl_col = "#c4b5fd" if is_dark else "#4f46e5"
        for i in range(7):
            d_obj = hozirgi_uz_vaqt.date() + timedelta(days=i)
            d_str = d_obj.strftime("%Y-%m-%d")
            k_nom = kun_qisqa[d_obj.weekday()]
            if not df_barcha.empty:
                d_band_df = df_barcha[(df_barcha['holat'] != 'Chiqib ketgan') & (df_barcha['kirish_sanasi'] <= d_str) & (df_barcha['chiqish_sanasi'] > d_str)]
                d_band_xonalar = len(set(d_band_df['xona'].unique()))
            else:
                d_band_xonalar = 0
            d_foiz = int(round((d_band_xonalar / jami_xonalar_soni) * 100))
            bar_color = "#8b5cf6" if i == 0 else "#6366f1"
            with bar_cols[i]:
                st.markdown(
                    f"<div style='text-align: center;'>"
                    f"<div style='font-size: 12px; font-weight: 700; color: {lbl_col}; margin-bottom: 6px;'>{d_foiz}%</div>"
                    f"<div style='height: 100px; width: 34px; background: rgba(124,58,237,0.15); border-radius: 8px; margin: 0 auto; display: flex; align-items: flex-end; overflow: hidden;'>"
                    f"<div style='width: 100%; height: {max(6, d_foiz)}%; background: {bar_color}; border-radius: 8px;'></div></div>"
                    f"<div style='font-size: 13px; margin-top: 6px; color: {text_main}; font-weight: 600;'>{k_nom} ({d_obj.strftime('%d.%m')})</div></div>",
                    unsafe_allow_html=True
                )

    st.markdown("---")
    st.subheader(f"💰 Moliya va Kassa Hisoboti — {g_davr_nomi}")

    if g_bosh_sana and g_tugash_sana:
        df_tol_filtr = df_tolovlar[(df_tolovlar['sana'] >= g_bosh_sana) & (df_tolovlar['sana'] <= g_tugash_sana)] if not df_tolovlar.empty else pd.DataFrame()
        df_sav_filtr = df_savdolar[(df_savdolar['sana'] >= g_bosh_sana) & (df_savdolar['sana'] <= g_tugash_sana)] if not df_savdolar.empty else pd.DataFrame()
        df_xar_filtr = df_xarajat[(df_xarajat['sana'] >= g_bosh_sana) & (df_xarajat['sana'] <= g_tugash_sana)] if not df_xarajat.empty else pd.DataFrame()
        umumiy_kassa_yotoq = df_tol_filtr[df_tol_filtr['manba'] != 'Market Savdo']['summa'].fillna(0).sum() if not df_tol_filtr.empty else 0
    else:
        df_tol_filtr = df_tolovlar
        df_sav_filtr = df_savdolar
        df_xar_filtr = df_xarajat
        umumiy_kassa_yotoq = df_barcha['tolagan_summa'].sum() if not df_barcha.empty else 0

    faol_odam_soni = int(faol_df['odam_soni'].fillna(1).sum()) if not faol_df.empty else 0
    umumiy_kassa_market = df_sav_filtr[df_sav_filtr['tolov_turi'] == 'Darhol']['jami_summa'].fillna(0).sum() if not df_sav_filtr.empty else 0
    jami_xarajatlar = df_xar_filtr['summa'].fillna(0).sum() if not df_xar_filtr.empty else 0
    umumiy_qarz = df_barcha[(df_barcha['qoldiq'] > 0) & (df_barcha['holat'] != 'Chiqib ketgan')]['qoldiq'].sum() if not df_barcha.empty else 0
    sof_balans = (umumiy_kassa_yotoq + umumiy_kassa_market) - jami_xarajatlar

    c1, c2, c3, c4, c5, c6 = st.columns(6, gap="small")
    with c1: st.markdown(chiroyli_kartochka("👥", "Faol Mehmon", f"{faol_odam_soni} kishi", "#8b5cf6"), unsafe_allow_html=True)
    with c2: st.markdown(chiroyli_kartochka("💰", "Yotoq Tushum", f"{umumiy_kassa_yotoq:,.0f}", "#f59e0b"), unsafe_allow_html=True)
    with c3: st.markdown(chiroyli_kartochka("🛒", "Market Savdo", f"{umumiy_kassa_market:,.0f}", "#10b981"), unsafe_allow_html=True)
    with c4: st.markdown(chiroyli_kartochka("➖", "Xarajatlar", f"{jami_xarajatlar:,.0f}", "#64748b"), unsafe_allow_html=True)
    with c5: st.markdown(chiroyli_kartochka("🏦", "Sof Balans", f"{sof_balans:,.0f}", "#2563eb"), unsafe_allow_html=True)
    with c6: st.markdown(chiroyli_kartochka("⚠️", "Joriy Qarzlar", f"{umumiy_qarz:,.0f}", "#ef4444"), unsafe_allow_html=True)

    if not df_tol_filtr.empty or not df_xar_filtr.empty:
        if not df_tol_filtr.empty:
            df_tol_filtr = df_tol_filtr.copy()
            df_tol_filtr['tolov_tafsiloti'] = df_tol_filtr['tolov_tafsiloti'].replace('', "Noma'lum").fillna("Noma'lum")
            kirim_gr = df_tol_filtr.groupby('tolov_tafsiloti')['summa'].sum().to_dict()
        else:
            kirim_gr = {}
        chiqim_gr = df_xar_filtr.groupby('tolov_turi')['summa'].sum().to_dict() if not df_xar_filtr.empty else {}
        
        standart_kassalar = ["Naqd", "Click", "Humo", "Uzcard", "Terminal"]
        barcha_turlar = sorted(list(set(list(kirim_gr.keys()) + list(chiqim_gr.keys()))))
        
        asosiy_list, boshqa_list = [], []
        boshqa_kirim_jami, boshqa_chiqim_jami = 0, 0
        
        for tur in barcha_turlar:
            k_s = kirim_gr.get(tur, 0)
            c_s = chiqim_gr.get(tur, 0)
            if tur in standart_kassalar:
                asosiy_list.append((tur, k_s, c_s, k_s - c_s))
            else:
                boshqa_kirim_jami += k_s
                boshqa_chiqim_jami += c_s
                boshqa_list.append({
                    "To'lov turi (Izoh)": tur,
                    "Kirim": f"{int(k_s):,} UZS",
                    "Xarajat": f"{int(c_s):,} UZS",
                    "Sof Qoldiq": f"{int(k_s - c_s):,} UZS"
                })
        
        if boshqa_list:
            asosiy_list.append(("📂 Boshqa to'lovlar (Jami)", boshqa_kirim_jami, boshqa_chiqim_jami, boshqa_kirim_jami - boshqa_chiqim_jami))
            
        t_cols = st.columns(4, gap="small")
        for idx, (nom, k_s, c_s, q_s) in enumerate(asosiy_list):
            with t_cols[idx % 4]:
                st.info(f"**{nom}**\n\n### {q_s:,.0f} UZS\n*(Kirim: {k_s:,.0f} | Xarajat: {c_s:,.0f})*")
                
        if boshqa_list:
            df_boshqa = pd.DataFrame(boshqa_list)
            with st.expander(f"📂 «Boshqa» to'lovlarning batafsil ro'yxatini ko'rish ({len(boshqa_list)} xil usul — Jami: {boshqa_kirim_jami - boshqa_chiqim_jami:,.0f} UZS)"):
                st.dataframe(df_boshqa, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_boshqa))

    df_mahsulotlar = db.read_df("SELECT nomi, hajmi, kategoriya, sub_kategoriya, narxi, qoldiq, izoh FROM mahsulotlar WHERE qoldiq <= 5 ORDER BY qoldiq ASC")
    if not df_mahsulotlar.empty:
        with st.expander(f"🚨 DIQQAT: Omborda {len(df_mahsulotlar)} ta mahsulot tugayapti! (Batafsil jadvalni ko'rish uchun bosing)", expanded=False):
            df_m_kam = df_mahsulotlar.copy()
            df_m_kam['hajmi'] = df_m_kam['hajmi'].replace('', '-')
            df_m_kam['izoh'] = df_m_kam['izoh'].fillna('')
            df_m_kam['narxi'] = df_m_kam['narxi'].apply(lambda x: f"{int(x):,} UZS")
            df_m_kam['Holat'] = df_m_kam['qoldiq'].apply(lambda q: "🔴 Tugagan (0 ta)" if q <= 0 else f"🟡 Kam qoldi ({q} ta)")
            df_m_kam = df_m_kam[['nomi', 'hajmi', 'kategoriya', 'sub_kategoriya', 'narxi', 'qoldiq', 'Holat', 'izoh']]
            df_m_kam.columns = ["Mahsulot Nomi", "Hajmi / O'lchami", "Kategoriya", "Turi", "Sotuv Narxi", "Qoldiq Soni", "Holat", "Izoh"]
            st.dataframe(df_m_kam, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_m_kam))

# ====================================================
# SAHIFA 2: 📅 TIMELINE & SHAXMATKA
# (2-SKRINSHOT TUZATISHI: ORTIQCHA PANELLARSIZ, TO'G'RIDAN-TO'G'RI JADVALDAGI SANALAR BOSILADI!)
# ====================================================
elif sahifa == "📅 Timeline & Shaxmatka":
    tl_col1, tl_col2 = st.columns([3, 1])
    with tl_col1:
        st.header("📅 Timeline & Xonalar Shaxmatkasi")
    with tl_col2:
        if hasattr(st, "dialog"):
            if st.button("➕ Yangi bron", type="primary", use_container_width=True):
                yangi_bron_modal()

    col_kat, col_kun, col_san = st.columns([2.2, 1.3, 1.1])
    tanlangan_katalog = col_kat.radio("Qanot (Qavat):", ["Barchasi", "Chap tomon", "O'rtadagi", "O'ng tomon"], horizontal=True)
    kun_soni_tl = col_kun.radio("Ko'rinish:", [7, 14, 30], index=1, horizontal=True, format_func=lambda x: f"{x} kun")
    bosh_sana = col_san.date_input("Boshlanish sanasi:", toshkent_vaqti().date() - timedelta(days=1))

    c_r1, c_r2 = st.columns([2.5, 1])
    rejim_tl = c_r1.radio(
        "Shaxmatka uslubi:",
        ["📊 Grafik Timeline (Videodagidek chiziqli + Hover)", "🔲 Jadval Shaxmatka (Bo'sh o'rinlar soni bilan)"],
        horizontal=True
    )
    arxiv_korsat_tl = c_r2.checkbox("⚪ Chiqib ketganlarni ham ko'rsatish", value=False)

    sana_royxati = [bosh_sana + timedelta(days=i) for i in range(kun_soni_tl)]
    sana_str_list = [d.strftime("%Y-%m-%d") for d in sana_royxati]
    bosh_sana_str = sana_str_list[0]
    oxirgi_sana_str = (bosh_sana + timedelta(days=kun_soni_tl)).strftime("%Y-%m-%d")
    tozalik_map = barcha_xona_tozalik_ol()
    kun_nom_qisqa = ["DU", "SE", "CH", "PA", "JU", "SH", "YA"]

    # AGAR JADVALDAGI SANA USTIGA BOSILGAN BO'LSA (?tl_date=YYYY-MM-DD), O'SHA SANADAGI XONALAR VA MIJOZLARNI KO'RSATISH!
    tanlangan_tl_sana = st.query_params.get("tl_date", None)
    if tanlangan_tl_sana:
        shu_kun_bronlar = db.read_df(
            "SELECT mijoz_id, mijoz, xona, xona_turi, odam_soni, sana, chiqish_sanasi, qoldiq, telefon, izoh FROM bronlar WHERE holat!='Chiqib ketgan' AND kirish_sanasi <= ? AND chiqish_sanasi > ?",
            (tanlangan_tl_sana, tanlangan_tl_sana)
        )
        with st.container(border=True):
            hd1, hd2 = st.columns([4.5, 1])
            band_x_soni = len(shu_kun_bronlar['xona'].unique()) if not shu_kun_bronlar.empty else 0
            jami_m_soni = int(shu_kun_bronlar['odam_soni'].sum()) if not shu_kun_bronlar.empty else 0
            hd1.markdown(f"##### 📅 **{tanlangan_tl_sana}** sanasidagi xonalar va mehmonlar: **{band_x_soni} / 36 ta xona band** ({jami_m_soni} nafar mehmon)")
            if hd2.button("✖️ Yopish", use_container_width=True):
                if "tl_date" in st.query_params:
                    del st.query_params["tl_date"]
                st.rerun()
            if not shu_kun_bronlar.empty:
                shu_kun_bronlar['Joy (Krovat)'] = shu_kun_bronlar.apply(lambda r: krovat_nomini_ajrat(r.get('xona_turi', ''), r.get('izoh', '')) or "Standart", axis=1)
                shu_kun_view = shu_kun_bronlar[['mijoz_id', 'mijoz', 'xona', 'Joy (Krovat)', 'odam_soni', 'sana', 'chiqish_sanasi', 'qoldiq', 'telefon']].copy()
                shu_kun_view.columns = ["ID", "Mehmon", "Xona", "Krovat / Joy", "Odam", "Kirgan Vaqti", "Ketish Sanasi", "Qoldiq Qarz", "Telefon"]
                shu_kun_view["Qoldiq Qarz"] = shu_kun_view["Qoldiq Qarz"].apply(lambda x: f"{max(0, int(x)):,} UZS")
                st.dataframe(shu_kun_view, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(shu_kun_view))
            else:
                st.success(f"🟢 {tanlangan_tl_sana} sanasida barcha 36 ta xona bo'sh!")

    if rejim_tl == "📊 Grafik Timeline (Videodagidek chiziqli + Hover)":
        st.markdown(
            "<div style='display:flex; gap:18px; font-size:13px; margin: 10px 0; flex-wrap:wrap;'>"
            "<span>🟢 <b>Kirish qilingan (To'langan)</b></span>"
            "<span>🟠 <b>Kutilmoqda (Oldindan bron)</b></span>"
            "<span>🔴 <b>To'lanmagan (Qarzdor)</b></span>"
            "<span>⚪ <b>Chiqib ketgan (Arxiv)</b></span>"
            "<span>💡 <i>Jadvaldagi <b>Sana (JU 23, SH 24...)</b> ustiga bossangiz — shu kundagi mehmonlar chiqadi!</i></span>"
            "</div>",
            unsafe_allow_html=True
        )

        if arxiv_korsat_tl:
            tl_bronlar = db.read_df(
                "SELECT * FROM bronlar WHERE kirish_sanasi < ? AND chiqish_sanasi > ? ORDER BY kirish_sanasi ASC, id ASC",
                (oxirgi_sana_str, bosh_sana_str)
            )
        else:
            tl_bronlar = db.read_df(
                "SELECT * FROM bronlar WHERE holat != 'Chiqib ketgan' AND kirish_sanasi < ? AND chiqish_sanasi > ? ORDER BY kirish_sanasi ASC, id ASC",
                (oxirgi_sana_str, bosh_sana_str)
            )

        bg_tbl = "#111420" if is_dark else "#ffffff"
        border_tbl = "#22273b" if is_dark else "#cbd5e1"
        txt_tbl = "#e2e8f0" if is_dark else "#0f172a"
        sec_hdr_bg = "#1e1b4b" if is_dark else "#ede9fe"
        sec_hdr_col = "#c4b5fd" if is_dark else "#4c1d95"
        room_bg = "rgba(124,58,237,0.06)" if is_dark else "#f8fafc"
        curr_user_q = st.session_state.user_login

        html_parts = [
            f"<style>"
            f".ysh-tl-wrap {{ overflow-x: auto; border: 1px solid {border_tbl}; border-radius: 14px; background: {bg_tbl}; padding: 8px; }}"
            f".ysh-wing-details {{ margin-bottom: 10px; border: 1px solid {border_tbl}; border-radius: 10px; overflow: visible; }}"
            f".ysh-wing-summary {{ padding: 10px 14px; font-weight: 800; font-size: 13px; background: {sec_hdr_bg}; color: {sec_hdr_col}; cursor: pointer; user-select: none; border-radius: 9px; list-style: none; display: flex; justify-content: space-between; align-items: center; }}"
            f".ysh-tl-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; color: {txt_tbl}; min-width: 950px; table-layout: fixed; }}"
            f".ysh-tl-table th, .ysh-tl-table td {{ border: 1px solid {border_tbl}; padding: 5px 3px; text-align: center; font-size: 12px; position: relative; vertical-align: middle; height: 38px; }}"
            f".ysh-date-link {{ display: block; text-decoration: none !important; color: inherit !important; padding: 2px; border-radius: 6px; transition: background 0.15s; }}"
            f".ysh-date-link:hover {{ background: rgba(139,92,246,0.35) !important; }}"
            f".ysh-tl-room {{ text-align: left !important; padding: 6px 12px !important; font-weight: 700; width: 145px !important; background: {room_bg}; }}"
            f".ysh-bar {{ display: block; padding: 6px 10px; border-radius: 8px; color: #ffffff !important; font-weight: 600; font-size: 12px; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin: 2px 1px; cursor: pointer; position: relative; box-shadow: 0 2px 6px rgba(0,0,0,0.25); }}"
            f".ysh-bar:hover {{ overflow: visible; z-index: 999; }}"
            f".ysh-bar .ysh-tip {{ visibility: hidden; opacity: 0; position: absolute; left: 8px; top: 32px; background: #0f172a; color: #f8fafc !important; border: 1px solid #7c3aed; border-radius: 10px; padding: 10px 14px; width: 265px; z-index: 1000; box-shadow: 0 10px 25px rgba(0,0,0,0.65); font-weight: 400; font-size: 12px; line-height: 1.5; transition: opacity 0.15s; pointer-events: none; white-space: normal; }}"
            f".ysh-bar .ysh-tip b, .ysh-bar .ysh-tip span {{ color: #f8fafc !important; }}"
            f".ysh-bar:hover .ysh-tip {{ visibility: visible; opacity: 1; }}"
            f"</style>"
            f"<div class='ysh-tl-wrap'>"
        ]

        # 3-QIZIL MAYDON TALABI: JADVALDAGI SANALARNING O'ZI BOSILADIGAN QILINDI!
        thead_html = "<thead><tr><th class='ysh-tl-room'>Xona</th>"
        for d in sana_royxati:
            d_iso = d.strftime("%Y-%m-%d")
            is_today = (d_iso == bugungi_sana)
            is_selected = (d_iso == tanlangan_tl_sana)
            if is_selected:
                th_style = "background: #ec4899; color: #ffffff !important; border-radius: 6px;"
            elif is_today:
                th_style = "background: #7c3aed; color: #ffffff !important; border-radius: 6px;"
            else:
                th_style = ""
            thead_html += (
                f"<th style='{th_style}' title='Shu sanadagi mehmonlarni ko`rish uchun bosing'>"
                f"<a class='ysh-date-link' href='?user={curr_user_q}&tl_date={d_iso}' target='_self'>"
                f"{kun_nom_qisqa[d.weekday()]}<br><b>{d.day}</b></a></th>"
            )
        thead_html += "</tr></thead>"

        for tomon, xonalar in XONALAR.items():
            if tanlangan_katalog != "Barchasi" and tomon != tanlangan_katalog:
                continue
            html_parts.append(
                f"<details class='ysh-wing-details' open>"
                f"<summary class='ysh-wing-summary'><span>▾ {tomon.upper()} ({len(xonalar)} XONA)</span><span style='font-size:11px; font-weight:500; opacity:0.85;'>Yig'ish / Ochish ↕️</span></summary>"
                f"<table class='ysh-tl-table'>{thead_html}<tbody>"
            )
            for xona, (sigim, _) in xonalar.items():
                iflos_dot = "<span style='color:#ef4444; float:right; font-size:15px;' title='Tozalash kerak'>●</span>" if tozalik_map.get(xona) == "Tozalash kerak" else ""
                tur_k = "Luxe" if tomon == "O'rtadagi" else f"{sigim} kishilik"
                
                x_df = tl_bronlar[tl_bronlar['xona'] == xona] if not tl_bronlar.empty else pd.DataFrame()
                
                lanes = []
                if not x_df.empty:
                    for _, br in x_df.iterrows():
                        k_s = str(br['kirish_sanasi'])
                        ch_s = str(br['chiqish_sanasi'])
                        start_idx = 0
                        for idx_d, d_s in enumerate(sana_str_list):
                            if d_s >= k_s:
                                start_idx = idx_d
                                break
                        end_idx = len(sana_str_list)
                        for idx_d, d_s in enumerate(sana_str_list):
                            if d_s >= ch_s:
                                end_idx = idx_d
                                break
                        if end_idx <= start_idx:
                            end_idx = min(len(sana_str_list), start_idx + 1)

                        joylandi = False
                        for lane in lanes:
                            if all(slot is None for slot in lane[start_idx:end_idx]):
                                lane[start_idx] = (br, end_idx - start_idx)
                                for s_i in range(start_idx + 1, end_idx):
                                    lane[s_i] = "SKIP"
                                joylandi = True
                                break
                        if not joylandi:
                            new_lane = [None] * len(sana_str_list)
                            new_lane[start_idx] = (br, end_idx - start_idx)
                            for s_i in range(start_idx + 1, end_idx):
                                new_lane[s_i] = "SKIP"
                            lanes.append(new_lane)

                if not lanes:
                    lanes = [[None] * len(sana_str_list)]

                rowspan_n = len(lanes)
                for l_idx, lane in enumerate(lanes):
                    html_parts.append("<tr>")
                    if l_idx == 0:
                        html_parts.append(
                            f"<td class='ysh-tl-room' rowspan='{rowspan_n}'>{xona} {iflos_dot}<br>"
                            f"<span style='font-size:11px; opacity:0.7; font-weight:400;'>{tur_k}</span></td>"
                        )
                    for slot in lane:
                        if slot == "SKIP":
                            continue
                        elif slot is None:
                            html_parts.append("<td></td>")
                        else:
                            br, span_len = slot
                            if br['holat'] == 'Chiqib ketgan':
                                b_col, hol_nom = "#64748b", "Chiqib ketgan"
                            elif float(br.get('qoldiq', 0) or 0) > 0:
                                b_col, hol_nom = "#dc2626", "Qarzdor"
                            elif br.get('bron_turi') == 'Bron' or br['kirish_sanasi'] > bugungi_sana:
                                b_col, hol_nom = "#d97706", "Kutilmoqda (Bron)"
                            else:
                                b_col, hol_nom = "#16a34a", "Kirish qilingan"

                            m_ism = str(br['mijoz']).replace("<", "").replace(">", "").replace("'", "`")
                            m_tel = str(br.get('telefon', '') or '—').replace("<", "").replace(">", "")
                            m_jam = int(br.get('faktik_narx', 0) or 0)
                            m_tol = int(br.get('tolagan_summa', 0) or 0)
                            m_qar = max(0, int(br.get('qoldiq', 0) or 0))
                            krovat_inf = krovat_nomini_ajrat(br.get('xona_turi', ''), br.get('izoh', ''))
                            krovat_qisqa = f" [{krovat_inf}]" if krovat_inf else ""
                            vik_icon = "🔒 " if "To'liq band" in str(br.get('xona_turi', '')) else ""

                            bar_html = (
                                f"<td colspan='{span_len}'>"
                                f"<div class='ysh-bar' style='background:{b_col};'>"
                                f"{vik_icon}{m_ism} ({br['odam_soni']}k){krovat_qisqa}"
                                f"<div class='ysh-tip'>"
                                f"<b>{m_ism}</b><br>"
                                f"<b>Joy (Krovat):</b> {krovat_inf or 'Standart'}<br>"
                                f"<b>Telefon:</b> {m_tel}<br>"
                                f"<b>Kelish:</b> {br.get('sana') or br['kirish_sanasi']}<br>"
                                f"<b>Ketish:</b> {br['chiqish_sanasi']} (12:00)<br>"
                                f"<b>Mehmon:</b> {br['odam_soni']} kishi ({br['kunlar']} kecha) • {hol_nom}<br>"
                                f"<b>Jami:</b> {m_jam:,} UZS<br>"
                                f"<b>To'langan / Qarz:</b> {m_tol:,} / {m_qar:,} UZS"
                                f"</div></div></td>"
                            )
                            html_parts.append(bar_html)
                    html_parts.append("</tr>")
            html_parts.append("</tbody></table></details>")

        html_parts.append("</div>")
        st.markdown("".join(html_parts), unsafe_allow_html=True)

    else:
        oraliq_bronlar = db.read_df("SELECT xona, xona_turi, kirish_sanasi, chiqish_sanasi, odam_soni FROM bronlar WHERE holat!='Chiqib ketgan' AND kirish_sanasi < ? AND chiqish_sanasi > ?", (oxirgi_sana_str, bosh_sana_str))
        for tomon, xonalar in XONALAR.items():
            if tanlangan_katalog != "Barchasi" and tomon != tanlangan_katalog:
                continue
            with st.expander(f"▾ {tomon.upper()} ({len(xonalar)} XONA)", expanded=True):
                matrix = []
                for xona, info in xonalar.items():
                    sigim = info[0]
                    iflos_b = " 🔴" if tozalik_map.get(xona) == "Tozalash kerak" else ""
                    qator = {"Xona": f"{xona} ({sigim} k){iflos_b}"}
                    xona_bronlar = oraliq_bronlar[oraliq_bronlar['xona'] == xona] if (not oraliq_bronlar.empty and 'xona' in oraliq_bronlar.columns) else pd.DataFrame()
                        
                    for d in sana_royxati:
                        d_str = d.strftime("%Y-%m-%d")
                        band = 0
                        if not xona_bronlar.empty:
                            band_mask = (xona_bronlar['kirish_sanasi'] <= d_str) & (xona_bronlar['chiqish_sanasi'] > d_str)
                            kunlik_df = xona_bronlar[band_mask]
                            for _, b_row in kunlik_df.iterrows():
                                if "To'liq band" in str(b_row.get('xona_turi', '') or ''):
                                    band += sigim
                                else:
                                    band += int(b_row.get('odam_soni', 1) or 1)
                        bosh = sigim - band
                        qator[d.strftime("%d.%m")] = "🟩 Bo'sh" if bosh == sigim else "🟥 Band" if bosh <= 0 else f"🟨 {bosh} ta"
                    matrix.append(qator)
                
                st.dataframe(
                    pd.DataFrame(matrix),
                    use_container_width=True,
                    hide_index=True,
                    column_config={"Xona": st.column_config.Column("Xona", width=165)}
                )

    st.markdown("---")
    st.subheader("🔍 Xona va Krovatlar (Joylar) holatini tekshirish")
    x_tanlov = st.selectbox("Xonani tanlang:", [f"{x} ({XONA_TOMON_MAP[x]})" for x in XONA_TOMON_MAP.keys()])
    xona_nomi = x_tanlov.split(" (")[0].strip()
    umumiy_sigim = xona_sigimini_ol(xona_nomi)
    bugun_ichidagilar = db.fetchall("SELECT mijoz, jinsi, sana, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh, xona_turi, telefon FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona_nomi, bugungi_sana, bugungi_sana))
    if not bugun_ichidagilar:
        st.success(f"🟢 **{xona_nomi} hozir bo'sh ({umumiy_sigim} kishilik) | Tozalik holati: {tozalik_map.get(xona_nomi, 'Toza')}**")
    else:
        for m in bugun_ichidagilar:
            joy_nom = krovat_nomini_ajrat(m[8], m[7])
            joy_badge = f" | 🛏️ **{joy_nom}**" if joy_nom else ""
            vik_m = " 🔒 *(To'liq xona vikup)*" if "To'liq band" in str(m[8] or '') else ""
            tel_m = f" | 📞 {m[9]}" if m[9] else ""
            qarz_matni = f" | ⚠️ Qarz: {m[5]:,.0f} UZS" if m[5] > 0 else ""
            st.markdown(f"- 👤 **{m[0]}** ({m[6]} kishi | {m[1]}{joy_badge}{tel_m}{vik_m} | 📥 Kirgan: {m[2]} | 🛫 Chiqish: {m[3]} 12:00){qarz_matni}")

# ====================================================
# SAHIFA 3: 📝 YANGI BRON / QABUL
# ====================================================
elif sahifa == "📝 Yangi Bron / Qabul":
    st.header("📝 Yangi Mijoz Qabul Qilish / Oldindan Bron")
    render_qabul_formasi("page")

# ====================================================
# SAHIFA 4: 👥 BRONLAR VA MEHMONLAR (JOY/KROVAT O'RNI BILAN!)
# ====================================================
elif sahifa == "👥 Bronlar va Mehmonlar":
    st.header("👥 Bronlar va Mehmonlar Boshqaruvi")
    df = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")
    
    ko_rejim = st.radio(
        "Bo'limni tanlang:",
        [
            "📋 Barcha Faol Mehmonlar va Arxiv (Jadval)",
            "🧾 Bron tafsilotlari (Shaxsiy karta, To'lovlar & Kvitansiya)",
            "🛠️ Tezkor Amallar (Qarz yopish, Muddat cho'zish, Ko'chirish, Checkout, Tahrirlash)"
        ],
        horizontal=True
    )
    st.markdown("---")

    if not df.empty:
        df['faktik_narx'] = df['faktik_narx'].fillna(0)
        df['tolagan_summa'] = df['tolagan_summa'].fillna(0)
        df['qoldiq'] = df['qoldiq'].fillna(0)
        df['izoh'] = df['izoh'].fillna('')
        df['xona_turi'] = df['xona_turi'].fillna('')
        df['kirish_vaqti_korsat'] = df.apply(lambda r: str(r['sana']) if '(' in str(r.get('sana', '')) else f"{r.get('kirish_sanasi', '')} (12:00)", axis=1)
        
        def xona_va_joy_korsat(r):
            x_str = f"{r['xona']} 🔒" if "To'liq band" in str(r.get('xona_turi', '')) else str(r['xona'])
            j_str = krovat_nomini_ajrat(r.get('xona_turi', ''), r.get('izoh', ''))
            return f"{x_str} ({j_str})" if j_str else x_str

        df['xona_korsat'] = df.apply(xona_va_joy_korsat, axis=1)

    if ko_rejim == "📋 Barcha Faol Mehmonlar va Arxiv (Jadval)":
        qidiruv = st.text_input("🔍 Mijoz F.I.O, ID, Xona yoki Izoh bo'yicha qidiruv:", placeholder="Ism, ID, xona yoki izoh...")
        df_q = df.copy()
        if qidiruv and not df_q.empty:
            df_q = df_q[
                df_q['mijoz'].str.contains(qidiruv, case=False, na=False) |
                df_q['mijoz_id'].str.contains(qidiruv, case=False, na=False) |
                df_q['xona'].str.contains(qidiruv, case=False, na=False) |
                df_q['izoh'].str.contains(qidiruv, case=False, na=False)
            ]

        faol_df = df_q[(df_q['holat'] != 'Chiqib ketgan') & (df_q['kirish_sanasi'] <= bugungi_sana)] if not df_q.empty else pd.DataFrame()
        bron_df = df_q[(df_q['holat'] != 'Chiqib ketgan') & (df_q['kirish_sanasi'] > bugungi_sana)] if not df_q.empty else pd.DataFrame()
        arxiv_df = df_q[df_q['holat'] == 'Chiqib ketgan'] if not df_q.empty else pd.DataFrame()
        if g_bosh_sana and g_tugash_sana and not arxiv_df.empty:
            arxiv_df = arxiv_df[(arxiv_df['chiqish_sanasi'] >= g_bosh_sana) & (arxiv_df['chiqish_sanasi'] <= g_tugash_sana)]

        def format_qoldiq_ustun(x):
            val = int(x)
            return f"0 UZS (Avans: +{abs(val):,})" if val < 0 else f"{val:,} UZS"

        def aqlli_holat_matni(r):
            if r['holat'] == 'Chiqib ketgan':
                return 'Chiqib ketgan'
            if r['qoldiq'] > 0:
                return '🚨 Vaqti tugagan (QARZ!)' if (r['chiqish_sanasi'] <= bugungi_sana and hozirgi_soat >= 6) else 'Qarzdorlik'
            if r['chiqish_sanasi'] == bugungi_sana and hozirgi_soat >= 6:
                return '⏳ Ketish vaqti (12:00)'
            return "To'langan"

        if not bron_df.empty:
            st.subheader("📅 Oldindan Bron qilinganlar")
            bron_korsatish = bron_df[['mijoz_id', 'mijoz', 'xona_korsat', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'izoh']].copy()
            bron_korsatish.columns = ["ID", "Mijoz", "Xona va Joy", "Odam", "Kun", "Jami Summa", "To'langan", "Qoldiq", "Kirish (Sana va Soat)", "Chiqish", "Izoh (To'liq)"]
            for col in ["Jami Summa", "To'langan"]:
                bron_korsatish[col] = bron_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
            bron_korsatish["Qoldiq"] = bron_korsatish["Qoldiq"].apply(format_qoldiq_ustun)
            st.dataframe(bron_korsatish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(bron_korsatish))

        st.subheader(f"🟢 Hozirgi (Faol) Mijozlar ({len(faol_df)} ta)")
        if not faol_df.empty:
            faol_korsatish = faol_df[['mijoz_id', 'mijoz', 'xona_korsat', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'holat', 'izoh']].copy()
            faol_korsatish['holat'] = faol_df.apply(aqlli_holat_matni, axis=1)
            faol_korsatish['chiqish_sanasi'] = faol_korsatish['chiqish_sanasi'] + ' 12:00'
            faol_korsatish.columns = ["ID", "Mijoz", "Xona va Joy", "Odam", "Kun", "Jami Summa", "To'langan", "Qoldiq", "Kirish (Sana va Soat)", "Chiqish", "Holat", "Izoh (To'liq)"]
            for col in ["Jami Summa", "To'langan"]:
                faol_korsatish[col] = faol_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
            faol_korsatish["Qoldiq"] = faol_korsatish["Qoldiq"].apply(format_qoldiq_ustun)
            st.dataframe(faol_korsatish.style.apply(rangla_jadval, axis=1), use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(faol_korsatish))
        else:
            st.info("📭 Hozircha hostelda faol mijozlar yo'q.")

        with st.expander(f"🗄️ Arxivdagi (Chiqib ketgan) mijozlar — Davr: {g_davr_nomi} ({len(arxiv_df)} ta)", expanded=bool(qidiruv and not arxiv_df.empty)):
            if not arxiv_df.empty:
                arx_korsatish = arxiv_df[['mijoz_id', 'mijoz', 'xona_korsat', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'holat', 'izoh']].copy()
                arx_korsatish.columns = ["ID", "Mijoz", "Xona va Joy", "Odam", "Kun", "Jami Summa", "To'langan", "Kirgan Vaqti", "Chiqib Ketgan Sana", "Holat", "Izoh (To'liq)"]
                for col in ["Jami Summa", "To'langan"]:
                    arx_korsatish[col] = arx_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(arx_korsatish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(arx_korsatish))
            else:
                st.info("Arxivda mijozlar topilmadi.")

    elif ko_rejim == "🧾 Bron tafsilotlari (Shaxsiy karta, To'lovlar & Kvitansiya)":
        if df.empty:
            st.info("Bazada mijozlar yo'q.")
        else:
            tanlangan_folio = st.selectbox(
                "🔍 Tafsilotlarini ko'rish uchun mehmonni tanlang:",
                df['mijoz_id'] + " — " + df['mijoz'] + " (" + df['xona_korsat'] + " | " + df['holat'] + ")"
            )
            f_id = tanlangan_folio.split(" — ")[0]
            f_row = df[df['mijoz_id'] == f_id].iloc[0]

            with st.container(border=True):
                fc1, fc2 = st.columns([2, 1.5])
                with fc1:
                    hol_badge = "🟢 Faol (Yashamoqda)" if f_row['holat'] != 'Chiqib ketgan' else "⚪ Chiqib ketgan (Arxiv)"
                    st.markdown(f"### 👤 {f_row['mijoz']}")
                    st.caption(f"📞 Telefon: **{f_row.get('telefon') or 'Kiritilmagan'}** | 🆔 Bron ID: `#{f_id}` | {hol_badge}")
                with fc2:
                    st.markdown(f"**📥 KIRISH:** `{f_row['kirish_vaqti_korsat']}`  ➔  **🛫 CHIQISH:** `{f_row['chiqish_sanasi']} 12:00`")
                    st.caption(f"🛏 Xona va Joy: **{f_row['xona_korsat']}** • Mehmon: **{f_row['odam_soni']} kishi** ({f_row['kunlar']} kecha)")

                b_c1, b_c2, b_c3 = st.columns(3, gap="medium")
                b_c1.metric("💰 JAMI HISOB", f"{int(f_row['faktik_narx']):,} UZS")
                b_c2.metric("✅ TO'LANGAN", f"{int(f_row['tolagan_summa']):,} UZS")
                b_c3.metric("⚠️ QARZ", f"{max(0, int(f_row['qoldiq'])):,} UZS")

            with st.container(border=True):
                st.markdown("##### 📝 Mehmonning ichki ma'lumotlari (Barchasi ixtiyoriy)")
                with st.form("folio_anketa_form", enter_to_submit=False):
                    m1, m2, m3 = st.columns(3, gap="medium")
                    with m1:
                        p_ism = st.text_input("Mehmon F.I.O (Ism):", value=str(f_row.get('mijoz') or ''))
                    with m2:
                        p_tel = st.text_input("Telefon raqami (ixtiyoriy):", value=str(f_row.get('telefon') or ''))
                    with m3:
                        p_izoh = st.text_input("Ichki izoh (ixtiyoriy):", value=str(f_row.get('izoh') or ''))

                    if st.form_submit_button("💾 Ma'lumotlarni yangilash", type="primary", use_container_width=True):
                        db.execute(
                            "UPDATE bronlar SET mijoz=?, telefon=?, izoh=? WHERE mijoz_id=?",
                            (p_ism.strip(), p_tel.strip(), p_izoh.strip(), f_id)
                        )
                        jurnalga_yozish(f_id, xodim_ismi, "Mijoz kartasi yangilandi", f"{p_ism}: Tel={p_tel}, Izoh={p_izoh}")
                        st.success("✅ Ma'lumotlar saqlandi!")
                        st.rerun()

            with st.expander("🖨️ Hisobni chop etish (Ichki Kvitansiya / Chek)"):
                st.markdown(
                    f"<div style='background:#ffffff; color:#0f172a; padding:24px; border-radius:12px; border:2px dashed #64748b; max-width:650px; margin:0 auto; font-family:monospace;'>"
                    f"<h3 style='text-align:center; color:#0f172a; margin:0;'>🏨 YANGI SERGELI HOSTEL (Y.S.H.)</h3>"
                    f"<p style='text-align:center; color:#475569; margin:4px 0 14px 0;'>Ichki Hisob-kitob Cheki № {f_id}</p>"
                    f"<hr style='border:1px solid #cbd5e1;'>"
                    f"<p style='color:#0f172a;'><b>Mehmon:</b> {f_row['mijoz']} ({f_row['odam_soni']} kishi)<br>"
                    f"<b>Telefon:</b> {f_row.get('telefon') or '—'}<br>"
                    f"<b>Joylashgan xona va joy:</b> {f_row['xona_korsat']}<br>"
                    f"<b>Kirish vaqti:</b> {f_row['kirish_vaqti_korsat']}<br>"
                    f"<b>Chiqish vaqti:</b> {f_row['chiqish_sanasi']} (soat 12:00)<br>"
                    f"<b>Yashash muddati:</b> {f_row['kunlar']} kecha</p>"
                    f"<hr style='border:1px solid #cbd5e1;'>"
                    f"<p style='color:#0f172a; font-size:15px;'><b>Jami hisoblangan summa:</b> {int(f_row['faktik_narx']):,} UZS<br>"
                    f"<b>To'langan summa:</b> {int(f_row['tolagan_summa']):,} UZS ({f_row.get('tolov_tafsiloti') or 'Naqd'})<br>"
                    f"<b>Qoldiq qarz:</b> {max(0, int(f_row['qoldiq'])):,} UZS</p>"
                    f"<hr style='border:1px solid #cbd5e1;'>"
                    f"<p style='color:#475569; font-size:12px;'>Mas'ul: {xodim_ismi} | Vaqt: {toshkent_vaqti().strftime('%d.%m.%Y %H:%M')}</p></div>",
                    unsafe_allow_html=True
                )

            with st.expander("🛏️ 1. Bandlangan xonalar (Kunma-kun yoyilma)", expanded=True):
                try:
                    k_dt = datetime.strptime(str(f_row['kirish_sanasi']), "%Y-%m-%d")
                except Exception:
                    k_dt = toshkent_vaqti()
                kunlik_qatorlar = []
                for k_i in range(int(f_row['kunlar'] or 1)):
                    s_kun = (k_dt + timedelta(days=k_i)).strftime("%d.%m.%Y")
                    kunlik_qatorlar.append({
                        "Sana (Kecha)": s_kun,
                        "Kim uchun bandlangan": f_row['mijoz'],
                        "Xona va Joy": f_row['xona_korsat'],
                        "Narx / Kecha": f"{int(f_row.get('kunlik_narx') or 0):,} UZS"
                    })
                st.dataframe(pd.DataFrame(kunlik_qatorlar), use_container_width=True, hide_index=True)

            df_m_tol = db.read_df("SELECT sana, manba, tolov_tafsiloti, summa, xodim FROM tolovlar_tarixi WHERE mijoz_id=? ORDER BY id DESC", (f_id,))
            df_m_qarz_savdo = db.read_df("SELECT vaqt, tafsilot, xodim FROM audit_log WHERE mijoz_id=? AND harakat='Market qarz' ORDER BY id DESC", (f_id,))

            with st.expander("🛒 2. Qo'shimcha xizmatlar (Marketdan xona qarziga olinganlar)", expanded=True):
                if not df_m_qarz_savdo.empty:
                    df_m_qarz_savdo.columns = ["Vaqt", "Olingan mahsulot va summa", "Mas'ul Xodim"]
                    st.dataframe(df_m_qarz_savdo, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_m_qarz_savdo))
                else:
                    st.caption("Qo'shimcha xizmat (Market qarz) ishlatilmagan.")

            with st.expander("💵 3. Qabul qilingan to'lovlar", expanded=True):
                kirim_tol = df_m_tol[df_m_tol['summa'] > 0].copy() if not df_m_tol.empty else pd.DataFrame()
                if not kirim_tol.empty:
                    kirim_tol['summa'] = kirim_tol['summa'].apply(lambda x: f"{int(x):,} UZS")
                    kirim_tol.columns = ["Sana", "Manba", "To'lov usuli", "Summa", "Qabul qilgan xodim"]
                    st.dataframe(kirim_tol, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(kirim_tol))
                else:
                    st.caption("To'lov qabul qilinmagan (0 UZS).")

            with st.expander("⏪ 4. Qaytarilgan to'lovlar (Vozvrat)", expanded=True):
                vozv_tol = df_m_tol[df_m_tol['summa'] < 0].copy() if not df_m_tol.empty else pd.DataFrame()
                if not vozv_tol.empty:
                    vozv_tol['summa'] = vozv_tol['summa'].apply(lambda x: f"{int(x):,} UZS")
                    vozv_tol.columns = ["Sana", "Sabab / Manba", "Qaytarilgan kassa", "Summa", "Mas'ul xodim"]
                    st.dataframe(vozv_tol, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(vozv_tol))
                else:
                    st.caption("Qaytarilgan to'lovlar (Vozvrat) mavjud emas (0 UZS).")

    else:
        barcha_faol_va_bron = df[df['holat'] != 'Chiqib ketgan'] if not df.empty else pd.DataFrame()
        amal_tanlov = st.radio(
            "Amalni tanlang:",
            ["💳 Qarzni yopish", "➕ Muddatni cho'zish", "🛏 Xonadan-xonaga ko'chirish", "🚪 Checkout (Xonani bo'shatish / Vozvrat)", "✏️ Mijoz ma'lumotlarini tahrirlash"],
            horizontal=True
        )

        if amal_tanlov == "💳 Qarzni yopish":
            qarzdorlar = df[(df['qoldiq'] > 0) & (df['holat'] != 'Chiqib ketgan')] if not df.empty else pd.DataFrame()
            if not qarzdorlar.empty:
                tanlangan_qarz = st.selectbox("Qarzdor mijozni tanlang:", qarzdorlar['mijoz_id'] + " - " + qarzdorlar['mijoz'] + " (" + qarzdorlar['xona_korsat'] + " | Qarzi: " + qarzdorlar['qoldiq'].astype(int).astype(str) + " UZS)")
                q_id = tanlangan_qarz.split(" - ")[0]
                q_row = qarzdorlar[qarzdorlar['mijoz_id'] == q_id].iloc[0]
                joriy_qarz_sum = int(q_row['qoldiq'])

                with st.form("qarz_form", enter_to_submit=False):
                    c_q1, c_q2 = st.columns(2, gap="medium")
                    with c_q1:
                        tolov_sum = st.number_input("Olinayotgan summa (UZS):", min_value=1000, step=5000, value=joriy_qarz_sum)
                        t_shakl = st.selectbox("Qarz To'lov shakli", ["Naqd", "Karta", "Onlayn"])
                    with c_q2:
                        t_tafsiloti = st.selectbox("Qarz To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
                        qarz_izoh = st.text_input("Qo'shimcha izoh (yoki 'Boshqa' to'lov nomi):")
                    
                    if st.form_submit_button("✅ To'lovni tasdiqlash", type="primary", use_container_width=True):
                        q_mijoz_ism = q_row['mijoz']
                        if t_tafsiloti == "Boshqa" and qarz_izoh.strip():
                            t_tafsiloti = f"Boshqa ({qarz_izoh.strip()})"
                        db.execute("UPDATE bronlar SET tolagan_summa=tolagan_summa+?, qoldiq=qoldiq-?, tolov_turi=?, tolov_tafsiloti=? WHERE mijoz_id=?", (tolov_sum, tolov_sum, t_shakl, t_tafsiloti, q_id))
                        db.execute("UPDATE bronlar SET holat='To''langan' WHERE mijoz_id=? AND qoldiq<=0", (q_id,))
                        db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                   (bugungi_sana, q_id, q_mijoz_ism, "Qarz yopish", tolov_sum, t_shakl, t_tafsiloti, xodim_ismi))
                        jurnalga_yozish(q_id, xodim_ismi, "Qarz yopildi", f"Summa: {tolov_sum:,.0f} ({t_tafsiloti})")
                        tg_xabar_yubor("Mijoz qarzi to'landi", f"👤 <b>Mijoz:</b> {q_mijoz_ism}\n💵 <b>To'landi:</b> {tolov_sum:,.0f} UZS ({t_tafsiloti})", xodim_ismi)
                        st.success("To'lov qabul qilindi!")
                        st.rerun()
            else:
                st.info("Hozircha qarzdor mijozlar yo'q.")

        elif amal_tanlov == "➕ Muddatni cho'zish":
            if not barcha_faol_va_bron.empty:
                with st.form("muddat_form", enter_to_submit=False):
                    tanlangan_id_chozish = st.selectbox("Mijozni tanlang:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (" + barcha_faol_va_bron['xona_korsat'] + ")")
                    qoshimcha_kun = st.number_input("Necha kun qo'shilmoqda?", min_value=1, value=1)
                    if st.form_submit_button("➕ Muddatni cho'zish", type="primary", use_container_width=True):
                        m_id = tanlangan_id_chozish.split(" - ")[0]
                        mijoz_data = barcha_faol_va_bron[barcha_faol_va_bron['mijoz_id'] == m_id].iloc[0]
                        eski_chiqish_str = str(mijoz_data['chiqish_sanasi'])
                        yangi_chiqish = datetime.strptime(eski_chiqish_str, "%Y-%m-%d") + timedelta(days=qoshimcha_kun)
                        yangi_chiqish_str = yangi_chiqish.strftime("%Y-%m-%d")
                        
                        x_nom = mijoz_data['xona']
                        x_sigim = xona_sigimini_ol(x_nom)
                        m_odam = int(mijoz_data['odam_soni'] or 1)
                        is_vikup = "To'liq band" in str(mijoz_data.get('xona_turi', '') or '')
                        kerakli_joy = x_sigim if is_vikup else m_odam
                        
                        band_joy = xonadagi_band_joyni_hisobla(x_nom, eski_chiqish_str, yangi_chiqish_str, exclude_mijoz_id=m_id)
                        bosh_joy = x_sigim - band_joy
                        
                        if kerakli_joy > bosh_joy:
                            st.error(f"⚠️ Xatolik: {x_nom} da {eski_chiqish_str} dan {yangi_chiqish_str} gacha bo'sh joy yetarli emas (Boshqa bron bor, bo'sh joy: {bosh_joy} ta)!")
                        else:
                            q_sum = mijoz_data['kunlik_narx'] * qoshimcha_kun
                            yangi_qoldiq = mijoz_data['qoldiq'] + q_sum
                            yangi_holat = "To'langan" if yangi_qoldiq <= 0 else "Qarzdorlik"
                            db.execute("UPDATE bronlar SET kunlar=kunlar+?, qoldiq=?, jami_summa=jami_summa+?, faktik_narx=faktik_narx+?, chiqish_sanasi=?, holat=? WHERE mijoz_id=?", (qoshimcha_kun, yangi_qoldiq, q_sum, q_sum, yangi_chiqish_str, yangi_holat, m_id))
                            jurnalga_yozish(m_id, xodim_ismi, "Muddat cho'zildi", f"+{qoshimcha_kun} kun ({q_sum:,.0f} UZS)")
                            tg_xabar_yubor("Muddat cho'zildi", f"👤 <b>Mijoz:</b> {mijoz_data['mijoz']}\n➕ <b>Qo'shildi:</b> +{qoshimcha_kun} kun ({q_sum:,.0f} UZS)\n🛫 <b>Yangi chiqish:</b> {yangi_chiqish_str} 12:00", xodim_ismi)
                            st.success("Muddat muvaffaqiyatli cho'zildi!")
                            st.rerun()
            else:
                st.info("Faol mijozlar mavjud emas.")

        elif amal_tanlov == "🛏 Xonadan-xonaga ko'chirish":
            if not barcha_faol_va_bron.empty:
                with st.form("kochirish_form", enter_to_submit=False):
                    koch_mijoz = st.selectbox("Ko'chiriladigan mijoz:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (Hozir: " + barcha_faol_va_bron['xona_korsat'] + ")")
                    y_xona_toliq = st.selectbox("Yangi Xonani tanlang:", BARCHA_XONALAR_ROYXATI)
                    koch_krovat_str = st.text_input("🛏️ Yangi xonadagi joyi (masalan: Chapdan 1-joy yoki O'ngdan 2-joy):", value="Chapdan 1-joy")
                    koch_toliq_band = st.checkbox("🔒 Yangi xonani to'liq band qilish (Vikup)")
                    if st.form_submit_button("🔄 Xonani almashtirish", type="primary", use_container_width=True):
                        k_id = koch_mijoz.split(" - ")[0]
                        k_data = barcha_faol_va_bron[barcha_faol_va_bron['mijoz_id'] == k_id].iloc[0]
                        y_tomon = y_xona_toliq.split(" | ")[0]
                        y_xona = y_xona_toliq.split(" | ")[1].split(" (")[0].strip()
                        eski_xona = k_data['xona']
                        m_odam = int(k_data['odam_soni'] or 1)
                        m_jins = str(k_data.get('jinsi', 'Erkak') or 'Erkak')
                        
                        y_sigim = XONALAR[y_tomon][y_xona][0]
                        band_joy = xonadagi_band_joyni_hisobla(y_xona, k_data['kirish_sanasi'], k_data['chiqish_sanasi'], exclude_mijoz_id=k_id)
                        bosh_joy = y_sigim - band_joy
                        kerakli = y_sigim if koch_toliq_band else m_odam
                        zid_jins = None if (koch_toliq_band or y_tomon == "O'rtadagi") else xona_jinsini_tekshir(y_xona, k_data['kirish_sanasi'], k_data['chiqish_sanasi'], m_jins, exclude_mijoz_id=k_id)
                        
                        if m_odam > y_sigim:
                            st.error(f"⚠️ {y_xona} jami {y_sigim} kishilik (Mijoz esa {m_odam} kishi)!")
                        elif kerakli > bosh_joy:
                            st.error(f"⚠️ {y_xona} da yetarli bo'sh joy yo'q (Bo'sh joy: {bosh_joy} ta)!")
                        elif zid_jins:
                            st.error(f"🚻 Xatolik: {y_xona} da hozir **{zid_jins}** mijoz(lar) bor! Umumiy xonaga **{m_jins}** mijozni ko'chirib bo'lmaydi.")
                        else:
                            baz_tur = "Dvuxspalniy" if y_tomon == "O'rtadagi" else ("2 alohida krovat" if y_sigim == 2 else f"{y_sigim} kishilik")
                            kr_b = f" [🛏️ {koch_krovat_str.strip()}]" if (y_tomon != "O'rtadagi" and koch_krovat_str.strip()) else ""
                            y_xona_turi = f"To'liq band ({baz_tur}){kr_b}" if (koch_toliq_band or y_tomon == "O'rtadagi") else f"{baz_tur}{kr_b}"
                            db.execute("UPDATE bronlar SET tomon=?, xona=?, xona_turi=? WHERE mijoz_id=?", (y_tomon, y_xona, y_xona_turi, k_id))
                            xona_tozalik_ozgartir(eski_xona, "Tozalash kerak")
                            jurnalga_yozish(k_id, xodim_ismi, "Xona ko'chirildi", f"{k_data['mijoz']}: {eski_xona} -> {y_xona} ({y_xona_turi})")
                            tg_xabar_yubor("Xona almashtirildi", f"👤 <b>Mijoz:</b> {k_data['mijoz']}\n🔄 <b>Ko'chirildi:</b> {eski_xona} ➡️ {y_xona} ({y_xona_turi})", xodim_ismi)
                            st.success(f"Mijoz {y_xona} ga ko'chirildi! ({eski_xona} tozalashga berildi)")
                            st.rerun()
            else:
                st.info("Ko'chirish uchun faol mijoz yo'q.")

        elif amal_tanlov == "🚪 Checkout (Xonani bo'shatish / Vozvrat)":
            if not barcha_faol_va_bron.empty:
                chiq_tanlov = st.selectbox("Xonani topshirayotgan mijozni tanlang:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (" + barcha_faol_va_bron['xona_korsat'] + " | Chiqish: " + barcha_faol_va_bron['chiqish_sanasi'] + ")")
                c_id = chiq_tanlov.split(" - ")[0]
                c_row = barcha_faol_va_bron[barcha_faol_va_bron['mijoz_id'] == c_id].iloc[0]

                with st.form("admin_checkout_form", enter_to_submit=False):
                    st.caption(f"👤 Mijoz: **{c_row['mijoz']}** | To'lagan: **{int(c_row['tolagan_summa']):,} UZS** | Qoldiq qarz: **{max(0, int(c_row['qoldiq'])):,} UZS**")
                    col_v1, col_v2 = st.columns(2, gap="medium")
                    with col_v1:
                        vozvrat_sum = st.number_input("⏪ Mijozga qaytarilgan summa / Vozvrat (0 = qaytarilmadi):", min_value=0, max_value=int(c_row['tolagan_summa'] or 0), value=0, step=10000)
                    with col_v2:
                        vozvrat_kassa = st.selectbox("Qaysi kassadan qaytarildi? (Agar vozvrat bo'lsa):", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                    vozvrat_izoh = st.text_input("Checkout / Vozvrat izohi (ixtiyoriy):", placeholder="Masalan: Mijoz 1 kun erta ketdi, kalit topshirildi...")

                    if st.form_submit_button("🚪 Kalitlarni topshirish (Checkout va Arxivlash)", type="primary", use_container_width=True):
                        if c_row['qoldiq'] > 0 and vozvrat_sum == 0:
                            st.error(f"⚠️ Mijozda {c_row['qoldiq']:,.0f} UZS qarz bor! Avval «💳 Qarzni yopish» bo'limidan qarzni qabul qiling.")
                        else:
                            yangi_tolagan = float(c_row['tolagan_summa']) - vozvrat_sum
                            yangi_faktik = yangi_tolagan if vozvrat_sum > 0 else float(c_row['faktik_narx'])
                            eski_izoh = str(c_row.get('izoh', '') or '')
                            qo_izoh = f"{eski_izoh} | Checkout: {vozvrat_izoh.strip()}".strip(" |") if vozvrat_izoh.strip() else eski_izoh

                            db.execute(
                                "UPDATE bronlar SET holat='Chiqib ketgan', chiqish_sanasi=?, tolagan_summa=?, faktik_narx=?, jami_summa=?, qoldiq=0, izoh=? WHERE mijoz_id=?",
                                (bugungi_sana, yangi_tolagan, yangi_faktik, yangi_faktik, qo_izoh, c_id)
                            )
                            xona_tozalik_ozgartir(c_row['xona'], "Tozalash kerak")
                            if vozvrat_sum > 0:
                                db.execute(
                                    "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                    (bugungi_sana, c_id, c_row['mijoz'], "Vozvrat (Pul qaytarish)", -vozvrat_sum, vozvrat_kassa, vozvrat_kassa, xodim_ismi)
                                )
                                jurnalga_yozish(c_id, xodim_ismi, "Checkout + Vozvrat", f"Mijoz ({c_row['mijoz']}) {c_row['xona']} ni bo'shatdi. Qaytarildi: -{vozvrat_sum:,.0f} UZS ({vozvrat_kassa})")
                                tg_xabar_yubor(
                                    "Checkout va Pul qaytarish (Vozvrat)",
                                    f"👤 <b>Mijoz:</b> {c_row['mijoz']}\n"
                                    f"🛏 <b>Bo'shagan xona:</b> {c_row['xona']} (🧹 Tozalashga berildi)\n"
                                    f"⏪ <b>Qaytarilgan summa (Vozvrat):</b> -{vozvrat_sum:,.0f} UZS ({vozvrat_kassa})\n"
                                    f"💰 <b>Qolgan sof to'lov:</b> {yangi_tolagan:,.0f} UZS",
                                    xodim_ismi, muhim=True
                                )
                            else:
                                jurnalga_yozish(c_id, xodim_ismi, "Checkout", f"Mijoz ({c_row['mijoz']}) {c_row['xona']} ni topshirdi va arxivga o'tkazildi")
                                tg_xabar_yubor(
                                    "Checkout (Mijoz chiqib ketdi)",
                                    f"👤 <b>Mijoz:</b> {c_row['mijoz']}\n🛏 <b>Bo'shagan xona:</b> {c_row['xona']} (🧹 Tozalashga berildi)",
                                    xodim_ismi
                                )
                            st.success(f"✅ {c_row['mijoz']} ({c_row['xona']}) chiqarildi va xona «🧹 Tozalash kerak» ro'yxatiga tushdi!")
                            st.rerun()
            else:
                st.info("Hozircha faol mijozlar yo'q.")

        elif amal_tanlov == "✏️ Mijoz ma'lumotlarini tahrirlash":
            if not df.empty:
                tahrir_tanlov = st.selectbox("Tahrirlanadigan mijozni tanlang:", df['mijoz_id'] + " - " + df['mijoz'] + " (" + df['xona_korsat'] + " | " + df['holat'] + ")")
                t_id = tahrir_tanlov.split(" - ")[0]
                t_row = df[df['mijoz_id'] == t_id].iloc[0]

                with st.form("tahrirlash_form", enter_to_submit=False):
                    st.caption(f"🆔 Mijoz ID: **{t_id}** ma'lumotlarini o'zgartirish")
                    e1, e2, e3 = st.columns(3, gap="medium")
                    with e1:
                        y_ism = st.text_input("Mijoz F.I.O / Telefon:", value=str(t_row['mijoz']))
                        joriy_xona_idx = 0
                        for idx, x_str in enumerate(BARCHA_XONALAR_ROYXATI):
                            if f"| {t_row['xona']} (" in x_str:
                                joriy_xona_idx = idx
                                break
                        y_xona_str = st.selectbox("Xona:", BARCHA_XONALAR_ROYXATI, index=joriy_xona_idx)
                        eski_krovat = krovat_nomini_ajrat(t_row.get('xona_turi', ''), t_row.get('izoh', '')) or "Chapdan 1-joy"
                        y_krovat_str = st.text_input("🛏️ Krovat / Joy o'rni (masalan: Chapdan 2-joy):", value=eski_krovat)
                        y_odam = st.number_input("Odam soni:", min_value=1, max_value=10, value=int(t_row['odam_soni'] or 1))
                        eski_vikup = "To'liq band" in str(t_row.get('xona_turi', '') or '')
                        y_vikup = st.checkbox("🔒 Xona to'liq band (Vikup)", value=eski_vikup)
                    with e2:
                        try:
                            def_kirish = datetime.strptime(str(t_row['kirish_sanasi']), "%Y-%m-%d")
                        except Exception:
                            def_kirish = toshkent_vaqti()
                        y_kirish = st.date_input("Kirish sanasi:", value=def_kirish)
                        eski_soat = str(t_row['sana']).split("(")[1].replace(")", "") if "(" in str(t_row.get('sana', '')) else toshkent_vaqti().strftime("%H:%M")
                        y_soat = st.text_input("Kirish soati (SS:DD):", value=eski_soat)
                        y_kunlar = st.number_input("Yashash kunlari:", min_value=1, max_value=365, value=int(t_row['kunlar'] or 1))
                    with e3:
                        y_faktik = st.number_input("Jami hisoblangan summa (UZS):", min_value=0, value=int(t_row['faktik_narx'] or 0), step=10000)
                        eski_tolagan = int(t_row['tolagan_summa'] or 0)
                        y_tolagan = st.number_input("Jami to'lagan summasi (UZS):", min_value=0, value=eski_tolagan, step=10000)
                        y_holat = st.selectbox("Holati:", ["To'langan", "Qarzdorlik", "Chiqib ketgan"], index=0 if t_row['holat']=="To'langan" else (2 if t_row['holat']=="Chiqib ketgan" else 1))
                        y_izoh = st.text_input("Izoh:", value=str(t_row['izoh'] or ''))

                    if st.form_submit_button("💾 O'zgarishlarni Saqlash", type="primary", use_container_width=True):
                        y_tomon = y_xona_str.split(" | ")[0]
                        y_xona = y_xona_str.split(" | ")[1].split(" (")[0].strip()
                        y_sigim = XONALAR[y_tomon][y_xona][0]
                        baz_tur = "Dvuxspalniy" if y_tomon == "O'rtadagi" else ("2 alohida krovat" if y_sigim == 2 else f"{y_sigim} kishilik")
                        kr_tag = f" [🛏️ {y_krovat_str.strip()}]" if (y_tomon != "O'rtadagi" and y_krovat_str.strip()) else ""
                        y_xona_turi = f"To'liq band ({baz_tur}){kr_tag}" if (y_vikup or y_tomon == "O'rtadagi") else f"{baz_tur}{kr_tag}"
                        y_kirish_str = y_kirish.strftime("%Y-%m-%d")
                        y_sana_vaqt_toliq = f"{y_kirish_str} ({y_soat.strip()})"
                        y_chiqish_str = (y_kirish + timedelta(days=y_kunlar)).strftime("%Y-%m-%d")
                        y_qoldiq = y_faktik - y_tolagan
                        if y_holat != "Chiqib ketgan":
                            y_holat = "To'langan" if y_qoldiq <= 0 else "Qarzdorlik"

                        toza_izoh = re.sub(r'\[🛏️ .*?\]', '', y_izoh).strip()
                        yak_izoh = f"{kr_tag.strip()} {toza_izoh}".strip()

                        db.execute("""
                            UPDATE bronlar SET 
                                mijoz=?, tomon=?, xona=?, xona_turi=?, odam_soni=?, sana=?, kirish_sanasi=?, chiqish_sanasi=?,
                                kunlar=?, faktik_narx=?, jami_summa=?, tolagan_summa=?, qoldiq=?, holat=?, izoh=?
                            WHERE mijoz_id=?
                        """, (y_ism.strip(), y_tomon, y_xona, y_xona_turi, y_odam, y_sana_vaqt_toliq, y_kirish_str, y_chiqish_str, y_kunlar, y_faktik, y_faktik, y_tolagan, y_qoldiq, y_holat, yak_izoh, t_id))
                        
                        farq_tolov = y_tolagan - eski_tolagan
                        if farq_tolov != 0:
                            t_taf_eski = str(t_row.get('tolov_tafsiloti', 'Naqd') or 'Naqd')
                            t_shakl_eski = str(t_row.get('tolov_turi', 'Naqd') or 'Naqd')
                            db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                       (bugungi_sana, t_id, y_ism.strip(), "Tahrirlash (Kassa tuzatish)", farq_tolov, t_shakl_eski, t_taf_eski, xodim_ismi))

                        jurnalga_yozish(t_id, xodim_ismi, "Mijoz tahrirlandi", f"Ism: {y_ism}, Xona: {y_xona} ({y_xona_turi}), Kirish: {y_sana_vaqt_toliq}, Jami: {y_faktik:,.0f}, To'lagan: {y_tolagan:,.0f}")
                        tg_xabar_yubor(
                            "Mijoz ma'lumotlari tahrirlandi",
                            f"🆔 <b>ID:</b> {t_id}\n"
                            f"👤 <b>Mijoz:</b> {y_ism} ({y_xona} — {y_xona_turi})\n"
                            f"🕒 <b>Kirish:</b> {y_sana_vaqt_toliq} ➡️ <b>Chiqish:</b> {y_chiqish_str} ({y_kunlar} kun)\n"
                            f"💰 <b>Yangi jami:</b> {y_faktik:,.0f} UZS | <b>To'lagan:</b> {y_tolagan:,.0f} UZS | <b>Qoldiq:</b> {max(0, y_qoldiq):,.0f} UZS",
                            xodim_ismi, muhim=True
                        )
                        st.success("✅ Mijoz ma'lumotlari va kassa balansi muvaffaqiyatli yangilandi!")
                        st.rerun()

# ====================================================
# SAHIFA 5: 🧹 XONA TOZALASH
# ====================================================
elif sahifa == "🧹 Xona tozalash":
    st.header("🧹 Xona tozalash (Housekeeping)")
    st.caption("👆 Xonalarni bosib «Toza» va «Tozalash kerak» holatlari o'rtasida almashtiring. Mijoz chiqib ketgan xona avtomatik ravishda «Tozalash kerak» blokiga tushadi.")

    qidir_x = st.text_input("🔍 Xona raqami bo'yicha qidirish:", placeholder="Masalan: 15-xona...")
    tozalik_map = barcha_xona_tozalik_ol()
    df_faol_x = db.read_df("SELECT DISTINCT xona FROM bronlar WHERE holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (bugungi_sana, bugungi_sana))
    band_xonalar_set = set(df_faol_x['xona'].tolist()) if not df_faol_x.empty else set()

    tozalash_kerak_list, bosh_toza_list, band_list = [], [], []

    for tomon, xonalar in XONALAR.items():
        for x_nom, (sigim, _) in xonalar.items():
            if qidir_x and qidir_x.lower() not in x_nom.lower():
                continue
            tur_nom = "Luxe" if tomon == "O'rtadagi" else f"Standart ({sigim} k)"
            hol = tozalik_map.get(x_nom, "Toza")
            if hol == "Tozalash kerak":
                tozalash_kerak_list.append((x_nom, tur_nom))
            elif x_nom in band_xonalar_set:
                band_list.append((x_nom, tur_nom))
            else:
                bosh_toza_list.append((x_nom, tur_nom))

    with st.container(border=True):
        th1, th2 = st.columns([4, 1.3])
        th1.markdown(f"##### 🔴 Tozalash kerak `{len(tozalash_kerak_list)}`")
        if tozalash_kerak_list:
            if th2.button("✔️ Hammasini tozalangan deb belgilash", use_container_width=True):
                for x_n, _ in tozalash_kerak_list:
                    xona_tozalik_ozgartir(x_n, "Toza")
                jurnalga_yozish("Housekeeping", xodim_ismi, "Xonalar tozalandi", f"Jami {len(tozalash_kerak_list)} ta xona toza deb belgilandi")
                st.rerun()

            cols_tk = st.columns(6, gap="small")
            for idx, (x_n, t_n) in enumerate(tozalash_kerak_list):
                with cols_tk[idx % 6]:
                    st.markdown(f"<div style='border:2px solid #ef4444; background:rgba(239,68,68,0.12); padding:12px; border-radius:12px; text-align:center; margin-bottom:6px;'><b>{x_n}</b><br><span style='font-size:12px; opacity:0.8;'>{t_n}</span></div>", unsafe_allow_html=True)
                    if st.button("✨ Toza bo'ldi", key=f"clean_{x_n}", use_container_width=True):
                        xona_tozalik_ozgartir(x_n, "Toza")
                        jurnalga_yozish("Housekeeping", xodim_ismi, "Xona tozalandi", f"{x_n} toza holatga o'tkazildi")
                        st.rerun()
        else:
            st.success("🎉 Barcha xonalar top-toza! Tozalash kerak bo'lgan xona yo'q.")

    st.write("")
    with st.container(border=True):
        st.markdown(f"##### 🟢 Bugun bo'sh (Toza) `{len(bosh_toza_list)}`")
        if bosh_toza_list:
            cols_bt = st.columns(6, gap="small")
            for idx, (x_n, t_n) in enumerate(bosh_toza_list):
                with cols_bt[idx % 6]:
                    st.markdown(f"<div style='border:1px solid #334155; background:rgba(34,197,94,0.08); padding:12px; border-radius:12px; text-align:center; margin-bottom:6px;'><b>{x_n}</b><br><span style='font-size:12px; opacity:0.8;'>{t_n}</span></div>", unsafe_allow_html=True)
                    if st.button("🧹 Tozalash kk", key=f"dirty_{x_n}", use_container_width=True):
                        xona_tozalik_ozgartir(x_n, "Tozalash kerak")
                        st.rerun()
        else:
            st.info("Bo'sh xonalar yo'q.")

    st.write("")
    with st.expander(f"🟣 Hozir mehmon yashayotgan band xonalar ({len(band_list)} ta)"):
        if band_list:
            cols_bd = st.columns(6, gap="small")
            for idx, (x_n, t_n) in enumerate(band_list):
                with cols_bd[idx % 6]:
                    st.markdown(f"<div style='border:1px solid #7c3aed; background:rgba(124,58,237,0.1); padding:10px; border-radius:10px; text-align:center; margin-bottom:6px;'><b>{x_n}</b><br><span style='font-size:11px; opacity:0.8;'>{t_n}</span></div>", unsafe_allow_html=True)
                    if st.button("🧹 Tozalash kk", key=f"dirty_b_{x_n}", use_container_width=True):
                        xona_tozalik_ozgartir(x_n, "Tozalash kerak")
                        st.rerun()

# ====================================================
# SAHIFA 6: 🛒 KASSA (POS MARKET)
# ====================================================
elif sahifa == "🛒 Kassa (POS Market)":
    st.header("🛒 Kassa (POS Mini-Market)")
    market_tanlov = st.radio("Bo'limni tanlang:", ["🛒 Kassa (Sotish)", "📊 Savdolar Tarixi"], horizontal=True)
    st.markdown("---")
    
    if market_tanlov == "🛒 Kassa (Sotish)":
        mahsulotlar = db.read_df("SELECT * FROM mahsulotlar WHERE qoldiq > 0")
        if mahsulotlar.empty:
            st.warning("⚠️ Omborda sotishga mahsulot yo'q.")
        else:
            mahsulotlar['Toliq_Nomi'] = mahsulotlar.apply(
                lambda r: f"{r['nomi']} ({r['hajmi']}) — {int(r['narxi']):,} UZS [Qoldi: {r['qoldiq']} ta]" if r['hajmi'] else f"{r['nomi']} — {int(r['narxi']):,} UZS [Qoldi: {r['qoldiq']} ta]",
                axis=1
            )
            faol_bronlar = db.read_df("SELECT mijoz_id, mijoz, xona FROM bronlar WHERE holat != 'Chiqib ketgan'")
            mijoz_variantlar = ["💵 Darhol To'lov (Umumiy xaridor)"]
            if not faol_bronlar.empty:
                mijoz_variantlar += (faol_bronlar['mijoz'] + " (" + faol_bronlar['xona'] + ") - ID: " + faol_bronlar['mijoz_id']).tolist()

            with st.form("market_sotuv_form", clear_on_submit=True, enter_to_submit=False):
                col_m1, col_m2 = st.columns(2, gap="medium")
                with col_m1:
                    tanlangan_tovar_label = st.selectbox("1. Mahsulotni tanlang:", mahsulotlar['Toliq_Nomi'].tolist())
                    miqdor = st.number_input("2. Sotilayotgan miqdori (dona):", min_value=1, value=1, step=1)
                with col_m2:
                    kim_olayapti = st.selectbox("3. Xaridor (Darhol to'lov yoki Xona qarziga):", mijoz_variantlar)
                    m_tafsiloti = st.selectbox("4. To'lov usuli (Darhol to'lov bo'lsa):", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                    m_boshqa_izoh = st.text_input("Agar «Boshqa» bo'lsa, nomini yozing (masalan: Payme, Alif):", placeholder="Ixtiyoriy...")
                
                if st.form_submit_button("🛒 SOTISHNI TASDIQLASH", type="primary", use_container_width=True):
                    tanlangan_qator = mahsulotlar[mahsulotlar['Toliq_Nomi'] == tanlangan_tovar_label].iloc[0]
                    maks_qoldiq = int(tanlangan_qator['qoldiq'])
                    if miqdor > maks_qoldiq:
                        st.error(f"⚠️ Omborda faqat {maks_qoldiq} ta bor! Siz {miqdor} ta kiritdingiz.")
                    else:
                        tovar_id = int(tanlangan_qator['id'])
                        tovar_nom_qisqa = f"{tanlangan_qator['nomi']} ({tanlangan_qator['hajmi']})" if tanlangan_qator['hajmi'] else tanlangan_qator['nomi']
                        tovar_narxi = float(tanlangan_qator['narxi'])
                        tovar_tannarxi = float(tanlangan_qator.get('tannarx', 0) or 0)
                        jami_sum = miqdor * tovar_narxi
                        sof_foyda_sum = miqdor * (tovar_narxi - tovar_tannarxi)

                        if m_tafsiloti == "Boshqa" and m_boshqa_izoh.strip():
                            m_tafsiloti = f"Boshqa ({m_boshqa_izoh.strip()})"

                        if kim_olayapti == "💵 Darhol To'lov (Umumiy xaridor)":
                            xaridor_nomi = "Umumiy xaridor"
                            tolov_turi_db = "Darhol"
                            tanlangan_mijoz_id = None
                        else:
                            tanlangan_mijoz_id = kim_olayapti.split("ID: ")[1]
                            xaridor_nomi = kim_olayapti.split(" (")[0]
                            tolov_turi_db = "Xona"
                            m_tafsiloti = "Xona qarziga"

                        try:
                            db.execute(
                                "INSERT INTO savdolar (sana, mahsulot_nomi, xaridor, miqdor, jami_summa, sof_foyda, tolov_turi, xodim, tolov_tafsiloti) VALUES (?,?,?,?,?,?,?,?,?)",
                                (bugungi_sana, tovar_nom_qisqa, xaridor_nomi, miqdor, jami_sum, sof_foyda_sum, tolov_turi_db, xodim_ismi, m_tafsiloti)
                            )
                        except Exception:
                            db.execute(
                                "INSERT INTO savdolar (sana, mahsulot_nomi, xaridor, miqdor, jami_summa, tolov_turi, xodim, tolov_tafsiloti) VALUES (?,?,?,?,?,?,?,?)",
                                (bugungi_sana, tovar_nom_qisqa, xaridor_nomi, miqdor, jami_sum, tolov_turi_db, xodim_ismi, m_tafsiloti)
                            )

                        db.execute("UPDATE mahsulotlar SET qoldiq = qoldiq - ? WHERE id = ?", (miqdor, tovar_id))

                        if tanlangan_mijoz_id:
                            db.execute("UPDATE bronlar SET jami_summa = jami_summa + ?, faktik_narx = faktik_narx + ?, qoldiq = qoldiq + ?, holat = 'Qarzdorlik' WHERE mijoz_id = ?", (jami_sum, jami_sum, jami_sum, tanlangan_mijoz_id))
                            jurnalga_yozish(tanlangan_mijoz_id, xodim_ismi, "Market qarz", f"{miqdor} ta {tovar_nom_qisqa}. Summa: {jami_sum:,.0f} UZS")
                        else:
                            db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                       (bugungi_sana, "Market", xaridor_nomi, "Market Savdo", jami_sum, "Darhol", m_tafsiloti, xodim_ismi))
                            jurnalga_yozish("Market (Sotuv)", xodim_ismi, "Naqd Savdo", f"{miqdor} ta {tovar_nom_qisqa} sotildi. Summa: {jami_sum:,.0f} UZS ({m_tafsiloti})")
                        
                        st.success(f"✅ {miqdor} ta {tovar_nom_qisqa} ({jami_sum:,.0f} UZS) sotildi!")
                        st.rerun()

    else:
        st.info(f"📅 Ko'rsatilayotgan davr: **{g_davr_nomi}**")
        if g_bosh_sana and g_tugash_sana:
            df_savdo = db.read_df("SELECT * FROM savdolar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (g_bosh_sana, g_tugash_sana))
        else:
            df_savdo = db.read_df("SELECT * FROM savdolar ORDER BY id DESC")

        if not df_savdo.empty:
            jami_m_sum = df_savdo['jami_summa'].fillna(0).sum()
            st.markdown(f"**Jami savdo ({len(df_savdo)} ta):** `{jami_m_sum:,.0f} UZS`")
            df_savdo_korsatish = df_savdo[['sana', 'mahsulot_nomi', 'xaridor', 'miqdor', 'jami_summa', 'tolov_tafsiloti', 'xodim']].copy()
            df_savdo_korsatish.columns = ["Sana", "Mahsulot", "Xaridor", "Miqdor", "Jami Summa", "To'lov Turi", "Sotuvchi (Admin)"]
            df_savdo_korsatish['Jami Summa'] = df_savdo_korsatish['Jami Summa'].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_savdo_korsatish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_savdo_korsatish))
        else:
            st.info(f"Tanlangan davrda ({g_davr_nomi}) savdo amalga oshirilmagan.")

# ====================================================
# SAHIFA 7: 📦 XIZMATLAR VA SKLAD
# ====================================================
elif sahifa == "📦 Xizmatlar va Sklad":
    st.header("📦 Xizmatlar, Do'kon va Sklad Boshqaruvi")
    ombor_tanlov = st.radio("Bo'limni tanlang:", ["📋 Mahsulotlar ro'yxati", "➕ Yangi tovar kiritish", "✏️ Tovarni tahrirlash / O'chirish"], horizontal=True)
    st.markdown("---")
    
    if ombor_tanlov == "➕ Yangi tovar kiritish":
        kat_nomi = st.radio(
            "📂 1. Avval mahsulot kategoriyasini tanlang:",
            ["Ichimliklar", "Gigiyena vositalari", "Oziq-ovqat", "Xo'jalik mollari", "Boshqa"],
            horizontal=True
        )
        
        if kat_nomi == "Ichimliklar":
            turi_variantlar = ["Gazli shirin suv (Cola, Fanta...)", "Energetik / Bankali ichimlik", "Mineral suv (Gazli / Gazsiz)", "Sharbat / Sok / Muzdek choy", "Boshqa ichimlik"]
            hajm_variantlar = ["0.25 L", "0.5 L", "1.0 L", "1.5 L", "2.0 L", "2.5 L", "Standart (Hajmsiz)"]
            misol_nom = "Masalan: Coca-Cola, Fanta, Bonaqua..."
        elif kat_nomi == "Gigiyena vositalari":
            turi_variantlar = ["Bir martalik (1 martalik)", "Komplekt (To'plam)", "Alohida (Dona)", "Suyuq / Gel / Shampun", "Boshqa gigiyena"]
            hajm_variantlar = ["1 martalik", "Standart (Dona)", "To'plam (Komplekt)", "Kichik", "Katta"]
            misol_nom = "Masalan: Shampun, Tish pastasi, Britva, Sovun..."
        elif kat_nomi == "Oziq-ovqat":
            turi_variantlar = ["Tez tayyorlanadigan (Rollton va h.k.)", "Shirinlik / Snek / Pechenye", "Non va non mahsulotlari", "Choy / Qahva", "Standart"]
            hajm_variantlar = ["1 porsiya / Dona", "Pachka / Quti", "Standart (Hajmsiz)", "0.5 kg", "1.0 kg"]
            misol_nom = "Masalan: Rollton, Alpen Gold, Qora choy..."
        else:
            turi_variantlar = ["Tozalik vositasi", "Inventar / Buyum", "Standart", "Boshqa"]
            hajm_variantlar = ["Standart (Dona)", "Quti / Pachka", "0.5 L", "1.0 L", "1.0 kg"]
            misol_nom = "Masalan: Kir yuvish kukuni, Salfetka..."

        with st.form("sklad_add_form", clear_on_submit=True, enter_to_submit=False):
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                sub_kat_nomi = st.selectbox(f"2. Mahsulot turi ({kat_nomi}):", turi_variantlar)
                tov_nomi = st.text_input("3. Mahsulot nomi:", placeholder=misol_nom)
                hajm_tanlov = st.selectbox("4. Hajmi / O'lchami:", hajm_variantlar)
                maxsus_hajm = st.text_input("✏️ Yoki boshqa o'lcham bo'lsa, shu yerga yozing (ixtiyoriy):", placeholder="Masalan: 0.33 L, 450 ml...")
            
            with c2:
                tov_tannarx = st.number_input("5. Olib kelish narxi / Tannarx (UZS):", min_value=0, value=5000, step=500)
                tov_narxi = st.number_input("6. Sotilish narxi (UZS):", min_value=1000, value=10000, step=1000)
                tov_soni = st.number_input("7. Skladga kelgan miqdori (dona):", min_value=1, value=10, step=1)
            
            if st.form_submit_button("➕ Skladga Qo'shish", type="primary", use_container_width=True):
                if not tov_nomi.strip():
                    st.error("Mahsulot nomini kiriting!")
                else:
                    t_nom = tov_nomi.strip()
                    if maxsus_hajm.strip():
                        t_hajm = maxsus_hajm.strip()
                    elif hajm_tanlov in ["Standart (Hajmsiz)", "Standart (Dona)"]:
                        t_hajm = ""
                    else:
                        t_hajm = hajm_tanlov

                    if db.fetchone("SELECT qoldiq FROM mahsulotlar WHERE nomi=? AND hajmi=?", (t_nom, t_hajm)):
                        db.execute("UPDATE mahsulotlar SET qoldiq = qoldiq + ?, tannarx = ?, narxi = ? WHERE nomi = ? AND hajmi = ?", (tov_soni, tov_tannarx, tov_narxi, t_nom, t_hajm))
                        st.success(f"✅ {t_nom} ({t_hajm if t_hajm else 'Standart'}) qoldig'iga +{tov_soni} ta qo'shildi!")
                        jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Qoldiq to'ldirildi", f"{t_nom} ({t_hajm}) ga {tov_soni} ta qo'shildi. Sotuv narxi: {tov_narxi:,.0f} UZS")
                    else:
                        db.execute("INSERT INTO mahsulotlar (nomi, kategoriya, sub_kategoriya, hajmi, tannarx, narxi, qoldiq, izoh) VALUES (?,?,?,?,?,?,?,?)", 
                                  (t_nom, kat_nomi, sub_kat_nomi, t_hajm, tov_tannarx, tov_narxi, tov_soni, ""))
                        st.success(f"✅ Yangi {t_nom} ({t_hajm if t_hajm else 'Standart'}) omborga qo'shildi!")
                        jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Yangi tovar keldi", f"{t_nom} ({t_hajm}) {tov_soni} ta kiritildi. Sotuv narxi: {tov_narxi:,.0f} UZS")
                    st.rerun()

    elif ombor_tanlov == "✏️ Tovarni tahrirlash / O'chirish":
        df_m_edit = db.read_df("SELECT * FROM mahsulotlar ORDER BY id DESC")
        if not df_m_edit.empty:
            df_m_edit['label'] = df_m_edit.apply(lambda r: f"{r['id']} | {r['nomi']} ({r['hajmi'] if r['hajmi'] else 'Standart'}) — Qoldiq: {r['qoldiq']} ta", axis=1)
            tanlangan_m_str = st.selectbox("Tahrirlanadigan tovarni tanlang:", df_m_edit['label'].tolist())
            m_edit_id = int(tanlangan_m_str.split(" | ")[0])
            m_row = df_m_edit[df_m_edit['id'] == m_edit_id].iloc[0]

            with st.form("sklad_edit_form", enter_to_submit=False):
                ce1, ce2 = st.columns(2, gap="medium")
                with ce1:
                    y_m_nomi = st.text_input("Mahsulot nomi:", value=str(m_row['nomi']))
                    y_m_hajm = st.text_input("Hajmi / O'lchami:", value=str(m_row['hajmi'] or ''))
                    y_m_izoh = st.text_input("Izoh:", value=str(m_row['izoh'] or ''))
                with ce2:
                    y_m_tannarx = st.number_input("Tannarxi (UZS):", min_value=0, value=int(m_row.get('tannarx', 0) or 0), step=500)
                    y_m_narx = st.number_input("Sotuv narxi (UZS):", min_value=0, value=int(m_row['narxi'] or 0), step=500)
                    y_m_qoldiq = st.number_input("Aniq qoldiq soni (dona):", min_value=0, value=int(m_row['qoldiq'] or 0), step=1)
                
                b1, b2 = st.columns(2, gap="medium")
                saqlash_m = b1.form_submit_button("💾 O'zgarishlarni saqlash", type="primary", use_container_width=True)
                ochirish_m = b2.form_submit_button("🗑️ Tovarni ombordan o'chirish", use_container_width=True)

                if saqlash_m:
                    db.execute("UPDATE mahsulotlar SET nomi=?, hajmi=?, tannarx=?, narxi=?, qoldiq=?, izoh=? WHERE id=?",
                               (y_m_nomi.strip(), y_m_hajm.strip(), y_m_tannarx, y_m_narx, y_m_qoldiq, y_m_izoh.strip(), m_edit_id))
                    jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Tovar tahrirlandi", f"{y_m_nomi} ({y_m_hajm}): Narx={y_m_narx:,.0f}, Qoldiq={y_m_qoldiq} ta")
                    st.success("✅ Tovar ma'lumotlari yangilandi!")
                    st.rerun()
                if ochirish_m:
                    db.execute("DELETE FROM mahsulotlar WHERE id=?", (m_edit_id,))
                    jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Tovar o'chirildi", f"{m_row['nomi']} ombordan o'chirildi")
                    st.success("🗑️ Tovar ombordan o'chirildi!")
                    st.rerun()
        else:
            st.info("Omborda tovar yo'q.")
                
    else:
        df_mahsulot = db.read_df("SELECT nomi, hajmi, kategoriya, sub_kategoriya, tannarx, narxi, qoldiq, izoh FROM mahsulotlar ORDER BY qoldiq ASC")
        if not df_mahsulot.empty: 
            df_mahsulot['izoh'] = df_mahsulot['izoh'].fillna('')
            df_mahsulot['tannarx'] = df_mahsulot['tannarx'].fillna(0)
            df_mahsulot.columns = ["Nomi", "Hajmi", "Kategoriya", "Sub-kat", "Tannarxi", "Sotuv Narxi", "Qoldiq", "Izoh (To'liq)"]
            df_mahsulot['Tannarxi'] = df_mahsulot['Tannarxi'].apply(lambda x: f"{int(x):,} UZS")
            df_mahsulot['Sotuv Narxi'] = df_mahsulot['Sotuv Narxi'].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_mahsulot, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_mahsulot))
        else:
            st.info("Sklad bo'sh.")

# ====================================================
# SAHIFA 8: 💸 XARAJAT VA SMENA
# ====================================================
elif sahifa == "💸 Xarajat va Smena":
    render_xarajatlar_va_smena(xodim_ismi, bugungi_sana, g_bosh_sana, g_tugash_sana, g_davr_nomi)

# ====================================================
# SAHIFA 9: 👑 CEO PANEL VA HISOBOTLAR
# ====================================================
elif sahifa == "👑 CEO va Hisobotlar":
    render_ceo_panel(xodim_ismi, bugungi_sana, g_bosh_sana, g_tugash_sana, g_davr_nomi)

# ====================================================
# SAHIFA 10: ⚙️ SOZLAMALAR
# ====================================================
elif sahifa == "⚙️ Sozlamalar":
    st.header("⚙️ Shaxsiy parol va ma'lumotlarni o'zgartirish")
    st.markdown(f"**Sizning profilingiz:** {xodim_ismi} (`{st.session_state.user_login}`)")
    col_s1, col_s2 = st.columns(2, gap="medium")
    with col_s1:
        with st.form("settings_form", enter_to_submit=False):
            yangi_ism = st.text_input("Ism-Sharifingiz:", value=xodim_ismi)
            yangi_parol = st.text_input("Yangi parol:", type="password")
            parol_tasdiq = st.text_input("Yangi parolni tasdiqlang:", type="password")
            if st.form_submit_button("Ma'lumotlarni saqlash", type="primary"):
                if yangi_parol and yangi_parol != parol_tasdiq:
                    st.error("⚠️ Parollar mos tushmadi!")
                else:
                    if yangi_parol:
                        db.execute("UPDATE xodimlar SET ism=?, parol=? WHERE login=?", (yangi_ism, yangi_parol, st.session_state.user_login))
                    else:
                        db.execute("UPDATE xodimlar SET ism=? WHERE login=?", (yangi_ism, st.session_state.user_login))
                    jurnalga_yozish("Tizim Sozlamalari", xodim_ismi, "Profil yangilandi", "Foydalanuvchi paroli/ismi o'zgartirildi")
                    st.session_state.logged_in = False
                    st.query_params.clear()
                    st.rerun()