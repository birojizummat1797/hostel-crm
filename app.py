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
        mijoz_id TEXT, jinsi TEXT,
        sana TEXT, tomon TEXT, xona TEXT, xona_turi TEXT,
        mijoz TEXT, toifa TEXT, odam_soni INTEGER, muddat TEXT, kunlar INTEGER,
        kunlik_narx REAL, jami_summa REAL, faktik_narx REAL, tolagan_summa REAL,
        qoldiq REAL, tolov_turi TEXT, tolov_tafsiloti TEXT, holat TEXT,
        kirish_sanasi TEXT, chiqish_sanasi TEXT,
        bron_turi TEXT DEFAULT 'Hozir kirish'
    )
''')

try: c.execute("ALTER TABLE bronlar ADD COLUMN bron_turi TEXT DEFAULT 'Hozir kirish'")
except: pass

# --- YANGI JADVALLAR (MINI-MARKET UCHUN) ---
c.execute('''
    CREATE TABLE IF NOT EXISTS mahsulotlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT, kategoriya TEXT, narxi REAL, qoldiq INTEGER
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS savdolar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sana TEXT, mahsulot_nomi TEXT, xaridor TEXT, miqdor INTEGER,
        jami_summa REAL, tolov_turi TEXT, xodim TEXT
    )
''')
# ------------------------------------------

c.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vaqt TEXT, mijoz_id TEXT, xodim TEXT, harakat TEXT, tafsilot TEXT
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        role TEXT PRIMARY KEY, login TEXT, parol TEXT
    )
''')

c.execute("SELECT COUNT(*) FROM users")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO users (role, login, parol) VALUES ('admin', 'admin', '123')")
    c.execute("INSERT INTO users (role, login, parol) VALUES ('ceo', 'ceo', '777')")
conn.commit()

def jurnalga_yozish(mijoz_id, xodim, harakat, tafsilot):
    hozir = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_log (vaqt, mijoz_id, xodim, harakat, tafsilot) VALUES (?,?,?,?,?)",
              (hozir, mijoz_id, xodim, harakat, tafsilot))
    conn.commit()

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Hisobot')
    return output.getvalue()

def rangla_jadval(row):
    holat_val = row.get('Holat') or row.get('holat')
    qoldiq_val = row.get('Qoldiq') if 'Qoldiq' in row else row.get('qoldiq', 0)
    
    if holat_val == 'Chiqib ketgan':
        return ['background-color: #f1f5f9; color: #94a3b8'] * len(row)
    elif qoldiq_val > 0:
        return ['background-color: #fef2f2; color: #b91c1c'] * len(row)
    else:
        return ['background-color: #f0fdf4; color: #15803d'] * len(row)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'reset_key' not in st.session_state:
    st.session_state.reset_key = 0

