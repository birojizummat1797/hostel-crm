import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# ==========================================
# 1. MA'LUMOTLAR BAZASINI SOZLASH
# ==========================================
conn = sqlite3.connect('hostel_crm.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS bronlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mijoz_id TEXT, jinsi TEXT, sana TEXT, tomon TEXT, xona TEXT, xona_turi TEXT,
        mijoz TEXT, toifa TEXT, odam_soni INTEGER, muddat TEXT, kunlar INTEGER,
        kunlik_narx REAL, jami_summa REAL, faktik_narx REAL, tolagan_summa REAL,
        qoldiq REAL, tolov_turi TEXT, tolov_tafsiloti TEXT, holat TEXT,
        kirish_sanasi TEXT, chiqish_sanasi TEXT, bron_turi TEXT DEFAULT 'Hozir kirish',
        izoh TEXT DEFAULT ''
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS mahsulotlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT, kategoriya TEXT, sub_kategoriya TEXT, hajmi TEXT,
        narxi REAL, qoldiq INTEGER, izoh TEXT DEFAULT ''
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS savdolar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sana TEXT, mahsulot_nomi TEXT, xaridor TEXT, miqdor INTEGER,
        jami_summa REAL, tolov_turi TEXT, xodim TEXT, tolov_tafsiloti TEXT DEFAULT ''
    )
