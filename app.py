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
        kirish_sanasi TEXT, chiqish_sanasi TEXT
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vaqt TEXT, mijoz_id TEXT, xodim TEXT, harakat TEXT, tafsilot TEXT
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        role TEXT PRIMARY KEY,
        login TEXT,
        parol TEXT
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
div[data-testid="metric-container"] {
    background-color: #ffffff; border: 1px solid #e0e6ed; padding: 15px 20px; border-radius: 12px;
    border-left: 6px solid #4CAF50; box-shadow: 2px 4px 15px rgba(0,0,0,0.05); transition: transform 0.2s ease-in-out;
}
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

t1, t2, t3, t4, t5, t6 = None, None, None, None, None, None

if st.session_state.role == "ceo":
    t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Aqlli Dashboard", "📝 Qabul va Bron", "🔲 Metro-Shaxmatka", "💼 Front-Ofis", "👑 CEO Paneli", "⚙️ Sozlamalar"])
else:
    t1, t2, t3, t4, t6 = st.tabs(["📈 Aqlli Dashboard", "📝 Qabul va Bron", "🔲 Metro-Shaxmatka", "💼 Front-Ofis (Boshqaruv)", "⚙️ Sozlamalar"])

# ----------------------------------------------------
# TAB 1: AQLLI DASHBOARD
# ----------------------------------------------------
if t1:
    with t1:
        st.header("📈 Hostel Analitikasi va Dashboard")
        df_barcha = pd.read_sql_query("SELECT * FROM bronlar", conn)
        
        if 'tolagan_summa' in df_barcha.columns: df_barcha['tolagan_summa'] = df_barcha['tolagan_summa'].fillna(0)
        if 'qoldiq' in df_barcha.columns: df_barcha['qoldiq'] = df_barcha['qoldiq'].fillna(0)

        if not df_barcha.empty:
            faol_mijozlar = df_barcha[df_barcha['holat'] != 'Chiqib ketgan']
            bugun_kelganlar = df_barcha[df_barcha['kirish_sanasi'] == bugungi_sana]
            bugun_ketadiganlar = df_barcha[df_barcha['chiqish_sanasi'] == bugungi_sana]
            umumiy_kassa = df_barcha['tolagan_summa'].sum()
            umumiy_qarz = df_barcha[df_barcha['qoldiq'] > 0]['qoldiq'].sum()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: st.markdown(chiroyli_kartochka("👥", "Hozirgi mehmon", f"{len(faol_mijozlar)}", "#8b5cf6"), unsafe_allow_html=True)
            with c2: st.markdown(chiroyli_kartochka("📥", "Kelganlar", f"{len(bugun_kelganlar)}", "#3b82f6"), unsafe_allow_html=True)
            with c3: st.markdown(chiroyli_kartochka("📤", "Ketadiganlar", f"{len(bugun_ketadiganlar)}", "#10b981"), unsafe_allow_html=True)
            with c4: st.markdown(chiroyli_kartochka("💰", "Sof Kassa", f"{umumiy_kassa:,.0f}", "#f59e0b"), unsafe_allow_html=True)
            with c5: st.markdown(chiroyli_kartochka("⚠️", "Umumiy Qarz", f"{umumiy_qarz:,.0f}", "#ef4444"), unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📅 Kirishlar dinamikasi")
                dinamika = df_barcha.groupby('kirish_sanasi').size().reset_index(name='Mijozlar soni')
                if not dinamika.empty: st.line_chart(dinamika.set_index('kirish_sanasi'), color="#3b82f6")
            with g2:
                st.subheader("🌍 Mijozlar toifasi (Segmentatsiya)")
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
        col1, col2, col3 = st.columns(3)
        with col1:
            mijoz_ism = st.text_input("Mijoz F.I.O / Telefon", key=f"ism_{k}")
            jinsi = st.radio("Jinsi", ["Erkak", "Ayol"], horizontal=True, key=f"jins_{k}")
            toifa = st.selectbox("Mijoz toifasi", ["O'zbekiston fuqarosi", "Chet el fuqarosi", "Talaba (Student)"], key=f"toifa_{k}")
            muddat = st.selectbox("Muddat turi", list(MUDDATLAR.keys()), key=f"muddat_{k}")
            kirish_sanasi = st.date_input("Kirish sanasi", datetime.today(), key=f"sana_{k}")
            
        with col2:
            tomon = st.selectbox("Tomon / Qanot", list(XONALAR.keys()), key=f"tomon_{k}")
            xona = st.selectbox("Xona raqami", list(XONALAR[tomon].keys()), key=f"xona_{k}")
            
            xona_sigimi = XONALAR[tomon][xona][0]
            odam_soni_variantlari = list(range(1, xona_sigimi + 1))
            odam_soni = st.selectbox("Odam soni", odam_soni_variantlari, key=f"odam_{k}")
            
            kunlar = st.number_input("Necha kun?", min_value=1, value=1, key=f"kun_{k}") if muddat == "Kunlik" else MUDDATLAR[muddat]
            chiqish_sanasi = kirish_sanasi + timedelta(days=kunlar)
            
            c.execute("SELECT SUM(odam_soni) FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona, chiqish_sanasi.strftime("%Y-%m-%d"), kirish_sanasi.strftime("%Y-%m-%d")))
            band = c.fetchone()[0] or 0
            bosh_joy = XONALAR[tomon][xona][0] - band
            
            joy_bor = True
            if bosh_joy <= 0: st.error(f"⚠️ {xona} band!"); joy_bor = False
            elif odam_soni > bosh_joy: st.error(f"⚠️ Faqat {bosh_joy} ta joy qolgan!"); joy_bor = False
            else: st.success(f"✅ {bosh_joy} ta bo'sh joy bor.")

        kunlik_stavka, standart_jami = narx_hisobla(tomon, xona, toifa, odam_soni, kunlar)
        with col3:
            st.info(f"🧾 **Standart jami:** {standart_jami:,.0f} so'm")
            # 12:00 QO'SHILDI
            st.success(f"📅 **Chiqish:** {chiqish_sanasi.strftime('%Y-%m-%d')} 12:00")
            if st.checkbox("⚙️ Admin maxsus narx", key=f"maxsus_{k}"):
                yakuniy_narx = st.number_input("KUNLIK narxni kiriting:", value=int(kunlik_stavka), step=5000, key=f"ynarx_{k}") * kunlar
            else: yakuniy_narx = standart_jami
                
            st.markdown(f"### 💰 JAMI SUMMA: {yakuniy_narx:,.0f} so'm")
            tolangan = st.number_input("To'lanayotgan summa:", value=0, step=10000, key=f"tol_{k}")
            tolov_shakli = st.selectbox("To'lov shakli", ["Naqd", "Karta", "Onlayn"])
            tolov_turi = st.selectbox("To'lov turi", ["Naqd", "Terminal karta", "Terminal naqd", "Click", "Uzcard", "Humo", "Boshqa"])

        qoldiq = yakuniy_narx - tolangan
        holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"

        st.divider()
        if joy_bor and st.button("✅ Bazaga saqlash", type="primary", use_container_width=True):
            if mijoz_ism.strip():
                yangi_id = id_yaratish(jinsi, kirish_sanasi, toifa)
                c.execute('''INSERT INTO bronlar (mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar, kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti, holat, kirish_sanasi, chiqish_sanasi) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (yangi_id, jinsi, datetime.now().strftime("%Y-%m-%d"), tomon, xona, "", mijoz_ism, toifa, odam_soni, muddat, kunlar, kunlik_stavka, standart_jami, yakuniy_narx, tolangan, qoldiq, tolov_shakli, tolov_turi, holat, kirish_sanasi.strftime("%Y-%m-%d"), chiqish_sanasi.strftime("%Y-%m-%d")))
                conn.commit()
                xodim_nomi = "CEO" if st.session_state.role == "ceo" else "Front-Ofis Admini"
                jurnalga_yozish(yangi_id, xodim_nomi, "Yangi Mijoz", f"To'ladi: {tolangan:,.0f} ({tolov_shakli} - {tolov_turi})")
                st.session_state.reset_key += 1
                st.toast(f"{yangi_id} saqlandi!", icon="✅")
                st.rerun()
            else:
                st.error("Mijoz ismini kiriting!")

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
        st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 4: FRONT-OFIS BOSHQARUV
# ----------------------------------------------------
if t4:
    with t4:
        st.header("💼 Mijozlar va Boshqaruv (Front-Ofis)")
        df = pd.read_sql_query("SELECT * FROM bronlar ORDER BY id DESC", conn)
        df['faktik_narx'] = df['faktik_narx'].fillna(0)
        df['tolagan_summa'] = df['tolagan_summa'].fillna(0)
        df['qoldiq'] = df['qoldiq'].fillna(0)
        xodim_nomi = "CEO" if st.session_state.role == "ceo" else "Front-Ofis Admini"
        
        if not df.empty:
            faol_df = df[df['holat'] != 'Chiqib ketgan']
            st.subheader("🟢 Hozirgi (Faol) Mijozlar")
            
            if not faol_df.empty:
                excel_data = to_excel(faol_df)
                st.download_button(label="📥 Faol Mijozlarni Excel qilib yuklash", data=excel_data, file_name=f"Faol_Mijozlar_{bugungi_sana}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                faol_korsatish = faol_df[['mijoz_id', 'mijoz', 'xona', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'chiqish_sanasi', 'holat']].copy()
                # 12:00 QO'SHILDI
                faol_korsatish['chiqish_sanasi'] = faol_korsatish['chiqish_sanasi'] + ' 12:00'
                faol_korsatish.columns = ['ID', 'Mijoz', 'Xona', 'Kun', 'Jami Summa', 'To\'langan', 'Qoldiq', 'Chiqish Sanasi', 'Holat']
                
                styler_faol = faol_korsatish.style.apply(rangla_jadval, axis=1).format({
                    'Jami Summa': '{:,.0f} UZS',
                    'To\'langan': '{:,.0f} UZS',
                    'Qoldiq': '{:,.0f} UZS'
                })
                st.dataframe(styler_faol, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            m1, m2 = st.columns(2)
            with m1:
                st.info("➕ Muddatni cho'zish (P продление)")
                if not faol_df.empty:
                    tanlangan_id_chozish = st.selectbox("Mijozni tanlang (Muddat cho'zish):", faol_df['mijoz_id'] + " - " + faol_df['mijoz'])
                    m_id = tanlangan_id_chozish.split(" - ")[0]
                    qoshimcha_kun = st.number_input("Necha kun qo'shilmoqda?", min_value=1, value=1)
                    if st.button("Muddatni cho'zish"):
                        mijoz_data = faol_df[faol_df['mijoz_id'] == m_id].iloc[0]
                        eski_chiqish = datetime.strptime(mijoz_data['chiqish_sanasi'], "%Y-%m-%d")
                        yangi_chiqish = eski_chiqish + timedelta(days=qoshimcha_kun)
                        qoshimcha_summa = mijoz_data['kunlik_narx'] * qoshimcha_kun
                        c.execute("UPDATE bronlar SET kunlar=kunlar+?, qoldiq=qoldiq+?, jami_summa=jami_summa+?, faktik_narx=faktik_narx+?, chiqish_sanasi=?, holat='Qarzdorlik' WHERE mijoz_id=?", 
                                  (qoshimcha_kun, qoshimcha_summa, qoshimcha_summa, qoshimcha_summa, yangi_chiqish.strftime("%Y-%m-%d"), m_id))
                        conn.commit()
                        jurnalga_yozish(m_id, xodim_nomi, "Muddat cho'zildi", f"+{qoshimcha_kun} kun. Qarziga {qoshimcha_summa:,.0f} qo'shildi.")
                        st.success("Muddat muvaffaqiyatli cho'zildi!")
                        st.rerun()

            with m2:
                st.warning("💳 Qarzni / To'lovni qabul qilish")
                qarzdorlar = faol_df[faol_df['qoldiq'] > 0]
                if not qarzdorlar.empty:
                    tanlangan_qarz = st.selectbox("Qarzdor mijoz:", qarzdorlar['mijoz_id'] + " - " + qarzdorlar['mijoz'])
                    q_id = tanlangan_qarz.split(" - ")[0]
                    q_summa = qarzdorlar[qarzdorlar['mijoz_id'] == q_id]['qoldiq'].values[0]
                    
                    tolov_sum = st.number_input("Olinayotgan summa:", value=int(q_summa), step=5000)
                    t_shakl = st.selectbox("Qarz To'lov shakli", ["Naqd", "Karta", "Onlayn"])
                    t_turi = st.selectbox("Qarz To'lov turi", ["Naqd", "Terminal karta", "Terminal naqd", "Click", "Uzcard", "Humo", "Boshqa"])
                    
                    if st.button("To'lovni kiritish"):
                        c.execute("UPDATE bronlar SET tolagan_summa=tolagan_summa+?, qoldiq=qoldiq-? WHERE mijoz_id=?", (tolov_sum, tolov_sum, q_id))
                        c.execute("UPDATE bronlar SET holat='To''langan' WHERE mijoz_id=? AND qoldiq<=0", (q_id,))
                        c.execute("UPDATE bronlar SET tolov_turi=?, tolov_tafsiloti=? WHERE mijoz_id=?", (t_shakl, t_turi, q_id))
                        conn.commit()
                        jurnalga_yozish(q_id, xodim_nomi, "Qarz yopildi", f"{tolov_sum:,.0f} to'landi ({t_shakl}-{t_turi})")
                        st.success("To'lov qabul qilindi!")
                        st.rerun()

            st.subheader("🗄️ Mijozlar Arxivi (Chiqib ketganlar)")
            arxiv_df = df[df['holat'] == 'Chiqib ketgan']
            if not arxiv_df.empty:
                excel_data_arxiv = to_excel(arxiv_df)
                st.download_button(label="📥 Arxivni Excel qilib yuklash", data=excel_data_arxiv, file_name=f"Arxiv_{bugungi_sana}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                arxiv_korsatish = arxiv_df[['mijoz_id', 'mijoz', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_sanasi', 'chiqish_sanasi', 'holat']].copy()
                # 12:00 QO'SHILDI
                arxiv_korsatish['chiqish_sanasi'] = arxiv_korsatish['chiqish_sanasi'] + ' 12:00'
                arxiv_korsatish.columns = ['ID', 'Mijoz', 'Jami Summa', 'To\'langan', 'Qoldiq', 'Kirish', 'Chiqish', 'Holat']
                
                styler_arxiv = arxiv_korsatish.style.apply(rangla_jadval, axis=1).format({
                    'Jami Summa': '{:,.0f} UZS',
                    'To\'langan': '{:,.0f} UZS', 
                    'Qoldiq': '{:,.0f} UZS'
                })
                st.dataframe(styler_arxiv, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 5: CEO PANEL
# ----------------------------------------------------
if t5:
    with t5:
        st.markdown("---")
        df_admin = pd.read_sql_query("SELECT * FROM bronlar ORDER BY id DESC", conn)
        df_audit = pd.read_sql_query("SELECT * FROM audit_log ORDER BY id DESC", conn)
        
        tab_a, tab_b, tab_c = st.tabs(["🚪 Checkout (Mijozni chiqarish)", "🕵️ O'zgarishlar Jurnali (Audit)", "🗑️ O'chirish (Xavfli)"])
        
        with tab_a:
            st.subheader("🚪 Mijozni chiqarish (Checkout)")
            faollar = df_admin[df_admin['holat'] != 'Chiqib ketgan']
            if not faollar.empty:
                chiq_id = st.selectbox("Xonani bo'shatadigan mijoz:", faollar['mijoz_id'] + " - " + faollar['xona'])
                c_id = chiq_id.split(" - ")[0]
                
                mijoz_qoldigi = faollar[faollar['mijoz_id'] == c_id]['qoldiq'].values[0]
                if mijoz_qoldigi > 0:
                    st.error(f"⚠️ DIQQAT! Mijozning {mijoz_qoldigi:,.0f} so'm qarzi bor. Qarz to'liq yopilmaguncha, uni tizimdan chiqara olmaysiz! Iltimos, adminlar qarzni olsin.")
                else:
                    if st.button("Mijozni Arxivlash (Chiqarish)"):
                        mijoz_data = df_admin[df_admin['mijoz_id'] == c_id].iloc[0]
                        eski_chiqish = mijoz_data['chiqish_sanasi']
                        c.execute("UPDATE bronlar SET holat = 'Chiqib ketgan', chiqish_sanasi = ? WHERE mijoz_id = ?", (bugungi_sana, c_id))
                        conn.commit()
                        
                        eslatma = "Mijoz xonani bo'shatdi."
                        if eski_chiqish > bugungi_sana:
                            eslatma = f"Erta chiqib ketdi (Eski sanasi: {eski_chiqish}). Pul qayta hisoblanmadi!"
                            
                        jurnalga_yozish(c_id, "CEO", "Checkout", eslatma)
                        st.success("Mijoz arxivlandi!")
                        st.rerun()
        
        with tab_b:
            st.subheader("🕵️ O'zgarishlar Tarixi (Kim nima qildi?)")
            if not df_audit.empty:
                excel_data_audit = to_excel(df_audit)
                st.download_button(label="📥 Audit Jurnalini yuklab olish", data=excel_data_audit, file_name=f"Audit_Jurnal_{bugungi_sana}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.dataframe(df_audit, use_container_width=True)
            
        with tab_c:
            st.error("🚨 XAVFLI ZONA: Tizimdan butunlay o'chirish")
            if not df_admin.empty:
                del_id = st.selectbox("O'chiriladigan ID:", df_admin['mijoz_id'] + " - " + df_admin['mijoz'])
                if st.button("⚠️ Butunlay o'chirish"):
                    d_id = del_id.split(" - ")[0]
                    c.execute("DELETE FROM bronlar WHERE mijoz_id = ?", (d_id,))
                    conn.commit()
                    jurnalga_yozish(d_id, "CEO", "O'chirish", "Mijoz bazadan butunlay yo'q qilindi.")
                    st.success("O'chirildi!")
                    st.rerun()

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
                yangi_parol = st.text_input("Yangi parol:", type="password", placeholder="Yangi parolni kiriting...")
                parol_tasdiq = st.text_input("Yangi parolni tasdiqlang:", type="password", placeholder="Parolni qayta kiriting...")
                
                submit_settings = st.form_submit_button("Ma'lumotlarni saqlash", type="primary")
                
                if submit_settings:
                    if yangi_parol and yangi_parol != parol_tasdiq:
                        st.error("⚠️ Parollar mos tushmadi! Iltimos qaytadan urinib ko'ring.")
                    else:
                        if yangi_parol:
                            c.execute("UPDATE users SET login=?, parol=? WHERE role=?", (yangi_login, yangi_parol, st.session_state.role))
                        else:
                            c.execute("UPDATE users SET login=? WHERE role=?", (yangi_login, st.session_state.role))
                        conn.commit()
                        
                        st.success("✅ Ma'lumotlar muvaffaqiyatli yangilandi! Tizimga yangi parolingiz bilan qaytadan kiring.")
                        st.session_state.logged_in = False
                        st.session_state.role = None
                        st.rerun()