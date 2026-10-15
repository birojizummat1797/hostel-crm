import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import (
    db, IS_POSTGRES, XONALAR, MUDDATLAR,
    xona_sigimini_ol, narx_hisobla, id_yaratish,
    jurnalga_yozish, barcha_bazani_yuklash, chiroyli_kartochka, rangla_jadval
)
from tg_bot import tg_xabar_yubor
from ceo_panel import render_xarajatlar_va_smena, render_ceo_panel

st.set_page_config(page_title="Yangi Sergeli Hostel CRM", layout="wide")
st.markdown("""<style>div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e6ed; padding: 15px 20px; border-radius: 12px; border-left: 6px solid #4CAF50; box-shadow: 2px 4px 15px rgba(0,0,0,0.05); }</style>""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'user_login' not in st.session_state: st.session_state.user_login = ""
if 'xodim_ismi' not in st.session_state: st.session_state.xodim_ismi = ""
if 'reset_key' not in st.session_state: st.session_state.reset_key = 0

# ==========================================
# 1. LOGIN OYNASI
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #2E3B55; margin-top: 50px;'>🏨 YSH CRM | ERP Tizimi</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            login_input = st.text_input("Login")
            parol_input = st.text_input("Parol", type="password")
            submit_login = st.form_submit_button("Kirish", use_container_width=True, type="primary")
            if submit_login:
                user = db.fetchone("SELECT role, ism, login FROM users WHERE login=? AND parol=?", (login_input.strip(), parol_input.strip()))
                if user:
                    st.session_state.logged_in = True
                    st.session_state.role = user[0]
                    st.session_state.xodim_ismi = user[1] if user[1] else user[2].upper()
                    st.session_state.user_login = user[2]
                    jurnalga_yozish("Tizim", st.session_state.xodim_ismi, "Tizimga kirdi", "Ish faoliyati boshlandi")
                    st.rerun()
                else:
                    st.error("Noto'g'ri login yoki parol!")
    st.stop()

# ==========================================
# 2. SIDEBAR VA NAVIGATSIYA
# ==========================================
xodim_ismi = st.session_state.xodim_ismi
bugungi_sana = datetime.today().strftime("%Y-%m-%d")
k = str(st.session_state.reset_key)

st.sidebar.title("🏨 YSH ERP")
st.sidebar.success(f"👤 **{xodim_ismi}**\n\nRol: {st.session_state.role.upper()}")

if IS_POSTGRES:
    st.sidebar.info("☁️ **Baza:** Online Cloud (PostgreSQL)")
else:
    st.sidebar.warning("💻 **Baza:** Lokal (SQLite)")

st.sidebar.download_button(
    label="💾 Barcha bazani yuklash (Excel)",
    data=barcha_bazani_yuklash(),
    file_name=f"YSH_CRM_Full_Backup_{bugungi_sana}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Tizimdan chiqish", use_container_width=True):
    jurnalga_yozish("Tizim", xodim_ismi, "Tizimdan chiqdi", "Ish faoliyati yakunlandi")
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.title("🏨 Yangi Sergeli Hostel CRM")

if st.session_state.role == "ceo":
    tabs = st.tabs(["📈 Dashboard", "📝 Qabul", "🔲 Shaxmatka", "💼 Mijozlar", "🛒 Market", "📦 Sklad", "💸 Xarajat va Smena", "👑 CEO Panel", "⚙️ Sozlamalar"])
    t1, t2, t3, t4, t_market, t_ombor, t_xarajat, t5, t6 = tabs
else:
    tabs = st.tabs(["📈 Dashboard", "📝 Qabul", "🔲 Shaxmatka", "💼 Mijozlar", "🛒 Market", "📦 Sklad", "💸 Xarajat va Smena", "⚙️ Sozlamalar"])
    t1, t2, t3, t4, t_market, t_ombor, t_xarajat, t6 = tabs
    t5 = None

# ----------------------------------------------------
# TAB 1: AQLLI DASHBOARD
# ----------------------------------------------------
with t1:
    st.header("📈 Moliya va Hostel Analitikasi")
    df_barcha = db.read_df("SELECT * FROM bronlar")
    df_savdolar = db.read_df("SELECT * FROM savdolar")
    df_tolovlar = db.read_df("SELECT * FROM tolovlar_tarixi")
    df_xarajat = db.read_df("SELECT * FROM xarajatlar")
    
    if 'tolagan_summa' in df_barcha.columns: df_barcha['tolagan_summa'] = df_barcha['tolagan_summa'].fillna(0)
    if 'qoldiq' in df_barcha.columns: df_barcha['qoldiq'] = df_barcha['qoldiq'].fillna(0)

    faol_mijozlar = df_barcha[(df_barcha['holat'] != 'Chiqib ketgan') & (df_barcha['kirish_sanasi'] <= bugungi_sana)] if not df_barcha.empty else pd.DataFrame()
    umumiy_kassa_yotoq = df_barcha['tolagan_summa'].sum() if not df_barcha.empty else 0
    umumiy_kassa_market = df_savdolar[df_savdolar['tolov_turi'] == 'Darhol']['jami_summa'].sum() if not df_savdolar.empty else 0
    market_sof_foyda = df_savdolar['sof_foyda'].fillna(0).sum() if not df_savdolar.empty and 'sof_foyda' in df_savdolar.columns else 0
    jami_xarajatlar = df_xarajat['summa'].fillna(0).sum() if not df_xarajat.empty else 0
    umumiy_qarz = df_barcha[(df_barcha['qoldiq'] > 0) & (df_barcha['holat'] != 'Chiqib ketgan')]['qoldiq'].sum() if not df_barcha.empty else 0
    sof_balans = (umumiy_kassa_yotoq + umumiy_kassa_market) - jami_xarajatlar

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.markdown(chiroyli_kartochka("👥", "Faol Mehmon", f"{len(faol_mijozlar)} ta", "#8b5cf6"), unsafe_allow_html=True)
    with c2: st.markdown(chiroyli_kartochka("💰", "Yotoq Tushum", f"{umumiy_kassa_yotoq:,.0f}", "#f59e0b"), unsafe_allow_html=True)
    with c3: st.markdown(chiroyli_kartochka("🛒", "Market Savdo", f"{umumiy_kassa_market:,.0f}", "#10b981"), unsafe_allow_html=True)
    with c4: st.markdown(chiroyli_kartochka("➖", "Xarajatlar", f"{jami_xarajatlar:,.0f}", "#64748b"), unsafe_allow_html=True)
    with c5: st.markdown(chiroyli_kartochka("🏦", "Sof Balans", f"{sof_balans:,.0f}", "#2563eb"), unsafe_allow_html=True)
    with c6: st.markdown(chiroyli_kartochka("⚠️", "Faol Qarzlar", f"{umumiy_qarz:,.0f}", "#ef4444"), unsafe_allow_html=True)

    if st.session_state.role == "ceo":
        st.caption(f"📈 **Marketdan qolgan jami sof foyda (marja):** {market_sof_foyda:,.0f} UZS")

    st.markdown("---")
    st.subheader("🧮 Kassadagi Haqiqiy Pul Qoldig'i (Kirim minus Xarajat)")
    if not df_tolovlar.empty:
        df_tolovlar['tolov_tafsiloti'] = df_tolovlar['tolov_tafsiloti'].replace('', "Noma'lum").fillna("Noma'lum")
        kirim_gr = df_tolovlar.groupby('tolov_tafsiloti')['summa'].sum().to_dict()
        chiqim_gr = df_xarajat.groupby('tolov_turi')['summa'].sum().to_dict() if not df_xarajat.empty else {}
        
        barcha_turlar = sorted(list(set(list(kirim_gr.keys()) + list(chiqim_gr.keys()))))
        t_cols = st.columns(4)
        for idx, tur in enumerate(barcha_turlar):
            kirim_s = kirim_gr.get(tur, 0)
            chiqim_s = chiqim_gr.get(tur, 0)
            qoldiq_s = kirim_s - chiqim_s
            with t_cols[idx % 4]:
                st.info(f"**{tur}**\n\n### {qoldiq_s:,.0f} UZS\n*(Kirim: {kirim_s:,.0f} | Rashod: {chiqim_s:,.0f})*")
    else:
        st.info("Hali kassa tushumlari mavjud emas.")

    df_mahsulotlar = db.read_df("SELECT * FROM mahsulotlar WHERE qoldiq <= 5")
    if not df_mahsulotlar.empty:
        st.error(f"🚨 **DIQQAT: Quyidagi {len(df_mahsulotlar)} ta mahsulot omborda tugayapti!**")
        st.warning("🛒 " + ", ".join([f"{r['nomi']} ({r['qoldiq']} ta qoldi)" for _, r in df_mahsulotlar.iterrows()]))

# ----------------------------------------------------
# TAB 2: QABUL VA BRON
# ----------------------------------------------------
with t2:
    bron_turi = st.radio("📌 Ro'yxatdan o'tish turi:", ["Hozir qabul qilish (Kirish)", "Oldindan band qilish (Bron)"], horizontal=True, key=f"bturi_{k}")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        mijoz_ism = st.text_input("Mijoz F.I.O / Telefon / Pasport", key=f"ism_{k}")
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
        
        oraliqdagi_bronlar = db.fetchall("SELECT mijoz, kirish_sanasi, chiqish_sanasi, odam_soni FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?", (xona, chiqish_str, kirish_str))
        band_res = db.fetchone("SELECT SUM(odam_soni) FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?", (xona, chiqish_str, kirish_str))
        band = band_res[0] if band_res and band_res[0] else 0
        bosh_joy = XONALAR[tomon][xona][0] - band
        
        joy_bor = True
        if bosh_joy <= 0: st.error(f"⚠️ {xona} to'liq band!"); joy_bor = False
        elif odam_soni > bosh_joy: st.error(f"⚠️ Bu xonada faqat {bosh_joy} ta joy qolgan!"); joy_bor = False
        else: st.success(f"✅ Mos {bosh_joy} ta bo'sh joy bor.")
        
        if oraliqdagi_bronlar:
            st.info("📌 **Tanlangan davrda xonadagi boshqa bandliklar:**")
            for b in oraliqdagi_bronlar: st.markdown(f"🗓 {b[1]} dan {b[2]} 12:00 gacha: **{b[0]}** ({b[3]} kishi)")

    kunlik_stavka, standart_jami = narx_hisobla(tomon, xona, toifa, odam_soni, kunlar)
    with col3:
        st.info(f"🧾 **Standart jami:** {standart_jami:,.0f} so'm")
        maxsus_belgi = st.checkbox("⚙️ Admin maxsus narx", key=f"maxsus_{k}")
        if maxsus_belgi:
            kunlik_stavka = st.number_input("KUNLIK narx:", value=int(kunlik_stavka), step=5000, key=f"ynarx_{k}")
            yakuniy_narx = kunlik_stavka * kunlar
        else:
            yakuniy_narx = standart_jami
        st.markdown(f"### 💰 JAMI: {yakuniy_narx:,.0f} so'm")
        tolangan = st.number_input("To'lanayotgan summa:", value=0, step=10000, key=f"tol_{k}")
        tolov_shakli = st.selectbox("To'lov shakli", ["Naqd", "Karta", "Onlayn"])
        t_taf = st.selectbox("To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
        if t_taf == "Boshqa":
            qoshimcha_izoh = st.text_input("Qaysi turda to'landi? (Izoh yozing):", placeholder="Payme, O'tkazma...")
            if qoshimcha_izoh: t_taf = f"Boshqa ({qoshimcha_izoh})"

    qoldiq = yakuniy_narx - tolangan
    holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"

    st.divider()
    if joy_bor and st.button("✅ Bazaga saqlash", type="primary", use_container_width=True):
        if mijoz_ism.strip():
            yangi_id = id_yaratish(jinsi, kirish_sanasi, toifa)
            saq_turi = 'Hozir kirish' if bron_turi == "Hozir qabul qilish (Kirish)" else 'Bron'
            hozirgi_sana = datetime.now().strftime("%Y-%m-%d")
            db.execute("""INSERT INTO bronlar (mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar, kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti, holat, kirish_sanasi, chiqish_sanasi, bron_turi, izoh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (yangi_id, jinsi, hozirgi_sana, tomon, xona, "", mijoz_ism, toifa, odam_soni, muddat, kunlar, kunlik_stavka, standart_jami, yakuniy_narx, tolangan, qoldiq, tolov_shakli, t_taf, holat, kirish_str, chiqish_str, saq_turi, ""))
            if tolangan > 0:
                db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                           (hozirgi_sana, yangi_id, mijoz_ism, "Yotoq (Qabul)", tolangan, tolov_shakli, t_taf, xodim_ismi))
            jurnalga_yozish(yangi_id, xodim_ismi, "Yangi " + saq_turi, f"Mijoz: {mijoz_ism}, Xona: {xona}, To'ladi: {tolangan:,.0f} ({t_taf})")
            tg_xabar_yubor(
                f"Yangi {saq_turi}",
                f"👤 <b>Mijoz:</b> {mijoz_ism} ({odam_soni} kishi)\n"
                f"🛏 <b>Xona:</b> {xona} ({kunlar} kun)\n"
                f"💰 <b>Jami hisob:</b> {yakuniy_narx:,.0f} UZS\n"
                f"✅ <b>To'ladi:</b> {tolangan:,.0f} UZS ({t_taf})\n"
                f"⚠️ <b>Qoldiq qarz:</b> {qoldiq:,.0f} UZS",
                xodim_ismi, muhim=maxsus_belgi
            )
            st.session_state.reset_key += 1
            st.rerun()
        else:
            st.error("Ismni kiriting!")