''')

ustunlar = [
    "ALTER TABLE bronlar ADD COLUMN bron_turi TEXT DEFAULT 'Hozir kirish'", 
    "ALTER TABLE bronlar ADD COLUMN izoh TEXT DEFAULT ''",
    "ALTER TABLE mahsulotlar ADD COLUMN sub_kategoriya TEXT DEFAULT ''", 
    "ALTER TABLE mahsulotlar ADD COLUMN hajmi TEXT DEFAULT ''", 
    "ALTER TABLE mahsulotlar ADD COLUMN izoh TEXT DEFAULT ''",
    "ALTER TABLE savdolar ADD COLUMN tolov_tafsiloti TEXT DEFAULT ''"
]
for sql in ustunlar:
    try: c.execute(sql)
    except sqlite3.OperationalError: pass

c.execute('''CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, vaqt TEXT, mijoz_id TEXT, xodim TEXT, harakat TEXT, tafsilot TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS users (role TEXT PRIMARY KEY, login TEXT, parol TEXT)''')
c.execute("SELECT COUNT(*) FROM users")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO users (role, login, parol) VALUES ('admin', 'admin', '123')")
    c.execute("INSERT INTO users (role, login, parol) VALUES ('ceo', 'ceo', '777')")
conn.commit()

# Hamma joyga xabar beruvchi funksiya
def jurnalga_yozish(obyekt_id, xodim, harakat, tafsilot):
    hozir = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_log (vaqt, mijoz_id, xodim, harakat, tafsilot) VALUES (?,?,?,?,?)", (hozir, obyekt_id, xodim, harakat, tafsilot))
    conn.commit()

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='Hisobot')
    return output.getvalue()

def rangla_jadval(row):
    holat_val = str(row.get('Holat', row.get('holat', '')))
    q_str = str(row.get('Qoldiq', row.get('qoldiq', '0'))).replace(' UZS', '').replace(',', '').strip()
    try: qoldiq_val = float(q_str)
    except: qoldiq_val = 0
        
    if holat_val == 'Chiqib ketgan': return ['background-color: #f1f5f9; color: #94a3b8'] * len(row)
    elif qoldiq_val > 0: return ['background-color: #fef2f2; color: #b91c1c'] * len(row)
    else: return ['background-color: #f0fdf4; color: #15803d'] * len(row)

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'reset_key' not in st.session_state: st.session_state.reset_key = 0

# ==========================================
# 2. XONALAR VA MANTIQ
# ==========================================
XONALAR = {
    "Chap tomon": {"1-xona": (4, 100000), "2-xona": (4, 100000), "3-xona": (4, 100000), "4-xona": (4, 100000), "5-xona": (4, 100000), "6-xona": (4, 100000), "7-xona": (2, 150000), "8-xona": (4, 100000), "9-xona": (4, 100000), "10-xona": (3, 110000), "11-xona": (2, 150000), "12-xona": (4, 100000), "13-xona": (4, 100000), "14-xona": (2, 150000)},
    "O'rtadagi": {f"{i}-xona": (2, 250000) for i in range(15, 22)},
    "O'ng tomon": {"22-xona": (2, 150000), "23-xona": (4, 100000), "24-xona": (4, 100000), "25-xona": (4, 100000), "26-xona": (4, 100000), "27-xona": (4, 100000), "28-xona": (2, 150000), "29-xona": (4, 100000), "30-xona": (4, 100000), "31-xona": (4, 100000), "32-xona": (2, 150000), "33-xona": (4, 100000), "34-xona": (4, 100000), "35-xona": (4, 100000), "36-xona": (4, 100000)}
}
MUDDATLAR = {"Kunlik": 1, "1 hafta (7 kun)": 7, "10 kun": 10, "15 kun": 15, "1 oylik (30 kun)": 30}

def xona_sigimini_ol(xona_nomi):
    for tomon in XONALAR.values():
        if xona_nomi in tomon: return tomon[xona_nomi][0]
    return 0

def narx_hisobla(tomon, xona, toifa, odam_soni, kunlar):
    sigim, bazaviy_narx = XONALAR[tomon][xona]
    if tomon == "O'rtadagi": kunlik = 300000 if toifa == "Chet el fuqarosi" else 250000
    else:
        if toifa == "Chet el fuqarosi": kunlik = (bazaviy_narx + 50000) * odam_soni
        elif toifa == "Talaba (Student)": kunlik = (bazaviy_narx * 0.5) * odam_soni
        else: kunlik = bazaviy_narx * odam_soni
    jami = kunlik * kunlar
    if kunlar >= 7: jami = jami * 0.9
    return kunlik, jami

def id_yaratish(jinsi, kirish_sanasi_obj, toifa):
    g_kod = "1" if jinsi == "Erkak" else "2"
    sana_kod = kirish_sanasi_obj.strftime("%y%m%d")
    t_kod = "1" if toifa == "O'zbekiston fuqarosi" else "2" if toifa == "Chet el fuqarosi" else "3"
    kirish_str = kirish_sanasi_obj.strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM bronlar WHERE kirish_sanasi = ?", (kirish_str,))
    tartib = c.fetchone()[0] + 1
    return f"{g_kod}{sana_kod}{t_kod}{tartib:03d}"

def chiroyli_kartochka(icon, title, value, bg_color):
    return f"<div style='background: linear-gradient(135deg, {bg_color} 0%, {bg_color}dd 100%); padding: 15px; border-radius: 12px; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.15); margin-bottom: 20px; font-family: sans-serif;'><div style='font-size: 14px; font-weight: 600; opacity: 0.9; margin-bottom: 5px;'>{icon} {title}</div><div style='font-size: 26px; font-weight: bold;'>{value}</div></div>"

# ==========================================
# 3. UI VA LOGIN
# ==========================================
st.set_page_config(page_title="Yangi Sergeli Hostel CRM", layout="wide")
st.markdown("""<style>div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e6ed; padding: 15px 20px; border-radius: 12px; border-left: 6px solid #4CAF50; box-shadow: 2px 4px 15px rgba(0,0,0,0.05); transition: transform 0.2s ease-in-out; } div[data-testid="metric-container"]:hover { transform: translateY(-3px); box-shadow: 2px 6px 20px rgba(0,0,0,0.1); }</style>""", unsafe_allow_html=True)

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #2E3B55; margin-top: 50px;'>🏨 YSH CRM Tizimi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            login_input = st.text_input("Login")
            parol_input = st.text_input("Parol", type="password")
            submit_login = st.form_submit_button("Kirish", use_container_width=True, type="primary")
            if submit_login:
                c.execute("SELECT role FROM users WHERE login=? AND parol=?", (login_input, parol_input))
                user = c.fetchone()
                if user:
                    st.session_state.logged_in = True
                    st.session_state.role = user[0]
                    jurnalga_yozish("Tizim", user[0].upper(), "Tizimga kirdi", "Ish faoliyati boshlandi")
                    st.rerun()
                else: st.error("Noto'g'ri login/parol!")
    st.stop()

st.sidebar.title("🏨 Boshqaruv")
rol_nomi = "Boshqaruvchi (CEO)" if st.session_state.role == "ceo" else "Front-Ofis Xodimi"
st.sidebar.success(f"Xush kelibsiz, {rol_nomi}!")
if st.sidebar.button("🚪 Tizimdan chiqish", use_container_width=True):
    jurnalga_yozish("Tizim", st.session_state.role.upper(), "Tizimdan chiqdi", "Ish faoliyati yakunlandi")
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.title("🏨 Yangi Sergeli Hostel CRM")
bugungi_sana = datetime.today().strftime("%Y-%m-%d")
k = str(st.session_state.reset_key)
xodim_ismi = "CEO" if st.session_state.role == "ceo" else "Front-Ofis Admini"

if st.session_state.role == "ceo":
    tabs = st.tabs(["📈 Dashboard", "📝 Qabul", "🔲 Shaxmatka", "💼 Mijozlar", "🛒 Market", "📦 Sklad", "👑 CEO Panel", "⚙️ Sozlamalar"])
    t1, t2, t3, t4, t_market, t_ombor, t5, t6 = tabs
else:
    tabs = st.tabs(["📈 Dashboard", "📝 Qabul", "🔲 Shaxmatka", "💼 Mijozlar", "🛒 Market", "📦 Sklad", "⚙️ Sozlamalar"])
    t1, t2, t3, t4, t_market, t_ombor, t6 = tabs
    t5 = None

# ----------------------------------------------------
# TAB 1: AQLLI DASHBOARD
# ----------------------------------------------------
if t1:
    with t1:
        st.header("📈 Hostel Analitikasi va Dashboard")
        df_barcha = pd.read_sql_query("SELECT * FROM bronlar", conn)
        df_savdolar = pd.read_sql_query("SELECT * FROM savdolar", conn)
        if 'tolagan_summa' in df_barcha.columns: df_barcha['tolagan_summa'] = df_barcha['tolagan_summa'].fillna(0)
        if 'qoldiq' in df_barcha.columns: df_barcha['qoldiq'] = df_barcha['qoldiq'].fillna(0)

        if not df_barcha.empty:
            faol_mijozlar = df_barcha[(df_barcha['holat'] != 'Chiqib ketgan') & (df_barcha['kirish_sanasi'] <= bugungi_sana)]
            bugun_kelganlar = df_barcha[df_barcha['kirish_sanasi'] == bugungi_sana]
            umumiy_kassa_yotoq = df_barcha['tolagan_summa'].sum()
            umumiy_kassa_market = df_savdolar['jami_summa'].sum() if not df_savdolar.empty else 0
            umumiy_qarz = df_barcha[df_barcha['qoldiq'] > 0]['qoldiq'].sum()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: st.markdown(chiroyli_kartochka("👥", "Hozirgi mehmon", f"{len(faol_mijozlar)}", "#8b5cf6"), unsafe_allow_html=True)
            with c2: st.markdown(chiroyli_kartochka("📥", "Kelganlar", f"{len(bugun_kelganlar)}", "#3b82f6"), unsafe_allow_html=True)
            with c3: st.markdown(chiroyli_kartochka("💰", "Yotoq Tushumi", f"{umumiy_kassa_yotoq:,.0f}", "#f59e0b"), unsafe_allow_html=True)
            with c4: st.markdown(chiroyli_kartochka("🛒", "Market Tushumi", f"{umumiy_kassa_market:,.0f}", "#10b981"), unsafe_allow_html=True)
            with c5: st.markdown(chiroyli_kartochka("⚠️", "Umumiy Qarz", f"{umumiy_qarz:,.0f}", "#ef4444"), unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("🧮 Tushumlarning To'lov Turlari Bo'yicha Holati")
            df_yotoq_t = df_barcha[df_barcha['tolagan_summa'] > 0][['tolov_tafsiloti', 'tolagan_summa']].rename(columns={'tolagan_summa': 'sum'})
            if not df_savdolar.empty and 'tolov_tafsiloti' in df_savdolar.columns:
                df_market_t = df_savdolar[df_savdolar['tolov_turi'] == 'Darhol'][['tolov_tafsiloti', 'jami_summa']].rename(columns={'jami_summa': 'sum'})
            else: df_market_t = pd.DataFrame(columns=['tolov_tafsiloti', 'sum'])
            df_kombayn = pd.concat([df_yotoq_t, df_market_t])
            df_kombayn['tolov_tafsiloti'] = df_kombayn['tolov_tafsiloti'].replace('', 'Noma\'lum tur').fillna("Noma'lum tur")
            tushum_turlari = df_kombayn.groupby('tolov_tafsiloti')['sum'].sum().reset_index().sort_values(by="sum", ascending=False)
            
            if not tushum_turlari.empty:
                t_cols = st.columns(4)
                for index, row in tushum_turlari.reset_index(drop=True).iterrows():
                    with t_cols[index % 4]: st.info(f"**{row['tolov_tafsiloti']}**\n\n### {row['sum']:,.0f} UZS")
            else: st.info("Hali kassa bo'sh.")

            st.markdown("---")
            df_mahsulotlar = pd.read_sql_query("SELECT * FROM mahsulotlar WHERE qoldiq <= 5", conn)
            if not df_mahsulotlar.empty:
                st.error(f"🚨 **DIQQAT: Quyidagi {len(df_mahsulotlar)} ta mahsulot omborda tugayapti!**")
                st.warning(f"🛒 " + ", ".join([f"{r['nomi']} ({r['qoldiq']} ta qoldi)" for _, r in df_mahsulotlar.iterrows()]))
        else: st.info("Hozircha bazada ma'lumot yo'q.")

# ----------------------------------------------------
# TAB 2: QABUL VA BRON
# ----------------------------------------------------
if t2:
    with t2:
        bron_turi = st.radio("📌 Ro'yxatdan o'tish turi:", ["Hozir qabul qilish (Kirish)", "Oldindan band qilish (Bron)"], horizontal=True, key=f"bturi_{k}")
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            mijoz_ism = st.text_input("Mijoz F.I.O / Telefon", key=f"ism_{k}")
            jinsi = st.radio("Jinsi", ["Erkak", "Ayol"], horizontal=True, key=f"jins_{k}")
            toifa = st.selectbox("Mijoz toifasi", ["O'zbekiston fuqarosi", "Chet el fuqarosi", "Talaba (Student)"], key=f"toifa_{k}")
            muddat = st.selectbox("Muddat turi", list(MUDDATLAR.keys()), key=f"muddat_{k}")
            if bron_turi == "Oldindan band qilish (Bron)": kirish_sanasi = st.date_input("Mijoz keladigan sana", datetime.today() + timedelta(days=1), key=f"sana_{k}")
            else: kirish_sanasi = st.date_input("Kirish sanasi", datetime.today(), key=f"sana_{k}")
            
        with col2:
            tomon = st.selectbox("Tomon / Qanot", list(XONALAR.keys()), key=f"tomon_{k}")
            xona = st.selectbox("Xona raqami", list(XONALAR[tomon].keys()), key=f"xona_{k}")
            xona_sigimi = XONALAR[tomon][xona][0]
            odam_soni = st.selectbox("Odam soni", list(range(1, xona_sigimi + 1)), key=f"odam_{k}")
            kunlar = st.number_input("Necha kun?", min_value=1, value=1, key=f"kun_{k}") if muddat == "Kunlik" else MUDDATLAR[muddat]
            chiqish_sanasi = kirish_sanasi + timedelta(days=kunlar)
            kirish_str = kirish_sanasi.strftime("%Y-%m-%d")
            chiqish_str = chiqish_sanasi.strftime("%Y-%m-%d")
            
            c.execute("SELECT mijoz, kirish_sanasi, chiqish_sanasi, odam_soni FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?", (xona, chiqish_str, kirish_str))
            oraliqdagi_bronlar = c.fetchall()
            c.execute("SELECT SUM(odam_soni) FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?", (xona, chiqish_str, kirish_str))
            band = c.fetchone()[0] or 0
            bosh_joy = XONALAR[tomon][xona][0] - band
            
            joy_bor = True
            if bosh_joy <= 0: st.error(f"⚠️ {xona} tanlangan sanalarda to'liq band!"); joy_bor = False
            elif odam_soni > bosh_joy: st.error(f"⚠️ Bu xonada o'sha sanalarga faqat {bosh_joy} ta joy qolgan xolos!"); joy_bor = False
            else: st.success(f"✅ Sanalarga mos {bosh_joy} ta bo'sh joy bor.")
                
            if oraliqdagi_bronlar:
                st.info("📌 **Tanlangan davrda xonadagi boshqa bandliklar:**")
                for b in oraliqdagi_bronlar: st.markdown(f"🗓 {b[1]} dan {b[2]} 12:00 gacha: **{b[0]}** ({b[3]} kishi)")

        kunlik_stavka, standart_jami = narx_hisobla(tomon, xona, toifa, odam_soni, kunlar)
        with col3:
            st.info(f"🧾 **Standart jami:** {standart_jami:,.0f} so'm")
            if st.checkbox("⚙️ Admin maxsus narx", key=f"maxsus_{k}"): yakuniy_narx = st.number_input("KUNLIK narx:", value=int(kunlik_stavka), step=5000, key=f"ynarx_{k}") * kunlar
            else: yakuniy_narx = standart_jami
            st.markdown(f"### 💰 JAMI: {yakuniy_narx:,.0f} so'm")
            tolangan = st.number_input("To'lanayotgan summa:", value=0, step=10000, key=f"tol_{k}")
            tolov_shakli = st.selectbox("To'lov shakli", ["Naqd", "Karta", "Onlayn"])
            t_taf = st.selectbox("To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
            if t_taf == "Boshqa":
                qoshimcha_izoh = st.text_input("Qaysi turda to'landi? (Izoh yozing):", placeholder="Masalan: Payme, O'tkazma...")
                if qoshimcha_izoh: t_taf = f"Boshqa ({qoshimcha_izoh})"

        qoldiq = yakuniy_narx - tolangan
        holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"

        st.divider()
        if joy_bor and st.button("✅ Bazaga saqlash", type="primary", use_container_width=True):
            if mijoz_ism.strip():
                yangi_id = id_yaratish(jinsi, kirish_sanasi, toifa)
                saq_turi = 'Hozir kirish' if bron_turi == "Hozir qabul qilish (Kirish)" else 'Bron'
                c.execute('''INSERT INTO bronlar (mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar, kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti, holat, kirish_sanasi, chiqish_sanasi, bron_turi, izoh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (yangi_id, jinsi, datetime.now().strftime("%Y-%m-%d"), tomon, xona, "", mijoz_ism, toifa, odam_soni, muddat, kunlar, kunlik_stavka, standart_jami, yakuniy_narx, tolangan, qoldiq, tolov_shakli, t_taf, holat, kirish_str, chiqish_str, saq_turi, ""))
                conn.commit()
                jurnalga_yozish(yangi_id, xodim_ismi, "Yangi " + saq_turi, f"To'ladi: {tolangan:,.0f} ({t_taf})")
                st.session_state.reset_key += 1
                st.rerun()
            else: st.error("Ismni kiriting!")

