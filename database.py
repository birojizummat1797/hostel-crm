import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, timezone
import io
import os
from tg_bot import tg_xabar_yubor

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

def toshkent_vaqti():
    return datetime.now(timezone.utc) + timedelta(hours=5)

# ==========================================
# AQLLI SANA VA DAVR FILTRI (CRM PRESETS)
# ==========================================
DAVR_VARIANTLARI = [
    "♾️ Barcha vaqt",
    "📍 Bugungi",
    "⏪ Kechagi",
    "📅 Bu haftalik (Dushanbadan)",
    "🗓️ Oxirgi 1 haftalik (7 kun)",
    "🔟 Oxirgi 10 kunlik",
    "📆 1 oylik (Shu oy boshidan)",
    "🔄 Oxirgi 1 oylik (30 kun)",
    "🛠️ Maxsus oraliq (Sana tanlash)"
]

def aqlli_sana_filtri_ui(joylashuv="sidebar", key_prefix="global"):
    uz_bugun = toshkent_vaqti().date()
    container = st.sidebar if joylashuv == "sidebar" else st

    tanlov = container.selectbox(
        "📅 Davr / Sana filtri:",
        DAVR_VARIANTLARI,
        index=0,
        key=f"{key_prefix}_davr_select"
    )

    if tanlov == "♾️ Barcha vaqt":
        return None, None, "Barcha vaqt"
    elif tanlov == "📍 Bugungi":
        b_sana, t_sana = uz_bugun, uz_bugun
    elif tanlov == "⏪ Kechagi":
        kecha = uz_bugun - timedelta(days=1)
        b_sana, t_sana = kecha, kecha
    elif tanlov == "📅 Bu haftalik (Dushanbadan)":
        b_sana = uz_bugun - timedelta(days=uz_bugun.weekday())
        t_sana = uz_bugun
    elif tanlov == "🗓️ Oxirgi 1 haftalik (7 kun)":
        b_sana = uz_bugun - timedelta(days=6)
        t_sana = uz_bugun
    elif tanlov == "🔟 Oxirgi 10 kunlik":
        b_sana = uz_bugun - timedelta(days=9)
        t_sana = uz_bugun
    elif tanlov == "📆 1 oylik (Shu oy boshidan)":
        b_sana = uz_bugun.replace(day=1)
        t_sana = uz_bugun
    elif tanlov == "🔄 Oxirgi 1 oylik (30 kun)":
        b_sana = uz_bugun - timedelta(days=29)
        t_sana = uz_bugun
    else:
        if joylashuv == "sidebar":
            c1, c2 = st.sidebar.columns(2)
        else:
            c1, c2 = st.columns(2)
        b_sana = c1.date_input("Dan:", uz_bugun - timedelta(days=7), key=f"{key_prefix}_b_sana")
        t_sana = c2.date_input("Gacha:", uz_bugun, key=f"{key_prefix}_t_sana")
        if b_sana > t_sana:
            b_sana, t_sana = t_sana, b_sana

    b_str = b_sana.strftime("%Y-%m-%d")
    t_str = t_sana.strftime("%Y-%m-%d")
    qisqa_nom = f"{b_str} ➔ {t_str}" if b_str != t_str else f"{b_str}"
    return b_str, t_str, qisqa_nom

# ==========================================
# 1. BAZA ARXITEKTURASI (CLOUD + LOKAL)
# ==========================================
DB_URL = None
try:
    if "DATABASE_URL" in st.secrets:
        DB_URL = st.secrets["DATABASE_URL"]
except Exception:
    pass
if not DB_URL:
    DB_URL = os.environ.get("DATABASE_URL")

IS_POSTGRES = bool(DB_URL and PSYCOPG2_AVAILABLE)

class DBWrapper:
    def __init__(self, is_pg, db_url):
        self.is_pg = is_pg
        self.db_url = db_url
        self.conn = None
        self.connect()

    def connect(self):
        if self.is_pg:
            self.conn = psycopg2.connect(self.db_url)
            self.conn.autocommit = True
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SET search_path TO public")
            except Exception:
                pass
        else:
            self.conn = sqlite3.connect('hostel_crm.db', check_same_thread=False)

    def _ensure_conn(self):
        if self.is_pg:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except Exception:
                self.connect()

    def _prepare_sql(self, sql):
        if self.is_pg:
            sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            sql = sql.replace("?", "%s")
        return sql

    def execute(self, sql, params=()):
        self._ensure_conn()
        sql = self._prepare_sql(sql)
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            if not self.is_pg:
                self.conn.commit()
            return cur
        except Exception as e:
            if self.is_pg:
                try:
                    self.conn.rollback()
                except Exception:
                    self.connect()
            raise e

    def fetchone(self, sql, params=()):
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql, params=()):
        cur = self.execute(sql, params)
        return cur.fetchall()

    def read_df(self, sql, params=None):
        self._ensure_conn()
        sql = self._prepare_sql(sql)
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        cols = [desc[0] for desc in cur.description]
        data = cur.fetchall()
        return pd.DataFrame(data, columns=cols)