# ----------------------------------------------------
# TAB 3: METRO SHAXMATKA
# ----------------------------------------------------
with t3:
    st.header("🔲 15-kunlik Xonalar Shaxmatkasi")
    col_kat, col_san = st.columns([2, 1])
    tanlangan_katalog = col_kat.radio("Qanot:", ["Barchasi", "Chap tomon", "O'rtadagi", "O'ng tomon"], horizontal=True)
    bosh_sana = col_san.date_input("Boshlanish sanasi:", datetime.today())
    
    sana_royxati = [bosh_sana + timedelta(days=i) for i in range(15)]
    bosh_sana_str = bosh_sana.strftime("%Y-%m-%d")
    oxirgi_sana_str = (bosh_sana + timedelta(days=15)).strftime("%Y-%m-%d")
    
    oraliq_bronlar = db.read_df("SELECT xona, kirish_sanasi, chiqish_sanasi, odam_soni FROM bronlar WHERE holat!='Chiqib ketgan' AND kirish_sanasi < ? AND chiqish_sanasi > ?", (oxirgi_sana_str, bosh_sana_str))
    
    matrix = []
    for tomon, xonalar in XONALAR.items():
        if tanlangan_katalog != "Barchasi" and tomon != tanlangan_katalog: continue
        for xona, info in xonalar.items():
            sigim = info[0]
            qator = {"Xona": f"{xona} ({sigim} k)" if tanlangan_katalog != "Barchasi" else f"{tomon[0]} | {xona} ({sigim} k)"}
            xona_bronlar = oraliq_bronlar[oraliq_bronlar['xona'] == xona] if (not oraliq_bronlar.empty and 'xona' in oraliq_bronlar.columns) else pd.DataFrame()
                
            for d in sana_royxati:
                d_str = d.strftime("%Y-%m-%d")
                band = 0
                if not xona_bronlar.empty:
                    band_mask = (xona_bronlar['kirish_sanasi'] <= d_str) & (xona_bronlar['chiqish_sanasi'] > d_str)
                    band = xona_bronlar[band_mask]['odam_soni'].sum()
                bosh = sigim - band
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
        
        bugun_ichidagilar = db.fetchall("SELECT mijoz, jinsi, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona_nomi, bugungi_sana, bugungi_sana))
        kelajakdagi_bronlar = db.fetchall("SELECT mijoz, jinsi, kirish_sanasi, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi>?", (xona_nomi, bugungi_sana))
        
        if not bugun_ichidagilar and not kelajakdagi_bronlar:
            st.success(f"🟢 **XONA TO'LIQ BO'SH — {xona_nomi} ({umumiy_sigim} kishilik)**")
        elif not bugun_ichidagilar and kelajakdagi_bronlar:
            eng_yaqin = sorted(kelajakdagi_bronlar, key=lambda x: x[2])[0]
            st.warning(f"🟡 **XONA HOZIR BO'SH, lekin {eng_yaqin[2]} dan boshlab band qilingan! — {xona_nomi}**")
        else:
            band_qilingan_joylar = sum([m[5] for m in bugun_ichidagilar])
            qoldiq_joy = umumiy_sigim - band_qilingan_joylar
            if qoldiq_joy > 0: st.warning(f"🟡 **XONADA HOZIR MIJOZLAR BOR — Qoldiq o'rin: {qoldiq_joy} ta. {xona_nomi}**")
            else: st.error(f"🔴 **XONA HOZIR TO'LIQ BAND — {xona_nomi}**")
        
        if bugun_ichidagilar:
            st.markdown("**Hozirgi mijozlar:**")
            for m in bugun_ichidagilar:
                qarz_matni = f" | ⚠️ Qarz: {m[4]:,.0f} UZS" if m[4] > 0 else ""
                st.markdown(f"- **{m[0]}** ({m[5]} kishi, 🛫 Chiqish: {m[2]} 12:00){qarz_matni}")
                if m[6]: st.info(f"💡 **CEO Izohi:** {m[6]}")
                
        if kelajakdagi_bronlar:
            st.info(f"📅 **Ushbu xonaga kelajakdagi bronlar ({len(kelajakdagi_bronlar)} ta):**")
            for b in kelajakdagi_bronlar:
                b_qarz = f" | ⚠️ Qarz: {b[5]:,.0f} UZS" if b[5] > 0 else ""
                st.markdown(f"- 🕒 Keladi: **{b[2]} 12:00** ({b[6]} kishi) - **{b[0]}** • 🛫 Ketadi: {b[3]} 12:00{b_qarz}")
                if b[7]: st.info(f"💡 **CEO Izohi:** {b[7]}")
    else:
        st.info("👆 Ma'lumotni ko'rish uchun yuqoridagi jadvaldan biror qatorni ustiga bosing.")

# ----------------------------------------------------
# TAB 4: FRONT-OFIS (Muddat cho'zish, Qarz yopish va Xona ko'chirish)
# ----------------------------------------------------
with t4:
    st.header("💼 Mijozlar va Boshqaruv (Front-Ofis)")
    df = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")
    
    if not df.empty:
        df['faktik_narx'] = df['faktik_narx'].fillna(0)
        df['tolagan_summa'] = df['tolagan_summa'].fillna(0)
        df['qoldiq'] = df['qoldiq'].fillna(0)
        df['izoh'] = df['izoh'].fillna('')
        
        qidiruv = st.text_input("🔍 Mijoz F.I.O, ID yoki Xona bo'yicha tezkor qidiruv:")
        if qidiruv:
            df = df[df['mijoz'].str.contains(qidiruv, case=False, na=False) | df['mijoz_id'].str.contains(qidiruv, case=False, na=False) | df['xona'].str.contains(qidiruv, case=False, na=False)]
        
        faol_df = df[(df['holat'] != 'Chiqib ketgan') & (df['kirish_sanasi'] <= bugungi_sana)]
        bron_df = df[(df['holat'] != 'Chiqib ketgan') & (df['kirish_sanasi'] > bugungi_sana)]
        
        if not bron_df.empty:
            st.subheader("📅 Oldindan Bron qilinganlar")
            bron_korsatish = bron_df[['mijoz_id', 'mijoz', 'xona', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_sanasi', 'izoh']].copy()
            bron_korsatish.columns = ["ID", "Mijoz", "Xona", "Kun", "Jami Summa", "To'langan", "Qoldiq", "Kelish Sanasi", "Izoh"]
            for col in ["Jami Summa", "To'langan", "Qoldiq"]: bron_korsatish[col] = bron_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(bron_korsatish, use_container_width=True, hide_index=True)

        st.subheader("🟢 Hozirgi (Faol) Mijozlar")
        if not faol_df.empty:
            faol_korsatish = faol_df[['mijoz_id', 'mijoz', 'xona', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'chiqish_sanasi', 'holat', 'izoh']].copy()
            faol_korsatish['chiqish_sanasi'] = faol_korsatish['chiqish_sanasi'] + ' 12:00'
            faol_korsatish.columns = ["ID", "Mijoz", "Xona", "Kun", "Jami Summa", "To'langan", "Qoldiq", "Chiqish", "Holat", "Izoh"]
            for col in ["Jami Summa", "To'langan", "Qoldiq"]: faol_korsatish[col] = faol_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(faol_korsatish.style.apply(rangla_jadval, axis=1), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.info("➕ Muddatni cho'zish")
            if not faol_df.empty:
                tanlangan_id_chozish = st.selectbox("Mijozni tanlang:", faol_df['mijoz_id'] + " - " + faol_df['mijoz'])
                qoshimcha_kun = st.number_input("Necha kun qo'shilmoqda?", min_value=1, value=1)
                if st.button("Muddatni cho'zish", use_container_width=True):
                    m_id = tanlangan_id_chozish.split(" - ")[0]
                    mijoz_data = faol_df[faol_df['mijoz_id'] == m_id].iloc[0]
                    yangi_chiqish = datetime.strptime(mijoz_data['chiqish_sanasi'], "%Y-%m-%d") + timedelta(days=qoshimcha_kun)
                    q_sum = mijoz_data['kunlik_narx'] * qoshimcha_kun
                    db.execute("UPDATE bronlar SET kunlar=kunlar+?, qoldiq=qoldiq+?, jami_summa=jami_summa+?, faktik_narx=faktik_narx+?, chiqish_sanasi=?, holat='Qarzdorlik' WHERE mijoz_id=?", (qoshimcha_kun, q_sum, q_sum, q_sum, yangi_chiqish.strftime("%Y-%m-%d"), m_id))
                    jurnalga_yozish(m_id, xodim_ismi, "Muddat cho'zildi", f"+{qoshimcha_kun} kun ({q_sum:,.0f} UZS)")
                    tg_xabar_yubor("Muddat cho'zildi", f"👤 <b>Mijoz:</b> {mijoz_data['mijoz']}\n➕ <b>Qo'shildi:</b> +{qoshimcha_kun} kun ({q_sum:,.0f} UZS)", xodim_ismi)
                    st.success("Muddat cho'zildi!")
                    st.rerun()

        with m2:
            st.warning("💳 Qarzni yopish")
            qarzdorlar = df[(df['qoldiq'] > 0) & (df['holat'] != 'Chiqib ketgan')]
            if not qarzdorlar.empty:
                tanlangan_qarz = st.selectbox("Qarzdor mijoz:", qarzdorlar['mijoz_id'] + " - " + qarzdorlar['mijoz'])
                q_id = tanlangan_qarz.split(" - ")[0]
                q_mijoz_ism = qarzdorlar[qarzdorlar['mijoz_id'] == q_id]['mijoz'].values[0]
                tolov_sum = st.number_input("Olinayotgan summa:", value=int(qarzdorlar[qarzdorlar['mijoz_id'] == q_id]['qoldiq'].values[0]), step=5000)
                t_shakl = st.selectbox("Qarz To'lov shakli", ["Naqd", "Karta", "Onlayn"])
                t_tafsiloti = st.selectbox("Qarz To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
                if t_tafsiloti == "Boshqa":
                    qarz_izoh = st.text_input("Izoh yozing:", placeholder="Payme...")
                    if qarz_izoh: t_tafsiloti = f"Boshqa ({qarz_izoh})"
                
                if st.button("To'lovni kiritish", use_container_width=True):
                    db.execute("UPDATE bronlar SET tolagan_summa=tolagan_summa+?, qoldiq=qoldiq-?, tolov_turi=?, tolov_tafsiloti=? WHERE mijoz_id=?", (tolov_sum, tolov_sum, t_shakl, t_tafsiloti, q_id))
                    db.execute("UPDATE bronlar SET holat='To''langan' WHERE mijoz_id=? AND qoldiq<=0", (q_id,))
                    db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                               (bugungi_sana, q_id, q_mijoz_ism, "Qarz yopish", tolov_sum, t_shakl, t_tafsiloti, xodim_ismi))
                    jurnalga_yozish(q_id, xodim_ismi, "Qarz yopildi", f"Summa: {tolov_sum:,.0f} ({t_tafsiloti})")
                    tg_xabar_yubor("Qarz to'landi", f"👤 <b>Mijoz:</b> {q_mijoz_ism}\n💵 <b>Summa:</b> {tolov_sum:,.0f} UZS ({t_tafsiloti})", xodim_ismi)
                    st.success("To'lov qabul qilindi!")
                    st.rerun()

        with m3:
            st.success("🛏 Xonadan-xonaga ko'chirish")
            if not faol_df.empty:
                koch_mijoz = st.selectbox("Ko'chiriladigan mijoz:", faol_df['mijoz_id'] + " - " + faol_df['mijoz'] + " (" + faol_df['xona'] + ")")
                k_id = koch_mijoz.split(" - ")[0]
                k_data = faol_df[faol_df['mijoz_id'] == k_id].iloc[0]
                y_tomon = st.selectbox("Yangi Qanot:", list(XONALAR.keys()))
                y_xona = st.selectbox("Yangi Xona:", list(XONALAR[y_tomon].keys()))
                if st.button("🔄 Xonani almashtirish", use_container_width=True):
                    eski_xona = k_data['xona']
                    db.execute("UPDATE bronlar SET tomon=?, xona=? WHERE mijoz_id=?", (y_tomon, y_xona, k_id))
                    jurnalga_yozish(k_id, xodim_ismi, "Xona ko'chirildi", f"{k_data['mijoz']}: {eski_xona} -> {y_xona}")
                    tg_xabar_yubor("Xona almashtirildi", f"👤 <b>Mijoz:</b> {k_data['mijoz']}\n🔄 <b>Ko'chirildi:</b> {eski_xona} ➡️ {y_xona}", xodim_ismi)
                    st.success(f"Mijoz {y_xona} ga ko'chirildi!")
                    st.rerun()

# ----------------------------------------------------
# TAB 5: MARKET
# ----------------------------------------------------
with t_market:
    st.header("🛒 Mini-Market (Savdo va Hisobot)")
    market_tanlov = st.radio("Bo'limni tanlang:", ["🛒 Kassa (Sotish)", "📊 Savdolar Tarixi"], horizontal=True)
    st.markdown("---")
    
    if market_tanlov == "🛒 Kassa (Sotish)":
        mahsulotlar = db.read_df("SELECT * FROM mahsulotlar WHERE qoldiq > 0")
        if mahsulotlar.empty:
            st.warning("⚠️ Omborda sotishga mahsulot yo'q.")
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
                tovar_tannarxi = tanlangan_qator.get('tannarx', 0) or 0
                maks_qoldiq = tanlangan_qator['qoldiq']
                asl_tovar_nomi = tanlangan_qator['nomi']
                
                miqdor = st.number_input(f"4. Miqdori (Omborda {maks_qoldiq} ta bor):", min_value=1, max_value=int(maks_qoldiq), value=1)
                jami_sum = miqdor * tovar_narxi
                sof_foyda_sum = miqdor * (tovar_narxi - tovar_tannarxi)
                
            with col_m2:
                st.info(f"🧾 **To'lanadigan summa:** {jami_sum:,.0f} UZS")
                tolov_usuli = st.radio("5. To'lov turi:", ["💵 Darhol To'lov", "🏨 Xona qarziga yozish"])
                m_tafsiloti = ""
                if tolov_usuli == "💵 Darhol To'lov":
                    m_tafsiloti = st.selectbox("Qaysi usulda to'landi?", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
                    if m_tafsiloti == "Boshqa":
                        m_izoh = st.text_input("Izoh yozing:", placeholder="Payme, O'tkazma...")
                        if m_izoh: m_tafsiloti = f"Boshqa ({m_izoh})"
                
                faol_bronlar = db.read_df("SELECT mijoz_id, mijoz, xona FROM bronlar WHERE holat != 'Chiqib ketgan'")
                tanlangan_mijoz_id = None
                if tolov_usuli == "🏨 Xona qarziga yozish":
                    if faol_bronlar.empty:
                        st.error("Hozircha xonada faol mijozlar yo'q.")
                    else:
                        mijoz_qator = st.selectbox("6. Qaysi mijozga?", faol_bronlar['mijoz'] + " (" + faol_bronlar['xona'] + ") - ID: " + faol_bronlar['mijoz_id'])
                        tanlangan_mijoz_id = mijoz_qator.split("ID: ")[1]
                        xaridor_nomi = mijoz_qator.split(" (")[0]
                        m_tafsiloti = "Xona qarziga"
                else:
                    xaridor_nomi = "Umumiy xaridor"
                    
                if st.button("🛒 SOTISH", type="primary", use_container_width=True):
                    db.execute("UPDATE mahsulotlar SET qoldiq = qoldiq - ? WHERE nomi = ? AND kategoriya = ? AND sub_kategoriya = ?", (miqdor, asl_tovar_nomi, kat_tanlov_m, sub_tanlov_m))
                    db.execute("INSERT INTO savdolar (sana, mahsulot_nomi, xaridor, miqdor, jami_summa, sof_foyda, tolov_turi, xodim, tolov_tafsiloti) VALUES (?,?,?,?,?,?,?,?,?)",
                              (bugungi_sana, tanlangan_tovar_toliq, xaridor_nomi, miqdor, jami_sum, sof_foyda_sum, tolov_usuli.split(" ")[1], xodim_ismi, m_tafsiloti))
                    if tanlangan_mijoz_id:
                        db.execute("UPDATE bronlar SET jami_summa = jami_summa + ?, faktik_narx = faktik_narx + ?, qoldiq = qoldiq + ?, holat = 'Qarzdorlik' WHERE mijoz_id = ?", (jami_sum, jami_sum, jami_sum, tanlangan_mijoz_id))
                        jurnalga_yozish(tanlangan_mijoz_id, xodim_ismi, "Market qarz", f"{miqdor} ta {tanlangan_tovar_toliq}. Summa: {jami_sum:,.0f} UZS")
                    else:
                        db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                   (bugungi_sana, "Market", xaridor_nomi, "Market Savdo", jami_sum, "Darhol", m_tafsiloti, xodim_ismi))
                        jurnalga_yozish("Market (Sotuv)", xodim_ismi, "Naqd Savdo", f"{miqdor} ta {tanlangan_tovar_toliq} sotildi. Summa: {jami_sum:,.0f} UZS ({m_tafsiloti})")
                    st.success(f"✅ {miqdor} ta {tanlangan_tovar_toliq} sotildi!")
                    st.rerun()

    else:
        df_savdo = db.read_df("SELECT * FROM savdolar ORDER BY id DESC")
        if not df_savdo.empty:
            df_savdo_korsatish = df_savdo[['sana', 'mahsulot_nomi', 'xaridor', 'miqdor', 'jami_summa', 'tolov_tafsiloti', 'xodim']].copy()
            df_savdo_korsatish.columns = ["Sana", "Mahsulot", "Xaridor", "Miqdor", "Jami Summa", "To'lov Turi", "Sotuvchi (Admin)"]
            df_savdo_korsatish['Jami Summa'] = df_savdo_korsatish['Jami Summa'].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_savdo_korsatish, use_container_width=True, hide_index=True)
        else:
            st.info("Hozircha marketda savdo amalga oshirilmagan.")

# ----------------------------------------------------
# TAB 6: OMBOR (Tannarx bilan)
# ----------------------------------------------------
with t_ombor:
    st.header("📦 Sklad (Ombor) Boshqaruvi")
    ombor_tanlov = st.radio("Bo'limni tanlang:", ["📋 Mahsulotlar ro'yxati", "➕ Yangi tovar kiritish"], horizontal=True)
    st.markdown("---")
    
    if ombor_tanlov == "➕ Yangi tovar kiritish":
        c1, c2 = st.columns(2)
        with c1:
            kat_tanlov = st.selectbox("1. Kategoriya:", ["Ichimliklar", "Gigiyena vositalari", "Oziq-ovqat", "Boshqa", "✏️ Boshqa (Qo'lda kiritish)"])
            kat_nomi = st.text_input("Kategoriyani yozing:") if kat_tanlov == "✏️ Boshqa (Qo'lda kiritish)" else kat_tanlov
            if kat_nomi == "Ichimliklar": sub_tanlov = st.selectbox("2. Turi:", ["Banichniy ichimliklar", "Gazli shirin suv (Cola, Fanta...)", "Soklar", "Mineral suv (Gazli/Gazsiz)", "✏️ Boshqa (Qo'lda kiritish)"])
            elif kat_nomi == "Gigiyena vositalari": sub_tanlov = st.selectbox("2. Turi:", ["Komplekt", "Alohida", "✏️ Boshqa (Qo'lda kiritish)"])
            else: sub_tanlov = st.selectbox("2. Turi:", ["Standart", "✏️ Boshqa (Qo'lda kiritish)"])
            sub_kat_nomi = st.text_input("Turni yozing:") if sub_tanlov == "✏️ Boshqa (Qo'lda kiritish)" else sub_tanlov
            tov_nomi = st.text_input("3. Mahsulot nomi (masalan, Coca-Cola):")
        
        with c2:
            hajm_tanlov = st.selectbox("4. Hajmi / O'lchami:", ["0.5 L", "1.0 L", "1.5 L", "Standart (Hajmsiz)", "✏️ Boshqa (Qo'lda kiritish)"])
            hajmi = st.text_input("Hajmni yozing:") if hajm_tanlov == "✏️ Boshqa (Qo'lda kiritish)" else ("" if hajm_tanlov == "Standart (Hajmsiz)" else hajm_tanlov)
            tov_tannarx = st.number_input("5. Olib kelish narxi / Tannarx (UZS):", min_value=0, value=5000, step=500)
            tov_narxi = st.number_input("6. Sotilish narxi (UZS):", min_value=1000, value=10000, step=1000)
            tov_soni = st.number_input("7. Skladga kelgan miqdori (dona):", min_value=1, step=1)
        
        if st.button("Skladga Qo'shish", type="primary", use_container_width=True):
            if not tov_nomi:
                st.error("Mahsulot nomini kiriting!")
            else:
                if db.fetchone("SELECT qoldiq FROM mahsulotlar WHERE nomi=? AND hajmi=?", (tov_nomi, hajmi)):
                    db.execute("UPDATE mahsulotlar SET qoldiq = qoldiq + ?, tannarx = ?, narxi = ? WHERE nomi = ? AND hajmi = ?", (tov_soni, tov_tannarx, tov_narxi, tov_nomi, hajmi))
                    st.success(f"{tov_nomi} qoldig'iga qo'shildi!")
                    jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Qoldiq to'ldirildi", f"{tov_nomi} ({hajmi}) ga {tov_soni} ta qo'shildi. Sotuv narxi: {tov_narxi:,.0f} UZS")
                else:
                    db.execute("INSERT INTO mahsulotlar (nomi, kategoriya, sub_kategoriya, hajmi, tannarx, narxi, qoldiq, izoh) VALUES (?,?,?,?,?,?,?,?)", 
                              (tov_nomi, kat_nomi, sub_kat_nomi, hajmi, tov_tannarx, tov_narxi, tov_soni, ""))
                    st.success(f"Yangi {tov_nomi} omborga qo'shildi!")
                    jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Yangi tovar keldi", f"{tov_nomi} ({hajmi}) {tov_soni} ta kiritildi. Sotuv narxi: {tov_narxi:,.0f} UZS")
                st.rerun()
                
    else:
        df_mahsulot = db.read_df("SELECT nomi, hajmi, kategoriya, sub_kategoriya, tannarx, narxi, qoldiq, izoh FROM mahsulotlar ORDER BY qoldiq ASC")
        if not df_mahsulot.empty: 
            df_mahsulot['izoh'] = df_mahsulot['izoh'].fillna('')
            df_mahsulot['tannarx'] = df_mahsulot['tannarx'].fillna(0)
            df_mahsulot.columns = ["Nomi", "Hajmi", "Kategoriya", "Sub-kat", "Tannarxi", "Sotuv Narxi", "Qoldiq", "Izoh"]
            df_mahsulot['Tannarxi'] = df_mahsulot['Tannarxi'].apply(lambda x: f"{int(x):,} UZS")
            df_mahsulot['Sotuv Narxi'] = df_mahsulot['Sotuv Narxi'].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_mahsulot, use_container_width=True, hide_index=True)
        else:
            st.info("Sklad bo'sh.")

# ----------------------------------------------------
# TAB 7: XARAJATLAR VA SMENA
# ----------------------------------------------------
with t_xarajat:
    render_xarajatlar_va_smena(xodim_ismi, bugungi_sana)

# ----------------------------------------------------
# TAB 8: CEO PANEL
# ----------------------------------------------------
if t5:
    with t5:
        render_ceo_panel(xodim_ismi, bugungi_sana)

# ----------------------------------------------------
# TAB 9: SOZLAMALAR
# ----------------------------------------------------
with t6:
    st.header("⚙️ Shaxsiy parol va ma'lumotlarni o'zgartirish")
    st.markdown(f"**Sizning profilingiz:** {xodim_ismi} (`{st.session_state.user_login}`)")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        with st.form("settings_form"):
            yangi_ism = st.text_input("Ism-Sharifingiz:", value=xodim_ismi)
            yangi_parol = st.text_input("Yangi parol:", type="password")
            parol_tasdiq = st.text_input("Yangi parolni tasdiqlang:", type="password")
            if st.form_submit_button("Ma'lumotlarni saqlash", type="primary"):
                if yangi_parol and yangi_parol != parol_tasdiq:
                    st.error("⚠️ Parollar mos tushmadi!")
                else:
                    if yangi_parol:
                        db.execute("UPDATE users SET ism=?, parol=? WHERE login=?", (yangi_ism, yangi_parol, st.session_state.user_login))
                    else:
                        db.execute("UPDATE users SET ism=? WHERE login=?", (yangi_ism, st.session_state.user_login))
                    jurnalga_yozish("Tizim Sozlamalari", xodim_ismi, "Profil yangilandi", "Foydalanuvchi paroli/ismi o'zgartirildi")
                    st.session_state.logged_in = False
                    st.rerun()