# ----------------------------------------------------
# TAB 3: METRO SHAXMATKA 
# ----------------------------------------------------
if t3:
    with t3:
        st.header("🔲 15-kunlik Xonalar Shaxmatkasi")
        col_kat, col_san = st.columns([2, 1])
        tanlangan_katalog = col_kat.radio("Qanot:", ["Barchasi", "Chap tomon", "O'rtadagi", "O'ng tomon"], horizontal=True)
        bosh_sana = col_san.date_input("Boshlanish sanasi:", datetime.today())
        sana_royxati = [bosh_sana + timedelta(days=i) for i in range(15)]
        matrix = []
        for tomon, xonalar in XONALAR.items():
            if tanlangan_katalog != "Barchasi" and tomon != tanlangan_katalog: continue
            for xona, info in xonalar.items():
                sigim = info[0]
                qator = {"Xona": f"{xona} ({sigim} k)" if tanlangan_katalog != "Barchasi" else f"{tomon[0]} | {xona} ({sigim} k)"}
                for d in sana_royxati:
                    d_str = d.strftime("%Y-%m-%d")
                    c.execute("SELECT SUM(odam_soni) FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona, d_str, d_str))
                    bosh = sigim - (c.fetchone()[0] or 0)
                    qator[d.strftime("%d.%m")] = "🟩 Bo'sh" if bosh == sigim else "🟥 Band" if bosh <= 0 else f"🟨 {bosh} ta"
                matrix.append(qator)
        
        grid_response = st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        st.markdown("---")
        st.subheader("🔍 Xona ichidagi aniq holat")
        
        selected_rows = grid_response.selection.rows
        if selected_rows:
            t_xona = pd.DataFrame(matrix).iloc[selected_rows[0]]["Xona"]
            xona_nomi = t_xona.split(" | ")[1] if " | " in t_xona else t_xona
            xona_nomi = xona_nomi.split(" (")[0].strip()
            umumiy_sigim = xona_sigimini_ol(xona_nomi)
            bugun = datetime.today().strftime("%Y-%m-%d")
            
            c.execute("SELECT mijoz, jinsi, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona_nomi, bugun, bugun))
            bugun_ichidagilar = c.fetchall()
            c.execute("SELECT mijoz, jinsi, kirish_sanasi, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi>?", (xona_nomi, bugun))
            kelajakdagi_bronlar = c.fetchall()
            
            if not bugun_ichidagilar and not kelajakdagi_bronlar: st.success(f"🟢 **XONA TO'LIQ BO'SH — {xona_nomi} ({umumiy_sigim} kishilik)**")
            elif not bugun_ichidagilar and kelajakdagi_bronlar:
                eng_yaqin = sorted(kelajakdagi_bronlar, key=lambda x: x[2])[0]
                st.warning(f"🟡 **XONA HOZIR BO'SH, lekin {eng_yaqin[2]} dan boshlab band qilingan! — {xona_nomi} ({umumiy_sigim} kishilik)**")
            else:
                band_qilingan_joylar = sum([m[5] for m in bugun_ichidagilar])
                qoldiq_joy = umumiy_sigim - band_qilingan_joylar
                if qoldiq_joy > 0: 
                    msg = f"🟡 **XONADA HOZIR MIJOZLAR BOR — Qoldiq o'rin: {qoldiq_joy} ta. {xona_nomi}**"
                    if kelajakdagi_bronlar: msg += "\n\n*(Diqqat: Kelajakda bronlar ham bor!)*"
                    st.warning(msg)
                else: st.error(f"🔴 **XONA HOZIR TO'LIQ BAND — {xona_nomi}**")
            
            if bugun_ichidagilar:
                st.markdown("**Hozirgi mijozlar:**")
                for m in bugun_ichidagilar:
                    m_ism, m_jinsi, m_chiqish, m_tolagan, m_qoldiq, m_odam, m_izoh = m
                    qarz_matni = f" | ⚠️ Qarz: {m_qoldiq:,.0f} UZS" if m_qoldiq > 0 else ""
                    st.markdown(f"- **{m_ism}** (🛫 Chiqish: {m_chiqish} 12:00){qarz_matni}")
                    if m_izoh: st.info(f"💡 **CEO Izohi:** {m_izoh}")
                    
            if kelajakdagi_bronlar:
                st.info(f"📅 **Ushbu xonaga kelajakdagi bronlar ({len(kelajakdagi_bronlar)} ta):**")
                for b in kelajakdagi_bronlar:
                    b_ism, b_jinsi, b_kirish, b_chiqish, b_tolagan, b_qoldiq, b_odam, b_izoh = b
                    b_qarz = f" | ⚠️ Qarz: {b_qoldiq:,.0f} UZS" if b_qoldiq > 0 else ""
                    st.markdown(f"- 🕒 Keladi: **{b_kirish} 12:00** ({b_odam} kishi) - **{b_ism}** • 🛫 Ketadi: {b_chiqish} 12:00{b_qarz}")
                    if b_izoh: st.info(f"💡 **CEO Izohi:** {b_izoh}")
        else: st.info("👆 Ma'lumotni ko'rish uchun yuqoridagi jadvaldan biror qatorni ustiga bosing.")

# ----------------------------------------------------
# TAB 4: FRONT-OFIS 
# ----------------------------------------------------
if t4:
    with t4:
        st.header("💼 Mijozlar va Boshqaruv (Front-Ofis)")
        df = pd.read_sql_query("SELECT * FROM bronlar ORDER BY id DESC", conn)
        df['faktik_narx'] = df['faktik_narx'].fillna(0)
        df['tolagan_summa'] = df['tolagan_summa'].fillna(0)
        df['qoldiq'] = df['qoldiq'].fillna(0)
        df['izoh'] = df['izoh'].fillna('')
        
        if not df.empty:
            faol_df = df[(df['holat'] != 'Chiqib ketgan') & (df['kirish_sanasi'] <= bugungi_sana)]
            bron_df = df[(df['holat'] != 'Chiqib ketgan') & (df['kirish_sanasi'] > bugungi_sana)]
            
            if not bron_df.empty:
                st.subheader("📅 Oldindan Bron qilinganlar")
                bron_korsatish = bron_df[['mijoz_id', 'mijoz', 'xona', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_sanasi', 'izoh']].copy()
                bron_korsatish.columns = ['ID', 'Mijoz', 'Xona', 'Kun', 'Jami Summa', 'To\'langan', 'Qoldiq', 'Kelish Sanasi', 'Izoh']
                for col in ['Jami Summa', 'To\'langan', 'Qoldiq']: bron_korsatish[col] = bron_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(bron_korsatish, use_container_width=True, hide_index=True)

            st.subheader("🟢 Hozirgi (Faol) Mijozlar")
            if not faol_df.empty:
                faol_korsatish = faol_df[['mijoz_id', 'mijoz', 'xona', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'chiqish_sanasi', 'holat', 'izoh']].copy()
                faol_korsatish['chiqish_sanasi'] = faol_korsatish['chiqish_sanasi'] + ' 12:00'
                faol_korsatish.columns = ['ID', 'Mijoz', 'Xona', 'Kun', 'Jami Summa', 'To\'langan', 'Qoldiq', 'Chiqish', 'Holat', 'Izoh']
                for col in ['Jami Summa', 'To\'langan', 'Qoldiq']: faol_korsatish[col] = faol_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(faol_korsatish.style.apply(rangla_jadval, axis=1), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            m1, m2 = st.columns(2)
            with m1:
                st.info("➕ Muddatni cho'zish")
                if not faol_df.empty:
                    tanlangan_id_chozish = st.selectbox("Mijozni tanlang (Muddat cho'zish):", faol_df['mijoz_id'] + " - " + faol_df['mijoz'])
                    qoshimcha_kun = st.number_input("Necha kun qo'shilmoqda?", min_value=1, value=1)
                    if st.button("Muddatni cho'zish"):
                        m_id = tanlangan_id_chozish.split(" - ")[0]
                        mijoz_data = faol_df[faol_df['mijoz_id'] == m_id].iloc[0]
                        yangi_chiqish = datetime.strptime(mijoz_data['chiqish_sanasi'], "%Y-%m-%d") + timedelta(days=qoshimcha_kun)
                        q_sum = mijoz_data['kunlik_narx'] * qoshimcha_kun
                        c.execute("UPDATE bronlar SET kunlar=kunlar+?, qoldiq=qoldiq+?, jami_summa=jami_summa+?, faktik_narx=faktik_narx+?, chiqish_sanasi=?, holat='Qarzdorlik' WHERE mijoz_id=?", (qoshimcha_kun, q_sum, q_sum, q_sum, yangi_chiqish.strftime("%Y-%m-%d"), m_id))
                        conn.commit()
                        jurnalga_yozish(m_id, xodim_ismi, "Muddat cho'zildi", f"+{qoshimcha_kun} kun.")
                        st.success("Muddat muvaffaqiyatli cho'zildi!")
                        st.rerun()

            with m2:
                st.warning("💳 Qarzni yopish")
                qarzdorlar = df[(df['qoldiq'] > 0) & (df['holat'] != 'Chiqib ketgan')]
                if not qarzdorlar.empty:
                    tanlangan_qarz = st.selectbox("Qarzdor mijoz:", qarzdorlar['mijoz_id'] + " - " + qarzdorlar['mijoz'])
                    q_id = tanlangan_qarz.split(" - ")[0]
                    tolov_sum = st.number_input("Olinayotgan summa:", value=int(qarzdorlar[qarzdorlar['mijoz_id'] == q_id]['qoldiq'].values[0]), step=5000)
                    t_shakl = st.selectbox("Qarz To'lov shakli", ["Naqd", "Karta", "Onlayn"])
                    t_tafsiloti = st.selectbox("Qarz To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
                    if t_tafsiloti == "Boshqa":
                        qarz_izoh = st.text_input("Qaysi turda to'landi? (Izoh yozing):", placeholder="Masalan: Payme...")
                        if qarz_izoh: t_tafsiloti = f"Boshqa ({qarz_izoh})"
                    
                    if st.button("To'lovni kiritish"):
                        c.execute("UPDATE bronlar SET tolagan_summa=tolagan_summa+?, qoldiq=qoldiq-?, tolov_turi=?, tolov_tafsiloti=? WHERE mijoz_id=?", (tolov_sum, tolov_sum, t_shakl, t_tafsiloti, q_id))
                        c.execute("UPDATE bronlar SET holat='To''langan' WHERE mijoz_id=? AND qoldiq<=0", (q_id,))
                        conn.commit()
                        jurnalga_yozish(q_id, xodim_ismi, "Qarz yopildi", f"Summa: {tolov_sum:,.0f} ({t_tafsiloti})")
                        st.success("To'lov qabul qilindi!")
                        st.rerun()

# ----------------------------------------------------
# TAB MARKET 
# ----------------------------------------------------
if t_market:
    with t_market:
        st.header("🛒 Mini-Market (Savdo va Hisobot)")
        tab_sotuv, tab_tarix = st.tabs(["🛒 Kassa (Sotish)", "📊 Savdolar Tarixi"])
        
        with tab_sotuv:
            mahsulotlar = pd.read_sql_query("SELECT * FROM mahsulotlar WHERE qoldiq > 0", conn)
            if mahsulotlar.empty: st.warning("⚠️ Omborda sotishga mahsulot yo'q.")
            else:
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    mahsulotlar['Toliq_Nomi'] = mahsulotlar.apply(lambda row: f"{row['nomi']} ({row['hajmi']})" if row['hajmi'] else row['nomi'], axis=1)
                    kat_tanlov_m = st.selectbox("1. Kategoriya:", mahsulotlar['kategoriya'].unique().tolist())
                    filtr_kat = mahsulotlar[mahsulotlar['kategoriya'] == kat_tanlov_m]
                    sub_tanlov_m = st.selectbox("2. Turi:", filtr_kat['sub_kategoriya'].unique().tolist())
                    filtr_sub = filtr_kat[filtr_kat['sub_kategoriya'] == sub_tanlov_m]
                    
                    tanlangan_tovar_toliq = st.selectbox("3. Mahsulotni tanlang:", filtr_sub['Toliq_Nomi'].tolist())
                    tanlangan_qator = filtr_sub[filtr_sub['Toliq_Nomi'] == tanlangan_tovar_toliq].iloc[0]
                    tovar_narxi = tanlangan_qator['narxi']
                    maks_qoldiq = tanlangan_qator['qoldiq']
                    asl_tovar_nomi = tanlangan_qator['nomi']
                    
                    miqdor = st.number_input(f"4. Miqdori (Omborda {maks_qoldiq} ta bor):", min_value=1, max_value=int(maks_qoldiq), value=1)
                    jami_sum = miqdor * tovar_narxi
                    
                with col_m2:
                    st.info(f"🧾 **To'lanadigan summa:** {jami_sum:,.0f} UZS")
                    tolov_usuli = st.radio("5. To'lov turi:", ["💵 Darhol To'lov", "🏨 Xona qarziga yozish"])
                    m_tafsiloti = ""
                    if tolov_usuli == "💵 Darhol To'lov":
                        m_tafsiloti = st.selectbox("Qaysi usulda to'landi?", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
                        if m_tafsiloti == "Boshqa":
                            m_izoh = st.text_input("Izoh yozing:", placeholder="Payme, O'tkazma...")
                            if m_izoh: m_tafsiloti = f"Boshqa ({m_izoh})"
                    
                    faol_bronlar = pd.read_sql_query("SELECT mijoz_id, mijoz, xona FROM bronlar WHERE holat != 'Chiqib ketgan'", conn)
                    tanlangan_mijoz_id = None
                    if tolov_usuli == "🏨 Xona qarziga yozish":
                        if faol_bronlar.empty: st.error("Hozircha xonada faol mijozlar yo'q.")
                        else:
                            mijoz_qator = st.selectbox("6. Qaysi mijozga?", faol_bronlar['mijoz'] + " (" + faol_bronlar['xona'] + ") - ID: " + faol_bronlar['mijoz_id'])
                            tanlangan_mijoz_id = mijoz_qator.split("ID: ")[1]
                            xaridor_nomi = mijoz_qator.split(" (")[0]
                            m_tafsiloti = "Xona qarziga"
                    else: xaridor_nomi = "Umumiy xaridor"
                        
                    if st.button("🛒 SOTISH", type="primary", use_container_width=True):
                        c.execute("UPDATE mahsulotlar SET qoldiq = qoldiq - ? WHERE nomi = ? AND kategoriya = ? AND sub_kategoriya = ?", (miqdor, asl_tovar_nomi, kat_tanlov_m, sub_tanlov_m))
                        c.execute("INSERT INTO savdolar (sana, mahsulot_nomi, xaridor, miqdor, jami_summa, tolov_turi, xodim, tolov_tafsiloti) VALUES (?,?,?,?,?,?,?,?)",
                                  (bugungi_sana, tanlangan_tovar_toliq, xaridor_nomi, miqdor, jami_sum, tolov_usuli.split(" ")[1], xodim_ismi, m_tafsiloti))
                        if tanlangan_mijoz_id:
                            c.execute("UPDATE bronlar SET jami_summa = jami_summa + ?, faktik_narx = faktik_narx + ?, qoldiq = qoldiq + ?, holat = 'Qarzdorlik' WHERE mijoz_id = ?", (jami_sum, jami_sum, jami_sum, tanlangan_mijoz_id))
                            jurnalga_yozish(tanlangan_mijoz_id, xodim_ismi, "Market qarz", f"{miqdor} ta {tanlangan_tovar_toliq}. Summa: {jami_sum:,.0f} UZS")
                        else:
                            jurnalga_yozish("Market (Sotuv)", xodim_ismi, "Naqd Savdo", f"{miqdor} ta {tanlangan_tovar_toliq} sotildi. Summa: {jami_sum:,.0f} UZS ({m_tafsiloti})")
                        conn.commit()
                        st.success(f"✅ {miqdor} ta {tanlangan_tovar_toliq} sotildi!")
                        st.rerun()

        with tab_tarix:
            df_savdo = pd.read_sql_query("SELECT * FROM savdolar ORDER BY id DESC", conn)
            if not df_savdo.empty:
                df_savdo_korsatish = df_savdo[['sana', 'mahsulot_nomi', 'xaridor', 'miqdor', 'jami_summa', 'tolov_tafsiloti', 'xodim']].copy()
                df_savdo_korsatish.columns = ['Sana', 'Mahsulot', 'Xaridor', 'Miqdor', 'Jami Summa', 'To\'lov Turi', 'Sotuvchi (Admin)']
                df_savdo_korsatish['Jami Summa'] = df_savdo_korsatish['Jami Summa'].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(df_savdo_korsatish, use_container_width=True, hide_index=True)
            else:
                st.info("Hozircha marketda savdo amalga oshirilmagan.")

# ----------------------------------------------------
# TAB OMBOR
# ----------------------------------------------------
if t_ombor:
    with t_ombor:
        st.header("📦 Sklad (Ombor) Boshqaruvi")
        tab_list, tab_add = st.tabs(["📋 Mahsulotlar ro'yxati", "➕ Yangi tovar kiritish"])
        
        with tab_add:
            st.subheader("Yangi mahsulot kiritish")
            c1, c2 = st.columns(2)
            with c1:
                kat_tanlov = st.selectbox("1. Kategoriya:", ["Ichimliklar", "Gigiyena vositalari", "Boshqa", "✏️ Boshqa (Qo'lda kiritish)"])
                kat_nomi = st.text_input("Kategoriyani yozing:") if kat_tanlov == "✏️ Boshqa (Qo'lda kiritish)" else kat_tanlov
                if kat_nomi == "Ichimliklar": sub_tanlov = st.selectbox("2. Turi:", ["Banichniy ichimliklar", "Gazli shirin suv (Cola, Fanta...)", "Soklar", "Mineral suv (Gazli/Gazsiz)", "✏️ Boshqa (Qo'lda kiritish)"])
                elif kat_nomi == "Gigiyena vositalari": sub_tanlov = st.selectbox("2. Turi:", ["Komplekt", "Alohida", "✏️ Boshqa (Qo'lda kiritish)"])
                else: sub_tanlov = st.selectbox("2. Turi:", ["Boshqa", "✏️ Boshqa (Qo'lda kiritish)"])
                sub_kat_nomi = st.text_input("Turni yozing:") if sub_tanlov == "✏️ Boshqa (Qo'lda kiritish)" else sub_tanlov
                tov_nomi = st.text_input("3. Mahsulot nomi (masalan, Coca-Cola):")
            
            with c2:
                hajm_tanlov = st.selectbox("4. Hajmi / O'lchami:", ["0.5 L", "1.0 L", "1.5 L", "Standart (Hajmsiz)", "✏️ Boshqa (Qo'lda kiritish)"])
                hajmi = st.text_input("Hajmni yozing:") if hajm_tanlov == "✏️ Boshqa (Qo'lda kiritish)" else ("" if hajm_tanlov == "Standart (Hajmsiz)" else hajm_tanlov)
                tov_narxi = st.number_input("5. Sotilish narxi (UZS):", min_value=1000, step=1000)
                tov_soni = st.number_input("6. Skladga kelgan miqdori (dona):", min_value=1, step=1)
            
            if st.button("Skladga Qo'shish", type="primary", use_container_width=True):
                if not tov_nomi: st.error("Mahsulot nomini kiriting!")
                else:
                    c.execute("SELECT qoldiq FROM mahsulotlar WHERE nomi=? AND hajmi=?", (tov_nomi, hajmi))
                    if c.fetchone():
                        c.execute("UPDATE mahsulotlar SET qoldiq = qoldiq + ?, narxi = ? WHERE nomi = ? AND hajmi = ?", (tov_soni, tov_narxi, tov_nomi, hajmi))
                        st.success(f"{tov_nomi} qoldig'iga qo'shildi!")
                        jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Qoldiq to'ldirildi", f"{tov_nomi} ({hajmi}) ga {tov_soni} ta qo'shildi. Narx: {tov_narxi:,.0f} UZS")
                    else:
                        c.execute("INSERT INTO mahsulotlar (nomi, kategoriya, sub_kategoriya, hajmi, narxi, qoldiq, izoh) VALUES (?,?,?,?,?,?,?)", 
                                  (tov_nomi, kat_nomi, sub_kat_nomi, hajmi, tov_narxi, tov_soni, ""))
                        st.success(f"Yangi {tov_nomi} omborga qo'shildi!")
                        jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Yangi tovar keldi", f"{tov_nomi} ({hajmi}) {tov_soni} ta kiritildi. Narx: {tov_narxi:,.0f} UZS")
                    conn.commit()
                    st.rerun()
                    
        with tab_list:
            df_mahsulot = pd.read_sql_query("SELECT nomi, hajmi, kategoriya, sub_kategoriya, narxi, qoldiq, izoh FROM mahsulotlar ORDER BY qoldiq ASC", conn)
            df_mahsulot['izoh'] = df_mahsulot['izoh'].fillna('')
            if not df_mahsulot.empty: 
                df_mahsulot.columns = ['Nomi', 'Hajmi', 'Kategoriya', 'Sub-kat', 'Narxi', 'Qoldiq', 'Izoh']
                df_mahsulot['Narxi'] = df_mahsulot['Narxi'].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(df_mahsulot, use_container_width=True, hide_index=True)
            else: st.info("Sklad bo'sh.")

# ----------------------------------------------------
# TAB 5: CEO PANEL (YANGI MUKAMMAL AUDIT BILAN)
# ----------------------------------------------------
if t5:
    with t5:
        st.markdown("---")
        df_admin = pd.read_sql_query("SELECT * FROM bronlar ORDER BY id DESC", conn)
        tab_a, tab_b, tab_c, tab_d = st.tabs(["🚪 Checkout", "🕵️ Batafsil Audit", "🗑️ O'chirish", "📝 Maxsus Izohlar"])
        
        with tab_a:
            st.subheader("🚪 Mijozni chiqarish (Checkout)")
            faollar = df_admin[df_admin['holat'] != 'Chiqib ketgan']
            if not faollar.empty:
                korsatkich = faollar['mijoz_id'] + " - " + faollar['xona'] + " (Chiqish: " + faollar['chiqish_sanasi'] + " 12:00)"
                chiq_id_toliq = st.selectbox("Xonani bo'shatadigan mijoz:", korsatkich)
                c_id = chiq_id_toliq.split(" - ")[0]
                if faollar[faollar['mijoz_id'] == c_id]['qoldiq'].values[0] > 0: st.error("⚠️ Qarz yopilmaguncha chiqarolmaysiz.")
                elif st.button("Mijozni Arxivlash"):
                    c.execute("UPDATE bronlar SET holat = 'Chiqib ketgan', chiqish_sanasi = ? WHERE mijoz_id = ?", (bugungi_sana, c_id))
                    conn.commit()
                    jurnalga_yozish(c_id, xodim_ismi, "Checkout", "Mijoz xonani topshirdi va tizimdan chiqarildi")
                    st.success("Mijoz arxivlandi!")
                    st.rerun()
        
        with tab_b:
            st.subheader("🕵️ Barcha O'zgarishlar Tarixi (Kuzatuv Jurnali)")
            df_audit = pd.read_sql_query("SELECT * FROM audit_log ORDER BY id DESC", conn)
            if not df_audit.empty: 
                df_a_korsatish = df_audit[['vaqt', 'mijoz_id', 'xodim', 'harakat', 'tafsilot']].copy()
                df_a_korsatish.columns = ['Sana va Vaqt', 'Obyekt / ID', 'Boshqaruvchi Xodim', 'Harakat Turi', 'Batafsil ma\'lumot']
                st.dataframe(df_a_korsatish, use_container_width=True, hide_index=True)
            else: st.info("Hozircha tizimda o'zgarishlar qayd etilmagan.")
            
        with tab_c:
            st.error("🚨 XAVFLI ZONA")
            if not df_admin.empty:
                del_id = st.selectbox("O'chiriladigan ID:", df_admin['mijoz_id'] + " - " + df_admin['mijoz'])
                if st.button("⚠️ Butunlay o'chirish"):
                    och_id = del_id.split(" - ")[0]
                    c.execute("DELETE FROM bronlar WHERE mijoz_id = ?", (och_id,))
                    conn.commit()
                    jurnalga_yozish(och_id, xodim_ismi, "O'chirish (Xavfli)", "Mijoz ma'lumotlari bazadan butunlay o'chirildi")
                    st.success("O'chirildi!")
                    st.rerun()
                    
        with tab_d:
            st.subheader("📝 Baza ma'lumotlariga maxfiy izoh yozish")
            st.markdown("Bu yerdagi izohlarni faqat CEO yoza oladi. Ular adminlarga asosiy jadvallarda ko'rinadi.")
            izoh_tanlov = st.radio("Qaysi bazaga izoh yozasiz?", ["Mijozlar (Bronlar)", "Sklad (Mahsulotlar)"], horizontal=True)
            if izoh_tanlov == "Mijozlar (Bronlar)":
                df_b = pd.read_sql_query("SELECT mijoz_id, mijoz, xona, izoh FROM bronlar WHERE holat!='Chiqib ketgan'", conn)
                if not df_b.empty:
                    t_mijoz = st.selectbox("Mijozni tanlang:", df_b['mijoz_id'] + " - " + df_b['mijoz'] + " (" + df_b['xona'] + ")")
                    m_id_izoh = t_mijoz.split(" - ")[0]
                    eski_izoh = df_b[df_b['mijoz_id'] == m_id_izoh]['izoh'].values[0]
                    if pd.isna(eski_izoh): eski_izoh = ""
                    yangi_izoh = st.text_area("Izoh yozing:", value=str(eski_izoh))
                    if st.button("Izohni Saqlash (Mijoz)"):
                        c.execute("UPDATE bronlar SET izoh=? WHERE mijoz_id=?", (yangi_izoh, m_id_izoh))
                        conn.commit()
                        jurnalga_yozish(m_id_izoh, "CEO", "Maxfiy Izoh yozildi", f"Yangi izoh: {yangi_izoh}")
                        st.success("Mijozga izoh qo'shildi!")
                        st.rerun()
                else: st.info("Faol mijozlar yo'q.")
            else:
                df_m = pd.read_sql_query("SELECT id, nomi, hajmi, qoldiq, izoh FROM mahsulotlar", conn)
                if not df_m.empty:
                    df_m['korsatkich'] = df_m['nomi'] + " " + df_m['hajmi'] + " (" + df_m['qoldiq'].astype(str) + " ta)"
                    t_mahs = st.selectbox("Mahsulotni tanlang:", df_m['korsatkich'])
                    m_id_m = df_m[df_m['korsatkich'] == t_mahs]['id'].values[0]
                    eski_izoh_m = df_m[df_m['id'] == m_id_m]['izoh'].values[0]
                    if pd.isna(eski_izoh_m): eski_izoh_m = ""
                    yangi_izoh_m = st.text_area("Izoh yozing:", value=str(eski_izoh_m))
                    if st.button("Izohni Saqlash (Mahsulot)"):
                        c.execute("UPDATE mahsulotlar SET izoh=? WHERE id=?", (yangi_izoh_m, int(m_id_m)))
                        conn.commit()
                        jurnalga_yozish(f"Sklad Mahsuloti (ID:{m_id_m})", "CEO", "Maxfiy Izoh yozildi", f"Yangi izoh: {yangi_izoh_m}")
                        st.success("Mahsulotga izoh qo'shildi!")
                        st.rerun()
                else: st.info("Skladda mahsulot yo'q.")

# ----------------------------------------------------
# TAB 6: SOZLAMALAR
# ----------------------------------------------------
if t6:
    with t6:
        st.header("⚙️ Shaxsiy ma'lumotlarni o'zgartirish")
        st.markdown(f"**Sizning profilingiz:** {rol_nomi}")
        c.execute("SELECT login FROM users WHERE role=?", (st.session_state.role,))
        res = c.fetchone()
        joriy_login = res[0] if res else ""
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            with st.form("settings_form"):
                yangi_login = st.text_input("Yangi login (nom):", value=joriy_login)
                yangi_parol = st.text_input("Yangi parol:", type="password")
                parol_tasdiq = st.text_input("Yangi parolni tasdiqlang:", type="password")
                if st.form_submit_button("Ma'lumotlarni saqlash", type="primary"):
                    if yangi_parol and yangi_parol != parol_tasdiq: st.error("⚠️ Parollar mos tushmadi!")
                    else:
                        if yangi_parol: c.execute("UPDATE users SET login=?, parol=? WHERE role=?", (yangi_login, yangi_parol, st.session_state.role))
                        else: c.execute("UPDATE users SET login=? WHERE role=?", (yangi_login, st.session_state.role))
                        conn.commit()
                        jurnalga_yozish("Tizim Sozlamalari", st.session_state.role.upper(), "Login/Parol", "Foydalanuvchi ma'lumotlari o'zgartirildi")
                        st.session_state.logged_in = False
                        st.session_state.role = None
                        st.rerun()