@st.cache_resource
def get_db():
    return DBWrapper(IS_POSTGRES, DB_URL)

db = get_db()

# ==========================================
# 2. XONALAR RO'YXATI VA JADVALLARNI YARATISH
# ==========================================
XONALAR = {
    "Chap tomon": {"1-xona": (4, 100000), "2-xona": (4, 100000), "3-xona": (4, 100000), "4-xona": (4, 100000), "5-xona": (4, 100000), "6-xona": (4, 100000), "7-xona": (2, 150000), "8-xona": (4, 100000), "9-xona": (4, 100000), "10-xona": (3, 110000), "11-xona": (2, 150000), "12-xona": (4, 100000), "13-xona": (4, 100000), "14-xona": (2, 150000)},
    "O'rtadagi": {f"{i}-xona": (2, 250000) for i in range(15, 22)},
    "O'ng tomon": {"22-xona": (2, 150000), "23-xona": (4, 100000), "24-xona": (4, 100000), "25-xona": (4, 100000), "26-xona": (4, 100000), "27-xona": (4, 100000), "28-xona": (2, 150000), "29-xona": (4, 100000), "30-xona": (4, 100000), "31-xona": (4, 100000), "32-xona": (2, 150000), "33-xona": (4, 100000), "34-xona": (4, 100000), "35-xona": (4, 100000), "36-xona": (4, 100000)}
}
BARCHA_XONALAR_ROYXATI = []
XONA_TOMON_MAP = {}
for t_nomi, x_dict in XONALAR.items():
    for x_nomi, x_info in x_dict.items():
        if t_nomi == "O'rtadagi":
            tavsif = f"{t_nomi} | {x_nomi} (2 kishilik - Dvuxspalniy)"
        elif x_info[0] == 2:
            tavsif = f"{t_nomi} | {x_nomi} (2 kishilik - 2 alohida krovat)"
        else:
            tavsif = f"{t_nomi} | {x_nomi} ({x_info[0]} kishilik)"
        BARCHA_XONALAR_ROYXATI.append(tavsif)
        XONA_TOMON_MAP[x_nomi] = t_nomi

MUDDATLAR = {"Kunlik": 1, "1 hafta (7 kun)": 7, "10 kun": 10, "15 kun": 15, "1 oylik (30 kun)": 30}

