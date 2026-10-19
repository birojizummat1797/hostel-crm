import streamlit as st
import pandas as pd
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone, time as dt_time
from database import (
    db, init_db, IS_POSTGRES, XONALAR, BARCHA_XONALAR_ROYXATI, XONA_TOMON_MAP, MUDDATLAR,
    xona_sigimini_ol, xonadagi_band_joyni_hisobla, xona_jinsini_tekshir, id_yaratish,
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
    st.session_state.ui_tema = "☀️ Yorug' (Standart)" if st.query_params.get("theme") == "light" else "🌙 Qorong'u (Dark UI)"
if 'faol_sahifa' not in st.session_state:
    st.session_state.faol_sahifa = st.query_params.get("page", "🏠 Boshqaruv paneli")
if 'oxirgi_avto_tekshiruv_ts' not in st.session_state:
    st.session_state.oxirgi_avto_tekshiruv_ts = 0.0
if 'sidebar_excel_tayyor' not in st.session_state:
    st.session_state.sidebar_excel_tayyor = False

# =========================================================
# TURBO-KESH QATLAMI (BAZAGA ORTIQCHA SO'ROVLARNI 85% QISQARTIRADI!)
# =========================================================
@st.cache_data(ttl=25, show_spinner=False)
def kesh_df_ol(sql, params=()):
    return db.read_df(sql, params)

def keshni_tozala():
    st.cache_data.clear()

@st.cache_resource
def init_reglament_db():
    db.execute("""
        CREATE TABLE IF NOT EXISTS tizim_sozlamalari (
            kalit TEXT PRIMARY KEY,
            qiymat TEXT
        )
    """)
    standart_sozlamalar = {
        "narx_4k": "100000",
        "narx_3k": "110000",
        "narx_2k": "150000",
        "narx_luxe_uz": "250000",
        "narx_luxe_chet": "300000",
        "ustama_chet": "50000",
        "chegirma_talaba": "50",
        "chegirma_hafta": "10",
        "hisob_soati": "12:00",
        "tg_token": "8542159383:AAH6-3BV3274-N84m6V6Q1_3C1bE78xX0fE",
        "ceo_chat_id": "6483211079",
        "owner_chat_id": "",
        "svodka_rejimi": "Har kuni 12:00 va 00:00 da",
        "oxirgi_svodka_12": "",
        "oxirgi_svodka_00": "",
        "reg_chap": (
            "**🛏️ Chap qanot (1-xonadan 14-xonagacha — 14 ta xona):**\n"
            "- **4 kishilik xonalar (1, 2, 3, 4, 5, 6, 8, 9, 12, 13):** Mahalliy `100,000 UZS` | Chet el `150,000 UZS` / joy\n"
            "- **3 kishilik xona (10-xona):** Mahalliy `110,000 UZS` | Chet el `160,000 UZS` / joy\n"
            "- **2 kishilik (2 alohida krovat — 7, 11, 14):** Mahalliy `150,000 UZS` | Chet el `200,000 UZS` / joy"
        ),
        "reg_orta": (
            "**🛌 O'rta sektor (15-xonadan 21-xonagacha — 7 ta Lyuks xona):**\n"
            "- **Bitta Dvuxspalniy (15–21-xonalar):**\n"
            "  - O'zbekiston fuqarolari uchun: `250,000 UZS` (xona narxi)\n"
            "  - Chet el fuqarolari uchun: `300,000 UZS` (xona narxi)"
        ),
        "reg_ong": (
            "**🛏️ O'ng qanot (22-xonadan 36-xonagacha — 15 ta xona):**\n"
            "- **2 kishilik (2 alohida krovat — 22, 28, 32):** Mahalliy `150,000 UZS` | Chet el `200,000 UZS` / joy\n"
            "- **4 kishilik xonalar (23, 24, 25, 26, 27, 29, 30, 31, 33, 34, 35, 36):** Mahalliy `100,000 UZS` | Chet el `150,000 UZS` / joy\n"
            "- **Maxsus qoidalar:** Talabalarga `50% chegirma`, 7+ kunga `10% chegirma`, Sutka hisobi: `12:00 dan ertangi 12:00 gacha`."
        )
    }
    try:
        mavjudlar = db.fetchall("SELECT kalit FROM tizim_sozlamalari")
        mavjud_set = {r[0] for r in mavjudlar}
        for k, v in standart_sozlamalar.items():
            if k not in mavjud_set:
                db.execute("INSERT INTO tizim_sozlamalari (kalit, qiymat) VALUES (?,?)", (k, v))
    except Exception:
        pass
    return True

init_reglament_db()

@st.cache_data(ttl=60, show_spinner=False)
def sozlamalarni_ol():
    natija = {}
    try:
        rows = db.fetchall("SELECT kalit, qiymat FROM tizim_sozlamalari")
        for k, v in rows:
            natija[k] = v
    except Exception:
        pass
    return natija

def sozlamani_saqla(kalit, qiymat):
    if db.fetchone("SELECT kalit FROM tizim_sozlamalari WHERE kalit=?", (kalit,)):
        db.execute("UPDATE tizim_sozlamalari SET qiymat=? WHERE kalit=?", (str(qiymat), kalit))
    else:
        db.execute("INSERT INTO tizim_sozlamalari (kalit, qiymat) VALUES (?,?)", (kalit, str(qiymat)))
    keshni_tozala()

# =========================================================
# IKKI KANALLI TELEGRAM MOTORI (CEO VA MEHMONXONA EGASI UCHUN)
# =========================================================
def _tg_direct_send(token, chat_id, html_text):
    if not token or not str(chat_id).strip():
        return False
    try:
        url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": str(chat_id).strip(),
            "text": html_text,
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def aqlli_tg_xabar(sarlavha, matn, xodim, turi="mijoz", muhim=False):
    soz = sozlamalarni_ol()
    token = soz.get("tg_token", "8542159383:AAH6-3BV3274-N84m6V6Q1_3C1bE78xX0fE")
    ceo_id = soz.get("ceo_chat_id", "6483211079")
    owner_id = soz.get("owner_chat_id", "").strip()

    tg_xabar_yubor(sarlavha, matn, xodim, muhim=muhim)

    if turi == "mijoz" and owner_id and owner_id != str(ceo_id).strip():
        uz_vaqt = toshkent_vaqti().strftime("%d.%m.%Y | %H:%M")
        belgi = "🚨 <b>[MUHIM]</b> " if muhim else "🏨 "
        xabar_matni = (
            f"{belgi}<b>Y.S.H. — MEHMONLAR HISOBOTI</b>\n"
            f"📌 <b>Amaliyot:</b> {sarlavha}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{matn}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <b>Mas'ul:</b> {xodim}\n"
            f"🕒 <b>Vaqt:</b> {uz_vaqt}"
        )
        _tg_direct_send(token, owner_id, xabar_matni)

# =========================================================
# 24 SOATLIK AVTOMATIK VA QO'LDA SVODKA YUBORISH TIZIMI
# =========================================================
def kunlik_svodka_shakllantir_va_yubor(xodim_ismi="Avto-Tizim (Y.S.H.)", majburiy=False):
    soz = sozlamalarni_ol()
    rejim = soz.get("svodka_rejimi", "Har kuni 12:00 va 00:00 da")
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")
    kecha_str = (uz_now.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    soat = uz_now.hour

    yuborish_kerak = False
    svodka_turi_nomi = "24 soatlik Kunlik Svodka"
    saqlash_kaliti = None

    if majburiy:
        yuborish_kerak = True
        svodka_turi_nomi = f"Tezkor Svodka ({uz_now.strftime('%d.%m.%Y %H:%M')})"
    else:
        if "12:00" in rejim and soat >= 12 and soz.get("oxirgi_svodka_12", "") != bugun_str:
            yuborish_kerak = True
            svodka_turi_nomi = f"Sutkalik Svodka (12:00 -> 12:00 | {bugun_str})"
            saqlash_kaliti = "oxirgi_svodka_12"
        elif "00:00" in rejim and soat < 12 and soz.get("oxirgi_svodka_00", "") != bugun_str:
            yuborish_kerak = True
            svodka_turi_nomi = f"Tungi 00:00 Svodka ({kecha_str} yakuni)"
            saqlash_kaliti = "oxirgi_svodka_00"

    if not yuborish_kerak:
        return False

    df_b = kesh_df_ol("SELECT * FROM bronlar")
    df_t = kesh_df_ol("SELECT * FROM tolovlar_tarixi WHERE sana >= ?", (kecha_str,))
    df_s = kesh_df_ol("SELECT * FROM savdolar WHERE sana >= ?", (kecha_str,))
    df_x = kesh_df_ol("SELECT * FROM xarajatlar WHERE sana >= ?", (kecha_str,))
    toz_map = barcha_xona_tozalik_ol()

    if not df_b.empty:
        df_b['odam_soni'] = df_b['odam_soni'].fillna(1).astype(int)
        df_b['qoldiq'] = df_b['qoldiq'].fillna(0)
        faol_m = df_b[(df_b['holat'] != 'Chiqib ketgan') & (df_b['kirish_sanasi'] <= bugun_str) & (df_b['chiqish_sanasi'] >= bugun_str)]
        band_x_soni = len(set(faol_m['xona'].unique()))
        faol_odam_soni = int(faol_m['odam_soni'].sum())

        kirgan_df = df_b[df_b['kirish_sanasi'].isin([kecha_str, bugun_str]) & (df_b['holat'] != 'Chiqib ketgan')]
        kirgan_odam = int(kirgan_df['odam_soni'].sum())
        kirgan_bron = len(kirgan_df)

        chiqqan_df = df_b[(df_b['chiqish_sanasi'].isin([kecha_str, bugun_str])) & (df_b['holat'] == 'Chiqib ketgan')]
        chiqqan_odam = int(chiqqan_df['odam_soni'].sum())
        chiqqan_bron = len(chiqqan_df)

        umumiy_qarz = float(df_b[(df_b['qoldiq'] > 0) & (df_b['holat'] != 'Chiqib ketgan')]['qoldiq'].sum())
    else:
        band_x_soni, faol_odam_soni, kirgan_odam, kirgan_bron, chiqqan_odam, chiqqan_bron, umumiy_qarz = 0, 0, 0, 0, 0, 0, 0.0

    tozalash_kk = sum(1 for h in toz_map.values() if h == "Tozalash kerak")
    bosh_x_soni = max(0, 36 - band_x_soni)

    yotoq_kirim = float(df_t[df_t['manba'] != 'Market Savdo']['summa'].fillna(0).sum()) if not df_t.empty else 0.0
    market_kirim = float(df_t[df_t['manba'] == 'Market Savdo']['summa'].fillna(0).sum()) if not df_t.empty else 0.0
    xarajat_sum = float(df_x['summa'].fillna(0).sum()) if not df_x.empty else 0.0
    sof_kassa = (yotoq_kirim + market_kirim) - xarajat_sum

    owner_matn = (
        f"🛏 <b>Hozir band xonalar:</b> {band_x_soni} / 36 ta ({faol_odam_soni} nafar mehmon)\n"
        f"🟢 <b>Bo'sh xonalar:</b> {bosh_x_soni} ta\n"
        f"📥 <b>Kirdi (24 soatda):</b> {kirgan_odam} kishi ({kirgan_bron} ta bron)\n"
        f"🛫 <b>Chiqib ketdi:</b> {chiqqan_odam} kishi ({chiqqan_bron} ta bron)\n"
        f"💰 <b>Yotoq bo'yicha tushum:</b> {yotoq_kirim:,.0f} UZS\n"
        f"⚠️ <b>Mehmonlardagi joriy qarzlar:</b> {umumiy_qarz:,.0f} UZS"
    )

    kam_tovarlar_soni = db.fetchone("SELECT COUNT(*) FROM mahsulotlar WHERE qoldiq <= 5")[0] or 0
    ceo_matn = (
        f"{owner_matn}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Market tushumi:</b> {market_kirim:,.0f} UZS ({len(df_s)} ta savdo)\n"
        f"➖ <b>Xarajatlar:</b> {xarajat_sum:,.0f} UZS\n"
        f"🏦 <b>Sof Kassa Balansi:</b> {sof_kassa:,.0f} UZS\n"
        f"🧹 <b>Tozalash kerak bo'lgan xonalar:</b> {tozalash_kk} ta\n"
        f"📦 <b>Skladda kam qolgan tovarlar:</b> {kam_tovarlar_soni} xil"
    )

    token = soz.get("tg_token", "8542159383:AAH6-3BV3274-N84m6V6Q1_3C1bE78xX0fE")
    owner_id = soz.get("owner_chat_id", "").strip()
    ceo_id = soz.get("ceo_chat_id", "6483211079").strip()

    tg_xabar_yubor(svodka_turi_nomi, ceo_matn, xodim_ismi)
    if owner_id and owner_id != ceo_id:
        uz_v = uz_now.strftime("%d.%m.%Y | %H:%M")
        owner_full = (
            f"📊 <b>{svodka_turi_nomi}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{owner_matn}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🕒 <b>Vaqt:</b> {uz_v}"
        )
        _tg_direct_send(token, owner_id, owner_full)

    if saqlash_kaliti:
        sozlamani_saqla(saqlash_kaliti, bugun_str)
    return True

# =========================================================
# DINAMIK TARIF KALKULYATORI
# =========================================================
def dinamik_narx_hisobla(tomon, xona, toifa, odam_soni, kunlar, toliq_xona=False, maxsus_chegirma_foiz=0):
    soz = sozlamalarni_ol()
    sigim = XONALAR[tomon][xona][0]
    hisob_odam = sigim if toliq_xona else odam_soni

    n_4k = float(soz.get("narx_4k", 100000) or 100000)
    n_3k = float(soz.get("narx_3k", 110000) or 110000)
    n_2k = float(soz.get("narx_2k", 150000) or 150000)
    n_luxe_uz = float(soz.get("narx_luxe_uz", 250000) or 250000)
    n_luxe_chet = float(soz.get("narx_luxe_chet", 300000) or 300000)
    ustama_chet = float(soz.get("ustama_chet", 50000) or 50000)
    cheg_talaba = float(soz.get("chegirma_talaba", 50) or 50)
    cheg_hafta = float(soz.get("chegirma_hafta", 10) or 10)

    if tomon == "O'rtadagi":
        bazaviy_kunlik = n_luxe_chet if toifa == "Chet el fuqarosi" else n_luxe_uz
    else:
        bazaviy_narx = n_2k if sigim == 2 else (n_3k if sigim == 3 else n_4k)
        if toifa == "Chet el fuqarosi":
            bazaviy_kunlik = (bazaviy_narx + ustama_chet) * hisob_odam
        elif toifa == "Talaba (Student)":
            bazaviy_kunlik = (bazaviy_narx * ((100.0 - cheg_talaba) / 100.0)) * hisob_odam
        else:
            bazaviy_kunlik = bazaviy_narx * hisob_odam

    standart_jami = bazaviy_kunlik * kunlar

    if maxsus_chegirma_foiz and float(maxsus_chegirma_foiz) > 0:
        amaldagi_chegirma = float(maxsus_chegirma_foiz)
    elif kunlar >= 7 and cheg_hafta > 0:
        amaldagi_chegirma = cheg_hafta
    else:
        amaldagi_chegirma = 0.0

    yakuniy_jami = standart_jami * ((100.0 - amaldagi_chegirma) / 100.0)
    yakuniy_kunlik = yakuniy_jami / max(1, kunlar)
    return yakuniy_kunlik, yakuniy_jami, amaldagi_chegirma

# =========================================================
# KORPORATIV UI/UX DIZAYN DVIJOGI (DARK & LIGHT MODE — 100% TO'LIQ TUZATILGAN)
# =========================================================
def mukammal_ui_ux_sozla(tema_nomi):
    if tema_nomi == "🌙 Qorong'u (Dark UI)":
        css = """
        <style>
        /* MOBIL EKRANLAR UCHUN IXCHAM DIZAYN */
        @media (max-width: 768px) {
            .block-container { padding-top: 1.5rem !important; padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
            div[data-testid="stHorizontalBlock"] {
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 8px !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                flex: 1 1 calc(50% - 8px) !important;
                min-width: 140px !important;
            }
        }
        /* 1. ASOSIY SAHIFA, TEPADAGI HEADER VA SIDEBAR FONI */
        :root {
            --primary-color: #8b5cf6 !important;
            --background-color: #0b0d14 !important;
            --secondary-background-color: #141724 !important;
            --text-color: #f8fafc !important;
        }
        header[data-testid="stHeader"] {
            background-color: #0b0d14 !important;
            border-bottom: 1px solid #1e2436 !important;
        }
        header[data-testid="stHeader"] * {
            color: #cbd5e1 !important;
        }
        .block-container { padding-top: 2.8rem !important; padding-bottom: 3rem !important; }
        .stApp { background-color: #0b0d14 !important; color: #f8fafc !important; }
        section[data-testid="stSidebar"] { background-color: #111420 !important; border-right: 1px solid #1e2436 !important; }
        
        /* 2. BARCHA MATNLAR VA SARLAVHALAR */
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

        /* 3. METRIC KARTOCHKALAR */
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

        div[data-testid="stAlert"] * {
            color: #f8fafc !important;
        }

        /* 4. TUGMALAR (BUTTONS) */
        .stButton > button, .stDownloadButton > button {
            background-color: #171c2e !important;
            color: #e2e8f0 !important;
            border: 1px solid #2a324b !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1rem !important;
            transition: all 0.18s ease !important;
        }
        section[data-testid="stSidebar"] .stButton > button {
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.62rem 1rem !important;
            margin-bottom: 2px !important;
        }
        .stButton > button *, .stDownloadButton > button * {
            color: #ffffff !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            background-color: #232a45 !important;
            border-color: #8b5cf6 !important;
            color: #ffffff !important;
        }
        button[kind="primary"], .stFormSubmitButton > button {
            background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
            border: 1px solid #a78bfa !important;
            color: #ffffff !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 0.62rem 1.1rem !important;
            box-shadow: 0 4px 14px rgba(124,58,237,0.4) !important;
        }
        button[kind="primary"] *, .stFormSubmitButton > button * {
            color: #ffffff !important;
        }

        /* 5. EXPANDER (YIG'ILUVCHI BLOKLAR — HOVERDA OQ BO'LIB QOLMASLIGI UCHUN!) */
        .stForm,
        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #141724 !important;
            border: 1px solid #2a324b !important;
            border-radius: 14px !important;
            padding: 16px !important;
        }
        div[data-testid="stExpander"] {
            background-color: #141724 !important;
            border: 1px solid #2a324b !important;
            border-radius: 14px !important;
            overflow: hidden !important;
        }
        div[data-testid="stExpander"] details {
            background-color: #141724 !important;
            border: none !important;
        }
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] details > summary {
            background-color: #181c2e !important;
            color: #f8fafc !important;
            padding: 12px 16px !important;
            border-radius: 12px !important;
            transition: background-color 0.15s ease !important;
        }
        div[data-testid="stExpander"] summary:hover,
        div[data-testid="stExpander"] details > summary:hover,
        div[data-testid="stExpander"] summary:focus,
        div[data-testid="stExpander"] summary:active {
            background-color: #232a45 !important;
            color: #ffffff !important;
        }
        div[data-testid="stExpander"] summary *,
        div[data-testid="stExpander"] summary:hover *,
        div[data-testid="stExpander"] summary span,
        div[data-testid="stExpander"] summary p,
        div[data-testid="stExpander"] summary svg {
            color: #ffffff !important;
            fill: #ffffff !important;
        }
        div[data-testid="stExpanderDetails"] {
            background-color: #141724 !important;
            color: #f8fafc !important;
            padding: 14px 16px !important;
            border-top: 1px solid #262b40 !important;
        }

        /* 6. MODAL OYNA (st.dialog) PORTALI */
        dialog,
        dialog[data-testid="stDialog"],
        dialog[open],
        div[data-testid="stDialog"],
        div[data-testid="stDialog"] > div,
        div[data-testid="stDialog"] > div > div,
        div[role="dialog"],
        div[role="dialog"] > div,
        div[aria-modal="true"],
        div[data-baseweb="modal"] > div,
        div[data-baseweb="modal"] > div > div {
            background-color: #111420 !important;
            color: #f8fafc !important;
            border-color: #3b4461 !important;
        }
        dialog label,
        dialog p,
        dialog h1,
        dialog h2,
        dialog h3,
        div[data-testid="stDialog"] label,
        div[data-testid="stDialog"] p,
        div[data-testid="stDialog"] h1,
        div[data-testid="stDialog"] h2,
        div[data-testid="stDialog"] h3,
        div[role="dialog"] label,
        div[role="dialog"] p,
        div[aria-modal="true"] label,
        div[aria-modal="true"] p {
            color: #f8fafc !important;
        }
        dialog button[aria-label="Close"],
        div[data-testid="stDialog"] button[aria-label="Close"],
        div[role="dialog"] button[aria-label="Close"] {
            color: #ffffff !important;
            background-color: #232a45 !important;
            border: 1px solid #6d28d9 !important;
            border-radius: 8px !important;
        }

        /* 7. INPUTLAR, SANALAR, SOATLAR VA NUMBER (+/-) TUGMALARI */
        .stApp input,
        dialog input,
        div[role="dialog"] input,
        div[data-testid="stDialog"] input,
        div[data-testid="stDateInput"] input,
        div[data-testid="stTimeInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input,
        .stApp textarea {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            background-color: #f8fafc !important;
            font-weight: 700 !important;
            caret-color: #0f172a !important;
        }
        .stApp input::placeholder,
        dialog input::placeholder,
        div[role="dialog"] input::placeholder,
        div[data-testid="stDialog"] input::placeholder,
        .stApp textarea::placeholder {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            font-weight: 400 !important;
            opacity: 1 !important;
        }
        div[data-testid="stNumberInput"] button {
            background-color: #e2e8f0 !important;
            color: #0f172a !important;
            border-left: 1px solid #cbd5e1 !important;
        }
        div[data-testid="stNumberInput"] button:hover {
            background-color: #cbd5e1 !important;
            color: #0f172a !important;
        }
        div[data-testid="stNumberInput"] button *,
        div[data-testid="stNumberInput"] button svg {
            color: #0f172a !important;
            fill: #0f172a !important;
        }
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="select"] > div {
            background-color: #f8fafc !important;
            color: #0f172a !important;
        }
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div,
        div[data-baseweb="select"] svg,
        div[data-testid="stDateInput"] svg,
        div[data-testid="stTimeInput"] svg,
        div[data-testid="stTimeInput"] div[data-baseweb="select"] * {
            color: #0f172a !important;
            fill: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            font-weight: 600 !important;
        }
        /* OCHILUVCHI RO'YXATLAR (DROPDOWN MENU / POPOVER) */
        div[data-baseweb="popover"] *,
        ul[role="listbox"],
        ul[role="listbox"] li,
        div[role="listbox"] * {
            background-color: #151928 !important;
            color: #f8fafc !important;
            -webkit-text-fill-color: #f8fafc !important;
        }
        ul[role="listbox"] li:hover,
        ul[role="listbox"] li[aria-selected="true"] {
            background-color: #6d28d9 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        div[data-baseweb="tag"] {
            background-color: #7c3aed !important;
        }
        div[data-baseweb="tag"] span,
        div[data-baseweb="tag"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    else:
        css = """
        <style>
        .block-container { padding-top: 2.8rem !important; padding-bottom: 3rem !important; }
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
        .stButton > button, .stDownloadButton > button {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            transition: all 0.18s ease !important;
        }
        section[data-testid="stSidebar"] .stButton > button {
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.62rem 1rem !important;
            margin-bottom: 2px !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            background-color: #e2e8f0 !important;
            border-color: #4f46e5 !important;
        }
        button[kind="primary"], .stFormSubmitButton > button {
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 0.62rem 1.1rem !important;
            box-shadow: 0 4px 12px rgba(79,70,229,0.3) !important;
        }
        button[kind="primary"] *, .stFormSubmitButton > button * { color: #ffffff !important; }
        .stApp input::placeholder, .stApp textarea::placeholder {
            color: #94a3b8 !important;
            font-weight: 400 !important;
        }
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

# =========================================================
# XONADAGI KROVAT / JOY O'RNI VA SUTKA FUNKSIYALARI
# =========================================================
def xonadagi_band_krovatlar(xona_nomi, kirish_str, chiqish_str, exclude_mijoz_id=None):
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")

    df_all_active = kesh_df_ol("SELECT mijoz_id, mijoz, xona, xona_turi, izoh, kirish_sanasi, chiqish_sanasi FROM bronlar WHERE holat!='Chiqib ketgan'")
    if df_all_active.empty:
        return {}

    x_rows = df_all_active[df_all_active['xona'] == xona_nomi]
    if exclude_mijoz_id:
        x_rows = x_rows[x_rows['mijoz_id'] != exclude_mijoz_id]

    band_map = {}
    sigim = xona_sigimini_ol(xona_nomi)
    for _, r in x_rows.iterrows():
        r_kir = str(r.get('kirish_sanasi') or '')
        r_chiq = str(r.get('chiqish_sanasi') or '')
        m_ism = r.get('mijoz', '')
        ef_chiq = (datetime.strptime(r_chiq, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if (r_kir == r_chiq and r_kir >= bugun_str) else r_chiq
        ef_yangi_chiq = (datetime.strptime(chiqish_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if kirish_str == chiqish_str else chiqish_str
        if r_kir < ef_yangi_chiq and ef_chiq > kirish_str:
            birikma = f"{r.get('xona_turi') or ''} {r.get('izoh') or ''}"
            if "Barcha joylar" in birikma or "To'liq band" in birikma:
                for j_i in range(1, sigim + 1):
                    band_map[j_i] = m_ism
            else:
                topildi = re.findall(r'(\d)-joy', birikma)
                for j_raqam in topildi:
                    band_map[int(j_raqam)] = m_ism
    return band_map

def krovat_nomini_ajrat(xona_turi_str, izoh_str=""):
    birikma = f"{xona_turi_str or ''} {izoh_str or ''}"
    m = re.search(r'\[🛏️ (.*?)\]', birikma)
    if m:
        joy_matn = m.group(1)
        joy_matn = joy_matn.replace("Chapdan ", "").replace("O'ngdan ", "").strip()
        return joy_matn
    return ""

def xona_sxemasi_kichik_html(sigim, band_map):
    kataklar = []
    for k_i in range(1, sigim + 1):
        if k_i in band_map:
            m_qisqa = str(band_map[k_i])[:11]
            kataklar.append(
                f"<div style='background:rgba(239,68,68,0.2); border:1px solid #ef4444; border-radius:8px; padding:6px 8px; text-align:center; font-size:12px;'>"
                f"🔴 <b>{k_i}-joy</b><br><span style='font-size:11px; opacity:0.85;'>{m_qisqa}</span></div>"
            )
        else:
            kataklar.append(
                f"<div style='background:rgba(34,197,94,0.16); border:1px solid #22c55e; border-radius:8px; padding:6px 8px; text-align:center; font-size:12px;'>"
                f"🟢 <b>{k_i}-joy</b><br><span style='font-size:11px; opacity:0.85;'>Bo'sh</span></div>"
            )
    if sigim == 3:
        kataklar.append("<div style='border:1px dashed rgba(148,163,184,0.25); border-radius:8px; padding:6px 8px; text-align:center; font-size:11px; opacity:0.5;'>—</div>")

    return (
        f"<div style='margin-bottom:8px; padding:8px; border-radius:10px; background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.25);'>"
        f"<div style='font-size:11.5px; font-weight:700; margin-bottom:6px; text-align:center;'>🧭 Xona joylashuv sxemasi (1 ➔ 2" + (" | 3 ➔ 4" if sigim == 4 else (" | 3" if sigim == 3 else "")) + "):</div>"
        f"<div style='display:grid; grid-template-columns:1fr 1fr; gap:6px;'>{''.join(kataklar)}</div></div>"
    )

def soat_matndan_time_ol(soat_str):
    try:
        qismlar = str(soat_str).strip().split(":")
        return dt_time(int(qismlar[0]) % 24, int(qismlar[1]) % 60)
    except Exception:
        hozir_t = toshkent_vaqti()
        return dt_time(hozir_t.hour, hozir_t.minute)

def bron_shu_kunda_faolmi(r_kirish, r_chiqish, r_holat, tekshir_sana_str):
    if str(r_holat) == 'Chiqib ketgan':
        return False
    k_s = str(r_kirish or '')
    ch_s = str(r_chiqish or '')
    if k_s == ch_s and k_s == tekshir_sana_str:
        return True
    return (k_s <= tekshir_sana_str) and (ch_s > tekshir_sana_str)

# ==========================================
# AVTO-LOGIN (REFRESHDA CHIQIB KETMASLIK UCHUN)
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
            login_input = st.text_input("Foydalanuvchi logini")
            parol_input = st.text_input("Maxfiy parol", type="password")
            submit_login = st.form_submit_button("Tizimga kirish", use_container_width=True, type="primary")
            if submit_login:
                user = db.fetchone("SELECT role, ism, login FROM xodimlar WHERE login=? AND parol=?", (login_input.strip(), parol_input.strip()))
                if user:
                    st.session_state.logged_in = True
                    st.session_state.role = user[0]
                    st.session_state.xodim_ismi = user[1] if user[1] else user[2].upper()
                    st.session_state.user_login = user[2]
                    st.query_params["user"] = user[2]
                    if user[0] == "housekeeping":
                        st.session_state.faol_sahifa = "🧹 Xona tozalash"
                    st.query_params["page"] = st.session_state.faol_sahifa
                    jurnalga_yozish("Tizim", st.session_state.xodim_ismi, "Tizimga kirdi", "Ish faoliyati boshlandi")
                    st.rerun()
                else:
                    st.error("Noto'g'ri login yoki parol kiritildi!")
    st.stop()

# =========================================================
# AVTO-CHECKOUT VA 24 SOATLIK SVODKANI HAR KLIKDA EMAS, HAR 5 DAQIQADA 1 MARTA TEKSHIRISH!
# =========================================================
hozir_ts = time.time()
if hozir_ts - st.session_state.oxirgi_avto_tekshiruv_ts > 300:
    avto_checkout_tekshir()
    kunlik_svodka_shakllantir_va_yubor()
    st.session_state.oxirgi_avto_tekshiruv_ts = hozir_ts

# ==========================================
# 2. ZAMONAVIY MENYU BAR
# ==========================================
xodim_ismi = st.session_state.xodim_ismi
hozirgi_uz_vaqt = toshkent_vaqti()
bugungi_sana = hozirgi_uz_vaqt.strftime("%Y-%m-%d")
hozirgi_soat = hozirgi_uz_vaqt.hour

st.sidebar.title("🏨 Y.S.H. ERP")
rol_nomi_korsat = "TOZALIK / XO'JALIK" if st.session_state.role == "housekeeping" else st.session_state.role.upper()
st.sidebar.markdown(f"<div style='font-size:14px; font-weight:700; margin-bottom:10px;'>👤 {xodim_ismi} ({rol_nomi_korsat})</div>", unsafe_allow_html=True)

tanlangan_tema = st.sidebar.selectbox(
    "🎨 Interfeys temasi:",
    ["🌙 Qorong'u (Dark UI)", "☀️ Yorug' (Standart)"],
    index=0 if st.session_state.ui_tema == "🌙 Qorong'u (Dark UI)" else 1
)
if tanlangan_tema != st.session_state.ui_tema:
    st.session_state.ui_tema = tanlangan_tema
    st.query_params["theme"] = "light" if tanlangan_tema == "☀️ Yorug' (Standart)" else "dark"

mukammal_ui_ux_sozla(tanlangan_tema)
is_dark = (tanlangan_tema == "🌙 Qorong'u (Dark UI)")

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='font-size:11.5px; font-weight:800; letter-spacing:1.2px; opacity:0.8; margin-bottom:8px;'>🧭 ASOSIY MENYU BAR</div>", unsafe_allow_html=True)

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
elif st.session_state.role == "housekeeping":
    menyu_variantlar = [
        "🧹 Xona tozalash",
        "📅 Timeline & Shaxmatka",
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

url_page = st.query_params.get("page", "")
if url_page in menyu_variantlar:
    st.session_state.faol_sahifa = url_page
elif st.session_state.faol_sahifa not in menyu_variantlar:
    st.session_state.faol_sahifa = menyu_variantlar[0]

for m_item in menyu_variantlar:
    is_active = (st.session_state.faol_sahifa == m_item)
    if st.sidebar.button(
        m_item,
        key=f"nav_btn_{m_item}",
        type="primary" if is_active else "secondary",
        use_container_width=True
    ):
        st.session_state.faol_sahifa = m_item
        st.query_params["page"] = m_item
        st.rerun()

sahifa = st.session_state.faol_sahifa

if st.session_state.role != "housekeeping":
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### 🔍 Global CRM Davr Filtri")
    g_bosh_sana, g_tugash_sana, g_davr_nomi = aqlli_sana_filtri_ui(joylashuv="sidebar", key_prefix="global")
    st.sidebar.markdown(f"<div style='font-size:13px; font-weight:600; margin-top:4px;'>📌 Faol davr: <b>{g_davr_nomi}</b></div>", unsafe_allow_html=True)

    # ON-DEMAND EXCEL BACKUP (HAR KLIKDA 7 TA JADVAL O'QILMASLIGI UCHUN!)
    st.sidebar.markdown("---")
    if not st.session_state.sidebar_excel_tayyor:
        if st.sidebar.button("📦 Excel zaxirani tayyorlash", use_container_width=True):
            st.session_state.sidebar_excel_tayyor = True
            st.rerun()
    else:
        st.sidebar.download_button(
            label="💾 Yuklab olish (.xlsx)",
            data=barcha_bazani_yuklash(),
            file_name=f"Y.S.H._ERP_Full_Backup_{bugungi_sana}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
else:
    g_bosh_sana, g_tugash_sana, g_davr_nomi = None, None, "Bugungi"

st.sidebar.write("")
if st.sidebar.button("🚪 Tizimdan chiqish", use_container_width=True):
    jurnalga_yozish("Tizim", xodim_ismi, "Tizimdan chiqdi", "Ish faoliyati yakunlandi")
    st.session_state.logged_in = False
    st.session_state.role = None
    st.query_params.clear()
    st.rerun()

# =========================================================
# VIZUAL XONALAR VA KROVATLAR XARITASI (2D MATRITSA: 1->2 | 3->4)
# =========================================================
def render_vizual_krovatlar_xaritasi(qidir_x=""):
    st.markdown("##### 🗺️ Xonalar va Krovatlar (Yotoq o'rinlari) Jonli Xaritasi")
    st.caption("Krovatlar joylashuvi xona ichidagi haqiqiy tartibda: 4 kishilikda (1 ➔ 2 tepada, 3 ➔ 4 pastda), 3 kishilikda (1 ➔ 2 tepada, 3 pastda), 2 kishilikda (1 ➔ 2 yonma-yon).")

    qanot_filtr = st.radio("Sektorni tanlang:", ["Barchasi", "Chap tomon", "O'rtadagi", "O'ng tomon"], horizontal=True, key="xarita_qanot_f")
    tozalik_map = barcha_xona_tozalik_ol()
    df_faol_b = kesh_df_ol("SELECT * FROM bronlar WHERE holat != 'Chiqib ketgan' ORDER BY id DESC")

    for tomon, xonalar in XONALAR.items():
        if qanot_filtr != "Barchasi" and tomon != qanot_filtr:
            continue
        st.markdown(f"###### 📍 {tomon.upper()} ({len(xonalar)} ta xona)")
        cols_x = st.columns(3, gap="medium")
        col_i = 0
        for x_nom, (sigim, _) in xonalar.items():
            if qidir_x and qidir_x.lower() not in x_nom.lower():
                continue

            if not df_faol_b.empty:
                x_m_mask = df_faol_b.apply(lambda r: r['xona'] == x_nom and bron_shu_kunda_faolmi(r['kirish_sanasi'], r['chiqish_sanasi'], r['holat'], bugungi_sana), axis=1)
                x_mehmonlar = df_faol_b[x_m_mask]
            else:
                x_mehmonlar = pd.DataFrame()

            toza_hol = tozalik_map.get(x_nom, "Toza")
            band_odam = 0
            x_jins = ""
            vikup_bor = False
            krovat_egalari = {}
            ketuvchilar = []

            if not x_mehmonlar.empty:
                for _, mr in x_mehmonlar.iterrows():
                    o_s = int(mr.get('odam_soni', 1) or 1)
                    band_odam += o_s
                    if not x_jins and mr.get('jinsi'):
                        x_jins = mr.get('jinsi')
                    birikma = f"{mr.get('xona_turi', '')} {mr.get('izoh', '')}"
                    if "To'liq band" in birikma or "Barcha joylar" in birikma or tomon == "O'rtadagi":
                        vikup_bor = True
                        for j_k in range(1, sigim + 1):
                            krovat_egalari[j_k] = f"{mr['mijoz']}"
                    else:
                        topildi = re.findall(r'(\d)-joy', birikma)
                        for j_raq in topildi:
                            krovat_egalari[int(j_raq)] = f"{mr['mijoz']}"
                    if str(mr.get('chiqish_sanasi', '')) == bugungi_sana:
                        ketuvchilar.append(f"{mr['mijoz']} ({o_s}k)")

            bosh_joy = 0 if vikup_bor else max(0, sigim - band_odam)

            if toza_hol == "Tozalash kerak":
                border_c = "#ef4444"
                hol_badge = "🔴 Tozalash kerak"
            elif bosh_joy == 0:
                border_c = "#8b5cf6"
                hol_badge = "🟣 To'liq band"
            elif band_odam > 0:
                border_c = "#f59e0b"
                hol_badge = f"🟡 {bosh_joy} ta bo'sh joy bor"
            else:
                border_c = "#22c55e"
                hol_badge = "🟢 To'liq bo'sh (Toza)"

            jins_badge = f" • {'👨 Erkaklar' if x_jins == 'Erkak' else '👩 Ayollar'}" if x_jins else ""
            tur_matn = "Lyuks (Dvuxspalniy)" if tomon == "O'rtadagi" else f"{sigim} kishilik"

            if tomon == "O'rtadagi":
                if band_odam > 0:
                    m_nom_l = ", ".join(x_mehmonlar['mijoz'].tolist())
                    krovat_html = f"<div style='padding:8px 10px; background:rgba(139,92,246,0.2); border:1px solid #8b5cf6; border-radius:8px; margin-top:6px; font-size:12.5px; text-align:center;'>🛌 <b>Dvuxspalniy:</b><br>{m_nom_l} ({band_odam} kishi)</div>"
                else:
                    krovat_html = "<div style='padding:8px 10px; background:rgba(34,197,94,0.14); border:1px solid #22c55e; border-radius:8px; margin-top:6px; font-size:12.5px; text-align:center;'>🟢 <b>Dvuxspalniy:</b><br>BO'SH</div>"
            else:
                grid_kataklar = []
                for k_i in range(1, sigim + 1):
                    if k_i in krovat_egalari:
                        m_qisqa = str(krovat_egalari[k_i])[:14]
                        grid_kataklar.append(
                            f"<div style='padding:6px 8px; background:rgba(239,68,68,0.18); border:1px solid #ef4444; border-radius:8px; font-size:12px; text-align:center;'>"
                            f"🔴 <b>{k_i}-joy</b><br><span style='font-size:11px; opacity:0.9;'>{m_qisqa}</span></div>"
                        )
                    else:
                        grid_kataklar.append(
                            f"<div style='padding:6px 8px; background:rgba(34,197,94,0.14); border:1px solid #22c55e; border-radius:8px; font-size:12px; text-align:center;'>"
                            f"🟢 <b>{k_i}-joy</b><br><span style='font-size:11px; opacity:0.9;'>BO'SH</span></div>"
                        )
                if sigim == 3:
                    grid_kataklar.append("<div style='padding:6px 8px; border:1px dashed rgba(148,163,184,0.25); border-radius:8px; font-size:11px; text-align:center; opacity:0.45;'>—</div>")
                krovat_html = f"<div style='display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:6px;'>{''.join(grid_kataklar)}</div>"

            ketish_html = f"<div style='margin-top:6px; padding:4px 8px; background:rgba(234,179,8,0.2); border-radius:6px; font-size:11.5px; color:#fde047;'>⏳ <b>Bugun 12:00 da chiqadi:</b> {', '.join(ketuvchilar)}</div>" if ketuvchilar else ""
            bg_c = "#151928" if is_dark else "#ffffff"

            with cols_x[col_i % 3]:
                st.markdown(
                    f"<div style='background:{bg_c}; border:2px solid {border_c}; border-radius:12px; padding:12px; margin-bottom:12px;'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<span style='font-size:15px; font-weight:800;'>🛏️ {x_nom}</span>"
                    f"<span style='font-size:12px; font-weight:700;'>{hol_badge}</span></div>"
                    f"<div style='font-size:12px; opacity:0.8; margin:3px 0 6px 0;'>{tur_matn}{jins_badge} • Bo'sh joy: <b>{bosh_joy}/{sigim}</b></div>"
                    f"{krovat_html}{ketish_html}</div>",
                    unsafe_allow_html=True
                )
            col_i += 1

# =========================================================
# YORDAMCHI FUNKSIYA: YANGI BRON FORMASI (@st.fragment BILAN TEZKOR!)
# =========================================================
def _render_qabul_inner(form_key_suffix="main"):
    mukammal_ui_ux_sozla(st.session_state.ui_tema)
    soz = sozlamalarni_ol()
    cheg_hafta_foiz = int(float(soz.get("chegirma_hafta", 10) or 10))
    cheg_talaba_foiz = int(float(soz.get("chegirma_talaba", 50) or 50))
    hisob_soat_str = soz.get("hisob_soati", "12:00")

    bg_box = "#141724" if is_dark else "#ffffff"
    bd_box = "#2a324b" if is_dark else "#cbd5e1"
    st.markdown(
        f"<div style='background:{bg_box}; border:1px solid {bd_box}; padding:10px 16px; border-radius:12px; margin-bottom:8px;'>"
        f"<span style='font-size:14px; font-weight:700; color:#a78bfa !important;'>🛏️ Xona va Sektor tanlovi</span> &nbsp;|&nbsp; "
        f"<span style='font-size:12.5px; color:#cbd5e1 !important;'>Sutka hisobi: <b>12:00 dan ertangi 12:00 gacha</b> (Chet el fuqarolariga +50,000 UZS)</span></div>",
        unsafe_allow_html=True
    )

    with st.container(border=True):
        c_top1, c_top2 = st.columns([1.5, 1.5], gap="medium")
        with c_top1:
            tomon = st.radio(
                "📍 1. Binoning qanotini (sektorini) tanlang:",
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

    uz_now_form = toshkent_vaqti()
    default_time_obj = dt_time(uz_now_form.hour, uz_now_form.minute)

    with st.form(f"qabul_form_{form_key_suffix}", clear_on_submit=True, enter_to_submit=False):
        f_top1, f_top2 = st.columns([1.4, 1.6], gap="medium")
        with f_top1:
            bron_turi = st.radio("📌 Rasmiylashtirish turi:", ["Hozir qabul qilish (Kirish)", "Oldindan band qilish (Bron)"], horizontal=True)
        with f_top2:
            sutka_rejimi = st.radio(
                "⏰ 12:00 Sutka hisobi (Chiqish vaqti):",
                [
                    "Avtomatik (00:00–11:59 da kelsa bugun 12:00 da, 12:00 dan keyin kelsa ertaga 12:00 da)",
                    "Standart (Kelgan sanadan keyingi kun 12:00 da)"
                ],
                index=0
            )
        st.markdown("---")
        col1, col2, col3 = st.columns(3, gap="medium")
        with col1:
            mijoz_ism = st.text_input("👤 Mehmon F.I.O (Ismi) *", placeholder="Masalan: Alisher Karimov")
            mijoz_tel = st.text_input("📞 Telefon raqami (ixtiyoriy):", placeholder="+998 90 123 45 67")
            jinsi = st.radio("🚻 Jinsi", ["Erkak", "Ayol"], horizontal=True)
            toifa = st.selectbox(
                f"🪪 Tarif toifasi (Chet el +50k | Talaba -{cheg_talaba_foiz}%)",
                ["O'zbekiston fuqarosi", "Chet el fuqarosi", "Talaba (Student)"]
            )
            
            ks1, ks2 = st.columns([1.25, 1.05])
            with ks1:
                kirish_sanasi = st.date_input("📅 Kelish sanasi *", uz_now_form.date())
            with ks2:
                kirish_soati_obj = st.time_input("🕒 Kelish soati *", value=default_time_obj, step=60)
            
        with col2:
            maks_odam = 2 if tomon == "O'rtadagi" else tanlangan_xona_sigim
            odam_soni = st.number_input(f"👥 Mehmonlar soni (1 - {maks_odam})", min_value=1, max_value=maks_odam, value=1)
            
            if tomon != "O'rtadagi":
                st.markdown(xona_sxemasi_kichik_html(tanlangan_xona_sigim, hozir_band_krovatlar), unsafe_allow_html=True)
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
                    f"🛏️ Yotoq o'rnini belgilang ({tanlangan_xona_nom}):",
                    krovat_opsiyalar,
                    default=default_krovat
                )
            else:
                tanlangan_krovatlar = []
                st.info("🛌 O'rtadagi Lyuks xona: Bitta Dvuxspalniy (To'liq xona)")

            toliq_band_vikup = st.checkbox("🔒 Xonani to'liq band qilish (Vikup — to'liq xona narxida)")
            kunlar = st.number_input(f"🌙 Yashash muddati (sutka) (7+ sutkaga {cheg_hafta_foiz}% chegirma)", min_value=1, max_value=365, value=1)

        with col3:
            maxsus_chegirma = st.number_input(
                f"🏷️ Admin/CEO maxsus chegirmasi % (0 = Avto {cheg_hafta_foiz}% 7+ kunga):",
                min_value=0, max_value=100, value=0, step=5
            )
            maxsus_kunlik = st.number_input("⚙️ Maxsus kunlik tarif (0 = Avtomatik standart hisob)", min_value=0, value=0, step=5000)
            tolangan = st.number_input("💵 Qabul qilingan to'lov summasi (UZS):", min_value=0, value=0, step=10000)
            tolov_shakli = st.selectbox("💳 To'lov shakli", ["Naqd", "Karta", "Onlayn"])
            t_taf = st.selectbox("🏦 Kassa / To'lov tizimi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
            qoshimcha_izoh = st.text_input("📝 Qo'shimcha izoh (ixtiyoriy):", placeholder="Payme, tashrif tafsiloti va h.k.")

        st.write("")
        submit_qabul = st.form_submit_button("✅ BRON QILISH / BAZAGA SAQLASH", type="primary", use_container_width=True)

        if submit_qabul:
            if not mijoz_ism.strip():
                st.error("⚠️ Mehmonning ism-sharifini kiriting!")
            else:
                xona = tanlangan_xona_nom
                xona_sigimi = tanlangan_xona_sigim
                bazaviy_tur = "Dvuxspalniy" if tomon == "O'rtadagi" else ("2 alohida krovat" if xona_sigimi == 2 else f"{xona_sigimi} kishilik")
                
                kiritilgan_soat = kirish_soati_obj.hour if kirish_soati_obj else uz_now_form.hour
                saq_turi = 'Hozir kirish' if bron_turi == "Hozir qabul qilish (Kirish)" else 'Bron'

                if saq_turi == 'Hozir kirish' and sutka_rejimi.startswith("Avtomatik") and kiritilgan_soat < 12:
                    chiqish_sanasi = kirish_sanasi + timedelta(days=max(0, kunlar - 1))
                    tonggi_sutka_belgi = True
                else:
                    chiqish_sanasi = kirish_sanasi + timedelta(days=kunlar)
                    tonggi_sutka_belgi = False

                kirish_str = kirish_sanasi.strftime("%Y-%m-%d")
                chiqish_str = chiqish_sanasi.strftime("%Y-%m-%d")
                
                band = xonadagi_band_joyni_hisobla(xona, kirish_str, chiqish_str)
                bosh_joy = xona_sigimi - band
                kerakli_joy = xona_sigimi if toliq_band_vikup else odam_soni
                zid_jins = None if (toliq_band_vikup or tomon == "O'rtadagi") else xona_jinsini_tekshir(xona, kirish_str, chiqish_str, jinsi)
                tanlangan_band_joylar = [k for k in tanlangan_krovatlar if "🔴 Band" in k]

                if odam_soni > xona_sigimi:
                    st.error(f"⚠️ {xona} sig'imi {xona_sigimi} kishilik! Siz {odam_soni} kishi kiritdingiz.")
                elif toliq_band_vikup and band > 0:
                    st.error(f"⚠️ {xona} ni to'liq band (Vikup) qilib bo'lmaydi, chunki tanlangan sanalarda xonada boshqa mehmon bor!")
                elif kerakli_joy > bosh_joy:
                    st.error(f"⚠️ Xatolik: {xona} da tanlangan sanalar uchun bo'sh o'rin yetarli emas (Bo'sh o'rin: {bosh_joy} ta)!")
                elif zid_jins:
                    st.error(f"🚻 Xatolik: {xona} da tanlangan sanalarda **{zid_jins}** mehmon(lar) joylashgan! Umumiy xonaga **{jinsi}** mehmonni qo'shib bo'lmaydi.")
                elif tomon != "O'rtadagi" and not toliq_band_vikup and tanlangan_band_joylar:
                    st.error(f"⚠️ Siz allaqachon band qilingan yotoq o'rnini tanladingiz: {', '.join(tanlangan_band_joylar)}. Iltimos, 🟢 Bo'sh joyni tanlang!")
                elif tomon != "O'rtadagi" and not toliq_band_vikup and odam_soni < xona_sigimi and len(tanlangan_krovatlar) != odam_soni:
                    st.error(f"⚠️ Siz **{odam_soni} nafar** mehmon kiritdingiz, iltimos ular uchun aynan **{odam_soni} ta** yotoq o'rnini (krovatni) belgilang! (Hozir {len(tanlangan_krovatlar)} ta tanlangan)")
                else:
                    if tomon == "O'rtadagi":
                        krovat_yorliq = "Dvuxspalniy"
                    elif toliq_band_vikup or odam_soni == xona_sigimi:
                        krovat_yorliq = f"Barcha joylar (1-{xona_sigimi}-joy)"
                    else:
                        joy_raqamlar = ", ".join([k.split(" (")[0] for k in tanlangan_krovatlar])
                        krovat_yorliq = joy_raqamlar

                    xona_turi_matn = f"To'liq band ({bazaviy_tur}) [🛏️ {krovat_yorliq}]" if (toliq_band_vikup or tomon == "O'rtadagi") else f"{bazaviy_tur} [🛏️ {krovat_yorliq}]"

                    kunlik_stavka, standart_jami, amaldagi_cheg_foiz = dinamik_narx_hisobla(
                        tomon, xona, toifa, odam_soni, kunlar,
                        toliq_xona=toliq_band_vikup,
                        maxsus_chegirma_foiz=maxsus_chegirma
                    )
                    if maxsus_kunlik > 0:
                        kunlik_stavka = maxsus_kunlik * ((100.0 - maxsus_chegirma) / 100.0) if maxsus_chegirma > 0 else maxsus_kunlik
                        yakuniy_narx = kunlik_stavka * kunlar
                        maxsus_belgi = True
                    else:
                        yakuniy_narx = standart_jami
                        maxsus_belgi = (maxsus_chegirma > 0)

                    if t_taf == "Boshqa" and qoshimcha_izoh.strip():
                        t_taf = f"Boshqa ({qoshimcha_izoh.strip()})"

                    qoldiq = yakuniy_narx - tolangan
                    holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"
                    yangi_id = id_yaratish(jinsi, kirish_sanasi, toifa)
                    
                    uz_now = toshkent_vaqti()
                    hozirgi_sana = uz_now.strftime("%Y-%m-%d")
                    soat_str = kirish_soati_obj.strftime("%H:%M") if kirish_soati_obj else uz_now.strftime("%H:%M")
                    kirish_vaqti_toliq = f"{kirish_str} ({soat_str})"
                    muddat_nomi = f"{kunlar} sutka"

                    izoh_parts = [f"[🛏️ {krovat_yorliq}]"]
                    if toliq_band_vikup:
                        izoh_parts.append("[🔒 To'liq xona vikup]")
                    if amaldagi_cheg_foiz > 0:
                        izoh_parts.append(f"[🏷️ Chegirma: -{int(amaldagi_cheg_foiz)}%]")
                    if tonggi_sutka_belgi:
                        izoh_parts.append(f"[⏰ Tonggi kirish: {chiqish_str} 12:00 gacha]")
                    if qoshimcha_izoh.strip():
                        izoh_parts.append(qoshimcha_izoh.strip())
                    izoh_yakuniy = " ".join(izoh_parts)

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
                    jurnalga_yozish(yangi_id, xodim_ismi, "Yangi " + saq_turi, f"Mijoz: {mijoz_ism} ({odam_soni} kishi | {toifa}), Xona: {xona} ({krovat_yorliq}), Kirish: {kirish_vaqti_toliq} -> Chiqish: {chiqish_str} 12:00, Jami: {yakuniy_narx:,.0f}, To'ladi: {tolangan:,.0f} ({t_taf})")
                    keshni_tozala()
                    
                    tel_qator = f"📞 <b>Telefon:</b> {mijoz_tel.strip()}\n" if mijoz_tel.strip() else ""
                    cheg_qator = f"🏷️ <b>Chegirma:</b> -{int(amaldagi_cheg_foiz)}%\n" if amaldagi_cheg_foiz > 0 else ""
                    aqlli_tg_xabar(
                        f"Yangi {saq_turi}",
                        f"👤 <b>Mijoz:</b> {mijoz_ism} ({odam_soni} kishi | {jinsi} | {toifa})\n"
                        f"{tel_qator}"
                        f"🛏 <b>Xona va Joy:</b> {xona} — <b>{krovat_yorliq}</b> ({kunlar} sutka)\n"
                        f"🕒 <b>Kirish:</b> {kirish_vaqti_toliq} ➡️ <b>Chiqish:</b> {chiqish_str} {hisob_soat_str}\n"
                        f"{cheg_qator}"
                        f"💰 <b>Jami hisob:</b> {yakuniy_narx:,.0f} UZS\n"
                        f"✅ <b>To'ladi:</b> {tolangan:,.0f} UZS ({t_taf})\n"
                        f"⚠️ <b>Qoldiq qarz:</b> {max(0, qoldiq):,.0f} UZS",
                        xodim_ismi, turi="mijoz", muhim=maxsus_belgi
                    )
                    st.success(f"✅ Mehmon ({mijoz_ism} — {odam_soni} kishi) {xona} ({krovat_yorliq}) ga joylashtirildi! Chiqish: {chiqish_str} {hisob_soat_str} | Jami: {yakuniy_narx:,.0f} UZS")
                    st.rerun()

if hasattr(st, "fragment"):
    @st.fragment
    def render_qabul_formasi(form_key_suffix="main"):
        _render_qabul_inner(form_key_suffix)
else:
    def render_qabul_formasi(form_key_suffix="main"):
        _render_qabul_inner(form_key_suffix)

if hasattr(st, "dialog"):
    @st.dialog("➕ Yangi bron / Mehmonni ro'yxatga olish", width="large")
    def yangi_bron_modal():
        _render_qabul_inner("modal")
else:
    def yangi_bron_modal():
        pass

# ====================================================
# SAHIFA 1: 🏠 BOSHQARUV PANELI
# ====================================================
if sahifa == "🏠 Boshqaruv paneli":
    hafta_kunlari_uz = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
    oy_nomlari_uz = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    bugun_matn = f"Bugun, {hozirgi_uz_vaqt.day}-{oy_nomlari_uz[hozirgi_uz_vaqt.month]}, {hafta_kunlari_uz[hozirgi_uz_vaqt.weekday()]}"

    d_top1, d_top2 = st.columns([3.2, 1.3], gap="medium")
    with d_top1:
        st.markdown(f"<h2 style='margin-bottom: 0px;'>Boshqaruv paneli</h2><p style='margin-top: 4px; margin-bottom: 18px;'>{bugun_matn} &nbsp;|&nbsp; Hisobot davri: <b>{g_davr_nomi}</b></p>", unsafe_allow_html=True)
    with d_top2:
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        if st.button("📲 24 soatlik Svodkani Telegramga yuborish", use_container_width=True):
            kunlik_svodka_shakllantir_va_yubor(xodim_ismi, majburiy=True)
            st.success("✅ Svodka CEO va Egaga yuborildi!")

    df_barcha = kesh_df_ol("SELECT * FROM bronlar ORDER BY id DESC")
    df_savdolar = kesh_df_ol("SELECT * FROM savdolar ORDER BY id DESC")
    df_tolovlar = kesh_df_ol("SELECT * FROM tolovlar_tarixi ORDER BY id DESC")
    df_xarajat = kesh_df_ol("SELECT * FROM xarajatlar ORDER BY id DESC")
    tozalik_map = barcha_xona_tozalik_ol()

    if not df_barcha.empty:
        df_barcha['tolagan_summa'] = df_barcha['tolagan_summa'].fillna(0)
        df_barcha['qoldiq'] = df_barcha['qoldiq'].fillna(0)
        df_barcha['odam_soni'] = df_barcha['odam_soni'].fillna(1).astype(int)

    jami_xonalar_soni = 36
    if not df_barcha.empty:
        faol_mask = df_barcha.apply(lambda r: bron_shu_kunda_faolmi(r['kirish_sanasi'], r['chiqish_sanasi'], r['holat'], bugungi_sana), axis=1)
        faol_df = df_barcha[faol_mask]
    else:
        faol_df = pd.DataFrame()

    band_xonalar_set = set(faol_df['xona'].unique()) if not faol_df.empty else set()
    band_xonalar_soni = len(band_xonalar_set)
    faol_mehmon_odam_soni = int(faol_df['odam_soni'].sum()) if not faol_df.empty else 0
    bandlik_foiz = int(round((band_xonalar_soni / jami_xonalar_soni) * 100))

    tozalash_kerak_soni = sum(1 for x, h in tozalik_map.items() if h == "Tozalash kerak" and x not in band_xonalar_set)
    bosh_toza_xonalar_soni = max(0, jami_xonalar_soni - band_xonalar_soni - tozalash_kerak_soni)

    bugungi_kirishlar_df = df_barcha[(df_barcha['kirish_sanasi'] == bugungi_sana) & (df_barcha['holat'] != 'Chiqib ketgan')].copy() if not df_barcha.empty else pd.DataFrame()
    if not bugungi_kirishlar_df.empty:
        bugungi_kirishlar_df['bron_ustuvor'] = bugungi_kirishlar_df['bron_turi'].apply(lambda x: 1 if x == 'Bron' else 0)
        bugungi_kirishlar_df = bugungi_kirishlar_df.sort_values(by=['bron_ustuvor', 'id'], ascending=[False, False])

    bugun_kirgan_odam_soni = int(bugungi_kirishlar_df['odam_soni'].sum()) if not bugungi_kirishlar_df.empty else 0
    bugun_kirgan_bron_soni = len(bugungi_kirishlar_df)
    hali_kirmagan_odam_soni = int(bugungi_kirishlar_df[bugungi_kirishlar_df['bron_turi'] == 'Bron']['odam_soni'].sum()) if not bugungi_kirishlar_df.empty else 0

    bugungi_chiqishlar_df = df_barcha[df_barcha['chiqish_sanasi'] == bugungi_sana].copy() if not df_barcha.empty else pd.DataFrame()
    if not bugungi_chiqishlar_df.empty:
        bugungi_chiqishlar_df = bugungi_chiqishlar_df.sort_values(by=['id'], ascending=False)

    bugun_chiqish_odam_soni = int(bugungi_chiqishlar_df['odam_soni'].sum()) if not bugungi_chiqishlar_df.empty else 0
    bugun_chiqish_bron_soni = len(bugungi_chiqishlar_df)
    hali_chiqmagan_odam_soni = int(bugungi_chiqishlar_df[bugungi_chiqishlar_df['holat'] != 'Chiqib ketgan']['odam_soni'].sum()) if not bugungi_chiqishlar_df.empty else 0

    bugungi_tushum_sum = float(df_tolovlar[df_tolovlar['sana'] == bugungi_sana]['summa'].fillna(0).sum()) if not df_tolovlar.empty else 0.0

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
            f"<div style='font-size: 13px; color: white; margin-bottom: 8px;'>{bandlik_foiz}% bandlik • Jami {faol_mehmon_odam_soni} kishi</div>"
            f"<div style='background: rgba(255,255,255,0.25); height: 6px; border-radius: 4px; width: 100%;'>"
            f"<div style='background: #ffffff; height: 6px; border-radius: 4px; width: {bandlik_foiz}%;'></div></div></div>",
            unsafe_allow_html=True
        )
    with oc2:
        st.markdown(
            f"<div style='background: {card_bg}; border: 1px solid {card_border}; padding: 20px; border-radius: 16px;'>"
            f"<div style='font-size: 14px; color: {text_sub};'>Bugungi kirishlar (Mehmon soni)</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: {text_main}; margin: 6px 0;'>{bugun_kirgan_odam_soni} <span style='font-size: 18px; font-weight: 600; opacity: 0.8;'>kishi</span></div>"
            f"<div style='font-size: 13px; color: {text_sub};'>{bugun_kirgan_bron_soni} ta bron ({hali_kirmagan_odam_soni} kishi kutilmoqda)</div></div>",
            unsafe_allow_html=True
        )
    with oc3:
        st.markdown(
            f"<div style='background: {card_bg}; border: 1px solid {card_border}; padding: 20px; border-radius: 16px;'>"
            f"<div style='font-size: 14px; color: {text_sub};'>Bugungi chiqishlar (Mehmon soni)</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: {text_main}; margin: 6px 0;'>{bugun_chiqish_odam_soni} <span style='font-size: 18px; font-weight: 600; opacity: 0.8;'>kishi</span></div>"
            f"<div style='font-size: 13px; color: {text_sub};'>{bugun_chiqish_bron_soni} ta bron ({hali_chiqmagan_odam_soni} kishi topshirmagan)</div></div>",
            unsafe_allow_html=True
        )
    with oc4:
        st.markdown(
            f"<div style='background: {card_bg}; border: 1px solid {card_border}; padding: 20px; border-radius: 16px;'>"
            f"<div style='font-size: 14px; color: {text_sub};'>Bugungi kassa kirim</div>"
            f"<div style='font-size: 32px; font-weight: 800; color: {text_main}; margin: 6px 0;'>{bugungi_tushum_sum:,.0f} UZS</div>"
            f"<div style='font-size: 13px; color: {text_sub};'>bugun qabul qilingan jami to'lovlar</div></div>",
            unsafe_allow_html=True
        )

    st.write("")
    with st.container(border=True):
        faol_chiqishlar = bugungi_chiqishlar_df[bugungi_chiqishlar_df['holat'] != 'Chiqib ketgan'] if not bugungi_chiqishlar_df.empty else pd.DataFrame()
        st.markdown(f"##### 🛎️ Bugungi kirish ({bugun_kirgan_odam_soni} kishi / {bugun_kirgan_bron_soni} ta bron) va chiqish ({hali_chiqmagan_odam_soni} kishi) amaliyotlari *(Eng yangilari yuqorida)*")
        if bugungi_kirishlar_df.empty and faol_chiqishlar.empty:
            st.caption("Bugun uchun rejalashtirilgan kirish yoki chiqish amaliyotlari mavjud emas.")
        else:
            row_bg = "#191e30" if is_dark else "#f1f5f9"
            for _, ch_row in faol_chiqishlar.iterrows():
                joy_str = krovat_nomini_ajrat(ch_row.get('xona_turi', ''), ch_row.get('izoh', ''))
                joy_b = f" • 🛏️ {joy_str}" if joy_str else ""
                qarz_b = f" | ⚠️ Qarz: {int(ch_row['qoldiq']):,} UZS" if ch_row['qoldiq'] > 0 else ""
                cc1, cc2 = st.columns([5.5, 1.3])
                cc1.markdown(
                    f"<div style='background:{row_bg}; padding:8px 14px; border-radius:10px; border-left:4px solid #eab308; font-size:13.5px;'>"
                    f"🟡 <b>{ch_row['mijoz']}</b> (<b>{ch_row['odam_soni']} kishi</b>{qarz_b}) &nbsp;—&nbsp; <span style='opacity:0.85;'>Bugun 12:00 da chiqadi • <b>{ch_row['xona']}</b>{joy_b}</span></div>",
                    unsafe_allow_html=True
                )
                if ch_row['qoldiq'] <= 0:
                    if cc2.button("🚪 Chiqarish", key=f"dash_out_{ch_row['mijoz_id']}", use_container_width=True):
                        db.execute("UPDATE bronlar SET holat='Chiqib ketgan' WHERE mijoz_id=?", (ch_row['mijoz_id'],))
                        xona_tozalik_ozgartir(ch_row['xona'], "Tozalash kerak")
                        jurnalga_yozish(ch_row['mijoz_id'], xodim_ismi, "Checkout", f"{ch_row['mijoz']} ({ch_row['xona']}) chiqib ketdi")
                        keshni_tozala()
                        aqlli_tg_xabar("Checkout (Mehmon chiqib ketdi)", f"👤 <b>Mijoz:</b> {ch_row['mijoz']} ({ch_row['odam_soni']} kishi)\n🛏 <b>Bo'shagan xona:</b> {ch_row['xona']}", xodim_ismi, turi="mijoz")
                        st.rerun()
                else:
                    cc2.markdown("<div style='text-align:center; padding:6px; background:rgba(239,68,68,0.2); border-radius:8px; color:#f87171; font-size:12px; font-weight:700;'>⚠️ Qarzdor</div>", unsafe_allow_html=True)

            for _, k_row in bugungi_kirishlar_df.iterrows():
                joy_str = krovat_nomini_ajrat(k_row.get('xona_turi', ''), k_row.get('izoh', ''))
                joy_b = f" • 🛏️ {joy_str}" if joy_str else ""
                soat_k = str(k_row['sana']).split("(")[1].replace(")", "") if "(" in str(k_row.get('sana', '')) else "12:00"
                chiq_k = f" ➡️ Chiqish: {k_row['chiqish_sanasi']} 12:00"
                if k_row.get('bron_turi') == 'Bron':
                    ck1, ck2 = st.columns([5.5, 1.3])
                    ck1.markdown(
                        f"<div style='background:{row_bg}; padding:8px 14px; border-radius:10px; border-left:4px solid #f59e0b; font-size:13.5px;'>"
                        f"🟠 <b>{k_row['mijoz']}</b> (<b>{k_row['odam_soni']} kishi</b>) &nbsp;—&nbsp; <span style='opacity:0.85;'>Bron kelishi ({soat_k}) • <b>{k_row['xona']}</b>{joy_b}{chiq_k}</span></div>",
                        unsafe_allow_html=True
                    )
                    if ck2.button("🔑 Check-in", key=f"dash_in_{k_row['mijoz_id']}", use_container_width=True):
                        db.execute("UPDATE bronlar SET bron_turi='Hozir kirish' WHERE mijoz_id=?", (k_row['mijoz_id'],))
                        jurnalga_yozish(k_row['mijoz_id'], xodim_ismi, "Check-in (Keldi)", f"Bron qilingan {k_row['mijoz']} ({k_row['xona']}) kelib joylashdi")
                        keshni_tozala()
                        aqlli_tg_xabar("Bron Check-in (Mehmon keldi)", f"👤 <b>Mijoz:</b> {k_row['mijoz']} ({k_row['odam_soni']} kishi)\n🛏 <b>Xona:</b> {k_row['xona']}{joy_b}", xodim_ismi, turi="mijoz")
                        st.rerun()
                else:
                    st.markdown(
                        f"<div style='background:{row_bg}; padding:8px 14px; border-radius:10px; border-left:4px solid #22c55e; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center; font-size:13.5px;'>"
                        f"<div>🟢 <b>{k_row['mijoz']}</b> (<b>{k_row['odam_soni']} kishi</b>) &nbsp;—&nbsp; <span style='opacity:0.85;'>Kelish (<b>{soat_k}</b>) • <b>{k_row['xona']}</b>{joy_b}{chiq_k}</span></div>"
                        f"<span style='background:rgba(34,197,94,0.18); color:#4ade80; border:1px solid #22c55e; padding:3px 12px; border-radius:20px; font-size:12px; font-weight:700;'>✔ Joylashgan</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

    with st.container(border=True):
        st.markdown("##### 🛏️ Xonalar fondining joriy holati")
        xh1, xh2, xh3 = st.columns(3, gap="medium")
        xh1.markdown(f"<div style='background:{card_bg}; border:1px solid {card_border}; padding:14px; border-radius:12px;'><div style='font-size:24px; font-weight:800; color:{text_main};'>{band_xonalar_soni} ta <span style='font-size:14px; font-weight:500; opacity:0.8;'>({faol_mehmon_odam_soni} kishi)</span></div><div style='font-size:13px; color:#a78bfa; font-weight:600;'>● Band xonalar</div></div>", unsafe_allow_html=True)
        xh2.markdown(f"<div style='background:{card_bg}; border:1px solid {card_border}; padding:14px; border-radius:12px;'><div style='font-size:24px; font-weight:800; color:{text_main};'>{bosh_toza_xonalar_soni} ta</div><div style='font-size:13px; color:#4ade80; font-weight:600;'>● Bo'sh (Toza)</div></div>", unsafe_allow_html=True)
        xh3.markdown(f"<div style='background:{card_bg}; border:1px solid {card_border}; padding:14px; border-radius:12px;'><div style='font-size:24px; font-weight:800; color:{text_main};'>{tozalash_kerak_soni} ta</div><div style='font-size:13px; color:#f87171; font-weight:600;'>● Tozalash talab etiladi</div></div>", unsafe_allow_html=True)

        st.write("")
        st.markdown("##### 📊 Yaqin 7 kunlik bandlik prognozi")
        kun_qisqa = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
        lbl_col = "#c4b5fd" if is_dark else "#4f46e5"
        bars_html_list = []
        for i in range(7):
            d_obj = hozirgi_uz_vaqt.date() + timedelta(days=i)
            d_str = d_obj.strftime("%Y-%m-%d")
            k_nom = kun_qisqa[d_obj.weekday()]
            if not df_barcha.empty:
                d_mask = df_barcha.apply(lambda r: bron_shu_kunda_faolmi(r['kirish_sanasi'], r['chiqish_sanasi'], r['holat'], d_str), axis=1)
                d_band_df = df_barcha[d_mask]
                d_band_xonalar = len(set(d_band_df['xona'].unique()))
                d_band_odam = int(d_band_df['odam_soni'].sum())
            else:
                d_band_xonalar = 0
                d_band_odam = 0
            d_foiz = int(round((d_band_xonalar / jami_xonalar_soni) * 100))
            bar_color = "#8b5cf6" if i == 0 else "#6366f1"
            bars_html_list.append(
                f"<div style='text-align: center; min-width: 0;'>"
                f"<div style='font-size: 11px; font-weight: 700; color: {lbl_col}; margin-bottom: 6px; white-space: nowrap;'>{d_foiz}% ({d_band_odam}k)</div>"
                f"<div style='height: 95px; width: 28px; max-width: 100%; background: rgba(124,58,237,0.16); border-radius: 8px; margin: 0 auto; display: flex; align-items: flex-end; overflow: hidden;'>"
                f"<div style='width: 100%; height: {max(6, d_foiz)}%; background: {bar_color}; border-radius: 8px;'></div></div>"
                f"<div style='font-size: 11.5px; margin-top: 6px; color: {text_main}; font-weight: 600; white-space: nowrap;'>{k_nom}<br><span style='font-size:10.5px; opacity:0.8;'>{d_obj.strftime('%d.%m')}</span></div></div>"
            )
        st.markdown(
            f"<div style='display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; padding: 10px 4px; overflow-x: auto;'>"
            f"{''.join(bars_html_list)}</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.subheader(f"💰 Moliya va Kassa Hisoboti — {g_davr_nomi}")

    if g_bosh_sana and g_tugash_sana:
        df_tol_filtr = df_tolovlar[(df_tolovlar['sana'] >= g_bosh_sana) & (df_tolovlar['sana'] <= g_tugash_sana)] if not df_tolovlar.empty else pd.DataFrame()
        df_xar_filtr = df_xarajat[(df_xarajat['sana'] >= g_bosh_sana) & (df_xarajat['sana'] <= g_tugash_sana)] if not df_xar_filtr.empty else pd.DataFrame()
    else:
        df_tol_filtr = df_tolovlar
        df_xar_filtr = df_xarajat

    if not df_tol_filtr.empty:
        umumiy_kassa_yotoq = float(df_tol_filtr[df_tol_filtr['manba'] != 'Market Savdo']['summa'].fillna(0).sum())
        umumiy_kassa_market = float(df_tol_filtr[df_tol_filtr['manba'] == 'Market Savdo']['summa'].fillna(0).sum())
    else:
        umumiy_kassa_yotoq = 0.0
        umumiy_kassa_market = 0.0

    jami_xarajatlar = float(df_xar_filtr['summa'].fillna(0).sum()) if not df_xar_filtr.empty else 0.0
    umumiy_qarz = float(df_barcha[(df_barcha['qoldiq'] > 0) & (df_barcha['holat'] != 'Chiqib ketgan')]['qoldiq'].sum()) if not df_barcha.empty else 0.0
    sof_balans = (umumiy_kassa_yotoq + umumiy_kassa_market) - jami_xarajatlar

    c1, c2, c3, c4, c5, c6 = st.columns(6, gap="small")
    with c1: st.markdown(chiroyli_kartochka("👥", "Faol Mehmon", f"{faol_mehmon_odam_soni} kishi ({len(faol_df)} bron)", "#8b5cf6"), unsafe_allow_html=True)
    with c2: st.markdown(chiroyli_kartochka("💰", "Yotoq Kirim", f"{umumiy_kassa_yotoq:,.0f}", "#f59e0b"), unsafe_allow_html=True)
    with c3: st.markdown(chiroyli_kartochka("🛒", "Market Kirim", f"{umumiy_kassa_market:,.0f}", "#10b981"), unsafe_allow_html=True)
    with c4: st.markdown(chiroyli_kartochka("➖", "Xarajatlar", f"{jami_xarajatlar:,.0f}", "#64748b"), unsafe_allow_html=True)
    with c5: st.markdown(chiroyli_kartochka("🏦", "Sof Kassa Balans", f"{sof_balans:,.0f}", "#2563eb"), unsafe_allow_html=True)
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
        boshqa_kirim_jami, boshqa_chiqim_jami = 0.0, 0.0
        
        for tur in barcha_turlar:
            k_s = float(kirim_gr.get(tur, 0))
            c_s = float(chiqim_gr.get(tur, 0))
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

    df_mahsulotlar = kesh_df_ol("SELECT nomi, hajmi, kategoriya, sub_kategoriya, narxi, qoldiq, izoh FROM mahsulotlar WHERE qoldiq <= 5 ORDER BY qoldiq ASC")
    if not df_mahsulotlar.empty:
        with st.expander(f"🚨 DIQQAT: Omborda {len(df_mahsulotlar)} ta mahsulot kam qolgan! (Jadvalni ko'rish uchun bosing)", expanded=False):
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
# ====================================================
elif sahifa == "📅 Timeline & Shaxmatka":
    tl_col1, tl_col2 = st.columns([3.4, 1.1], gap="medium")
    with tl_col1:
        st.markdown("<h2 style='margin: 0; padding-top: 4px;'>📅 Timeline va Xonalar Shaxmatkasi</h2>", unsafe_allow_html=True)
    with tl_col2:
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if hasattr(st, "dialog") and st.session_state.role != "housekeeping":
            if st.button("➕ Yangi bron qo'shish", type="primary", use_container_width=True):
                yangi_bron_modal()

    st.write("")
    with st.container(border=True):
        f_col1, f_col2, f_col3, f_col4 = st.columns([1.8, 1.2, 2.0, 1.1], gap="medium")
        with f_col1:
            tanlangan_katalog = st.radio("📍 Binoning qanoti (Sektor):", ["Barchasi", "Chap tomon", "O'rtadagi", "O'ng tomon"], horizontal=True)
        with f_col2:
            kun_soni_tl = st.radio("🗓️ Davr ko'lami:", [7, 14, 30], index=1, horizontal=True, format_func=lambda x: f"{x} kun")
        with f_col3:
            rejim_tl = st.radio("🖥️ Ko'rinish rejimi:", ["📊 Vizual Timeline", "🔲 Jadval Shaxmatka", "🗺️ Jonli Krovatlar Xaritasi"], horizontal=True)
        with f_col4:
            bosh_sana = st.date_input("📅 Boshlanish sanasi:", toshkent_vaqti().date() - timedelta(days=1))
            arxiv_korsat_tl = st.checkbox("⚪ Arxivni ko'rsatish", value=False)

    sana_royxati = [bosh_sana + timedelta(days=i) for i in range(kun_soni_tl)]
    sana_str_list = [d.strftime("%Y-%m-%d") for d in sana_royxati]
    bosh_sana_str = sana_str_list[0]
    oxirgi_sana_str = (bosh_sana + timedelta(days=kun_soni_tl)).strftime("%Y-%m-%d")
    tozalik_map = barcha_xona_tozalik_ol()
    kun_nom_qisqa = ["DU", "SE", "CH", "PA", "JU", "SH", "YA"]

    if rejim_tl == "🗺️ Jonli Krovatlar Xaritasi":
        render_vizual_krovatlar_xaritasi()
    elif rejim_tl == "📊 Vizual Timeline":
        st.markdown(
            "<div style='display:flex; gap:18px; font-size:13px; margin: 10px 0; flex-wrap:wrap;'>"
            "<span>🟢 <b>Joylashgan (To'langan)</b></span>"
            "<span>🟠 <b>Oldindan bron (Kutilmoqda)</b></span>"
            "<span>🔴 <b>Qarzdorlik mavjud</b></span>"
            "<span>⚪ <b>Chiqib ketgan (Arxiv)</b></span>"
            "<span>💡 <i>Jadval tepasidagi <b>Sana (JU 16, SH 17...)</b> ustiga bossangiz — shu kundagi mehmonlar oynasi ochiladi!</i></span>"
            "</div>",
            unsafe_allow_html=True
        )

        if arxiv_korsat_tl:
            tl_bronlar = kesh_df_ol(
                "SELECT * FROM bronlar WHERE kirish_sanasi < ? AND chiqish_sanasi >= ? ORDER BY kirish_sanasi ASC, id ASC",
                (oxirgi_sana_str, bosh_sana_str)
            )
        else:
            tl_bronlar = kesh_df_ol(
                "SELECT * FROM bronlar WHERE holat != 'Chiqib ketgan' AND kirish_sanasi < ? AND chiqish_sanasi >= ? ORDER BY kirish_sanasi ASC, id ASC",
                (oxirgi_sana_str, bosh_sana_str)
            )

        bg_tbl = "#111420" if is_dark else "#ffffff"
        border_tbl = "#22273b" if is_dark else "#cbd5e1"
        txt_tbl = "#e2e8f0" if is_dark else "#0f172a"
        sec_hdr_bg = "#1e1b4b" if is_dark else "#ede9fe"
        sec_hdr_col = "#c4b5fd" if is_dark else "#4c1d95"
        room_bg = "rgba(124,58,237,0.06)" if is_dark else "#f8fafc"

        html_parts = [
            f"<style>"
            f".ysh-tl-wrap {{ overflow-x: auto; border: 1px solid {border_tbl}; border-radius: 14px; background: {bg_tbl}; padding: 8px; }}"
            f".ysh-wing-details {{ margin-bottom: 10px; border: 1px solid {border_tbl}; border-radius: 10px; overflow: visible; }}"
            f".ysh-wing-summary {{ padding: 10px 14px; font-weight: 800; font-size: 13px; background: {sec_hdr_bg}; color: {sec_hdr_col}; cursor: pointer; user-select: none; border-radius: 9px; list-style: none; display: flex; justify-content: space-between; align-items: center; }}"
            f".ysh-tl-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; color: {txt_tbl}; min-width: 950px; table-layout: fixed; }}"
            f".ysh-tl-table th, .ysh-tl-table td {{ border: 1px solid {border_tbl}; padding: 5px 3px; text-align: center; font-size: 12px; position: relative; vertical-align: middle; height: 38px; }}"
            f".ysh-date-pop {{ position: relative; }}"
            f".ysh-date-pop[open] > .ysh-date-sum {{ background: #ec4899 !important; color: #ffffff !important; box-shadow: 0 0 10px rgba(236,72,153,0.6); }}"
            f".ysh-date-sum {{ list-style: none; cursor: pointer; padding: 3px 2px; border-radius: 6px; user-select: none; transition: all 0.15s; }}"
            f".ysh-date-sum::-webkit-details-marker {{ display: none; }}"
            f".ysh-date-sum:hover {{ background: rgba(139,92,246,0.35); }}"
            f".ysh-date-box {{ position: absolute; top: 46px; left: 50%; transform: translateX(-50%); background: #0f172a; color: #f8fafc !important; border: 2px solid #8b5cf6; border-radius: 12px; padding: 12px 14px; width: 310px; z-index: 3000; box-shadow: 0 16px 35px rgba(0,0,0,0.85); text-align: left; font-weight: 400; font-size: 12px; line-height: 1.5; white-space: normal; }}"
            f".ysh-date-box b, .ysh-date-box div, .ysh-date-box span {{ color: #f8fafc !important; }}"
            f".ysh-tl-room {{ text-align: left !important; padding: 6px 12px !important; font-weight: 700; width: 145px !important; background: {room_bg}; }}"
            f".ysh-bar {{ display: block; padding: 6px 10px; border-radius: 8px; color: #ffffff !important; font-weight: 600; font-size: 12px; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin: 2px 1px; cursor: pointer; position: relative; box-shadow: 0 2px 6px rgba(0,0,0,0.25); }}"
            f".ysh-bar:hover {{ overflow: visible; z-index: 999; }}"
            f".ysh-bar .ysh-tip {{ visibility: hidden; opacity: 0; position: absolute; left: 8px; top: 32px; background: #0f172a; color: #f8fafc !important; border: 1px solid #7c3aed; border-radius: 10px; padding: 10px 14px; width: 265px; z-index: 1000; box-shadow: 0 10px 25px rgba(0,0,0,0.65); font-weight: 400; font-size: 12px; line-height: 1.5; transition: opacity 0.15s; pointer-events: none; white-space: normal; }}"
            f".ysh-bar .ysh-tip b, .ysh-bar .ysh-tip span {{ color: #f8fafc !important; }}"
            f".ysh-bar:hover .ysh-tip {{ visibility: visible; opacity: 1; }}"
            f"</style>"
            f"<div class='ysh-tl-wrap'>"
        ]

        # Sanalar sarlavhasi barcha qanotlar uchun bir marta hisoblanadi (3x tezroq!)
        thead_html = "<thead><tr><th class='ysh-tl-room'>Xona</th>"
        for idx_d, d in enumerate(sana_royxati):
            d_iso = d.strftime("%Y-%m-%d")
            is_today = (d_iso == bugungi_sana)
            th_style = "background: #7c3aed; color: #ffffff !important; border-radius: 6px;" if is_today else ""
            
            if not tl_bronlar.empty:
                kun_mask = tl_bronlar.apply(lambda r: bron_shu_kunda_faolmi(r['kirish_sanasi'], r['chiqish_sanasi'], r['holat'], d_iso), axis=1)
                kun_df = tl_bronlar[kun_mask]
            else:
                kun_df = pd.DataFrame()
            
            band_x_c = len(kun_df['xona'].unique()) if not kun_df.empty else 0
            jami_m_c = int(kun_df['odam_soni'].fillna(1).sum()) if not kun_df.empty else 0
            
            if kun_df.empty:
                ro_html = "<div style='color:#4ade80 !important; margin-top:6px; font-weight:600;'>🟢 Barcha 36 ta xona bo'sh</div>"
            else:
                qatorlar_list = []
                for _, kr in kun_df.iterrows():
                    m_n = str(kr['mijoz']).replace("<", "").replace(">", "").replace("'", "`")
                    j_inf = krovat_nomini_ajrat(kr.get('xona_turi', ''), kr.get('izoh', ''))
                    j_txt = f" ({j_inf})" if j_inf else ""
                    qatorlar_list.append(f"<div style='padding:4px 0; border-bottom:1px solid #1e293b;'>🛏️ <b>{kr['xona']}</b>{j_txt}: {m_n} (<b>{kr['odam_soni']} kishi</b>)</div>")
                ro_html = "<div style='max-height:190px; overflow-y:auto; margin-top:6px;'>" + "".join(qatorlar_list) + "</div>"

            pos_style = "right: 0; left: auto; transform: none;" if idx_d >= len(sana_royxati) - 3 else ("left: 0; transform: none;" if idx_d <= 1 else "")

            thead_html += (
                f"<th style='{th_style}' title='Shu kundagi mehmonlarni ko`rish uchun bosing'>"
                f"<details class='ysh-date-pop' name='ysh_exclusive_date'>"
                f"<summary class='ysh-date-sum'>{kun_nom_qisqa[d.weekday()]}<br><b>{d.day}</b></summary>"
                f"<div class='ysh-date-box' style='{pos_style}'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:5px;'>"
                f"<span style='font-size:13px; font-weight:700; color:#a78bfa !important;'>📅 {d.strftime('%d.%m.%Y')} ({kun_nom_qisqa[d.weekday()]})</span>"
                f"<span style='font-size:11px; opacity:0.75; cursor:pointer;' onclick='this.closest(\"details\").removeAttribute(\"open\")'>✖ Yopish</span>"
                f"</div>"
                f"<div style='margin-top:5px; font-size:11.5px;'>Band xonalar: <b>{band_x_c}/36</b> &nbsp;|&nbsp; Jami mehmon: <b>{jami_m_c} kishi</b></div>"
                f"{ro_html}"
                f"</div></details></th>"
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
                        if ch_s < sana_str_list[0] or k_s > sana_str_list[-1]:
                            continue
                        if k_s == ch_s and ch_s < sana_str_list[0]:
                            continue

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
                                b_col, hol_nom = "#d97706", "Oldindan bron"
                            else:
                                b_col, hol_nom = "#16a34a", "Joylashgan"

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
                                f"<b>Mehmon:</b> {br['odam_soni']} kishi ({br['kunlar']} sutka) • {hol_nom}<br>"
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
        oraliq_bronlar = kesh_df_ol("SELECT xona, xona_turi, kirish_sanasi, chiqish_sanasi, odam_soni, holat FROM bronlar WHERE holat!='Chiqib ketgan' AND kirish_sanasi < ? AND chiqish_sanasi >= ?", (oxirgi_sana_str, bosh_sana_str))
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
                            band_mask = xona_bronlar.apply(lambda r: bron_shu_kunda_faolmi(r['kirish_sanasi'], r['chiqish_sanasi'], r['holat'], d_str), axis=1)
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
    st.subheader("🔍 Xona va yotoq o'rinlari (krovatlar) holatini tekshirish")
    x_tanlov = st.selectbox("Xonani tanlang:", [f"{x} ({XONA_TOMON_MAP[x]})" for x in XONA_TOMON_MAP.keys()])
    xona_nomi = x_tanlov.split(" (")[0].strip()
    umumiy_sigim = xona_sigimini_ol(xona_nomi)
    barcha_xona_m = db.fetchall("SELECT mijoz, jinsi, sana, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh, xona_turi, telefon, kirish_sanasi, holat FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' ORDER BY id DESC", (xona_nomi,))
    bugun_ichidagilar = [m for m in barcha_xona_m if bron_shu_kunda_faolmi(m[10], m[3], m[11], bugungi_sana)]
    if not bugun_ichidagilar:
        st.success(f"🟢 **{xona_nomi} hozir to'liq bo'sh ({umumiy_sigim} kishilik) | Tozalik holati: {tozalik_map.get(xona_nomi, 'Toza')}**")
    else:
        jami_xona_odam = sum(int(m[6] or 1) for m in bugun_ichidagilar)
        st.info(f"🛏️ **{xona_nomi}** ichida hozir jami **{jami_xona_odam} nafar** mehmon yashamoqda ({len(bugun_ichidagilar)} ta bron):")
        for m in bugun_ichidagilar:
            joy_nom = krovat_nomini_ajrat(m[8], m[7])
            joy_badge = f" | 🛏️ **{joy_nom}**" if joy_nom else ""
            vik_m = " 🔒 *(To'liq xona vikup)*" if "To'liq band" in str(m[8] or '') else ""
            tel_m = f" | 📞 {m[9]}" if m[9] else ""
            qarz_matni = f" | ⚠️ Qarz: {m[5]:,.0f} UZS" if m[5] > 0 else ""
            st.markdown(f"- 👤 **{m[0]}** (**{m[6]} kishi** | {m[1]}{joy_badge}{tel_m}{vik_m} | 📥 Kirgan: {m[2]} | 🛫 Chiqish: {m[3]} 12:00){qarz_matni}")

# ====================================================
# SAHIFA 3: 📝 YANGI BRON / QABUL
# ====================================================
elif sahifa == "📝 Yangi Bron / Qabul":
    st.header("📝 Yangi Mehmon Qabul Qilish / Oldindan Bron")
    render_qabul_formasi("page")

# ====================================================
# SAHIFA 4: 👥 BRONLAR VA MEHMONLAR
# ====================================================
elif sahifa == "👥 Bronlar va Mehmonlar":
    st.header("👥 Bronlar va Mehmonlar Boshqaruvi")
    df = kesh_df_ol("SELECT * FROM bronlar ORDER BY id DESC")
    
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
        df = df.copy()
        df['faktik_narx'] = df['faktik_narx'].fillna(0)
        df['tolagan_summa'] = df['tolagan_summa'].fillna(0)
        df['qoldiq'] = df['qoldiq'].fillna(0)
        df['odam_soni'] = df['odam_soni'].fillna(1).astype(int)
        df['izoh'] = df['izoh'].fillna('')
        df['xona_turi'] = df['xona_turi'].fillna('')
        df['kirish_vaqti_korsat'] = df.apply(lambda r: str(r['sana']) if '(' in str(r.get('sana', '')) else f"{r.get('kirish_sanasi', '')} (12:00)", axis=1)
        
        def xona_va_joy_korsat(r):
            x_str = f"{r['xona']} 🔒" if "To'liq band" in str(r.get('xona_turi', '')) else str(r['xona'])
            j_str = krovat_nomini_ajrat(r.get('xona_turi', ''), r.get('izoh', ''))
            return f"{x_str} ({j_str})" if j_str else x_str

        df['xona_korsat'] = df.apply(xona_va_joy_korsat, axis=1)

    if ko_rejim == "📋 Barcha Faol Mehmonlar va Arxiv (Jadval)":
        qidiruv = st.text_input("🔍 Mehmon F.I.O, ID, Xona yoki Izoh bo'yicha tezkor qidiruv:", placeholder="Ism, ID, xona yoki izoh...")
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
            bron_odam_jami = int(bron_df['odam_soni'].sum())
            st.subheader(f"📅 Oldindan Bron qilinganlar ({bron_odam_jami} kishi / {len(bron_df)} ta bron)")
            bron_korsatish = bron_df[['mijoz_id', 'mijoz', 'xona_korsat', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'izoh']].copy()
            bron_korsatish.columns = ["ID", "Mehmon", "Xona va Joy", "Odam", "Sutka", "Jami Summa", "To'langan", "Qoldiq", "Kirish (Sana va Soat)", "Chiqish", "Izoh (To'liq)"]
            for col in ["Jami Summa", "To'langan"]:
                bron_korsatish[col] = bron_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
            bron_korsatish["Qoldiq"] = bron_korsatish["Qoldiq"].apply(format_qoldiq_ustun)
            st.dataframe(bron_korsatish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(bron_korsatish))

        faol_odam_jami = int(faol_df['odam_soni'].sum()) if not faol_df.empty else 0
        st.subheader(f"🟢 Hozirgi (Faol) Mehmonlar ({faol_odam_jami} kishi / {len(faol_df)} ta bron)")
        if not faol_df.empty:
            faol_korsatish = faol_df[['mijoz_id', 'mijoz', 'xona_korsat', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'holat', 'izoh']].copy()
            faol_korsatish['holat'] = faol_df.apply(aqlli_holat_matni, axis=1)
            faol_korsatish['chiqish_sanasi'] = faol_korsatish['chiqish_sanasi'] + ' 12:00'
            faol_korsatish.columns = ["ID", "Mehmon", "Xona va Joy", "Odam", "Sutka", "Jami Summa", "To'langan", "Qoldiq", "Kirish (Sana va Soat)", "Chiqish", "Holat", "Izoh (To'liq)"]
            for col in ["Jami Summa", "To'langan"]:
                faol_korsatish[col] = faol_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
            faol_korsatish["Qoldiq"] = faol_korsatish["Qoldiq"].apply(format_qoldiq_ustun)
            st.dataframe(faol_korsatish.style.apply(rangla_jadval, axis=1), use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(faol_korsatish))
        else:
            st.info("📭 Hozircha hostelda faol mehmonlar yo'q.")

        arxiv_odam_jami = int(arxiv_df['odam_soni'].sum()) if not arxiv_df.empty else 0
        with st.expander(f"🗄️ Arxivdagi (Chiqib ketgan) mehmonlar — Davr: {g_davr_nomi} ({arxiv_odam_jami} kishi / {len(arxiv_df)} ta bron)", expanded=bool(qidiruv and not arxiv_df.empty)):
            if not arxiv_df.empty:
                arx_korsatish = arxiv_df[['mijoz_id', 'mijoz', 'xona_korsat', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'holat', 'izoh']].copy()
                arx_korsatish.columns = ["ID", "Mehmon", "Xona va Joy", "Odam", "Sutka", "Jami Summa", "To'langan", "Kirgan Vaqti", "Chiqib Ketgan Sana", "Holat", "Izoh (To'liq)"]
                for col in ["Jami Summa", "To'langan"]:
                    arx_korsatish[col] = arx_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(arx_korsatish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(arx_korsatish))
            else:
                st.info("Arxivda yozuvlar topilmadi.")

    elif ko_rejim == "🧾 Bron tafsilotlari (Shaxsiy karta, To'lovlar & Kvitansiya)":
        if df.empty:
            st.info("Bazada ma'lumotlar yo'q.")
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
                    st.caption(f"🛏 Xona va Joy: **{f_row['xona_korsat']}** • Mehmon: **{f_row['odam_soni']} kishi** ({f_row['kunlar']} sutka)")

                b_c1, b_c2, b_c3 = st.columns(3, gap="medium")
                b_c1.metric("💰 JAMI HISOB", f"{int(f_row['faktik_narx']):,} UZS")
                b_c2.metric("✅ TO'LANGAN", f"{int(f_row['tolagan_summa']):,} UZS")
                b_c3.metric("⚠️ QARZ", f"{max(0, int(f_row['qoldiq'])):,} UZS")

            with st.container(border=True):
                st.markdown("##### 📝 Mehmonning aloqa va ichki ma'lumotlari")
                with st.form("folio_anketa_form", enter_to_submit=False):
                    m1, m2, m3 = st.columns(3, gap="medium")
                    with m1:
                        p_ism = st.text_input("Mehmon F.I.O (Ismi):", value=str(f_row.get('mijoz') or ''))
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
                        keshni_tozala()
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
                    f"<b>Yashash muddati:</b> {f_row['kunlar']} sutka</p>"
                    f"<hr style='border:1px solid #cbd5e1;'>"
                    f"<p style='color:#0f172a; font-size:15px;'><b>Jami hisoblangan summa:</b> {int(f_row['faktik_narx']):,} UZS<br>"
                    f"<b>To'langan summa:</b> {int(f_row['tolagan_summa']):,} UZS ({f_row.get('tolov_tafsiloti') or 'Naqd'})<br>"
                    f"<b>Qoldiq qarz:</b> {max(0, int(f_row['qoldiq'])):,} UZS</p>"
                    f"<hr style='border:1px solid #cbd5e1;'>"
                    f"<p style='color:#475569; font-size:12px;'>Mas'ul: {xodim_ismi} | Vaqt: {toshkent_vaqti().strftime('%d.%m.%Y %H:%M')}</p></div>",
                    unsafe_allow_html=True
                )

            with st.expander("🛏️ 1. Bandlangan xonalar (Sutkama-sutka yoyilma)", expanded=True):
                try:
                    k_dt = datetime.strptime(str(f_row['kirish_sanasi']), "%Y-%m-%d")
                except Exception:
                    k_dt = toshkent_vaqti()
                kunlik_qatorlar = []
                for k_i in range(int(f_row['kunlar'] or 1)):
                    s_kun = (k_dt + timedelta(days=k_i)).strftime("%d.%m.%Y")
                    kunlik_qatorlar.append({
                        "Sana (Sutka)": s_kun,
                        "Kim uchun bandlangan": f"{f_row['mijoz']} ({f_row['odam_soni']} kishi)",
                        "Xona va Joy": f_row['xona_korsat'],
                        "Narx / Sutka": f"{int(f_row.get('kunlik_narx') or 0):,} UZS"
                    })
                st.dataframe(pd.DataFrame(kunlik_qatorlar), use_container_width=True, hide_index=True)

            df_m_tol = kesh_df_ol("SELECT sana, manba, tolov_tafsiloti, summa, xodim FROM tolovlar_tarixi WHERE mijoz_id=? ORDER BY id DESC", (f_id,))
            df_m_qarz_savdo = kesh_df_ol("SELECT vaqt, tafsilot, xodim FROM audit_log WHERE mijoz_id=? AND harakat='Market qarz' ORDER BY id DESC", (f_id,))

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
            ["💳 Qarzni yopish", "➕ Muddatni cho'zish", "🛏 Xonadan-xonaga ko'chirish", "🚪 Checkout (Xonani bo'shatish / Vozvrat)", "✏️ Mehmon ma'lumotlarini tahrirlash"],
            horizontal=True
        )

        if amal_tanlov == "💳 Qarzni yopish":
            qarzdorlar = df[(df['qoldiq'] > 0) & (df['holat'] != 'Chiqib ketgan')] if not df.empty else pd.DataFrame()
            if not qarzdorlar.empty:
                tanlangan_qarz = st.selectbox("Qarzdor mehmonni tanlang:", qarzdorlar['mijoz_id'] + " - " + qarzdorlar['mijoz'] + " (" + qarzdorlar['xona_korsat'] + " | Qarzi: " + qarzdorlar['qoldiq'].astype(int).astype(str) + " UZS)")
                q_id = tanlangan_qarz.split(" - ")[0]
                q_row = qarzdorlar[qarzdorlar['mijoz_id'] == q_id].iloc[0]
                joriy_qarz_sum = int(q_row['qoldiq'])

                with st.form("qarz_form", enter_to_submit=False):
                    c_q1, c_q2 = st.columns(2, gap="medium")
                    with c_q1:
                        tolov_sum = st.number_input("Qabul qilinayotgan summa (UZS):", min_value=1000, step=5000, value=joriy_qarz_sum)
                        t_shakl = st.selectbox("To'lov shakli", ["Naqd", "Karta", "Onlayn"])
                    with c_q2:
                        t_tafsiloti = st.selectbox("Kassa / To'lov tizimi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
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
                        keshni_tozala()
                        aqlli_tg_xabar("Mehmon qarzi to'landi", f"👤 <b>Mijoz:</b> {q_mijoz_ism}\n💵 <b>To'landi:</b> {tolov_sum:,.0f} UZS ({t_tafsiloti})", xodim_ismi, turi="mijoz")
                        st.success("To'lov muvaffaqiyatli qabul qilindi!")
                        st.rerun()
            else:
                st.info("Hozircha qarzdor mehmonlar yo'q.")

        elif amal_tanlov == "➕ Muddatni cho'zish":
            if not barcha_faol_va_bron.empty:
                with st.form("muddat_form", enter_to_submit=False):
                    mc1, mc2, mc3 = st.columns([2, 1, 1], gap="medium")
                    with mc1:
                        tanlangan_id_chozish = st.selectbox("Mehmonni tanlang:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (" + barcha_faol_va_bron['xona_korsat'] + ")")
                    with mc2:
                        qoshimcha_kun = st.number_input("Qo'shilayotgan sutka soni:", min_value=1, value=1)
                    with mc3:
                        chozish_chegirma = st.number_input("🏷️ Chegirma % (ixtiyoriy):", min_value=0, max_value=100, value=0, step=5)

                    if st.form_submit_button("➕ Yashash muddatini uzaytirish", type="primary", use_container_width=True):
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
                            st.error(f"⚠️ Xatolik: {x_nom} da {eski_chiqish_str} dan {yangi_chiqish_str} gacha bo'sh o'rin yetarli emas (Boshqa bron mavjud, bo'sh o'rin: {bosh_joy} ta)!")
                        else:
                            bazaviy_q_sum = float(mijoz_data['kunlik_narx']) * qoshimcha_kun
                            q_sum = bazaviy_q_sum * ((100.0 - float(chozish_chegirma)) / 100.0) if chozish_chegirma > 0 else bazaviy_q_sum
                            yangi_qoldiq = float(mijoz_data['qoldiq']) + q_sum
                            yangi_holat = "To'langan" if yangi_qoldiq <= 0 else "Qarzdorlik"
                            db.execute("UPDATE bronlar SET kunlar=kunlar+?, qoldiq=?, jami_summa=jami_summa+?, faktik_narx=faktik_narx+?, chiqish_sanasi=?, holat=? WHERE mijoz_id=?", (qoshimcha_kun, yangi_qoldiq, q_sum, q_sum, yangi_chiqish_str, yangi_holat, m_id))
                            jurnalga_yozish(m_id, xodim_ismi, "Muddat cho'zildi", f"+{qoshimcha_kun} sutka ({q_sum:,.0f} UZS)")
                            keshni_tozala()
                            aqlli_tg_xabar("Muddat cho'zildi", f"👤 <b>Mijoz:</b> {mijoz_data['mijoz']}\n➕ <b>Qo'shildi:</b> +{qoshimcha_kun} sutka ({q_sum:,.0f} UZS)\n🛫 <b>Yangi chiqish:</b> {yangi_chiqish_str} 12:00", xodim_ismi, turi="mijoz", muhim=(chozish_chegirma > 0))
                            st.success("Yashash muddati muvaffaqiyatli uzaytirildi!")
                            st.rerun()
            else:
                st.info("Faol mehmonlar mavjud emas.")

        elif amal_tanlov == "🛏 Xonadan-xonaga ko'chirish":
            if not barcha_faol_va_bron.empty:
                with st.form("kochirish_form", enter_to_submit=False):
                    koch_mijoz = st.selectbox("Ko'chiriladigan mehmon:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (Joriy: " + barcha_faol_va_bron['xona_korsat'] + ")")
                    y_xona_toliq = st.selectbox("Yangi xonani tanlang:", BARCHA_XONALAR_ROYXATI)
                    koch_krovat_str = st.text_input("🛏️ Yangi xonadagi yotoq o'rni (masalan: 1-joy yoki 1-joy, 2-joy):", value="1-joy")
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
                            st.error(f"⚠️ {y_xona} sig'imi {y_sigim} kishilik (Mehmon esa {m_odam} kishi)!")
                        elif kerakli > bosh_joy:
                            st.error(f"⚠️ {y_xona} da yetarli bo'sh o'rin yo'q (Bo'sh o'rin: {bosh_joy} ta)!")
                        elif zid_jins:
                            st.error(f"🚻 Xatolik: {y_xona} da hozir **{zid_jins}** mehmon(lar) bor! Umumiy xonaga **{m_jins}** mehmonni ko'chirib bo'lmaydi.")
                        else:
                            baz_tur = "Dvuxspalniy" if y_tomon == "O'rtadagi" else ("2 alohida krovat" if y_sigim == 2 else f"{y_sigim} kishilik")
                            if y_tomon == "O'rtadagi":
                                kr_b = " [🛏️ Dvuxspalniy]"
                            elif koch_toliq_band or m_odam == y_sigim:
                                kr_b = f" [🛏️ Barcha joylar (1-{y_sigim}-joy)]"
                            else:
                                kr_b = f" [🛏️ {koch_krovat_str.strip()}]" if koch_krovat_str.strip() else ""
                            y_xona_turi = f"To'liq band ({baz_tur}){kr_b}" if (koch_toliq_band or y_tomon == "O'rtadagi") else f"{baz_tur}{kr_b}"
                            eski_iz_toza = re.sub(r'\[🛏️ .*?\]', '', str(k_data.get('izoh', '') or '')).strip()
                            yangi_iz_koch = f"{kr_b.strip()} {eski_iz_toza}".strip()
                            db.execute("UPDATE bronlar SET tomon=?, xona=?, xona_turi=?, izoh=? WHERE mijoz_id=?", (y_tomon, y_xona, y_xona_turi, yangi_iz_koch, k_id))
                            xona_tozalik_ozgartir(eski_xona, "Tozalash kerak")
                            jurnalga_yozish(k_id, xodim_ismi, "Xona ko'chirildi", f"{k_data['mijoz']}: {eski_xona} -> {y_xona} ({y_xona_turi})")
                            keshni_tozala()
                            aqlli_tg_xabar("Xona almashtirildi", f"👤 <b>Mijoz:</b> {k_data['mijoz']}\n🔄 <b>Ko'chirildi:</b> {eski_xona} ➡️ {y_xona} ({y_xona_turi})", xodim_ismi, turi="mijoz")
                            st.success(f"Mehmon {y_xona} ga ko'chirildi! ({eski_xona} tozalash ro'yxatiga o'tkazildi)")
                            st.rerun()
            else:
                st.info("Ko'chirish uchun faol mehmon yo'q.")

        elif amal_tanlov == "🚪 Checkout (Xonani bo'shatish / Vozvrat)":
            if not barcha_faol_va_bron.empty:
                chiq_tanlov = st.selectbox("Xonani topshirayotgan mehmonni tanlang:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (" + barcha_faol_va_bron['xona_korsat'] + " | Chiqish: " + barcha_faol_va_bron['chiqish_sanasi'] + ")")
                c_id = chiq_tanlov.split(" - ")[0]
                c_row = barcha_faol_va_bron[barcha_faol_va_bron['mijoz_id'] == c_id].iloc[0]

                reja_kun = int(c_row.get('kunlar', 1) or 1)
                eski_faktik = float(c_row.get('faktik_narx', 0) or 0)
                eski_tol = float(c_row.get('tolagan_summa', 0) or 0)
                eski_qar = float(c_row.get('qoldiq', 0) or 0)
                kun_stavka = float(c_row.get('kunlik_narx', 0) or (eski_faktik / max(1, reja_kun)))

                st.info(
                    f"👤 **Mehmon:** {c_row['mijoz']} ({c_row['odam_soni']} kishi) | "
                    f"🌙 **Bron qilingan:** {reja_kun} sutka | "
                    f"💰 **Jami hisob:** {eski_faktik:,.0f} UZS | "
                    f"✅ **To'lagan:** {eski_tol:,.0f} UZS | "
                    f"⚠️ **Qoldiq qarz:** {max(0.0, eski_qar):,.0f} UZS"
                )

                erta_ketish = st.checkbox("🧮 Mijoz muddatidan oldin ketyaptimi? (Haqiqiy yashagan kuniga qarab Vozvratni avtomatik hisoblash)")
                if erta_ketish:
                    ec1, ec2 = st.columns(2, gap="medium")
                    with ec1:
                        haqiqiy_kun = st.number_input("🌙 Haqiqiy yashagan sutkasi:", min_value=0, max_value=reja_kun, value=max(1, reja_kun - 1))
                    with ec2:
                        stavka_in = st.number_input("💵 1 sutkalik hisob stavkasi (UZS):", min_value=0, value=int(kun_stavka), step=5000)
                    yangi_hisob_sum = float(haqiqiy_kun * stavka_in)
                    avto_vozvrat_sum = int(max(0.0, eski_tol - yangi_hisob_sum))
                    st.success(f"📊 **Qayta hisob:** {haqiqiy_kun} sutka × {stavka_in:,.0f} = **{yangi_hisob_sum:,.0f} UZS** ➡️ Mijozga qaytariladigan **Vozvrat: {avto_vozvrat_sum:,.0f} UZS**")
                else:
                    haqiqiy_kun = reja_kun
                    yangi_hisob_sum = eski_faktik
                    avto_vozvrat_sum = 0

                with st.form("admin_checkout_form", enter_to_submit=False):
                    col_v1, col_v2 = st.columns(2, gap="medium")
                    with col_v1:
                        vozvrat_sum = st.number_input("⏪ Mehmonga qaytarilgan summa / Vozvrat (0 = qaytarilmadi):", min_value=0, max_value=int(eski_tol), value=avto_vozvrat_sum, step=5000)
                    with col_v2:
                        vozvrat_kassa = st.selectbox("Qaysi kassadan qaytarildi? (Agar vozvrat bo'lsa):", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                    vozvrat_izoh = st.text_input("Checkout / Vozvrat izohi (ixtiyoriy):", placeholder="Masalan: 10 kun o'rniga 5 kun yashadi, 5 kunlik puli qaytarildi...")

                    if st.form_submit_button("🚪 Kalitlarni topshirish (Checkout va Arxivlash)", type="primary", use_container_width=True):
                        qolgan_qarz_check = (yangi_hisob_sum - (eski_tol - vozvrat_sum)) if erta_ketish else c_row['qoldiq']
                        if qolgan_qarz_check > 0 and vozvrat_sum == 0:
                            st.error(f"⚠️ Mehmonda {qolgan_qarz_check:,.0f} UZS qarz bor! Avval «💳 Qarzni yopish» bo'limidan qarzni qabul qiling (yoki CEO panelidan qayta hisoblang).")
                        else:
                            yangi_tolagan = eski_tol - vozvrat_sum
                            yangi_faktik = yangi_tolagan if (vozvrat_sum > 0 or erta_ketish) else eski_faktik
                            eski_izoh = str(c_row.get('izoh', '') or '')
                            qo_izoh = f"{eski_izoh} | Checkout ({haqiqiy_kun} sutka): {vozvrat_izoh.strip()}".strip(" |") if (vozvrat_izoh.strip() or erta_ketish) else eski_izoh

                            db.execute(
                                "UPDATE bronlar SET holat='Chiqib ketgan', kunlar=?, muddat=?, chiqish_sanasi=?, tolagan_summa=?, faktik_narx=?, jami_summa=?, qoldiq=0, izoh=? WHERE mijoz_id=?",
                                (haqiqiy_kun, f"{haqiqiy_kun} sutka", bugungi_sana, yangi_tolagan, yangi_faktik, yangi_faktik, qo_izoh, c_id)
                            )
                            xona_tozalik_ozgartir(c_row['xona'], "Tozalash kerak")
                            if vozvrat_sum > 0:
                                db.execute(
                                    "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                    (bugungi_sana, c_id, c_row['mijoz'], "Vozvrat (Pul qaytarish)", -vozvrat_sum, vozvrat_kassa, vozvrat_kassa, xodim_ismi)
                                )
                                jurnalga_yozish(c_id, xodim_ismi, "Checkout + Vozvrat", f"Mijoz ({c_row['mijoz']}) {c_row['xona']} ni bo'shatdi ({haqiqiy_kun} sutka). Qaytarildi: -{vozvrat_sum:,.0f} UZS ({vozvrat_kassa})")
                                keshni_tozala()
                                aqlli_tg_xabar(
                                    "Checkout va Pul qaytarish (Vozvrat)",
                                    f"👤 <b>Mijoz:</b> {c_row['mijoz']} ({c_row['odam_soni']} kishi)\n"
                                    f"🛏 <b>Bo'shagan xona:</b> {c_row['xona']} (🧹 Tozalashga berildi)\n"
                                    f"🌙 <b>Yashagan muddati:</b> {haqiqiy_kun} sutka (Reja: {reja_kun} sutka)\n"
                                    f"⏪ <b>Qaytarilgan summa (Vozvrat):</b> -{vozvrat_sum:,.0f} UZS ({vozvrat_kassa})\n"
                                    f"💰 <b>Qolgan sof to'lov:</b> {yangi_tolagan:,.0f} UZS",
                                    xodim_ismi, turi="mijoz", muhim=True
                                )
                            else:
                                jurnalga_yozish(c_id, xodim_ismi, "Checkout", f"Mijoz ({c_row['mijoz']}) {c_row['xona']} ni topshirdi va arxivga o'tkazildi")
                                keshni_tozala()
                                aqlli_tg_xabar(
                                    "Checkout (Mijoz chiqib ketdi)",
                                    f"👤 <b>Mijoz:</b> {c_row['mijoz']} ({c_row['odam_soni']} kishi)\n🛏 <b>Bo'shagan xona:</b> {c_row['xona']} (🧹 Tozalashga berildi)",
                                    xodim_ismi, turi="mijoz"
                                )
                            st.success(f"✅ {c_row['mijoz']} ({c_row['xona']}) chiqarildi va xona «🧹 Tozalash kerak» ro'yxatiga o'tkazildi!")
                            st.rerun()
            else:
                st.info("Hozircha faol mehmonlar yo'q.")

        elif amal_tanlov == "✏️ Mehmon ma'lumotlarini tahrirlash":
            if not df.empty:
                tahrir_tanlov = st.selectbox("Tahrirlanadigan mehmonni tanlang:", df['mijoz_id'] + " - " + df['mijoz'] + " (" + df['xona_korsat'] + " | " + df['holat'] + ")")
                t_id = tahrir_tanlov.split(" - ")[0]
                t_row = df[df['mijoz_id'] == t_id].iloc[0]

                with st.form("tahrirlash_form", enter_to_submit=False):
                    st.caption(f"🆔 Bron ID: **{t_id}** ma'lumotlarini tahrirlash")
                    e1, e2, e3 = st.columns(3, gap="medium")
                    with e1:
                        y_ism = st.text_input("Mehmon F.I.O / Telefon:", value=str(t_row['mijoz']))
                        toifa_list = ["O'zbekiston fuqarosi", "Chet el fuqarosi", "Talaba (Student)"]
                        joriy_toifa = str(t_row.get('toifa') or "O'zbekiston fuqarosi")
                        y_toifa = st.selectbox("🪪 Tarif toifasi:", toifa_list, index=toifa_list.index(joriy_toifa) if joriy_toifa in toifa_list else 0)
                        joriy_xona_idx = 0
                        for idx, x_str in enumerate(BARCHA_XONALAR_ROYXATI):
                            if f"| {t_row['xona']} (" in x_str:
                                joriy_xona_idx = idx
                                break
                        y_xona_str = st.selectbox("Xona:", BARCHA_XONALAR_ROYXATI, index=joriy_xona_idx)
                        eski_krovat = krovat_nomini_ajrat(t_row.get('xona_turi', ''), t_row.get('izoh', '')) or "1-joy"
                        y_krovat_str = st.text_input("🛏️ Yotoq o'rni (masalan: 1-joy yoki 1-joy, 2-joy):", value=eski_krovat)
                        y_odam = st.number_input("Mehmonlar soni:", min_value=1, max_value=10, value=int(t_row['odam_soni'] or 1))
                        eski_vikup = "To'liq band" in str(t_row.get('xona_turi', '') or '')
                        y_vikup = st.checkbox("🔒 Xona to'liq band (Vikup)", value=eski_vikup)
                    with e2:
                        try:
                            def_kirish = datetime.strptime(str(t_row['kirish_sanasi']), "%Y-%m-%d").date()
                        except Exception:
                            def_kirish = toshkent_vaqti().date()
                        try:
                            def_chiqish = datetime.strptime(str(t_row['chiqish_sanasi']), "%Y-%m-%d").date()
                        except Exception:
                            def_chiqish = def_kirish + timedelta(days=int(t_row['kunlar'] or 1))

                        y_kirish = st.date_input("📅 Kirish sanasi:", value=def_kirish)
                        eski_soat = str(t_row['sana']).split("(")[1].replace(")", "") if "(" in str(t_row.get('sana', '')) else toshkent_vaqti().strftime("%H:%M")
                        y_soat_obj = st.time_input("🕒 Kirish soati:", value=soat_matndan_time_ol(eski_soat), step=60)
                        y_kunlar = st.number_input("🌙 Yashash sutkasi:", min_value=1, max_value=365, value=int(t_row['kunlar'] or 1))
                        avto_sana_mosla = st.checkbox("📅 Chiqish sanasini sutka soniga qarab avtomatik hisoblash", value=True)
                        y_chiqish_date = st.date_input("🛫 Yoki chiqish sanasini qo'lda tanlang (12:00 da):", value=def_chiqish)
                    with e3:
                        avto_tarif_qayta_hisob = st.checkbox("🔄 Standart tarif bo'yicha Jami summani avtomatik qayta hisoblash (Xato hisobni tuzatish)", value=False)
                        y_faktik = st.number_input("💰 Jami hisoblangan summa (UZS) (Qo'lda):", min_value=0, value=int(t_row['faktik_narx'] or 0), step=10000)
                        y_tahrir_chegirma = st.number_input("🏷️ Jami summadan chegirma % (0 = o'zgarmaydi):", min_value=0, max_value=100, value=0, step=5)
                        eski_tolagan = int(t_row['tolagan_summa'] or 0)
                        y_tolagan = st.number_input("💵 Jami to'lagan summasi (UZS) (Kassa):", min_value=0, value=eski_tolagan, step=10000)
                        y_holat = st.selectbox("Holati:", ["To'langan", "Qarzdorlik", "Chiqib ketgan"], index=0 if t_row['holat']=="To'langan" else (2 if t_row['holat']=="Chiqib ketgan" else 1))
                        y_izoh = st.text_input("Izoh:", value=str(t_row['izoh'] or ''))

                    if st.form_submit_button("💾 O'zgarishlarni Saqlash", type="primary", use_container_width=True):
                        y_tomon = y_xona_str.split(" | ")[0]
                        y_xona = y_xona_str.split(" | ")[1].split(" (")[0].strip()
                        y_sigim = XONALAR[y_tomon][y_xona][0]
                        baz_tur = "Dvuxspalniy" if y_tomon == "O'rtadagi" else ("2 alohida krovat" if y_sigim == 2 else f"{y_sigim} kishilik")
                        if y_tomon == "O'rtadagi":
                            kr_tag = " [🛏️ Dvuxspalniy]"
                        elif y_vikup or y_odam == y_sigim:
                            kr_tag = f" [🛏️ Barcha joylar (1-{y_sigim}-joy)]"
                        else:
                            kr_tag = f" [🛏️ {y_krovat_str.strip()}]" if y_krovat_str.strip() else ""
                        y_xona_turi = f"To'liq band ({baz_tur}){kr_tag}" if (y_vikup or y_tomon == "O'rtadagi") else f"{baz_tur}{kr_tag}"
                        y_kirish_str = y_kirish.strftime("%Y-%m-%d")
                        y_soat_str = y_soat_obj.strftime("%H:%M") if y_soat_obj else eski_soat
                        y_sana_vaqt_toliq = f"{y_kirish_str} ({y_soat_str})"

                        if avto_sana_mosla:
                            y_chiqish_str = (y_kirish + timedelta(days=y_kunlar)).strftime("%Y-%m-%d")
                        else:
                            y_chiqish_str = y_chiqish_date.strftime("%Y-%m-%d")

                        if avto_tarif_qayta_hisob:
                            y_kunlik_st, hisob_jami, _ = dinamik_narx_hisobla(
                                y_tomon, y_xona, y_toifa, y_odam, y_kunlar,
                                toliq_xona=y_vikup, maxsus_chegirma_foiz=y_tahrir_chegirma
                            )
                            y_faktik = int(round(hisob_jami))
                        else:
                            if y_tahrir_chegirma > 0:
                                y_faktik = int(round(y_faktik * ((100.0 - float(y_tahrir_chegirma)) / 100.0)))
                            y_kunlik_st = round(y_faktik / max(1, y_kunlar))

                        y_qoldiq = y_faktik - y_tolagan
                        if y_holat != "Chiqib ketgan":
                            y_holat = "To'langan" if y_qoldiq <= 0 else "Qarzdorlik"
                        else:
                            y_qoldiq = 0

                        toza_izoh = re.sub(r'\[🛏️ .*?\]', '', y_izoh).strip()
                        yak_izoh = f"{kr_tag.strip()} {toza_izoh}".strip()

                        db.execute("""
                            UPDATE bronlar SET 
                                mijoz=?, toifa=?, tomon=?, xona=?, xona_turi=?, odam_soni=?, sana=?, kirish_sanasi=?, chiqish_sanasi=?,
                                kunlar=?, muddat=?, kunlik_narx=?, faktik_narx=?, jami_summa=?, tolagan_summa=?, qoldiq=?, holat=?, izoh=?
                            WHERE mijoz_id=?
                        """, (
                            y_ism.strip(), y_toifa, y_tomon, y_xona, y_xona_turi, y_odam, y_sana_vaqt_toliq, y_kirish_str, y_chiqish_str,
                            y_kunlar, f"{y_kunlar} sutka", y_kunlik_st, y_faktik, y_faktik, y_tolagan, y_qoldiq, y_holat, yak_izoh, t_id
                        ))
                        
                        farq_tolov = y_tolagan - eski_tolagan
                        if farq_tolov != 0:
                            t_taf_eski = str(t_row.get('tolov_tafsiloti', 'Naqd') or 'Naqd')
                            t_shakl_eski = str(t_row.get('tolov_turi', 'Naqd') or 'Naqd')
                            manba_nom = "Vozvrat (Tahrirlash)" if farq_tolov < 0 else "Tahrirlash (Kassa tuzatish)"
                            db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                       (bugungi_sana, t_id, y_ism.strip(), manba_nom, farq_tolov, t_shakl_eski, t_taf_eski, xodim_ismi))

                        jurnalga_yozish(t_id, xodim_ismi, "Mijoz tahrirlandi", f"Ism: {y_ism} ({y_odam} kishi | {y_toifa}), Xona: {y_xona} ({y_xona_turi}), Sutka: {y_kunlar}, Jami: {y_faktik:,.0f}, To'lagan: {y_tolagan:,.0f}")
                        keshni_tozala()
                        aqlli_tg_xabar(
                            "Mijoz ma'lumotlari tahrirlandi",
                            f"🆔 <b>ID:</b> {t_id}\n"
                            f"👤 <b>Mijoz:</b> {y_ism} ({y_odam} kishi | {y_toifa} | {y_xona})\n"
                            f"🕒 <b>Kirish:</b> {y_sana_vaqt_toliq} ➡️ <b>Chiqish:</b> {y_chiqish_str} 12:00 ({y_kunlar} sutka)\n"
                            f"💰 <b>Yangi jami:</b> {y_faktik:,.0f} UZS | <b>To'lagan:</b> {y_tolagan:,.0f} UZS | <b>Qoldiq:</b> {max(0, y_qoldiq):,.0f} UZS",
                            xodim_ismi, turi="mijoz", muhim=True
                        )
                        st.success("✅ Mehmon ma'lumotlari, hisob-kitob va kassa balansi muvaffaqiyatli yangilandi!")
                        st.rerun()

# ====================================================
# SAHIFA 5: 🧹 XONA TOZALASH
# ====================================================
elif sahifa == "🧹 Xona tozalash":
    st.header("🧹 Xona tozalash va Krovatlar Joylashuvi (Housekeeping)")
    rejim_toza = st.radio(
        "Ko'rinishni tanlang:",
        ["🧹 Tozalik holatini boshqarish (Tezkor tugmalar)", "🗺️ Xonalar va Krovatlar (Yotoq o'rinlari) Xaritasi"],
        horizontal=True
    )
    qidir_x = st.text_input("🔍 Xona raqami bo'yicha qidirish:", placeholder="Masalan: 15-xona...")

    if rejim_toza == "🗺️ Xonalar va Krovatlar (Yotoq o'rinlari) Xaritasi":
        render_vizual_krovatlar_xaritasi(qidir_x)
    else:
        st.caption("👆 Xonalarni tanlab «Toza» yoki «Tozalash kerak» holatiga o'tkazing. Mehmon chiqib ketgan xona avtomatik ravishda «Tozalash kerak» blokiga tushadi.")
        tozalik_map = barcha_xona_tozalik_ol()
        df_barcha_x = kesh_df_ol("SELECT xona, kirish_sanasi, chiqish_sanasi, holat FROM bronlar WHERE holat!='Chiqib ketgan'")
        if not df_barcha_x.empty:
            faol_x_mask = df_barcha_x.apply(lambda r: bron_shu_kunda_faolmi(r['kirish_sanasi'], r['chiqish_sanasi'], r['holat'], bugungi_sana), axis=1)
            band_xonalar_set = set(df_barcha_x[faol_x_mask]['xona'].unique())
        else:
            band_xonalar_set = set()

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
            th1.markdown(f"##### 🔴 Tozalash talab etiladigan xonalar `{len(tozalash_kerak_list)}`")
            if tozalash_kerak_list:
                if th2.button("✔️ Barchasini tozalangan deb belgilash", use_container_width=True):
                    for x_n, _ in tozalash_kerak_list:
                        xona_tozalik_ozgartir(x_n, "Toza")
                    jurnalga_yozish("Housekeeping", xodim_ismi, "Xonalar tozalandi", f"Jami {len(tozalash_kerak_list)} ta xona toza deb belgilandi")
                    st.rerun()

                cols_tk = st.columns(6, gap="small")
                for idx, (x_n, t_n) in enumerate(tozalash_kerak_list):
                    with cols_tk[idx % 6]:
                        st.markdown(f"<div style='border:2px solid #ef4444; background:rgba(239,68,68,0.12); padding:12px; border-radius:12px; text-align:center; margin-bottom:6px;'><b>{x_n}</b><br><span style='font-size:12px; opacity:0.8;'>{t_n}</span></div>", unsafe_allow_html=True)
                        if st.button("✨ Tozalandi", key=f"clean_{x_n}", use_container_width=True):
                            xona_tozalik_ozgartir(x_n, "Toza")
                            jurnalga_yozish("Housekeeping", xodim_ismi, "Xona tozalandi", f"{x_n} toza holatga o'tkazildi")
                            st.rerun()
            else:
                st.success("🎉 Barcha xonalar toza! Tozalash talab etiladigan xona yo'q.")

        st.write("")
        with st.container(border=True):
            st.markdown(f"##### 🟢 Bo'sh va toza xonalar `{len(bosh_toza_list)}`")
            if bosh_toza_list:
                cols_bt = st.columns(6, gap="small")
                for idx, (x_n, t_n) in enumerate(bosh_toza_list):
                    with cols_bt[idx % 6]:
                        st.markdown(f"<div style='border:1px solid #334155; background:rgba(34,197,94,0.08); padding:12px; border-radius:12px; text-align:center; margin-bottom:6px;'><b>{x_n}</b><br><span style='font-size:12px; opacity:0.8;'>{t_n}</span></div>", unsafe_allow_html=True)
                        if st.button("🧹 Tozalashga berish", key=f"dirty_{x_n}", use_container_width=True):
                            xona_tozalik_ozgartir(x_n, "Tozalash kerak")
                            st.rerun()
            else:
                st.info("Bo'sh xonalar yo'q.")

        st.write("")
        with st.expander(f"🟣 Hozir mehmon yashayotgan band xonalar ({len(band_list)} ta)", expanded=True):
            if band_list:
                cols_bd = st.columns(6, gap="small")
                for idx, (x_n, t_n) in enumerate(band_list):
                    with cols_bd[idx % 6]:
                        st.markdown(f"<div style='border:1px solid #7c3aed; background:rgba(124,58,237,0.1); padding:10px; border-radius:10px; text-align:center; margin-bottom:6px;'><b>{x_n}</b><br><span style='font-size:11px; opacity:0.8;'>{t_n}</span></div>", unsafe_allow_html=True)
                        if st.button("🧹 Tozalashga berish", key=f"dirty_b_{x_n}", use_container_width=True):
                            xona_tozalik_ozgartir(x_n, "Tozalash kerak")
                            st.rerun()

# ====================================================
# SAHIFA 6: 🛒 KASSA (POS MARKET)
# ====================================================
elif sahifa == "🛒 Kassa (POS Market)":
    st.header("🛒 Kassa (POS Mini-Market)")
    market_tanlov = st.radio("Bo'limni tanlang:", ["🛒 Savdo oynasi (Kassa)", "📊 Savdolar tarixi"], horizontal=True)
    st.markdown("---")
    
    if market_tanlov == "🛒 Savdo oynasi (Kassa)":
        mahsulotlar = kesh_df_ol("SELECT * FROM mahsulotlar WHERE qoldiq > 0")
        if mahsulotlar.empty:
            st.warning("⚠️ Omborda sotuv uchun mahsulot qolmagan.")
        else:
            mahsulotlar = mahsulotlar.copy()
            mahsulotlar['Toliq_Nomi'] = mahsulotlar.apply(
                lambda r: f"{r['nomi']} ({r['hajmi']}) — {int(r['narxi']):,} UZS [Qoldi: {r['qoldiq']} ta]" if r['hajmi'] else f"{r['nomi']} — {int(r['narxi']):,} UZS [Qoldi: {r['qoldiq']} ta]",
                axis=1
            )
            faol_bronlar = kesh_df_ol("SELECT mijoz_id, mijoz, xona FROM bronlar WHERE holat != 'Chiqib ketgan'")
            mijoz_variantlar = ["💵 Darhol To'lov (Umumiy xaridor)"]
            if not faol_bronlar.empty:
                mijoz_variantlar += (faol_bronlar['mijoz'] + " (" + faol_bronlar['xona'] + ") - ID: " + faol_bronlar['mijoz_id']).tolist()

            with st.form("market_sotuv_form", clear_on_submit=True, enter_to_submit=False):
                col_m1, col_m2 = st.columns(2, gap="medium")
                with col_m1:
                    tanlangan_tovar_label = st.selectbox("1. Mahsulotni tanlang:", mahsulotlar['Toliq_Nomi'].tolist())
                    miqdor = st.number_input("2. Sotilayotgan miqdori (dona):", min_value=1, value=1, step=1)
                with col_m2:
                    kim_olayapti = st.selectbox("3. Xaridor (Darhol to'lov yoki Xona hisobiga):", mijoz_variantlar)
                    m_tafsiloti = st.selectbox("4. To'lov usuli (Darhol to'lov bo'lsa):", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                    m_boshqa_izoh = st.text_input("Agar «Boshqa» bo'lsa, to'lov tizimi nomini yozing:", placeholder="Ixtiyoriy...")
                
                if st.form_submit_button("🛒 SOTUVNI TASDIQLASH", type="primary", use_container_width=True):
                    tanlangan_qator = mahsulotlar[mahsulotlar['Toliq_Nomi'] == tanlangan_tovar_label].iloc[0]
                    maks_qoldiq = int(tanlangan_qator['qoldiq'])
                    if miqdor > maks_qoldiq:
                        st.error(f"⚠️ Omborda faqat {maks_qoldiq} ta mavjud! Siz {miqdor} ta kiritdingiz.")
                    else:
                        tovar_id = int(tanlangan_qator['id'])
                        tovar_nom_qisqa = f"{tanlangan_qator['nomi']} ({tanlangan_qator['hajmi']})" if tanlangan_qator['hajmi'] else tanlangan_qator['nomi']
                        tovar_narxi = float(tanlangan_qator['narxi'])
                        tovar_tannarxi = float(tanlangan_qator.get('tannarx', 0) or 0)
                        jami_sum = miqdor * tovar_narxi
                        sof_foyda_sum = miqdor * (tovar_narxi - tovar_tannarxi)
                        yangi_qoldiq_t = maks_qoldiq - miqdor

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
                        
                        keshni_tozala()
                        aqlli_tg_xabar(
                            "Market Savdosi (POS)",
                            f"🛍 <b>Mahsulot:</b> {tovar_nom_qisqa} ({miqdor} dona)\n"
                            f"👤 <b>Xaridor:</b> {xaridor_nomi}\n"
                            f"💵 <b>Summa:</b> {jami_sum:,.0f} UZS ({m_tafsiloti})\n"
                            f"📦 <b>Skladda qoldi:</b> {yangi_qoldiq_t} dona",
                            xodim_ismi, turi="moliya"
                        )
                        st.success(f"✅ {miqdor} ta {tovar_nom_qisqa} ({jami_sum:,.0f} UZS) sotildi!")
                        st.rerun()

    else:
        st.info(f"📅 Ko'rsatilayotgan davr: **{g_davr_nomi}**")
        if g_bosh_sana and g_tugash_sana:
            df_savdo = kesh_df_ol("SELECT * FROM savdolar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (g_bosh_sana, g_tugash_sana))
        else:
            df_savdo = kesh_df_ol("SELECT * FROM savdolar ORDER BY id DESC")

        if not df_savdo.empty:
            jami_m_sum = df_savdo['jami_summa'].fillna(0).sum()
            jami_m_dona = int(df_savdo['miqdor'].fillna(1).sum())
            st.markdown(f"**Jami savdo aylanmasi ({len(df_savdo)} ta xarid / {jami_m_dona} dona tovar):** `{jami_m_sum:,.0f} UZS`")
            df_savdo_korsatish = df_savdo[['sana', 'mahsulot_nomi', 'xaridor', 'miqdor', 'jami_summa', 'tolov_tafsiloti', 'xodim']].copy()
            df_savdo_korsatish.columns = ["Sana", "Mahsulot", "Xaridor", "Miqdor", "Jami Summa", "To'lov Turi", "Mas'ul Xodim"]
            df_savdo_korsatish['Jami Summa'] = df_savdo_korsatish['Jami Summa'].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_savdo_korsatish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_savdo_korsatish))
        else:
            st.info(f"Tanlangan davrda ({g_davr_nomi}) savdo amaliyotlari qayd etilmagan.")

# ====================================================
# SAHIFA 7: 📦 XIZMATLAR VA SKLAD
# ====================================================
elif sahifa == "📦 Xizmatlar va Sklad":
    st.header("📦 Xizmatlar, Do'kon va Sklad Boshqaruvi")
    ombor_tanlov = st.radio("Bo'limni tanlang:", ["📋 Mahsulotlar qoldig'i (Ro'yxat)", "➕ Yangi tovar kirim qilish", "✏️ Tovarni tahrirlash / O'chirish"], horizontal=True)
    st.markdown("---")
    
    if ombor_tanlov == "➕ Yangi tovar kirim qilish":
        kat_nomi = st.radio(
            "📂 1. Mahsulot kategoriyasini tanlang:",
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
                maxsus_hajm = st.text_input("✏️ Yoki maxsus o'lcham kiriting (ixtiyoriy):", placeholder="Masalan: 0.33 L, 450 ml...")
            
            with c2:
                tov_tannarx = st.number_input("5. Xarid narxi / Tannarx (UZS):", min_value=0, value=5000, step=500)
                tov_narxi = st.number_input("6. Sotuv narxi (UZS):", min_value=1000, value=10000, step=1000)
                tov_soni = st.number_input("7. Kirim miqdori (dona):", min_value=1, value=10, step=1)
            
            if st.form_submit_button("➕ Omborga Kirim Qilish", type="primary", use_container_width=True):
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

                    keshni_tozala()
                    aqlli_tg_xabar(
                        "Skladga tovar kirim qilindi",
                        f"📦 <b>Mahsulot:</b> {t_nom} ({t_hajm or 'Standart'})\n"
                        f"➕ <b>Kirim soni:</b> +{tov_soni} dona\n"
                        f"💰 <b>Tannarx / Sotuv:</b> {tov_tannarx:,.0f} / {tov_narxi:,.0f} UZS",
                        xodim_ismi, turi="moliya"
                    )
                    st.rerun()

    elif ombor_tanlov == "✏️ Tovarni tahrirlash / O'chirish":
        df_m_edit = kesh_df_ol("SELECT * FROM mahsulotlar ORDER BY id DESC")
        if not df_m_edit.empty:
            df_m_edit = df_m_edit.copy()
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
                    keshni_tozala()
                    aqlli_tg_xabar("Sklad tovari tahrirlandi", f"📦 <b>Tovar:</b> {y_m_nomi} ({y_m_hajm})\n🔢 <b>Yangi qoldiq:</b> {y_m_qoldiq} dona | <b>Narx:</b> {y_m_narx:,.0f} UZS", xodim_ismi, turi="moliya", muhim=True)
                    st.success("✅ Tovar ma'lumotlari yangilandi!")
                    st.rerun()
                if ochirish_m:
                    db.execute("DELETE FROM mahsulotlar WHERE id=?", (m_edit_id,))
                    jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Tovar o'chirildi", f"{m_row['nomi']} ombordan o'chirildi")
                    keshni_tozala()
                    aqlli_tg_xabar("Skladdan tovar o'chirildi!", f"🗑️ <b>O'chirilgan tovar:</b> {m_row['nomi']}", xodim_ismi, turi="moliya", muhim=True)
                    st.success("🗑️ Tovar ombordan o'chirildi!")
                    st.rerun()
        else:
            st.info("Omborda tovar yo'q.")
                
    else:
        df_mahsulot = kesh_df_ol("SELECT nomi, hajmi, kategoriya, sub_kategoriya, tannarx, narxi, qoldiq, izoh FROM mahsulotlar ORDER BY qoldiq ASC")
        if not df_mahsulot.empty:
            df_mahsulot = df_mahsulot.copy()
            df_mahsulot['izoh'] = df_mahsulot['izoh'].fillna('')
            df_mahsulot['tannarx'] = df_mahsulot['tannarx'].fillna(0)
            df_mahsulot.columns = ["Nomi", "Hajmi", "Kategoriya", "Turi", "Tannarxi", "Sotuv Narxi", "Qoldiq", "Izoh (To'liq)"]
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
    st.markdown("---")
    with st.expander("🧹 Tozalik xodimasi (Housekeeping) hisobini tez yaratish"):
        with st.form("hk_user_quick_form", clear_on_submit=True, enter_to_submit=False):
            hc1, hc2, hc3 = st.columns(3)
            hk_ism = hc1.text_input("Tozalik xodimasi F.I.O:", placeholder="Masalan: Ozoda opa")
            hk_login = hc2.text_input("Login:", placeholder="Masalan: tozalik1")
            hk_parol = hc3.text_input("Parol:", placeholder="Masalan: 1234")
            if st.form_submit_button("➕ Tozalik xodimasini qo'shish (Faqat Xonalar xaritasi va Tozalash ko'rinadi)", type="primary", use_container_width=True):
                if hk_ism.strip() and hk_login.strip() and hk_parol.strip():
                    if db.fetchone("SELECT login FROM xodimlar WHERE login=?", (hk_login.strip(),)):
                        st.error("Bunday login band!")
                    else:
                        db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES (?,?,?,?)", (hk_login.strip(), "housekeeping", hk_parol.strip(), hk_ism.strip()))
                        jurnalga_yozish("Xodimlar", xodim_ismi, "Tozalik xodimasi qo'shildi", f"{hk_ism} ({hk_login})")
                        keshni_tozala()
                        st.success(f"✅ {hk_ism} (`{hk_login}`) tizimga qo'shildi!")
                        st.rerun()

# ====================================================
# SAHIFA 10: ⚙️ SOZLAMALAR
# ====================================================
elif sahifa == "⚙️ Sozlamalar":
    st.header("⚙️ Tizim, Tariflar va Profil Sozlamalari Markazi")
    st.caption("Shaxsiy profil xavfsizligi, Telegram 2-kanalli xabarnoma (CEO & Egasi), 24 soatlik Avto-Svodka va dinamik tariflar")

    joriy_soz = sozlamalarni_ol()

    col_s1, col_s2 = st.columns([1.15, 1.35], gap="large")
    with col_s1:
        with st.container(border=True):
            st.subheader("🔐 Shaxsiy profil va Xavfsizlik")
            st.markdown(f"👤 **Foydalanuvchi:** `{xodim_ismi}` &nbsp;|&nbsp; 🔑 **Login:** `{st.session_state.user_login}` &nbsp;|&nbsp; 🛡️ **Huquq:** `{rol_nomi_korsat}`")
            st.write("")
            with st.form("settings_form", enter_to_submit=False):
                yangi_ism = st.text_input("Ism-Sharifingiz (Hujjatlar va Auditda ko'rinadi):", value=xodim_ismi)
                yangi_parol = st.text_input("Yangi parol (o'zgartirish uchun kiriting):", type="password")
                parol_tasdiq = st.text_input("Yangi parolni tasdiqlang:", type="password")
                st.write("")
                if st.form_submit_button("💾 Profil ma'lumotlarini saqlash", type="primary", use_container_width=True):
                    if yangi_parol and yangi_parol != parol_tasdiq:
                        st.error("⚠️ Kiritilgan yangi parollar bir-biriga mos tushmadi!")
                    else:
                        if yangi_parol:
                            db.execute("UPDATE xodimlar SET ism=?, parol=? WHERE login=?", (yangi_ism.strip(), yangi_parol.strip(), st.session_state.user_login))
                        else:
                            db.execute("UPDATE xodimlar SET ism=? WHERE login=?", (yangi_ism.strip(), st.session_state.user_login))
                        jurnalga_yozish("Tizim Sozlamalari", xodim_ismi, "Profil yangilandi", "Foydalanuvchi paroli/ismi o'zgartirildi")
                        keshni_tozala()
                        st.session_state.logged_in = False
                        st.query_params.clear()
                        st.rerun()

    with col_s2:
        with st.container(border=True):
            st.subheader("🖥️ Tizim Diagnostikasi va Ma'lumotlar Bazasi")
            baza_turi_matn = "Online Cloud (PostgreSQL)" if IS_POSTGRES else "Lokal Server (SQLite)"
            jami_bron_c = db.fetchone("SELECT COUNT(*) FROM bronlar")[0] or 0
            jami_mehmon_c = db.fetchone("SELECT SUM(odam_soni) FROM bronlar")[0] or 0
            jami_savdo_c = db.fetchone("SELECT COUNT(*) FROM savdolar")[0] or 0
            jami_audit_c = db.fetchone("SELECT COUNT(*) FROM audit_log")[0] or 0

            sm1, sm2 = st.columns(2)
            sm1.metric("☁️ Ma'lumotlar bazasi", baza_turi_matn)
            sm2.metric("🕒 Server vaqti (Toshkent)", hozirgi_uz_vaqt.strftime("%d.%m.%Y | %H:%M"))

            sm3, sm4, sm5 = st.columns(3)
            sm3.metric("🛏️ Jami mehmonlar", f"{jami_mehmon_c} kishi ({jami_bron_c} bron)")
            sm4.metric("🛒 Market savdolari", f"{jami_savdo_c} ta")
            sm5.metric("🕵️ Audit yozuvlari", f"{jami_audit_c} ta")

            st.write("")
            act1, act2 = st.columns(2, gap="small")
            with act1:
                if st.button("🔄 Tizim keshini yangilash", use_container_width=True):
                    keshni_tozala()
                    st.success("✅ Tizim keshi tozalandi!")
            with act2:
                if st.button("📲 24 soatlik Svodkani hozir yuborish", use_container_width=True):
                    kunlik_svodka_shakllantir_va_yubor(xodim_ismi, majburiy=True)
                    st.success("✅ Svodka Telegramga yuborildi!")

    st.write("")
    with st.container(border=True):
        st.subheader("📋 Hostel Xonalar Fondi, Standart Tariflar va Ichki Reglament")
        st.caption("Quyidagi tariflar va qoidalar CEO tomonidan tasdiqlangan bo'lib, barcha adminlar uchun Qabul bo'limida avtomatik amal qiladi.")

        n4_v = int(float(joriy_soz.get('narx_4k', 100000)))
        n3_v = int(float(joriy_soz.get('narx_3k', 110000)))
        n2_v = int(float(joriy_soz.get('narx_2k', 150000)))
        ust_v = int(float(joriy_soz.get('ustama_chet', 50000)))

        k_m1, k_m2, k_m3, k_m4, k_m5 = st.columns(5)
        k_m1.metric("🛏️ 4 kishilik (Mahalliy / Chet el)", f"{n4_v//1000}k / {(n4_v+ust_v)//1000}k UZS")
        k_m2.metric("🛏️ 3 kishilik (Mahalliy / Chet el)", f"{n3_v//1000}k / {(n3_v+ust_v)//1000}k UZS")
        k_m3.metric("🛏️ 2 kishilik (Mahalliy / Chet el)", f"{n2_v//1000}k / {(n2_v+ust_v)//1000}k UZS")
        k_m4.metric("🛌 Lyuks (Mahalliy / Chet el)", f"{int(float(joriy_soz.get('narx_luxe_uz', 250000)))//1000}k / {int(float(joriy_soz.get('narx_luxe_chet', 300000)))//1000}k UZS")
        k_m5.metric("🎓 Talaba / 7+ kun chegirma", f"-{joriy_soz.get('chegirma_talaba', '50')}% / -{joriy_soz.get('chegirma_hafta', '10')}%")

        st.write("")
        r_c1, r_c2, r_c3 = st.columns(3, gap="medium")
        with r_c1:
            st.info(joriy_soz.get("reg_chap", ""))
        with r_c2:
            st.info(joriy_soz.get("reg_orta", ""))
        with r_c3:
            st.info(joriy_soz.get("reg_ong", ""))

        if st.session_state.role == "ceo":
            st.write("")
            with st.expander("📲 Telegram Bot: CEO va Mehmonxona Egasi (Owner) kanallarini hamda Avto-Svodkani sozlash (Faqat CEO)", expanded=False):
                st.info("👑 **CEO Chat ID** ga barcha moliyaviy jarayonlar (Mehmonlar + Market + Sklad + Xarajatlar) boradi.\n\n🏛️ **Mehmonxona Egasi (Owner) Chat ID** ga esa faqat mehmonlar kirdi-chiqdisi, yotoq to'lovlari va 24 soatlik mehmonlar svodkasi boradi.")
                with st.form("tg_routing_form", enter_to_submit=False):
                    tg1, tg2, tg3 = st.columns(3, gap="medium")
                    with tg1:
                        y_ceo_id = st.text_input("👑 CEO Telegram Chat ID:", value=joriy_soz.get("ceo_chat_id", "6483211079"))
                    with tg2:
                        y_owner_id = st.text_input("🏛️ Mehmonxona Egasi (Owner) Chat ID:", value=joriy_soz.get("owner_chat_id", ""), placeholder="Masalan: 123456789")
                    with tg3:
                        sv_opts = ["Har kuni 12:00 va 00:00 da", "Faqat har kuni 12:00 da (Sutka yakuni)", "Faqat har kuni 00:00 da"]
                        joriy_sv = joriy_soz.get("svodka_rejimi", "Har kuni 12:00 va 00:00 da")
                        y_sv_rejim = st.selectbox("⏰ 24 soatlik Avto-Svodka vaqti:", sv_opts, index=sv_opts.index(joriy_sv) if joriy_sv in sv_opts else 0)

                    if st.form_submit_button("💾 Telegram va Avto-Svodka sozlamalarini saqlash", type="primary", use_container_width=True):
                        sozlamani_saqla("ceo_chat_id", y_ceo_id.strip())
                        sozlamani_saqla("owner_chat_id", y_owner_id.strip())
                        sozlamani_saqla("svodka_rejimi", y_sv_rejim)
                        jurnalga_yozish("Telegram Sozlamalari", xodim_ismi, "Telegram ID yangilandi", f"CEO ID={y_ceo_id}, Owner ID={y_owner_id}, Svodka={y_sv_rejim}")
                        st.success("✅ Telegram qabul qiluvchilar va Avto-Svodka rejimi saqlandi!")
                        st.rerun()

            with st.expander("👑 ✏️ Tariflar, Chegirmalar va Ichki Reglamentni tahrirlash (Faqat CEO huquqi bilan)", expanded=False):
                st.warning("💡 Diqqat: Bu yerda kiritilgan har qanday narx, chegirma va reglament o'zgarishi saqlanishi bilan barcha Adminlar ekranida yangilanadi va Qabul bo'limidagi hisob-kitoblar yangi tariflar bo'yicha amalga oshiriladi!")
                with st.form("ceo_reglament_edit_form", enter_to_submit=False):
                    st.markdown("##### 💰 1. Xonalar va Toifalar bo'yicha Bazaviy Kunlik Narxlar (UZS)")
                    p_c1, p_c2, p_c3, p_c4 = st.columns(4, gap="medium")
                    with p_c1:
                        y_n4 = st.number_input("4 kishilik xona (1 kishi):", min_value=10000, step=5000, value=int(float(joriy_soz.get("narx_4k", 100000))))
                        y_n3 = st.number_input("3 kishilik xona (1 kishi):", min_value=10000, step=5000, value=int(float(joriy_soz.get("narx_3k", 110000))))
                    with p_c2:
                        y_n2 = st.number_input("2 kishilik alohida krovat (1 kishi):", min_value=10000, step=5000, value=int(float(joriy_soz.get("narx_2k", 150000))))
                        y_ustama = st.number_input("Chet el fuqarosi ustamasi (1 joyga):", min_value=0, step=5000, value=int(float(joriy_soz.get("ustama_chet", 50000))))
                    with p_c3:
                        y_luxe_uz = st.number_input("O'rta Lyuks (O'zbekiston fuqarosi):", min_value=50000, step=10000, value=int(float(joriy_soz.get("narx_luxe_uz", 250000))))
                        y_luxe_ch = st.number_input("O'rta Lyuks (Chet el fuqarosi):", min_value=50000, step=10000, value=int(float(joriy_soz.get("narx_luxe_chet", 300000))))
                    with p_c4:
                        y_ch_tal = st.number_input("Talaba chegirmasi (%):", min_value=0, max_value=90, step=5, value=int(float(joriy_soz.get("chegirma_talaba", 50))))
                        y_ch_haf = st.number_input("7+ kunlik chegirma (%):", min_value=0, max_value=90, step=5, value=int(float(joriy_soz.get("chegirma_hafta", 10))))

                    st.markdown("---")
                    st.markdown("##### 📝 2. Barcha Adminlarga ko'rinadigan Reglament va Eslatma matnlari")
                    t_c1, t_c2, t_c3 = st.columns(3, gap="medium")
                    with t_c1:
                        y_reg_chap = st.text_area("Chap qanot reglamenti:", value=joriy_soz.get("reg_chap", ""), height=170)
                    with t_c2:
                        y_reg_orta = st.text_area("O'rta sektor reglamenti:", value=joriy_soz.get("reg_orta", ""), height=170)
                    with t_c3:
                        y_reg_ong = st.text_area("O'ng qanot va Maxsus qoidalar:", value=joriy_soz.get("reg_ong", ""), height=170)

                    if st.form_submit_button("✅ Barcha Tarif va Reglament o'zgarishlarini tasdiqlash va saqlash", type="primary", use_container_width=True):
                        sozlamani_saqla("narx_4k", y_n4)
                        sozlamani_saqla("narx_3k", y_n3)
                        sozlamani_saqla("narx_2k", y_n2)
                        sozlamani_saqla("ustama_chet", y_ustama)
                        sozlamani_saqla("narx_luxe_uz", y_luxe_uz)
                        sozlamani_saqla("narx_luxe_chet", y_luxe_ch)
                        sozlamani_saqla("chegirma_talaba", y_ch_tal)
                        sozlamani_saqla("chegirma_hafta", y_ch_haf)
                        sozlamani_saqla("reg_chap", y_reg_chap.strip())
                        sozlamani_saqla("reg_orta", y_reg_orta.strip())
                        sozlamani_saqla("reg_ong", y_reg_ong.strip())

                        jurnalga_yozish(
                            "Reglament va Tariflar",
                            xodim_ismi,
                            "Tariflar yangilandi (CEO)",
                            f"4k={y_n4:,}, 3k={y_n3:,}, 2k={y_n2:,}, Ustama=+{y_ustama:,}, Lyuks={y_luxe_uz:,}/{y_luxe_ch:,}, Talaba=-{y_ch_tal}%, 7+kun=-{y_ch_haf}%"
                        )
                        aqlli_tg_xabar(
                            "Hostel Tariflari va Reglamenti yangilandi",
                            f"👑 <b>CEO tomonidan yangi tariflar o'rnatildi:</b>\n"
                            f"• 4 kishilik: <b>{y_n4:,} UZS</b> (Chet el: {y_n4+y_ustama:,})\n"
                            f"• 3 kishilik: <b>{y_n3:,} UZS</b> (Chet el: {y_n3+y_ustama:,})\n"
                            f"• 2 kishilik: <b>{y_n2:,} UZS</b> (Chet el: {y_n2+y_ustama:,})\n"
                            f"• Lyuks (O'rta): <b>{y_luxe_uz:,} / {y_luxe_ch:,} UZS</b>\n"
                            f"• Chegirmalar: Talaba <b>-{y_ch_tal}%</b> | 7+ kun <b>-{y_ch_haf}%</b>",
                            xodim_ismi, turi="moliya", muhim=True
                        )
                        st.success("✅ Tariflar va Reglament muvaffaqiyatli yangilandi! Endi barcha adminlar yangi sozlamalar asosida ishlaydi.")
                        st.rerun()

        if st.session_state.role != "housekeeping":
            df_oxirgi_kirish = kesh_df_ol("SELECT vaqt, xodim, harakat, tafsilot FROM audit_log ORDER BY id DESC LIMIT 8")
            if not df_oxirgi_kirish.empty:
                st.markdown("---")
                st.markdown("##### 🕒 Tizimdagi oxirgi faolliklar (Tezkor jurnal)")
                df_oxirgi_kirish = df_oxirgi_kirish.copy()
                df_oxirgi_kirish.columns = ["Sana va Vaqt", "Foydalanuvchi", "Amaliyot", "Tafsilot"]
                st.dataframe(df_oxirgi_kirish, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_oxirgi_kirish))