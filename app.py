import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from database import (
    db, init_db, IS_POSTGRES, XONALAR, BARCHA_XONALAR_ROYXATI, XONA_TOMON_MAP, MUDDATLAR,
    xona_sigimini_ol, narx_hisobla, id_yaratish,
    jurnalga_yozish, barcha_bazani_yuklash, chiroyli_kartochka, rangla_jadval
)
from tg_bot import tg_xabar_yubor
from ceo_panel import render_xarajatlar_va_smena, render_ceo_panel

# Toshkent vaqti (UTC + 5 soat)
def toshkent_vaqti():
    return datetime.now(timezone.utc) + timedelta(hours=5)

st.set_page_config(page_title="Yangi Sergeli Hostel CRM", layout="wide")
st.markdown("""<style>div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e6ed; padding: 15px 20px; border-radius: 12px; border-left: 6px solid #4CAF50; box-shadow: 2px 4px 15px rgba(0,0,0,0.05); }</style>""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'role' not in st.session_state: st.session_state.role = None
if 'user_login' not in st.session_state: st.session_state.user_login = ""
if 'xodim_ismi' not in st.session_state: st.session_state.xodim_ismi = ""

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
# 1. LOGIN OYNASI (ZAGRUZKASIZ FORM)
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
# 2. SIDEBAR VA NAVIGATSIYA
# ==========================================
xodim_ismi = st.session_state.xodim_ismi
hozirgi_uz_vaqt = toshkent_vaqti()
bugungi_sana = hozirgi_uz_vaqt.strftime("%Y-%m-%d")

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
    st.query_params.clear()
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

    st.markdown("---")
    st.subheader("🧮 Kassadagi Sof Tushum (Foyda)")
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
                st.info(f"**{tur}**\n\n### {qoldiq_s:,.0f} UZS\n*(Kirim: {kirim_s:,.0f} | Xarajat: {chiqim_s:,.0f})*")
    else:
        st.info("Hali kassa tushumlari mavjud emas.")

    df_mahsulotlar = db.read_df("SELECT * FROM mahsulotlar WHERE qoldiq <= 5")
    if not df_mahsulotlar.empty:
        st.error(f"🚨 **DIQQAT: Quyidagi {len(df_mahsulotlar)} ta mahsulot omborda tugayapti!**")
        st.warning("🛒 " + ", ".join([f"{r['nomi']} ({r['qoldiq']} ta qoldi)" for _, r in df_mahsulotlar.iterrows()]))

# ----------------------------------------------------
# TAB 2: QABUL VA BRON (Qanotlar ajratilgan + Zagruzkasiz Form!)
# ----------------------------------------------------
with t2:
    st.subheader("📝 Yangi Mijoz Qabul Qilish / Bron")
    
    # 1. Qanotni tanlash (xonalar faqat shu qanot bo'yicha chiqishi uchun)
    tomon = st.radio(
        "📍 Avval qanotni (tomonni) tanlang:",
        ["Chap tomon", "O'rtadagi", "O'ng tomon"],
        horizontal=True
    )
    
    # Tanlangan qanotdagi xonalarni krovat turi va sig'imi bilan chiroyli shakllantirish
    xona_variantlar = []
    for x_nom, (sigim, _) in XONALAR[tomon].items():
        if tomon == "O'rtadagi":
            tavsif = f"{x_nom} (2 kishilik - Bitta Dvuxspalniy)"
        elif sigim == 2:
            tavsif = f"{x_nom} (2 kishilik - 2 ta alohida krovat)"
        else:
            tavsif = f"{x_nom} ({sigim} kishilik)"
        xona_variantlar.append(tavsif)

    # 2. Asosiy ma'lumotlar formasi (ichida hech qanday zagruzka bo'lmaydi)
    with st.form("qabul_form", clear_on_submit=True):
        bron_turi = st.radio("📌 Ro'yxatdan o'tish turi:", ["Hozir qabul qilish (Kirish)", "Oldindan band qilish (Bron)"], horizontal=True)
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            mijoz_ism = st.text_input("Mijoz F.I.O / Telefon / Pasport")
            jinsi = st.radio("Jinsi", ["Erkak", "Ayol"], horizontal=True)
            toifa = st.selectbox("Mijoz toifasi", ["O'zbekiston fuqarosi", "Chet el fuqarosi", "Talaba (Student)"])
            kirish_sanasi = st.date_input("Kirish (kelish) sanasi", toshkent_vaqti().date())
            
        with col2:
            tanlangan_xona_label = st.selectbox(f"🛏 Xona raqami ({tomon}):", xona_variantlar)
            maks_odam = 2 if tomon == "O'rtadagi" else 4
            odam_soni = st.number_input(f"Odam soni (1 - {maks_odam})", min_value=1, max_value=maks_odam, value=1)
            kunlar = st.number_input("Necha kun yashaydi? (7+ kunga 10% chegirma)", min_value=1, max_value=365, value=1)
            maxsus_kunlik = st.number_input("⚙️ Admin maxsus KUNLIK narx (0 = Avto standart hisoblash)", min_value=0, value=0, step=5000)

        with col3:
            tolangan = st.number_input("Hozir to'lanayotgan summa (UZS):", min_value=0, value=0, step=10000)
            tolov_shakli = st.selectbox("To'lov shakli", ["Naqd", "Karta", "Onlayn"])
            t_taf = st.selectbox("To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
            qoshimcha_izoh = st.text_input("Izoh (yoki 'Boshqa' to'lov turi nomi):", placeholder="Payme, Pasport seriya va h.k.")

        submit_qabul = st.form_submit_button("✅ BAZAGA SAQLASH", type="primary", use_container_width=True)

        if submit_qabul:
            if not mijoz_ism.strip():
                st.error("⚠️ Mijoz ismini kiriting!")
            else:
                xona = tanlangan_xona_label.split(" (")[0].strip()
                xona_sigimi = XONALAR[tomon][xona][0]
                xona_turi_matn = "Dvuxspalniy" if tomon == "O'rtadagi" else ("2 alohida krovat" if xona_sigimi == 2 else f"{xona_sigimi} kishilik")
                
                chiqish_sanasi = kirish_sanasi + timedelta(days=kunlar)
                kirish_str = kirish_sanasi.strftime("%Y-%m-%d")
                chiqish_str = chiqish_sanasi.strftime("%Y-%m-%d")
                
                band_res = db.fetchone("SELECT SUM(odam_soni) FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<? AND chiqish_sanasi>?", (xona, chiqish_str, kirish_str))
                band = band_res[0] if band_res and band_res[0] else 0
                bosh_joy = xona_sigimi - band
                
                if odam_soni > xona_sigimi:
                    st.error(f"⚠️ {xona} jami {xona_sigimi} kishilik! Siz {odam_soni} kishi kiritdingiz.")
                elif odam_soni > bosh_joy:
                    st.error(f"⚠️ Xatolik: {xona} da tanlangan sanalar uchun faqat {bosh_joy} ta bo'sh joy bor (Siz {odam_soni} kishi kiritdingiz)!")
                else:
                    kunlik_stavka, standart_jami = narx_hisobla(tomon, xona, toifa, odam_soni, kunlar)
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
                    kirish_vaqti_toliq = f"{kirish_str} ({uz_now.strftime('%H:%M')})"
                    muddat_nomi = f"{kunlar} kun"

                    db.execute("""INSERT INTO bronlar (mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar, kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti, holat, kirish_sanasi, chiqish_sanasi, bron_turi, izoh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (yangi_id, jinsi, kirish_vaqti_toliq, tomon, xona, xona_turi_matn, mijoz_ism.strip(), toifa, odam_soni, muddat_nomi, kunlar, kunlik_stavka, standart_jami, yakuniy_narx, tolangan, qoldiq, tolov_shakli, t_taf, holat, kirish_str, chiqish_str, saq_turi, qoshimcha_izoh.strip()))
                    if tolangan > 0:
                        db.execute("INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                   (hozirgi_sana, yangi_id, mijoz_ism.strip(), "Yotoq (Qabul)", tolangan, tolov_shakli, t_taf, xodim_ismi))
                    jurnalga_yozish(yangi_id, xodim_ismi, "Yangi " + saq_turi, f"Mijoz: {mijoz_ism}, Xona: {xona} ({xona_turi_matn}), Kirish: {kirish_vaqti_toliq}, To'ladi: {tolangan:,.0f} ({t_taf})")
                    
                    tg_xabar_yubor(
                        f"Yangi {saq_turi}",
                        f"👤 <b>Mijoz:</b> {mijoz_ism} ({odam_soni} kishi)\n"
                        f"🛏 <b>Xona:</b> {xona} — {xona_turi_matn} ({kunlar} kun)\n"
                        f"🕒 <b>Kirish:</b> {kirish_vaqti_toliq} ➡️ <b>Chiqish:</b> {chiqish_str} 12:00\n"
                        f"💰 <b>Jami hisob:</b> {yakuniy_narx:,.0f} UZS\n"
                        f"✅ <b>To'ladi:</b> {tolangan:,.0f} UZS ({t_taf})\n"
                        f"⚠️ <b>Qoldiq qarz:</b> {qoldiq:,.0f} UZS",
                        xodim_ismi, muhim=maxsus_belgi
                    )
                    st.success(f"✅ Mijoz ({mijoz_ism}) {xona} ({xona_turi_matn}) ga muvaffaqiyatli joylashtirildi! Jami hisob: {yakuniy_narx:,.0f} UZS")
                    st.rerun()

# ----------------------------------------------------
# TAB 3: METRO SHAXMATKA
# ----------------------------------------------------
with t3:
    st.header("🔲 15-kunlik Xonalar Shaxmatkasi")
    col_kat, col_san = st.columns([2, 1])
    tanlangan_katalog = col_kat.radio("Qanot:", ["Barchasi", "Chap tomon", "O'rtadagi", "O'ng tomon"], horizontal=True)
    bosh_sana = col_san.date_input("Boshlanish sanasi:", toshkent_vaqti().date())
    
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
        
        bugun_ichidagilar = db.fetchall("SELECT mijoz, jinsi, sana, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi<=? AND chiqish_sanasi>?", (xona_nomi, bugungi_sana, bugungi_sana))
        kelajakdagi_bronlar = db.fetchall("SELECT mijoz, jinsi, kirish_sanasi, chiqish_sanasi, tolagan_summa, qoldiq, odam_soni, izoh FROM bronlar WHERE xona=? AND holat!='Chiqib ketgan' AND kirish_sanasi>?", (xona_nomi, bugungi_sana))
        
        if not bugun_ichidagilar and not kelajakdagi_bronlar:
            st.success(f"🟢 **XONA TO'LIQ BO'SH — {xona_nomi} ({umumiy_sigim} kishilik)**")
        elif not bugun_ichidagilar and kelajakdagi_bronlar:
            eng_yaqin = sorted(kelajakdagi_bronlar, key=lambda x: x[2])[0]
            st.warning(f"🟡 **XONA HOZIR BO'SH, lekin {eng_yaqin[2]} dan boshlab band qilingan! — {xona_nomi}**")
        else:
            band_qilingan_joylar = sum([m[6] for m in bugun_ichidagilar])
            qoldiq_joy = umumiy_sigim - band_qilingan_joylar
            if qoldiq_joy > 0: st.warning(f"🟡 **XONADA HOZIR MIJOZLAR BOR — Qoldiq o'rin: {qoldiq_joy} ta. {xona_nomi}**")
            else: st.error(f"🔴 **XONA HOZIR TO'LIQ BAND — {xona_nomi}**")
        
        if bugun_ichidagilar:
            st.markdown("**Hozirgi mijozlar:**")
            for m in bugun_ichidagilar:
                qarz_matni = f" | ⚠️ Qarz: {m[5]:,.0f} UZS" if m[5] > 0 else ""
                st.markdown(f"- **{m[0]}** ({m[6]} kishi | 📥 Kirgan: {m[2]} | 🛫 Chiqish: {m[3]} 12:00){qarz_matni}")
                if m[7]: st.info(f"💡 **Izoh:** {m[7]}")
                
        if kelajakdagi_bronlar:
            st.info(f"📅 **Ushbu xonaga kelajakdagi bronlar ({len(kelajakdagi_bronlar)} ta):**")
            for b in kelajakdagi_bronlar:
                b_qarz = f" | ⚠️ Qarz: {b[5]:,.0f} UZS" if b[5] > 0 else ""
                st.markdown(f"- 🕒 Keladi: **{b[2]} 12:00** ({b[6]} kishi) - **{b[0]}** • 🛫 Ketadi: {b[3]} 12:00{b_qarz}")
                if b[7]: st.info(f"💡 **Izoh:** {b[7]}")
    else:
        st.info("👆 Ma'lumotni ko'rish uchun yuqoridagi jadvaldan biror qatorni ustiga bosing.")

# ----------------------------------------------------
# TAB 4: FRONT-OFIS (Kirish sanasi va Soati + Tahrirlash + Zagruzkasiz Formlar)
# ----------------------------------------------------
with t4:
    st.header("💼 Mijozlar va Boshqaruv (Front-Ofis)")
    df = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")
    
    qidiruv = st.text_input("🔍 Mijoz F.I.O, ID yoki Xona bo'yicha tezkor qidiruv:", placeholder="Ism, ID yoki xona raqamini yozing...")
    
    if not df.empty:
        df['faktik_narx'] = df['faktik_narx'].fillna(0)
        df['tolagan_summa'] = df['tolagan_summa'].fillna(0)
        df['qoldiq'] = df['qoldiq'].fillna(0)
        df['izoh'] = df['izoh'].fillna('')
        
        # Agar eski mijozlarda 'sana' ustunida soat bo'lmasa, kirish_sanasi bilan to'ldiramiz
        df['kirish_vaqti_korsat'] = df.apply(
            lambda r: str(r['sana']) if '(' in str(r.get('sana', '')) else f"{r.get('kirish_sanasi', '')} (12:00)",
            axis=1
        )
        
        if qidiruv:
            df = df[df['mijoz'].str.contains(qidiruv, case=False, na=False) | df['mijoz_id'].str.contains(qidiruv, case=False, na=False) | df['xona'].str.contains(qidiruv, case=False, na=False)]
        
        faol_df = df[(df['holat'] != 'Chiqib ketgan') & (df['kirish_sanasi'] <= bugungi_sana)]
        bron_df = df[(df['holat'] != 'Chiqib ketgan') & (df['kirish_sanasi'] > bugungi_sana)]
        barcha_faol_va_bron = df[df['holat'] != 'Chiqib ketgan']
    else:
        faol_df = pd.DataFrame()
        bron_df = pd.DataFrame()
        barcha_faol_va_bron = pd.DataFrame()

    if not bron_df.empty:
        st.subheader("📅 Oldindan Bron qilinganlar")
        bron_korsatish = bron_df[['mijoz_id', 'mijoz', 'xona', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'izoh']].copy()
        bron_korsatish.columns = ["ID", "Mijoz", "Xona", "Odam", "Kun", "Jami Summa", "To'langan", "Qoldiq", "Kirish (Sana va Soat)", "Chiqish Sanasi", "Izoh"]
        for col in ["Jami Summa", "To'langan", "Qoldiq"]: bron_korsatish[col] = bron_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
        st.dataframe(bron_korsatish, use_container_width=True, hide_index=True)

    st.subheader("🟢 Hozirgi (Faol) Mijozlar")
    if not faol_df.empty:
        faol_korsatish = faol_df[['mijoz_id', 'mijoz', 'xona', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'qoldiq', 'kirish_vaqti_korsat', 'chiqish_sanasi', 'holat', 'izoh']].copy()
        faol_korsatish['chiqish_sanasi'] = faol_korsatish['chiqish_sanasi'] + ' 12:00'
        faol_korsatish.columns = ["ID", "Mijoz", "Xona", "Odam", "Kun", "Jami Summa", "To'langan", "Qoldiq", "Kirish (Sana va Soat)", "Chiqish", "Holat", "Izoh"]
        for col in ["Jami Summa", "To'langan", "Qoldiq"]: faol_korsatish[col] = faol_korsatish[col].apply(lambda x: f"{int(x):,} UZS")
        st.dataframe(faol_korsatish.style.apply(rangla_jadval, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("📭 Hozircha hostelda faol mijozlar yo'q. Yangi mehmon kiritish uchun **📝 Qabul** bo'limiga o'ting.")
    
    st.markdown("---")
    st.subheader("🛠️ Mijozlar Boshqaruvi va Tahrirlash (Zagruzkasiz)")
    amal_tanlov = st.radio("Amalni tanlang:", ["💳 Qarzni yopish", "➕ Muddatni cho'zish", "🛏 Xonadan-xonaga ko'chirish", "✏️ Mijoz ma'lumotlarini tahrirlash (O'zgartirish)"], horizontal=True)

    if amal_tanlov == "💳 Qarzni yopish":
        qarzdorlar = df[(df['qoldiq'] > 0) & (df['holat'] != 'Chiqib ketgan')] if not df.empty else pd.DataFrame()
        if not qarzdorlar.empty:
            with st.form("qarz_form", clear_on_submit=True):
                c_q1, c_q2 = st.columns(2)
                with c_q1:
                    tanlangan_qarz = st.selectbox("Qarzdor mijozni tanlang:", qarzdorlar['mijoz_id'] + " - " + qarzdorlar['mijoz'] + " (Qarzi: " + qarzdorlar['qoldiq'].astype(int).astype(str) + " UZS)")
                    tolov_sum = st.number_input("Olinayotgan summa (UZS):", min_value=1000, step=5000, value=50000)
                with c_q2:
                    t_shakl = st.selectbox("Qarz To'lov shakli", ["Naqd", "Karta", "Onlayn"])
                    t_tafsiloti = st.selectbox("Qarz To'lov turi", ["Naqd", "Terminal", "Click", "Uzcard", "Humo", "Boshqa"])
                    qarz_izoh = st.text_input("Qo'shimcha izoh (ixtiyoriy):")
                
                if st.form_submit_button("✅ To'lovni tasdiqlash", type="primary", use_container_width=True):
                    q_id = tanlangan_qarz.split(" - ")[0]
                    q_mijoz_ism = qarzdorlar[qarzdorlar['mijoz_id'] == q_id]['mijoz'].values[0]
                    if t_tafsiloti == "Boshqa" and qarz_izoh: t_tafsiloti = f"Boshqa ({qarz_izoh})"
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
            with st.form("muddat_form"):
                tanlangan_id_chozish = st.selectbox("Mijozni tanlang:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (" + barcha_faol_va_bron['xona'] + ")")
                qoshimcha_kun = st.number_input("Necha kun qo'shilmoqda?", min_value=1, value=1)
                if st.form_submit_button("➕ Muddatni cho'zish", type="primary", use_container_width=True):
                    m_id = tanlangan_id_chozish.split(" - ")[0]
                    mijoz_data = barcha_faol_va_bron[barcha_faol_va_bron['mijoz_id'] == m_id].iloc[0]
                    yangi_chiqish = datetime.strptime(mijoz_data['chiqish_sanasi'], "%Y-%m-%d") + timedelta(days=qoshimcha_kun)
                    q_sum = mijoz_data['kunlik_narx'] * qoshimcha_kun
                    db.execute("UPDATE bronlar SET kunlar=kunlar+?, qoldiq=qoldiq+?, jami_summa=jami_summa+?, faktik_narx=faktik_narx+?, chiqish_sanasi=?, holat='Qarzdorlik' WHERE mijoz_id=?", (qoshimcha_kun, q_sum, q_sum, q_sum, yangi_chiqish.strftime("%Y-%m-%d"), m_id))
                    jurnalga_yozish(m_id, xodim_ismi, "Muddat cho'zildi", f"+{qoshimcha_kun} kun ({q_sum:,.0f} UZS)")
                    tg_xabar_yubor("Muddat cho'zildi", f"👤 <b>Mijoz:</b> {mijoz_data['mijoz']}\n➕ <b>Qo'shildi:</b> +{qoshimcha_kun} kun ({q_sum:,.0f} UZS)", xodim_ismi)
                    st.success("Muddat cho'zildi!")
                    st.rerun()
        else:
            st.info("Faol mijozlar mavjud emas.")

    elif amal_tanlov == "🛏 Xonadan-xonaga ko'chirish":
        if not barcha_faol_va_bron.empty:
            with st.form("kochirish_form"):
                koch_mijoz = st.selectbox("Ko'chiriladigan mijoz:", barcha_faol_va_bron['mijoz_id'] + " - " + barcha_faol_va_bron['mijoz'] + " (Hozir: " + barcha_faol_va_bron['xona'] + ")")
                y_xona_toliq = st.selectbox("Yangi Xonani tanlang:", BARCHA_XONALAR_ROYXATI)
                if st.form_submit_button("🔄 Xonani almashtirish", type="primary", use_container_width=True):
                    k_id = koch_mijoz.split(" - ")[0]
                    k_data = barcha_faol_va_bron[barcha_faol_va_bron['mijoz_id'] == k_id].iloc[0]
                    y_tomon = y_xona_toliq.split(" | ")[0]
                    y_xona = y_xona_toliq.split(" | ")[1].split(" (")[0].strip()
                    eski_xona = k_data['xona']
                    db.execute("UPDATE bronlar SET tomon=?, xona=? WHERE mijoz_id=?", (y_tomon, y_xona, k_id))
                    jurnalga_yozish(k_id, xodim_ismi, "Xona ko'chirildi", f"{k_data['mijoz']}: {eski_xona} -> {y_xona}")
                    tg_xabar_yubor("Xona almashtirildi", f"👤 <b>Mijoz:</b> {k_data['mijoz']}\n🔄 <b>Ko'chirildi:</b> {eski_xona} ➡️ {y_xona}", xodim_ismi)
                    st.success(f"Mijoz {y_xona} ga ko'chirildi!")
                    st.rerun()
        else:
            st.info("Ko'chirish uchun faol mijoz yo'q.")

    elif amal_tanlov == "✏️ Mijoz ma'lumotlarini tahrirlash (O'zgartirish)":
        if not df.empty:
            tahrir_tanlov = st.selectbox("Tahrirlanadigan mijozni tanlang:", df['mijoz_id'] + " - " + df['mijoz'] + " (" + df['xona'] + ")")
            t_id = tahrir_tanlov.split(" - ")[0]
            t_row = df[df['mijoz_id'] == t_id].iloc[0]

            with st.form("tahrirlash_form"):
                st.caption(f"🆔 Mijoz ID: **{t_id}** ma'lumotlarini o'zgartirish")
                e1, e2, e3 = st.columns(3)
                with e1:
                    y_ism = st.text_input("Mijoz F.I.O / Telefon:", value=str(t_row['mijoz']))
                    joriy_xona_idx = 0
                    for idx, x_str in enumerate(BARCHA_XONALAR_ROYXATI):
                        if f"| {t_row['xona']} (" in x_str:
                            joriy_xona_idx = idx
                            break
                    y_xona_str = st.selectbox("Xona:", BARCHA_XONALAR_ROYXATI, index=joriy_xona_idx)
                    y_odam = st.number_input("Odam soni:", min_value=1, max_value=10, value=int(t_row['odam_soni'] or 1))
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
                    y_tolagan = st.number_input("Jami to'lagan summasi (UZS):", min_value=0, value=int(t_row['tolagan_summa'] or 0), step=10000)
                    y_holat = st.selectbox("Holati:", ["To'langan", "Qarzdorlik", "Chiqib ketgan"], index=0 if t_row['holat']=="To'langan" else (2 if t_row['holat']=="Chiqib ketgan" else 1))
                    y_izoh = st.text_input("Izoh:", value=str(t_row['izoh'] or ''))

                if st.form_submit_button("💾 O'zgarishlarni Saqlash", type="primary", use_container_width=True):
                    y_tomon = y_xona_str.split(" | ")[0]
                    y_xona = y_xona_str.split(" | ")[1].split(" (")[0].strip()
                    y_kirish_str = y_kirish.strftime("%Y-%m-%d")
                    y_sana_vaqt_toliq = f"{y_kirish_str} ({y_soat.strip()})"
                    y_chiqish_str = (y_kirish + timedelta(days=y_kunlar)).strftime("%Y-%m-%d")
                    y_qoldiq = y_faktik - y_tolagan
                    if y_holat != "Chiqib ketgan":
                        y_holat = "To'langan" if y_qoldiq <= 0 else "Qarzdorlik"

                    db.execute("""
                        UPDATE bronlar SET 
                            mijoz=?, tomon=?, xona=?, odam_soni=?, sana=?, kirish_sanasi=?, chiqish_sanasi=?,
                            kunlar=?, faktik_narx=?, jami_summa=?, tolagan_summa=?, qoldiq=?, holat=?, izoh=?
                        WHERE mijoz_id=?
                    """, (y_ism.strip(), y_tomon, y_xona, y_odam, y_sana_vaqt_toliq, y_kirish_str, y_chiqish_str, y_kunlar, y_faktik, y_faktik, y_tolagan, y_qoldiq, y_holat, y_izoh.strip(), t_id))
                    
                    jurnalga_yozish(t_id, xodim_ismi, "Mijoz tahrirlandi", f"Ism: {y_ism}, Xona: {y_xona}, Kirish: {y_sana_vaqt_toliq}, Jami: {y_faktik:,.0f}, To'lagan: {y_tolagan:,.0f}")
                    tg_xabar_yubor(
                        "Mijoz ma'lumotlari tahrirlandi",
                        f"🆔 <b>ID:</b> {t_id}\n"
                        f"👤 <b>Mijoz:</b> {y_ism} ({y_xona})\n"
                        f"🕒 <b>Kirish:</b> {y_sana_vaqt_toliq} ➡️ <b>Chiqish:</b> {y_chiqish_str} ({y_kunlar} kun)\n"
                        f"💰 <b>Yangi jami:</b> {y_faktik:,.0f} UZS | <b>To'lagan:</b> {y_tolagan:,.0f} UZS | <b>Qoldiq:</b> {y_qoldiq:,.0f} UZS",
                        xodim_ismi, muhim=True
                    )
                    st.success("✅ Mijoz ma'lumotlari muvaffaqiyatli yangilandi!")
                    st.rerun()
        else:
            st.info("Tahrirlash uchun bazada mijoz yo'q.")

# ----------------------------------------------------
# TAB 5: MARKET (Zagruzkasiz Form)
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
            mahsulotlar['Toliq_Nomi'] = mahsulotlar.apply(
                lambda r: f"{r['nomi']} ({r['hajmi']}) — {int(r['narxi']):,} UZS [Qoldi: {r['qoldiq']} ta]" if r['hajmi'] else f"{r['nomi']} — {int(r['narxi']):,} UZS [Qoldi: {r['qoldiq']} ta]",
                axis=1
            )
            faol_bronlar = db.read_df("SELECT mijoz_id, mijoz, xona FROM bronlar WHERE holat != 'Chiqib ketgan'")
            mijoz_variantlar = ["💵 Darhol To'lov (Umumiy xaridor)"]
            if not faol_bronlar.empty:
                mijoz_variantlar += (faol_bronlar['mijoz'] + " (" + faol_bronlar['xona'] + ") - ID: " + faol_bronlar['mijoz_id']).tolist()

            with st.form("market_sotuv_form", clear_on_submit=True):
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    tanlangan_tovar_label = st.selectbox("1. Mahsulotni tanlang:", mahsulotlar['Toliq_Nomi'].tolist())
                    miqdor = st.number_input("2. Sotilayotgan miqdori (dona):", min_value=1, value=1, step=1)
                with col_m2:
                    kim_olayapti = st.selectbox("3. Xaridor (Darhol to'lov yoki Xona qarziga):", mijoz_variantlar)
                    m_tafsiloti = st.selectbox("4. To'lov usuli (Darhol to'lov bo'lsa):", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                
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
                        
                        st.success(f"✅ {miqdor} ta {tovar_nom_qisqa} ({jami_sum:,.0f} UZS) sotildi va savdolar tarixiga qo'shildi!")
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
# TAB 6: OMBOR (Zagruzkasiz Form)
# ----------------------------------------------------
with t_ombor:
    st.header("📦 Sklad (Ombor) Boshqaruvi")
    ombor_tanlov = st.radio("Bo'limni tanlang:", ["📋 Mahsulotlar ro'yxati", "➕ Yangi tovar kiritish"], horizontal=True)
    st.markdown("---")
    
    if ombor_tanlov == "➕ Yangi tovar kiritish":
        with st.form("sklad_add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                kat_nomi = st.selectbox("1. Kategoriya:", ["Ichimliklar", "Gigiyena vositalari", "Oziq-ovqat", "Xo'jalik mollari", "Boshqa"])
                sub_kat_nomi = st.selectbox("2. Turi:", ["Gazli ichimlik", "Gazsiz suv / Sok", "Komplekt", "Alohida / Dona", "Standart"])
                tov_nomi = st.text_input("3. Mahsulot nomi (masalan, Coca-Cola):")
                hajmi = st.text_input("4. Hajmi / O'lchami (masalan: 0.5 L, 1.5 L yoki bo'sh qoldiring):")
            
            with c2:
                tov_tannarx = st.number_input("5. Olib kelish narxi / Tannarx (UZS):", min_value=0, value=5000, step=500)
                tov_narxi = st.number_input("6. Sotilish narxi (UZS):", min_value=1000, value=10000, step=1000)
                tov_soni = st.number_input("7. Skladga kelgan miqdori (dona):", min_value=1, value=10, step=1)
            
            if st.form_submit_button("➕ Skladga Qo'shish", type="primary", use_container_width=True):
                if not tov_nomi.strip():
                    st.error("Mahsulot nomini kiriting!")
                else:
                    t_nom = tov_nomi.strip()
                    t_hajm = hajmi.strip()
                    if db.fetchone("SELECT qoldiq FROM mahsulotlar WHERE nomi=? AND hajmi=?", (t_nom, t_hajm)):
                        db.execute("UPDATE mahsulotlar SET qoldiq = qoldiq + ?, tannarx = ?, narxi = ? WHERE nomi = ? AND hajmi = ?", (tov_soni, tov_tannarx, tov_narxi, t_nom, t_hajm))
                        st.success(f"{t_nom} qoldig'iga +{tov_soni} ta qo'shildi!")
                        jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Qoldiq to'ldirildi", f"{t_nom} ({t_hajm}) ga {tov_soni} ta qo'shildi. Sotuv narxi: {tov_narxi:,.0f} UZS")
                    else:
                        db.execute("INSERT INTO mahsulotlar (nomi, kategoriya, sub_kategoriya, hajmi, tannarx, narxi, qoldiq, izoh) VALUES (?,?,?,?,?,?,?,?)", 
                                  (t_nom, kat_nomi, sub_kat_nomi, t_hajm, tov_tannarx, tov_narxi, tov_soni, ""))
                        st.success(f"Yangi {t_nom} omborga qo'shildi!")
                        jurnalga_yozish("Sklad (Ombor)", xodim_ismi, "Yangi tovar keldi", f"{t_nom} ({t_hajm}) {tov_soni} ta kiritildi. Sotuv narxi: {tov_narxi:,.0f} UZS")
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
                        db.execute("UPDATE xodimlar SET ism=?, parol=? WHERE login=?", (yangi_ism, yangi_parol, st.session_state.user_login))
                    else:
                        db.execute("UPDATE xodimlar SET ism=? WHERE login=?", (yangi_ism, st.session_state.user_login))
                    jurnalga_yozish("Tizim Sozlamalari", xodim_ismi, "Profil yangilandi", "Foydalanuvchi paroli/ismi o'zgartirildi")
                    st.session_state.logged_in = False
                    st.query_params.clear()
                    st.rerun()