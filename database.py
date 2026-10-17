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
# 2. JADVALLAR VA YANGI USTUNLARNI YARATISH
# ==========================================
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
            izoh TEXT DEFAULT ''
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

    yangi_ustunlar = [
        "ALTER TABLE bronlar ADD COLUMN bron_turi TEXT DEFAULT 'Hozir kirish'", 
        "ALTER TABLE bronlar ADD COLUMN izoh TEXT DEFAULT ''",
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
    return True

init_db()

# ==========================================
# 3. XONALAR VA BIZNES MANTIQ FUNKSIYALARI
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

def xona_sigimini_ol(xona_nomi):
    for tomon in XONALAR.values():
        if xona_nomi in tomon: return tomon[xona_nomi][0]
    return 0

def xonadagi_band_joyni_hisobla(xona_nomi, kirish_str, chiqish_str, exclude_mijoz_id=None):
    sigim = xona_sigimini_ol(xona_nomi)
    if exclude_mijoz_id:
        rows = db.fetchall(
            "SELECT odam_soni, xona_turi FROM bronlar WHERE xona=? AND mijoz_id!=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?",
            (xona_nomi, exclude_mijoz_id, chiqish_str, kirish_str)
        )
    else:
        rows = db.fetchall(
            "SELECT odam_soni, xona_turi FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?",
            (xona_nomi, chiqish_str, kirish_str)
        )
    band = 0
    for r_odam, r_tur in rows:
        if "To'liq band" in str(r_tur or ''):
            band += sigim
        else:
            band += int(r_odam or 1)
    return min(sigim, band)

def xona_jinsini_tekshir(xona_nomi, kirish_str, chiqish_str, yangi_jins, exclude_mijoz_id=None):
    """
    Umumiy xonada o'tirgan mijozlarning jinsi bilan yangi mijoz jinsini solishtiradi.
    Agar mos kelmasa, xonadagi jins nomini qaytaradi (masalan 'Erkak' yoki 'Ayol'), mos bo'lsa None qaytaradi.
    """
    if exclude_mijoz_id:
        rows = db.fetchall(
            "SELECT jinsi FROM bronlar WHERE xona=? AND mijoz_id!=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?",
            (xona_nomi, exclude_mijoz_id, chiqish_str, kirish_str)
        )
    else:
        rows = db.fetchall(
            "SELECT jinsi FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?",
            (xona_nomi, chiqish_str, kirish_str)
        )
    for (mavjud_jins,) in rows:
        if mavjud_jins and mavjud_jins != yangi_jins:
            return mavjud_jins
    return None

def narx_hisobla(tomon, xona, toifa, odam_soni, kunlar, toliq_xona=False):
    sigim, bazaviy_narx = XONALAR[tomon][xona]
    hisob_odam = sigim if toliq_xona else odam_soni
    if tomon == "O'rtadagi":
        kunlik = 300000 if toifa == "Chet el fuqarosi" else 250000
    else:
        if toifa == "Chet el fuqarosi": kunlik = (bazaviy_narx + 50000) * hisob_odam
        elif toifa == "Talaba (Student)": kunlik = (bazaviy_narx * 0.5) * hisob_odam
        else: kunlik = bazaviy_narx * hisob_odam
    jami = kunlik * kunlar
    if kunlar >= 7: jami = jami * 0.9
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
        jurnalga_yozish(
            m_id,
            "Avto-Tizim (Y.S.H.)",
            "Avto-Checkout (Arxivlandi)",
            f"Mijoz ({m_ism} | {m_xona}) yashash muddati ({m_chiqish} 12:00) yakunlangani sababli avtomatik arxivga o'tkazildi."
        )
        tg_xabar_yubor(
            "Avtomatik Checkout (Arxivga o'tkazildi)",
            f"👤 <b>Mijoz:</b> {m_ism} ({m_odam} kishi)\n"
            f"🛏 <b>Bo'shagan xona:</b> {m_xona}\n"
            f"⏰ <b>Sabab:</b> Mijozning yashash muddati (<b>{m_chiqish} soat 12:00</b>) yakunlanganligi va muddat uzaytirilmaganligi sababli tizim tomonidan avtomatik ravishda faol ro'yxatdan chiqarildi va arxivga o'tkazildi.",
            "Avto-Nazorat (Y.S.H. ERP)"
        )

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
        elif any(k in col_lower for k in ["mijoz", "mahsulot", "nomi", "kategoriya", "xodim", "harakat", "kirish", "chiqish", "vaqt", "xona"]):
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
        db.read_df("SELECT * FROM savdolar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (bosh_sana_str, tugash_sana_str)).to_excel(writer, index=False, sheet_name='Market_Savdolar')
        db.read_df("SELECT * FROM xarajatlar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (bosh_sana_str, tugash_sana_str)).to_excel(writer, index=False, sheet_name='Mayda_Xarajatlar')
        db.read_df("SELECT * FROM mahsulotlar ORDER BY qoldiq ASC").to_excel(writer, index=False, sheet_name='Sklad_Qoldiq')
        db.read_df("SELECT * FROM tolovlar_tarixi WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (bosh_sana_str, tugash_sana_str)).to_excel(writer, index=False, sheet_name='Kassa_Kirimlar')
        db.read_df("SELECT * FROM audit_log WHERE vaqt >= ? AND vaqt <= ? ORDER BY id DESC", (bosh_sana_str + " 00:00:00", tugash_sana_str + " 23:59:59")).to_excel(writer, index=False, sheet_name='Sklad_va_Tizim_Auditi')
    return output.getvalue()

def chiroyli_kartochka(icon, title, value, bg_color):
    return f"<div style='background: linear-gradient(135deg, {bg_color} 0%, {bg_color}dd 100%); padding: 15px; border-radius: 12px; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.15); margin-bottom: 20px; font-family: sans-serif;'><div style='font-size: 13px; font-weight: 600; opacity: 0.9; margin-bottom: 5px;'>{icon} {title}</div><div style='font-size: 22px; font-weight: bold;'>{value}</div></div>"

def rangla_jadval(row):
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
        
    if holat_val == 'Chiqib ketgan':
        return ['background-color: #f1f5f9; color: #64748b'] * len(row)
    elif qoldiq_val > 0:
        return ['background-color: #fef2f2; color: #b91c1c; font-weight: 600'] * len(row)
    elif (chiqish_raw == bugun_str and soat >= 6) or (chiqish_raw != '' and chiqish_raw < bugun_str):
        return ['background-color: #fef08a; color: #854d0e; font-weight: 600'] * len(row)
    else:
        return ['background-color: #f0fdf4; color: #15803d'] * len(row)