@st.cache_resource
def init_db():
    db.execute("""
        CREATE TABLE IF NOT EXISTS bronlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mijoz_id TEXT, jinsi TEXT, sana TEXT, tomon TEXT, xona TEXT, xona_turi TEXT,
            mijoz TEXT, toifa TEXT, odam_soni INTEGER, muddat TEXT, kunlar INTEGER,
            kunlik_narx REAL, jami_summa REAL, faktik_narx REAL, tolagan_summa REAL,
            qoldiq REAL, tolov_turi TEXT, tolov_tafsiloti TEXT, holat TEXT,
            kirish_sanasi TEXT, chiqish_sanasi TEXT, bron_turi TEXT DEFAULT 'Hozir kirish',
            izoh TEXT DEFAULT '', telefon TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS xona_tozalik (
            xona TEXT PRIMARY KEY,
            holat TEXT DEFAULT 'Toza',
            vaqt TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS mahsulotlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomi TEXT, kategoriya TEXT, sub_kategoriya TEXT, hajmi TEXT,
            tannarx REAL DEFAULT 0, narxi REAL, qoldiq INTEGER, izoh TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS savdolar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sana TEXT, mahsulot_nomi TEXT, xaridor TEXT, miqdor INTEGER,
            jami_summa REAL, sof_foyda REAL DEFAULT 0, tolov_turi TEXT, xodim TEXT, tolov_tafsiloti TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS tolovlar_tarixi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sana TEXT, mijoz_id TEXT, mijoz_ismi TEXT, manba TEXT,
            summa REAL, tolov_shakli TEXT, tolov_tafsiloti TEXT, xodim TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS xarajatlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaqt TEXT, sana TEXT, kategoriya TEXT, summa REAL,
            tolov_turi TEXT, izoh TEXT, xodim TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS smenalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaqt TEXT, xodim TEXT, naqd_tushum REAL, karta_tushum REAL,
            xarajatlar_sum REAL, sof_kassa REAL, izoh TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaqt TEXT, mijoz_id TEXT, xodim TEXT, harakat TEXT, tafsilot TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS xodimlar (
            login TEXT PRIMARY KEY,
            role TEXT,
            parol TEXT,
            ism TEXT DEFAULT ''
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS tizim_sozlamalari (
            kalit TEXT PRIMARY KEY,
            qiymat TEXT
        )
    """)

    yangi_ustunlar = [
        "ALTER TABLE bronlar ADD COLUMN bron_turi TEXT DEFAULT 'Hozir kirish'", 
        "ALTER TABLE bronlar ADD COLUMN izoh TEXT DEFAULT ''",
        "ALTER TABLE bronlar ADD COLUMN telefon TEXT DEFAULT ''",
        "ALTER TABLE mahsulotlar ADD COLUMN sub_kategoriya TEXT DEFAULT ''", 
        "ALTER TABLE mahsulotlar ADD COLUMN hajmi TEXT DEFAULT ''", 
        "ALTER TABLE mahsulotlar ADD COLUMN izoh TEXT DEFAULT ''",
        "ALTER TABLE mahsulotlar ADD COLUMN tannarx REAL DEFAULT 0",
        "ALTER TABLE savdolar ADD COLUMN tolov_tafsiloti TEXT DEFAULT ''",
        "ALTER TABLE savdolar ADD COLUMN sof_foyda REAL DEFAULT 0"
    ]
    for sql in yangi_ustunlar:
        try:
            db.execute(sql)
        except Exception:
            pass

    try:
        if db.fetchone("SELECT COUNT(*) FROM xona_tozalik")[0] == 0:
            for t_dict in XONALAR.values():
                for x_nom in t_dict.keys():
                    db.execute("INSERT INTO xona_tozalik (xona, holat, vaqt) VALUES (?, 'Toza', '')", (x_nom,))
    except Exception:
        pass

    if db.fetchone("SELECT COUNT(*) FROM xodimlar")[0] == 0:
        try:
            eski = db.fetchall("SELECT login, role, parol FROM users")
            for u in eski:
                ism_val = "Boshqaruvchi (CEO)" if u[1] == "ceo" else "Front-Ofis Admini"
                db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES (?,?,?,?)", (u[0], u[1], u[2], ism_val))
        except Exception:
            pass

    if db.fetchone("SELECT COUNT(*) FROM xodimlar")[0] == 0:
        db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES ('admin', 'admin', '123', 'Asosiy Admin')")
        db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES ('ceo', 'ceo', '777', 'Boshqaruvchi (CEO)')")
        db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES ('tozalik', 'housekeeping', '111', 'Tozalik Xodimasi')")
    return True

init_db()

# ==========================================
# 3. XONA TOZALIGI VA SUTKA (12:00-12:00) MANTIQ FUNKSIYALARI
# ==========================================
def xona_tozalik_ozgartir(xona_nomi, yangi_holat="Tozalash kerak"):
    hozir = toshkent_vaqti().strftime("%Y-%m-%d %H:%M")
    try:
        mavjud = db.fetchone("SELECT xona FROM xona_tozalik WHERE xona=?", (xona_nomi,))
        if mavjud:
            db.execute("UPDATE xona_tozalik SET holat=?, vaqt=? WHERE xona=?", (yangi_holat, hozir, xona_nomi))
        else:
            db.execute("INSERT INTO xona_tozalik (xona, holat, vaqt) VALUES (?,?,?)", (xona_nomi, yangi_holat, hozir))
    except Exception:
        pass

def barcha_xona_tozalik_ol():
    try:
        rows = db.fetchall("SELECT xona, holat FROM xona_tozalik")
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

def xona_sigimini_ol(xona_nomi):
    for tomon in XONALAR.values():
        if xona_nomi in tomon: return tomon[xona_nomi][0]
    return 0