# ==========================================
# 2. XONALAR VA MANTIQ
# ==========================================
XONALAR = {
    "Chap tomon": {"1-xona": (4, 100000), "2-xona": (4, 100000), "3-xona": (4, 100000), "4-xona": (4, 100000), 
                   "5-xona": (4, 100000), "6-xona": (4, 100000), "7-xona": (2, 150000), "8-xona": (4, 100000), 
                   "9-xona": (4, 100000), "10-xona": (3, 110000), "11-xona": (2, 150000), "12-xona": (4, 100000), 
                   "13-xona": (4, 100000), "14-xona": (2, 150000)},
    "O'rtadagi": {f"{i}-xona": (2, 250000) for i in range(15, 22)},
    "O'ng tomon": {"22-xona": (2, 150000), "23-xona": (4, 100000), "24-xona": (4, 100000), "25-xona": (4, 100000), 
                   "26-xona": (4, 100000), "27-xona": (4, 100000), "28-xona": (2, 150000), "29-xona": (4, 100000), 
                   "30-xona": (4, 100000), "31-xona": (4, 100000), "32-xona": (2, 150000), "33-xona": (4, 100000), 
                   "34-xona": (4, 100000), "35-xona": (4, 100000), "36-xona": (4, 100000)}
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
    return f"""
    <div style="background: linear-gradient(135deg, {bg_color} 0%, {bg_color}dd 100%); padding: 15px; border-radius: 12px; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.15); margin-bottom: 20px; font-family: sans-serif;">
        <div style="font-size: 14px; font-weight: 600; opacity: 0.9; margin-bottom: 5px;">{icon} {title}</div>
        <div style="font-size: 26px; font-weight: bold;">{value}</div>
    </div>
    """

# ==========================================
# 3. UI VA LOGIN OYNASI
# ==========================================
st.set_page_config(page_title="Yangi Sergeli Hostel CRM", layout="wide")

st.markdown("""
<style>
div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e6ed; padding: 15px 20px; border-radius: 12px; border-left: 6px solid #4CAF50; box-shadow: 2px 4px 15px rgba(0,0,0,0.05); transition: transform 0.2s ease-in-out; }
div[data-testid="metric-container"]:hover { transform: translateY(-3px); box-shadow: 2px 6px 20px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #2E3B55; margin-top: 50px;'>🏨 YSH CRM Tizimi</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Avtorizatsiyadan o'ting</h4>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("login_form"):
            login_input = st.text_input("Login", placeholder="Foydalanuvchi nomini kiriting...")
            parol_input = st.text_input("Parol", type="password", placeholder="Maxfiy parolni kiriting...")
            submit_login = st.form_submit_button("Kirish", use_container_width=True, type="primary")
            
            if submit_login:
                c.execute("SELECT role FROM users WHERE login=? AND parol=?", (login_input, parol_input))
                user = c.fetchone()
                if user:
                    st.session_state.logged_in = True
                    st.session_state.role = user[0]
                    st.rerun()
                else:
                    st.error("Login yoki parol noto'g'ri!")
    st.stop()

# ==========================================
# 4. ASOSIY DASTUR
# ==========================================
st.sidebar.title("🏨 Boshqaruv")
rol_nomi = "Boshqaruvchi (CEO)" if st.session_state.role == "ceo" else "Front-Ofis Xodimi"
st.sidebar.success(f"Xush kelibsiz, {rol_nomi}!")

if st.sidebar.button("🚪 Tizimdan chiqish", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.title("🏨 Yangi Sergeli Hostel CRM")
bugungi_sana = datetime.today().strftime("%Y-%m-%d")
k = str(st.session_state.reset_key)
xodim_ismi = "CEO" if st.session_state.role == "ceo" else "Front-Ofis Admini"

if st.session_state.role == "ceo":
    tabs = st.tabs(["📈 Dashboard", "📝 Qabul", "🔲 Shaxmatka", "💼 Mijozlar", "🛒 Kassa & Market", "📦 Sklad", "👑 CEO Panel", "⚙️ Sozlamalar"])
    t1, t2, t3, t4, t_market, t_ombor, t5, t6 = tabs
else:
    tabs = st.tabs(["📈 Dashboard", "📝 Qabul", "🔲 Shaxmatka", "💼 Mijozlar", "🛒 Kassa & Market", "📦 Sklad", "⚙️ Sozlamalar"])
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
            umumiy_tushum = umumiy_kassa_yotoq + umumiy_kassa_market
            umumiy_qarz = df_barcha[df_barcha['qoldiq'] > 0]['qoldiq'].sum()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: st.markdown(chiroyli_kartochka("👥", "Hozirgi mehmon", f"{len(faol_mijozlar)}", "#8b5cf6"), unsafe_allow_html=True)
            with c2: st.markdown(chiroyli_kartochka("📥", "Kelganlar", f"{len(bugun_kelganlar)}", "#3b82f6"), unsafe_allow_html=True)
            with c3: st.markdown(chiroyli_kartochka("💰", "Yotoq Tushumi", f"{umumiy_kassa_yotoq:,.0f}", "#f59e0b"), unsafe_allow_html=True)
            with c4: st.markdown(chiroyli_kartochka("🛒", "Market Tushumi", f"{umumiy_kassa_market:,.0f}", "#10b981"), unsafe_allow_html=True)
            with c5: st.markdown(chiroyli_kartochka("⚠️", "Umumiy Qarz", f"{umumiy_qarz:,.0f}", "#ef4444"), unsafe_allow_html=True)
            
            # SKLAD OGOHLANTIRISHI (Qoldiq kamayganda)
            df_mahsulotlar = pd.read_sql_query("SELECT * FROM mahsulotlar WHERE qoldiq <= 5", conn)
            if not df_mahsulotlar.empty:
                st.error(f"🚨 **DIQQAT: Quyidagi {len(df_mahsulotlar)} ta mahsulot omborda tugayapti!**")
                tugayotgan = ", ".join([f"{r['nomi']} ({r['qoldiq']} ta qoldi)" for _, r in df_mahsulotlar.iterrows()])
                st.warning(f"🛒 {tugayotgan}")

            st.markdown("<br>", unsafe_allow_html=True)
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📅 Kirishlar dinamikasi")
                dinamika = df_barcha.groupby('kirish_sanasi').size().reset_index(name='Mijozlar soni')
                if not dinamika.empty: st.line_chart(dinamika.set_index('kirish_sanasi'), color="#3b82f6")
            with g2:
                st.subheader("🌍 Mijozlar toifasi")
                toifa_stat = faol_mijozlar['toifa'].value_counts().reset_index()
                toifa_stat.columns = ['Toifa', 'Soni']
                if not toifa_stat.empty: st.bar_chart(toifa_stat.set_index('Toifa'), color="#10b981")
        else:
            st.info("Hozircha bazada ma'lumot yo'q.")

# ----------------------------------------------------
# TAB 2: QABUL VA BRON 
# ----------------------------------------------------
if t2:
    with t2:
        col_type = st.columns(1)[0]
        bron_turi = col_type.radio("📌 Ro'yxatdan o'tish turi:", ["Hozir qabul qilish (Kirish)", "Oldindan band qilish (Bron)"], horizontal=True, key=f"bturi_{k}")
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
            
            c.execute("SELECT SUM(odam_soni) FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona, chiqish_sanasi.strftime("%Y-%m-%d"), kirish_sanasi.strftime("%Y-%m-%d")))
            band = c.fetchone()[0] or 0
            bosh_joy = XONALAR[tomon][xona][0] - band
            
            joy_bor = True
            if bosh_joy <= 0: st.error(f"⚠️ {xona} band!"); joy_bor = False
            elif odam_soni > bosh_joy: st.error(f"⚠️ {bosh_joy} ta joy qolgan!"); joy_bor = False
            else: st.success(f"✅ {bosh_joy} ta bo'sh joy bor.")

        kunlik_stavka, standart_jami = narx_hisobla(tomon, xona, toifa, odam_soni, kunlar)
        with col3:
            st.info(f"🧾 **Standart jami:** {standart_jami:,.0f} so'm")
            if st.checkbox("⚙️ Admin maxsus narx", key=f"maxsus_{k}"): yakuniy_narx = st.number_input("KUNLIK narx:", value=int(kunlik_stavka), step=5000, key=f"ynarx_{k}") * kunlar
            else: yakuniy_narx = standart_jami
                
            st.markdown(f"### 💰 JAMI: {yakuniy_narx:,.0f} so'm")
            tolangan = st.number_input("To'lanayotgan summa:", value=0, step=10000, key=f"tol_{k}")
            tolov_shakli = st.selectbox("To'lov shakli", ["Naqd", "Karta", "Onlayn"])
            tolov_turi = st.selectbox("To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo"])

        qoldiq = yakuniy_narx - tolangan
        holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"

        st.divider()
        if joy_bor and st.button("✅ Bazaga saqlash", type="primary", use_container_width=True):
            if mijoz_ism.strip():
                yangi_id = id_yaratish(jinsi, kirish_sanasi, toifa)
                saq_turi = 'Hozir kirish' if bron_turi == "Hozir qabul qilish (Kirish)" else 'Bron'
                
                c.execute('''INSERT INTO bronlar (mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar, kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti, holat, kirish_sanasi, chiqish_sanasi, bron_turi) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (yangi_id, jinsi, datetime.now().strftime("%Y-%m-%d"), tomon, xona, "", mijoz_ism, toifa, odam_soni, muddat, kunlar, kunlik_stavka, standart_jami, yakuniy_narx, tolangan, qoldiq, tolov_shakli, tolov_turi, holat, kirish_sanasi.strftime("%Y-%m-%d"), chiqish_sanasi.strftime("%Y-%m-%d"), saq_turi))
                conn.commit()
                jurnalga_yozish(yangi_id, xodim_ismi, "Yangi " + saq_turi, f"To'ladi: {tolangan:,.0f}")
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
        
        df_matrix = pd.DataFrame(matrix)
        grid_response = st.dataframe(df_matrix, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        st.markdown("---")
        st.subheader("🔍 Xona ichidagi aniq holat")
        
        selected_rows = grid_response.selection.rows
        if selected_rows:
            tanlangan_qator_matni = df_matrix.iloc[selected_rows[0]]["Xona"]
            xona_nomi = tanlangan_qator_matni.split(" | ")[1] if " | " in tanlangan_qator_matni else tanlangan_qator_matni
            xona_nomi = xona_nomi.split(" (")[0].strip()
            
            umumiy_sigim = xona_sigimini_ol(xona_nomi)
            bugun = datetime.today().strftime("%Y-%m-%d")
            c.execute("SELECT mijoz, jinsi, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona_nomi, bugun, bugun))
            bugun_ichidagilar = c.fetchall()
            
            if not bugun_ichidagilar: st.success(f"🟢 **XONA TO'LIQ BO'SH — {xona_nomi} ({umumiy_sigim} kishilik)**")
            else:
                band_qilingan_joylar = sum([m[5] for m in bugun_ichidagilar])
                qoldiq_joy = umumiy_sigim - band_qilingan_joylar
                if qoldiq_joy > 0: st.warning(f"🟡 **XONADA MIJOZLAR BOR — Qoldiq o'rin: {qoldiq_joy} ta. {xona_nomi}**")
                else: st.error(f"🔴 **XONA TO'LIQ BAND — {xona_nomi}**")

                for m in bugun_ichidagilar:
                    st.markdown(f"- **{m[0]}** (🛫 Chiqish: {m[2]} 12:00) | Qarz: {m[4]:,.0f} UZS")
        else:
            st.info("👆 Ma'lumotni ko'rish uchun yuqoridagi jadvaldan biror qatorni ustiga bosing.")

# ----------------------------------------------------
# TAB 4: FRONT-OFIS
# ----------------------------------------------------
if t4:
    with t4:
        st.header("💼 Mijozlar va Boshqaruv (Front-Ofis)")
        # ... (Oldingi kodlardagidek qoladi, arxivlash va cho'zish amallari)
        st.info("Bu bo'limda mijozlar ro'yxati, muddat cho'zish va qarz yopish ishlari bajariladi.")

# ----------------------------------------------------
# TAB MARKET (YANGI)
# ----------------------------------------------------
if t_market:
    with t_market:
        st.header("🛒 Mini-Market va Kassa")
        
        mahsulotlar = pd.read_sql_query("SELECT * FROM mahsulotlar WHERE qoldiq > 0", conn)
        
        if mahsulotlar.empty:
            st.warning("⚠️ Hozircha omborda sotishga mahsulot yo'q. 'Sklad' bo'limidan mahsulot qo'shing.")
        else:
            kategoriyalar = mahsulotlar['kategoriya'].unique().tolist()
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                tanlangan_kat = st.selectbox("1. Kategoriyani tanlang:", kategoriyalar)
                filtr_mahsulot = mahsulotlar[mahsulotlar['kategoriya'] == tanlangan_kat]
                
                tovar_nomlari = filtr_mahsulot['nomi'].tolist()
                tanlangan_tovar = st.selectbox("2. Mahsulotni tanlang:", tovar_nomlari)
                
                tovar_narxi = filtr_mahsulot[filtr_mahsulot['nomi'] == tanlangan_tovar]['narxi'].values[0]
                maksimal_qoldiq = filtr_mahsulot[filtr_mahsulot['nomi'] == tanlangan_tovar]['qoldiq'].values[0]
                
                miqdor = st.number_input(f"3. Miqdori (Omborda {maksimal_qoldiq} ta bor):", min_value=1, max_value=int(maksimal_qoldiq), value=1)
                jami_sum = miqdor * tovar_narxi
                
            with col_m2:
                st.info(f"🧾 **To'lanadigan summa:** {jami_sum:,.0f} UZS")
                tolov_usuli = st.radio("4. To'lov turi:", ["💵 Darhol To'lov (Naqd/Karta)", "🏨 Xona qarziga yozish (Checkoutgacha)"])
                
                faol_bronlar = pd.read_sql_query("SELECT mijoz_id, mijoz, xona FROM bronlar WHERE holat != 'Chiqib ketgan'", conn)
                tanlangan_mijoz_id = None
                
                if tolov_usuli == "🏨 Xona qarziga yozish (Checkoutgacha)":
                    if faol_bronlar.empty:
                        st.error("Hozircha xonada faol mijozlar yo'q.")
                    else:
                        mijoz_qator = st.selectbox("5. Qaysi mijozni hisobiga qo'shilsin?", faol_bronlar['mijoz'] + " (" + faol_bronlar['xona'] + ") - ID: " + faol_bronlar['mijoz_id'])
                        tanlangan_mijoz_id = mijoz_qator.split("ID: ")[1]
                        xaridor_nomi = mijoz_qator.split(" (")[0]
                else:
                    xaridor_nomi = "Umumiy xaridor (Tashqaridan)"
                    
                if st.button("🛒 SOTISH", type="primary", use_container_width=True):
                    # Ombordan ayirish
                    c.execute("UPDATE mahsulotlar SET qoldiq = qoldiq - ? WHERE nomi = ?", (miqdor, tanlangan_tovar))
                    
                    # Savdolar bazasiga yozish
                    c.execute("INSERT INTO savdolar (sana, mahsulot_nomi, xaridor, miqdor, jami_summa, tolov_turi, xodim) VALUES (?,?,?,?,?,?,?)",
                              (bugungi_sana, tanlangan_tovar, xaridor_nomi, miqdor, jami_sum, tolov_usuli.split(" ")[1], xodim_ismi))
                    
                    # Agar mijoz qarziga yozilsa, bronlar bazasini yangilash
                    if tanlangan_mijoz_id:
                        c.execute("UPDATE bronlar SET jami_summa = jami_summa + ?, faktik_narx = faktik_narx + ?, qoldiq = qoldiq + ?, holat = 'Qarzdorlik' WHERE mijoz_id = ?",
                                  (jami_sum, jami_sum, jami_sum, tanlangan_mijoz_id))
                        jurnalga_yozish(tanlangan_mijoz_id, xodim_ismi, "Marketdan Qarzga oldi", f"{miqdor} ta {tanlangan_tovar}. Summa: {jami_sum:,.0f} UZS")
                    
                    conn.commit()
                    st.success(f"✅ {miqdor} ta {tanlangan_tovar} muvaffaqiyatli sotildi!")
                    st.rerun()

# ----------------------------------------------------
# TAB OMBOR (YANGI)
# ----------------------------------------------------
if t_ombor:
    with t_ombor:
        st.header("📦 Sklad (Ombor) Boshqaruvi")
        
        tab_list, tab_add = st.tabs(["📋 Mahsulotlar ro'yxati va Sklad", "➕ Yangi tovar kiritish"])
        
        with tab_add:
            with st.form("yangi_tovar_form"):
                kat_nomi = st.selectbox("Kategoriya:", ["Ichimliklar", "Gigiyena vositalari", "Boshqa"])
                tov_nomi = st.text_input("Mahsulot nomi (masalan, Coca-Cola 0.5L):")
                tov_narxi = st.number_input("Sotilish narxi (UZS):", min_value=1000, step=1000)
                tov_soni = st.number_input("Skladga kelgan miqdori (dona):", min_value=1, step=1)
                
                if st.form_submit_button("Skladga Qo'shish"):
                    c.execute("SELECT qoldiq FROM mahsulotlar WHERE nomi=?", (tov_nomi,))
                    bor_tovar = c.fetchone()
                    if bor_tovar:
                        c.execute("UPDATE mahsulotlar SET qoldiq = qoldiq + ?, narxi = ? WHERE nomi = ?", (tov_soni, tov_narxi, tov_nomi))
                        st.success("Bordagi tovar ustiga qo'shildi!")
                    else:
                        c.execute("INSERT INTO mahsulotlar (nomi, kategoriya, narxi, qoldiq) VALUES (?,?,?,?)", (tov_nomi, kat_nomi, tov_narxi, tov_soni))
                        st.success("Yangi mahsulot omborga qo'shildi!")
                    conn.commit()
                    st.rerun()
                    
        with tab_list:
            df_mahsulot = pd.read_sql_query("SELECT nomi, kategoriya, narxi, qoldiq FROM mahsulotlar ORDER BY qoldiq ASC", conn)
            if not df_mahsulot.empty:
                st.dataframe(df_mahsulot.style.format({'narxi': '{:,.0f} UZS'}), use_container_width=True)
            else:
                st.info("Sklad bo'sh.")

# ----------------------------------------------------
# TAB 5: CEO PANEL
# ----------------------------------------------------
if t5:
    with t5:
        st.markdown("---")
        # (Oldingi checkout va o'chirish logikalari...)
        st.info("CEO Checkout va Audit bo'limi")