def xonadagi_band_joyni_hisobla(xona_nomi, kirish_str, chiqish_str, exclude_mijoz_id=None):
    sigim = xona_sigimini_ol(xona_nomi)
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")

    if exclude_mijoz_id:
        rows = db.fetchall(
            "SELECT odam_soni, xona_turi, kirish_sanasi, chiqish_sanasi FROM bronlar WHERE xona=? AND mijoz_id!=? AND holat!='Chiqib ketgan'",
            (xona_nomi, exclude_mijoz_id)
        )
    else:
        rows = db.fetchall(
            "SELECT odam_soni, xona_turi, kirish_sanasi, chiqish_sanasi FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan'",
            (xona_nomi,)
        )

    band = 0
    for r_odam, r_tur, r_kir, r_chiq in rows:
        r_kir = str(r_kir or '')
        r_chiq = str(r_chiq or '')
        ef_chiq = (datetime.strptime(r_chiq, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if (r_kir == r_chiq and r_kir >= bugun_str) else r_chiq
        ef_yangi_chiq = (datetime.strptime(chiqish_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if kirish_str == chiqish_str else chiqish_str

        if r_kir < ef_yangi_chiq and ef_chiq > kirish_str:
            if "To'liq band" in str(r_tur or ''):
                band += sigim
            else:
                band += int(r_odam or 1)
    return min(sigim, band)

def xona_jinsini_tekshir(xona_nomi, kirish_str, chiqish_str, yangi_jins, exclude_mijoz_id=None):
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")

    if exclude_mijoz_id:
        rows = db.fetchall(
            "SELECT jinsi, kirish_sanasi, chiqish_sanasi FROM bronlar WHERE xona=? AND mijoz_id!=? AND holat!='Chiqib ketgan'",
            (xona_nomi, exclude_mijoz_id)
        )
    else:
        rows = db.fetchall(
            "SELECT jinsi, kirish_sanasi, chiqish_sanasi FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan'",
            (xona_nomi,)
        )
    for mavjud_jins, r_kir, r_chiq in rows:
        r_kir = str(r_kir or '')
        r_chiq = str(r_chiq or '')
        ef_chiq = (datetime.strptime(r_chiq, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if (r_kir == r_chiq and r_kir >= bugun_str) else r_chiq
        ef_yangi_chiq = (datetime.strptime(chiqish_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if kirish_str == chiqish_str else chiqish_str
        if r_kir < ef_yangi_chiq and ef_chiq > kirish_str:
            if mavjud_jins and mavjud_jins != yangi_jins:
                return mavjud_jins
    return None

def narx_hisobla(tomon, xona, toifa, odam_soni, kunlar, toliq_xona=False, maxsus_chegirma_foiz=None):
    sigim, bazaviy_narx = XONALAR[tomon][xona]
    hisob_odam = sigim if toliq_xona else odam_soni
    if tomon == "O'rtadagi":
        kunlik = 300000 if toifa == "Chet el fuqarosi" else 250000
    else:
        if toifa == "Chet el fuqarosi":
            kunlik = (bazaviy_narx + 50000) * hisob_odam
        elif toifa == "Talaba (Student)":
            kunlik = (bazaviy_narx * 0.5) * hisob_odam
        else:
            kunlik = bazaviy_narx * hisob_odam

    jami = kunlik * kunlar
    if maxsus_chegirma_foiz is not None and maxsus_chegirma_foiz > 0:
        jami = jami * ((100.0 - float(maxsus_chegirma_foiz)) / 100.0)
    elif kunlar >= 7:
        jami = jami * 0.9
    return kunlik, jami

def id_yaratish(jinsi, kirish_sanasi_obj, toifa):
    g_kod = "1" if jinsi == "Erkak" else "2"
    sana_kod = kirish_sanasi_obj.strftime("%y%m%d")
    t_kod = "1" if toifa == "O'zbekiston fuqarosi" else "2" if toifa == "Chet el fuqarosi" else "3"
    kirish_str = kirish_sanasi_obj.strftime("%Y-%m-%d")
    res = db.fetchone("SELECT COUNT(*) FROM bronlar WHERE kirish_sanasi = ?", (kirish_str,))
    tartib = (res[0] if res else 0) + 1
    return f"{g_kod}{sana_kod}{t_kod}{tartib:03d}"

def jurnalga_yozish(obyekt_id, xodim, harakat, tafsilot):
    hozir = toshkent_vaqti().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT INTO audit_log (vaqt, mijoz_id, xodim, harakat, tafsilot) VALUES (?,?,?,?,?)", (hozir, obyekt_id, xodim, harakat, tafsilot))

# =========================================================
# 24 SOATLIK AVTO-SVODKA (EGASI VA CEO UCHUN ALOHIDA MAZMUNDA!)
# =========================================================
def kunlik_svodka_yubor(xodim="Avto-Tizim (Y.S.H.)", davr_sarlavha="24 soatlik Sutkalik Svodka"):
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")
    kecha_str = (uz_now - timedelta(days=1)).strftime("%Y-%m-%d")

    df_b = db.read_df("SELECT * FROM bronlar")
    df_tol = db.read_df("SELECT * FROM tolovlar_tarixi WHERE sana IN (?, ?)", (kecha_str, bugun_str))
    df_sav = db.read_df("SELECT * FROM savdolar WHERE sana IN (?, ?)", (kecha_str, bugun_str))
    df_xar = db.read_df("SELECT * FROM xarajatlar WHERE sana IN (?, ?)", (kecha_str, bugun_str))
    tozalik_map = barcha_xona_tozalik_ol()

    if not df_b.empty:
        df_b['odam_soni'] = df_b['odam_soni'].fillna(1).astype(int)
        df_b['qoldiq'] = df_b['qoldiq'].fillna(0)
        faol_df = df_b[(df_b['holat'] != 'Chiqib ketgan') & (df_b['kirish_sanasi'] <= bugun_str) & ((df_b['chiqish_sanasi'] > bugun_str) | (df_b['chiqish_sanasi'] == bugun_str))]
        bugun_kirgan_df = df_b[df_b['kirish_sanasi'] == bugun_str]
        kecha_kirgan_df = df_b[df_b['kirish_sanasi'] == kecha_str]
        bugun_chiqqan_df = df_b[(df_b['chiqish_sanasi'] == bugun_str) & (df_b['holat'] == 'Chiqib ketgan')]
    else:
        faol_df = bugun_kirgan_df = kecha_kirgan_df = bugun_chiqqan_df = pd.DataFrame()

    band_xonalar = len(set(faol_df['xona'].unique())) if not faol_df.empty else 0
    faol_odam = int(faol_df['odam_soni'].sum()) if not faol_df.empty else 0
    bugun_kir_odam = int(bugun_kirgan_df['odam_soni'].sum()) if not bugun_kirgan_df.empty else 0
    kecha_kir_odam = int(kecha_kirgan_df['odam_soni'].sum()) if not kecha_kirgan_df.empty else 0
    bugun_chiq_odam = int(bugun_chiqqan_df['odam_soni'].sum()) if not bugun_chiqqan_df.empty else 0
    joriy_qarz = float(df_b[(df_b['holat'] != 'Chiqib ketgan') & (df_b['qoldiq'] > 0)]['qoldiq'].sum()) if not df_b.empty else 0.0
    iflos_xonalar = sum(1 for h in tozalik_map.values() if h == "Tozalash kerak")

    df_tol_bugun = df_tol[df_tol['sana'] == bugun_str] if not df_tol.empty else pd.DataFrame()
    yotoq_tushum_bugun = float(df_tol_bugun[df_tol_bugun['manba'] != 'Market Savdo']['summa'].fillna(0).sum()) if not df_tol_bugun.empty else 0.0
    market_tushum_bugun = float(df_tol_bugun[df_tol_bugun['manba'] == 'Market Savdo']['summa'].fillna(0).sum()) if not df_tol_bugun.empty else 0.0

    df_sav_bugun = df_sav[df_sav['sana'] == bugun_str] if not df_sav.empty else pd.DataFrame()
    market_sof_foyda = float(df_sav_bugun['sof_foyda'].fillna(0).sum()) if (not df_sav_bugun.empty and 'sof_foyda' in df_sav_bugun.columns) else 0.0

    df_xar_bugun = df_xar[df_xar['sana'] == bugun_str] if not df_xar.empty else pd.DataFrame()
    xarajat_bugun = float(df_xar_bugun['summa'].fillna(0).sum()) if not df_xar_bugun.empty else 0.0
    sof_kassa_bugun = (yotoq_tushum_bugun + market_tushum_bugun) - xarajat_bugun

    # 1. MEHMONXONA EGASI UCHUN XABAR (FAQAT MIJOZLAR KIRDI-CHIQDISI VA YOTOQ HISOBI)
    egasi_matn = (
        f"📅 <b>Sana:</b> {bugun_str}\n"
        f"🛏 <b>Hozir band xonalar:</b> {band_xonalar} / 36 ta\n"
        f"👥 <b>Hozir yashayotgan mehmonlar:</b> {faol_odam} kishi\n"
        f"📥 <b>Bugun kirgan mehmonlar:</b> {bugun_kir_odam} kishi ({len(bugun_kirgan_df)} ta bron)\n"
        f"⏪ <b>Kecha kirgan mehmonlar:</b> {kecha_kir_odam} kishi ({len(kecha_kirgan_df)} ta bron)\n"
        f"🛫 <b>Bugun chiqib ketganlar:</b> {bugun_chiq_odam} kishi\n"
        f"💰 <b>Bugungi Yotoq Tushumi:</b> {yotoq_tushum_bugun:,.0f} UZS\n"
        f"⚠️ <b>Mijozlarning joriy qarzi:</b> {joriy_qarz:,.0f} UZS"
    )
    tg_xabar_yubor(f"📊 {davr_sarlavha} (Mijozlar)", egasi_matn, xodim, kanal="egasi")

    # 2. CEO UCHUN TO'LIQ HISOBOT (MIJOZLAR + MARKET + SKLAD + XARAJAT + SOF BALANS)
    kam_tovarlar = db.fetchone("SELECT COUNT(*) FROM mahsulotlar WHERE qoldiq <= 5")[0] or 0
    ceo_matn = (
        f"{egasi_matn}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Bugungi Market Tushumi:</b> {market_tushum_bugun:,.0f} UZS (Sof foyda: +{market_sof_foyda:,.0f} UZS)\n"
        f"➖ <b>Bugungi Xarajatlar:</b> -{xarajat_bugun:,.0f} UZS\n"
        f"🏦 <b>Bugungi Sof Kassa Balansi:</b> <b>{sof_kassa_bugun:,.0f} UZS</b>\n"
        f"🧹 <b>Tozalash kerak bo'lgan xonalar:</b> {iflos_xonalar} ta\n"
        f"📦 <b>Skladda kam qolgan tovarlar:</b> {kam_tovarlar} xil"
    )
    return tg_xabar_yubor(f"👑 {davr_sarlavha} (To'liq Moliya & Operatsiya)", ceo_matn, xodim, kanal="ceo")

def avto_checkout_tekshir():
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")
    soat = uz_now.hour

    if soat >= 12:
        muddati_yetganlar = db.fetchall(
            "SELECT mijoz_id, mijoz, xona, chiqish_sanasi, odam_soni FROM bronlar WHERE holat != 'Chiqib ketgan' AND qoldiq <= 0 AND chiqish_sanasi <= ?",
            (bugun_str,)
        )
    else:
        muddati_yetganlar = db.fetchall(
            "SELECT mijoz_id, mijoz, xona, chiqish_sanasi, odam_soni FROM bronlar WHERE holat != 'Chiqib ketgan' AND qoldiq <= 0 AND chiqish_sanasi < ?",
            (bugun_str,)
        )

    for m_id, m_ism, m_xona, m_chiqish, m_odam in muddati_yetganlar:
        db.execute("UPDATE bronlar SET holat = 'Chiqib ketgan' WHERE mijoz_id = ?", (m_id,))
        xona_tozalik_ozgartir(m_xona, "Tozalash kerak")
        jurnalga_yozish(
            m_id,
            "Avto-Tizim (Y.S.H.)",
            "Avto-Checkout (Arxivlandi)",
            f"Mijoz ({m_ism} | {m_xona}) yashash muddati ({m_chiqish} 12:00) yakunlangani sababli avtomatik arxivga o'tkazildi. {m_xona} 'Tozalash kerak' holatiga o'tdi."
        )
        tg_xabar_yubor(
            "Avtomatik Checkout (Arxivga o'tkazildi)",
            f"👤 <b>Mijoz:</b> {m_ism} ({m_odam} kishi)\n"
            f"🛏 <b>Bo'shagan xona:</b> {m_xona} (🧹 Tozalashga berildi)\n"
            f"⏰ <b>Sabab:</b> Mijozning yashash muddati (<b>{m_chiqish} soat 12:00</b>) yakunlanganligi sababli avtomatik arxivga o'tkazildi.",
            "Avto-Nazorat (Y.S.H. ERP)",
            kanal="mijoz"
        )

    # AVTO-SVODKA TEKSHIRUVI (12:00 VA 00:00 DA DUBLIKATSIZ JO'NATISH)
    try:
        r_rejim = db.fetchone("SELECT qiymat FROM tizim_sozlamalari WHERE kalit='svodka_rejim'")
        svodka_rejim = r_rejim[0] if r_rejim else "Har kuni 12:00 da (Sutka yakuni)"

        if "12:00" in svodka_rejim or "Ikkalasi" in svodka_rejim:
            if soat >= 12:
                r_12 = db.fetchone("SELECT qiymat FROM tizim_sozlamalari WHERE kalit='oxirgi_svodka_12'")
                if not r_12 or r_12[0] != bugun_str:
                    if r_12:
                        db.execute("UPDATE tizim_sozlamalari SET qiymat=? WHERE kalit='oxirgi_svodka_12'", (bugun_str,))
                    else:
                        db.execute("INSERT INTO tizim_sozlamalari (kalit, qiymat) VALUES ('oxirgi_svodka_12', ?)", (bugun_str,))
                    kunlik_svodka_yubor("Avto-Svodka (12:00)", "12:00 dan 12:00 gacha 24 soatlik Svodka")

        if "00:00" in svodka_rejim or "Ikkalasi" in svodka_rejim:
            r_00 = db.fetchone("SELECT qiymat FROM tizim_sozlamalari WHERE kalit='oxirgi_svodka_00'")
            if not r_00 or r_00[0] != bugun_str:
                if r_00:
                    db.execute("UPDATE tizim_sozlamalari SET qiymat=? WHERE kalit='oxirgi_svodka_00'", (bugun_str,))
                else:
                    db.execute("INSERT INTO tizim_sozlamalari (kalit, qiymat) VALUES ('oxirgi_svodka_00', ?)", (bugun_str,))
                kunlik_svodka_yubor("Avto-Svodka (00:00)", "Kunlik 00:00 Svodka")
    except Exception:
        pass

def avto_kenglik_sozla(df):
    config = {}
    if df is None or df.empty:
        return config
    for col in df.columns:
        try:
            max_data_len = int(df[col].astype(str).map(len).max())
        except Exception:
            max_data_len = len(str(col))
        max_len = max(max_data_len, len(str(col)))
        
        col_lower = str(col).lower()
        if any(k in col_lower for k in ["izoh", "tafsilot", "batafsil", "ma'lumot", "to'lov turi"]):
            px = max(280, min(max_len * 9 + 40, 1200))
            config[col] = st.column_config.Column(label=str(col), width=px)
        elif any(k in col_lower for k in ["mijoz", "mehmon", "mahsulot", "nomi", "kategoriya", "xodim", "harakat", "kirish", "chiqish", "vaqt", "xona"]):
            px = max(160, min(max_len * 9 + 30, 500))
            config[col] = st.column_config.Column(label=str(col), width=px)
    return config

def barcha_bazani_yuklash():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        db.read_df("SELECT * FROM bronlar").to_excel(writer, index=False, sheet_name='Bronlar')
        db.read_df("SELECT * FROM tolovlar_tarixi").to_excel(writer, index=False, sheet_name='Tolovlar_Tarixi')
        db.read_df("SELECT * FROM xarajatlar").to_excel(writer, index=False, sheet_name='Xarajatlar')
        db.read_df("SELECT * FROM smenalar").to_excel(writer, index=False, sheet_name='Smenalar')
        db.read_df("SELECT * FROM mahsulotlar").to_excel(writer, index=False, sheet_name='Sklad')
        db.read_df("SELECT * FROM savdolar").to_excel(writer, index=False, sheet_name='Market_Savdo')
        db.read_df("SELECT * FROM audit_log").to_excel(writer, index=False, sheet_name='Audit_Log')
    return output.getvalue()

def haftalik_hisobot_yuklash(bosh_sana_str, tugash_sana_str):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if bosh_sana_str and tugash_sana_str:
            db.read_df("SELECT * FROM savdolar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (bosh_sana_str, tugash_sana_str)).to_excel(writer, index=False, sheet_name='Market_Savdolar')
            db.read_df("SELECT * FROM xarajatlar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (bosh_sana_str, tugash_sana_str)).to_excel(writer, index=False, sheet_name='Mayda_Xarajatlar')
            db.read_df("SELECT * FROM mahsulotlar ORDER BY qoldiq ASC").to_excel(writer, index=False, sheet_name='Sklad_Qoldiq')
            db.read_df("SELECT * FROM tolovlar_tarixi WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (bosh_sana_str, tugash_sana_str)).to_excel(writer, index=False, sheet_name='Kassa_Kirimlar')
            db.read_df("SELECT * FROM audit_log WHERE vaqt >= ? AND vaqt <= ? ORDER BY id DESC", (bosh_sana_str + " 00:00:00", tugash_sana_str + " 23:59:59")).to_excel(writer, index=False, sheet_name='Sklad_va_Tizim_Auditi')
        else:
            db.read_df("SELECT * FROM savdolar ORDER BY id DESC").to_excel(writer, index=False, sheet_name='Market_Savdolar')
            db.read_df("SELECT * FROM xarajatlar ORDER BY id DESC").to_excel(writer, index=False, sheet_name='Mayda_Xarajatlar')
            db.read_df("SELECT * FROM mahsulotlar ORDER BY qoldiq ASC").to_excel(writer, index=False, sheet_name='Sklad_Qoldiq')
            db.read_df("SELECT * FROM tolovlar_tarixi ORDER BY id DESC").to_excel(writer, index=False, sheet_name='Kassa_Kirimlar')
            db.read_df("SELECT * FROM audit_log ORDER BY id DESC").to_excel(writer, index=False, sheet_name='Sklad_va_Tizim_Auditi')
    return output.getvalue()

def chiroyli_kartochka(icon, title, value, bg_color):
    is_dark = st.session_state.get("ui_tema", "🌙 Qorong'u (Dark UI)") == "🌙 Qorong'u (Dark UI)"
    if is_dark:
        return (
            f"<div style='background: #141724; border: 1px solid #262b40; border-top: 4px solid {bg_color}; "
            f"padding: 16px; border-radius: 14px; color: #f8fafc; box-shadow: 0 6px 16px rgba(0,0,0,0.35); "
            f"margin-bottom: 18px; font-family: sans-serif;'>"
            f"<div style='font-size: 13px; color: #cbd5e1; font-weight: 600; margin-bottom: 6px;'>{icon} {title}</div>"
            f"<div style='font-size: 21px; font-weight: 800; color: #ffffff;'>{value}</div></div>"
        )
    return (
        f"<div style='background: linear-gradient(135deg, {bg_color} 0%, {bg_color}dd 100%); "
        f"padding: 16px; border-radius: 14px; color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.12); "
        f"margin-bottom: 18px; font-family: sans-serif;'>"
        f"<div style='font-size: 13px; font-weight: 600; opacity: 0.95; margin-bottom: 6px;'>{icon} {title}</div>"
        f"<div style='font-size: 21px; font-weight: bold; color: white;'>{value}</div></div>"
    )

def rangla_jadval(row):
    is_dark = st.session_state.get("ui_tema", "🌙 Qorong'u (Dark UI)") == "🌙 Qorong'u (Dark UI)"
    holat_val = str(row.get('Holat', row.get('holat', '')))
    q_raw = str(row.get('Qoldiq', row.get('qoldiq', '0')))
    chiqish_raw = str(row.get('Chiqish', row.get('chiqish_sanasi', ''))).split(' ')[0].strip()
    
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")
    soat = uz_now.hour

    if 'Avans' in q_raw:
        qoldiq_val = 0
    else:
        q_str = q_raw.split('UZS')[0].replace(',', '').strip()
        try:
            qoldiq_val = float(q_str)
        except Exception:
            qoldiq_val = 0
        
    if is_dark:
        if holat_val == 'Chiqib ketgan':
            return ['background-color: #1e293b; color: #94a3b8'] * len(row)
        elif qoldiq_val > 0:
            return ['background-color: #451a1a; color: #fca5a5; font-weight: 600'] * len(row)
        elif (chiqish_raw == bugun_str and soat >= 6) or (chiqish_raw != '' and chiqish_raw < bugun_str):
            return ['background-color: #422006; color: #fde047; font-weight: 600'] * len(row)
        else:
            return ['background-color: #063928; color: #6ee7b7'] * len(row)
    else:
        if holat_val == 'Chiqib ketgan':
            return ['background-color: #f1f5f9; color: #64748b'] * len(row)
        elif qoldiq_val > 0:
            return ['background-color: #fef2f2; color: #b91c1c; font-weight: 600'] * len(row)
        elif (chiqish_raw == bugun_str and soat >= 6) or (chiqish_raw != '' and chiqish_raw < bugun_str):
            return ['background-color: #fef08a; color: #854d0e; font-weight: 600'] * len(row)
        else:
            return ['background-color: #f0fdf4; color: #15803d'] * len(row)