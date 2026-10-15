import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import db, jurnalga_yozish, haftalik_hisobot_yuklash
from tg_bot import tg_xabar_yubor

def render_xarajatlar_va_smena(xodim_ismi, bugungi_sana):
    st.header("💸 Xarajatlar (Rashod) va Smena Topshirish")
    tanlov = st.radio("Bo'limni tanlang:", ["➖ Yangi Xarajat kiritish", "🔄 Smenani yopish (Z-Hisobot)", "📋 Xarajatlar va Smenalar tarixi"], horizontal=True)
    st.markdown("---")

    if tanlov == "➖ Yangi Xarajat kiritish":
        with st.form("xarajat_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                kat = st.selectbox("Xarajat turi:", ["Xo'jalik va Tozalik vositalari", "Kommunal to'lovlar", "Oziq-ovqat (Non, choy...)", "Ta'mirlash (Santexnik, usta...)", "Xodimlar avansi / maoshi", "Boshqa xarajat"])
                summa = st.number_input("Xarajat summasi (UZS):", min_value=1000, step=5000)
            with c2:
                tolov_turi = st.selectbox("Qaysi kassadan olindi?", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                izoh = st.text_input("Batafsil izoh (Nima olindi yoki kimga berildi?):", placeholder="Masalan: Kir yuvish kukuni 3 kg...")

            if st.form_submit_button("➖ Xarajatni tasdiqlash", type="primary", use_container_width=True):
                if not izoh.strip():
                    st.error("Iltimos, xarajat sababini (izohni) yozing!")
                else:
                    hozir = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    db.execute("INSERT INTO xarajatlar (vaqt, sana, kategoriya, summa, tolov_turi, izoh, xodim) VALUES (?,?,?,?,?,?,?)",
                               (hozir, bugungi_sana, kat, summa, tolov_turi, izoh, xodim_ismi))
                    jurnalga_yozish("Kassa (Rashod)", xodim_ismi, "Xarajat qilindi", f"{kat}: {summa:,.0f} UZS ({tolov_turi}) - {izoh}")
                    st.success("✅ Xarajat bazaga kiritildi va haftalik hisobotga qo'shildi!")
                    st.rerun()

    elif tanlov == "🔄 Smenani yopish (Z-Hisobot)":
        st.subheader(f"📊 Bugungi smena hisoboti ({bugungi_sana})")
        df_tol = db.read_df("SELECT * FROM tolovlar_tarixi WHERE sana=?", (bugungi_sana,))
        df_xar = db.read_df("SELECT * FROM xarajatlar WHERE sana=?", (bugungi_sana,))

        naqd_tushum = df_tol[df_tol['tolov_tafsiloti'] == 'Naqd']['summa'].sum() if not df_tol.empty else 0
        karta_tushum = df_tol[df_tol['tolov_tafsiloti'] != 'Naqd']['summa'].sum() if not df_tol.empty else 0
        naqd_xarajat = df_xar[df_xar['tolov_turi'] == 'Naqd']['summa'].sum() if not df_xar.empty else 0
        umumiy_xarajat = df_xar['summa'].sum() if not df_xar.empty else 0
        sof_naqd_kassa = naqd_tushum - naqd_xarajat

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💵 Bugungi Naqd Kirim", f"{naqd_tushum:,.0f} UZS")
        k2.metric("💳 Bugungi Karta/Onlayn", f"{karta_tushum:,.0f} UZS")
        k3.metric("➖ Jami Xarajatlar", f"{umumiy_xarajat:,.0f} UZS")
        k4.metric("🏦 Kassadagi Sof Naqd", f"{sof_naqd_kassa:,.0f} UZS")

        with st.form("smena_form", clear_on_submit=True):
            smena_izoh = st.text_area("Smena bo'yicha izoh (ixtiyoriy):", placeholder="Smena tinch o'tdi, kalitlar va kassa topshirildi...")
            if st.form_submit_button("✅ Smenani yopish va Hisobotga saqlash", type="primary", use_container_width=True):
                hozir = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.execute("INSERT INTO smenalar (vaqt, xodim, naqd_tushum, karta_tushum, xarajatlar_sum, sof_kassa, izoh) VALUES (?,?,?,?,?,?,?)",
                           (hozir, xodim_ismi, naqd_tushum, karta_tushum, umumiy_xarajat, sof_naqd_kassa, smena_izoh))
                jurnalga_yozish("Smena (Z-Hisobot)", xodim_ismi, "Smena yopildi", f"Sof naqd: {sof_naqd_kassa:,.0f}, Karta: {karta_tushum:,.0f}, Rashod: {umumiy_xarajat:,.0f}")
                st.success("🎉 Smena muvaffaqiyatli yopildi va bazaga saqlandi!")
                st.rerun()

    else:
        c_x, c_s = st.columns(2)
        with c_x:
            st.markdown("##### 💸 Oxirgi Xarajatlar")
            df_x = db.read_df("SELECT vaqt, kategoriya, summa, tolov_turi, izoh, xodim FROM xarajatlar ORDER BY id DESC")
            if not df_x.empty:
                df_x.columns = ["Vaqt", "Kategoriya", "Summa", "Kassa", "Izoh", "Xodim"]
                df_x["Summa"] = df_x["Summa"].apply(lambda x: f"{int(x):,} UZS")
                st.dataframe(df_x, use_container_width=True, hide_index=True)
            else:
                st.info("Xarajatlar kiritilmagan.")
        with c_s:
            st.markdown("##### 🔄 Topshirilgan Smenalar")
            df_s = db.read_df("SELECT vaqt, xodim, naqd_tushum, karta_tushum, xarajatlar_sum, sof_kassa, izoh FROM smenalar ORDER BY id DESC")
            if not df_s.empty:
                df_s.columns = ["Vaqt", "Xodim", "Naqd", "Karta", "Rashod", "Sof Kassa", "Izoh"]
                for col in ["Naqd", "Karta", "Rashod", "Sof Kassa"]:
                    df_s[col] = df_s[col].apply(lambda x: f"{int(x):,}")
                st.dataframe(df_s, use_container_width=True, hide_index=True)
            else:
                st.info("Smenalar hali yopilmagan.")


def render_ceo_panel(xodim_ismi, bugungi_sana):
    st.header("👑 CEO Boshqaruv Paneli")
    ceo_tanlov = st.radio(
        "Kerakli bo'limni tanlang:",
        ["📊 Haftalik Hisobot (Sklad va Xarajat)", "🚪 Checkout", "👥 Xodimlar (Adminlar)", "🕵️ Batafsil Audit", "📝 Maxsus Izohlar", "🗑️ O'chirish"],
        horizontal=True
    )
    st.markdown("---")
    df_admin = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")

    if ceo_tanlov == "📊 Haftalik Hisobot (Sklad va Xarajat)":
        st.subheader("📦 Sklad, Market Savdolar va Mayda Xarajatlar bo'yicha Yig'ma Hisobot")
        st.markdown("Telegram botga faqat mijozlar xabari boradi. Sklad kirim-chiqimi, Market savdolari va barcha mayda xarajatlar shu yerda yig'ilib boradi.")
        
        c_d1, c_d2 = st.columns(2)
        with c_d1:
            bosh_sana = st.date_input("Boshlanish sanasi:", datetime.today() - timedelta(days=7))
        with c_d2:
            tugash_sana = st.date_input("Tugash sanasi:", datetime.today())

        b_str = bosh_sana.strftime("%Y-%m-%d")
        t_str = tugash_sana.strftime("%Y-%m-%d")

        df_h_savdo = db.read_df("SELECT * FROM savdolar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (b_str, t_str))
        df_h_xarajat = db.read_df("SELECT * FROM xarajatlar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (b_str, t_str))
        df_h_ombor = db.read_df("SELECT nomi, hajmi, kategoriya, tannarx, narxi, qoldiq FROM mahsulotlar ORDER BY qoldiq ASC")

        jami_savdo_sum = df_h_savdo['jami_summa'].fillna(0).sum() if not df_h_savdo.empty else 0
        jami_xarajat_sum = df_h_xarajat['summa'].fillna(0).sum() if not df_h_xarajat.empty else 0
        ombor_qiymati = (df_h_ombor['narxi'].fillna(0) * df_h_ombor['qoldiq'].fillna(0)).sum() if not df_h_ombor.empty else 0

        m1, m2, m3 = st.columns(3)
        m1.metric(f"🛒 Davr ichida Market Savdosi ({len(df_h_savdo)} ta)", f"{jami_savdo_sum:,.0f} UZS")
        m2.metric(f"➖ Davr ichida Mayda Xarajatlar ({len(df_h_xarajat)} ta)", f"{jami_xarajat_sum:,.0f} UZS")
        m3.metric("📦 Hozirgi Skladdagi Tovarlar Qiymati", f"{ombor_qiymati:,.0f} UZS")

        st.download_button(
            label=f"📥 {b_str} dan {t_str} gacha To'liq Hisobotni Yuklab Olish (Excel)",
            data=haftalik_hisobot_yuklash(b_str, t_str),
            file_name=f"YSH_Haftalik_Hisobot_{b_str}_{t_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

        st.markdown("---")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("##### 🛒 Market Savdolari (Tanlangan davr)")
            if not df_h_savdo.empty:
                st.dataframe(df_h_savdo[['sana', 'mahsulot_nomi', 'miqdor', 'jami_summa', 'tolov_tafsiloti', 'xodim']], use_container_width=True, hide_index=True)
            else:
                st.info("Bu davrda savdo bo'lmagan.")
        with col_t2:
            st.markdown("##### 💸 Mayda-chuyda Xarajatlar (Tanlangan davr)")
            if not df_h_xarajat.empty:
                st.dataframe(df_h_xarajat[['sana', 'kategoriya', 'summa', 'tolov_turi', 'izoh', 'xodim']], use_container_width=True, hide_index=True)
            else:
                st.info("Bu davrda xarajat kiritilmagan.")

    elif ceo_tanlov == "🚪 Checkout":
        if not df_admin.empty:
            faollar = df_admin[df_admin['holat'] != 'Chiqib ketgan']
            if not faollar.empty:
                with st.form("checkout_form"):
                    korsatkich = faollar['mijoz_id'] + " - " + faollar['mijoz'] + " (" + faollar['xona'] + " | Chiqish: " + faollar['chiqish_sanasi'] + " 12:00)"
                    chiq_id_toliq = st.selectbox("Xonani bo'shatadigan mijoz:", korsatkich)
                    if st.form_submit_button("🚪 Mijozni chiqarish va Arxivlash", type="primary"):
                        c_id = chiq_id_toliq.split(" - ")[0]
                        mijoz_qator = faollar[faollar['mijoz_id'] == c_id].iloc[0]
                        if mijoz_qator['qoldiq'] > 0:
                            st.error(f"⚠️ Mijozda {mijoz_qator['qoldiq']:,.0f} UZS qarz bor! Qarz yopilmaguncha chiqarolmaysiz.")
                        else:
                            db.execute("UPDATE bronlar SET holat = 'Chiqib ketgan', chiqish_sanasi = ? WHERE mijoz_id = ?", (bugungi_sana, c_id))
                            jurnalga_yozish(c_id, xodim_ismi, "Checkout", f"Mijoz ({mijoz_qator['mijoz']}) {mijoz_qator['xona']} ni topshirdi")
                            tg_xabar_yubor("Checkout (Mijoz chiqib ketdi)", f"👤 <b>Mijoz:</b> {mijoz_qator['mijoz']}\n🛏 <b>Xona:</b> {mijoz_qator['xona']}", xodim_ismi)
                            st.success("Mijoz arxivlandi!")
                            st.rerun()
            else:
                st.info("Hozircha faol mijozlar yo'q.")
        else:
            st.info("Bazada ma'lumot yo'q.")

    elif ceo_tanlov == "👥 Xodimlar (Adminlar)":
        st.subheader("👥 Tizim foydalanuvchilari va Shaxsiy Admin profillari")
        c_u1, c_u2 = st.columns([1.2, 1])
        with c_u1:
            df_users = db.read_df("SELECT login, ism, role, parol FROM xodimlar")
            df_users.columns = ["Login", "Ism-Sharif (Auditda ko'rinadi)", "Rol", "Parol"]
            st.dataframe(df_users, use_container_width=True, hide_index=True)

            och_royxat = [l for l in df_users["Login"].tolist() if l != 'ceo']
            if och_royxat:
                with st.form("del_user_form"):
                    och_login = st.selectbox("Xodimni o'chirish (Loginni tanlang):", och_royxat)
                    if st.form_submit_button("🗑️ Tanlangan xodimni o'chirish"):
                        db.execute("DELETE FROM xodimlar WHERE login=?", (och_login,))
                        jurnalga_yozish("Xodimlar", xodim_ismi, "Xodim o'chirildi", f"Login: {och_login}")
                        st.success("Xodim o'chirildi!")
                        st.rerun()

            st.markdown("---")
            if st.button("📲 Telegram Bot aloqasini tekshirish (Test xabar)"):
                natija = tg_xabar_yubor("Aloqa tekshiruvi", "✅ Telegram bot faqat Mijozlar bo'yicha ma'lumotlarni yuborishga sozlandi!", xodim_ismi)
                if natija:
                    st.success("✅ Telegramingizga xabar yuborildi!")
                else:
                    st.error("⚠️ Xabar bormadi. Token va Chat ID ni tekshiring.")

        with c_u2:
            st.markdown("##### ➕ Yangi Admin (Xodim) qo'shish")
            with st.form("new_user_form", clear_on_submit=True):
                u_ism = st.text_input("Xodim Ism-Sharifi (masalan: Admin Sardor)")
                u_login = st.text_input("Kirish uchun Login (masalan: sardor)")
                u_parol = st.text_input("Parol")
                u_role = st.selectbox("Huquqi (Roli):", ["admin", "ceo"])
                if st.form_submit_button("➕ Xodimni yaratish", type="primary", use_container_width=True):
                    if u_ism.strip() and u_login.strip() and u_parol.strip():
                        mavjud = db.fetchone("SELECT login FROM xodimlar WHERE login=?", (u_login.strip(),))
                        if mavjud:
                            st.error("Bunday login band! Boshqa login yozing.")
                        else:
                            db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES (?,?,?,?)",
                                       (u_login.strip(), u_role, u_parol.strip(), u_ism.strip()))
                            jurnalga_yozish("Xodimlar", xodim_ismi, "Yangi xodim qo'shildi", f"{u_ism} ({u_login}) - {u_role}")
                            st.success(f"✅ {u_ism} tizimga qo'shildi!")
                            st.rerun()
                    else:
                        st.error("Barcha maydonlarni to'ldiring!")

    elif ceo_tanlov == "🕵️ Batafsil Audit":
        df_audit = db.read_df("SELECT * FROM audit_log ORDER BY id DESC")
        if not df_audit.empty:
            qidir_audit = st.text_input("🔍 Audit ichidan qidirish (Xodim ismi, harakat yoki mijoz bo'yicha):")
            if qidir_audit:
                df_audit = df_audit[
                    df_audit['xodim'].str.contains(qidir_audit, case=False, na=False) |
                    df_audit['harakat'].str.contains(qidir_audit, case=False, na=False) |
                    df_audit['tafsilot'].str.contains(qidir_audit, case=False, na=False)
                ]
            df_a_korsatish = df_audit[['vaqt', 'mijoz_id', 'xodim', 'harakat', 'tafsilot']].copy()
            df_a_korsatish.columns = ["Sana va Vaqt", "Obyekt / ID", "Mas'ul Xodim", "Harakat Turi", "Batafsil ma'lumot"]
            st.dataframe(df_a_korsatish, use_container_width=True, hide_index=True)
        else:
            st.info("Hozircha tizimda o'zgarishlar qayd etilmagan.")

    elif ceo_tanlov == "📝 Maxsus Izohlar":
        st.markdown("Bu yerdagi izohlarni faqat CEO yoza oladi. Ular adminlarga asosiy jadvallarda ko'rinadi.")
        izoh_tanlov = st.radio("Qaysi bazaga izoh yozasiz?", ["Mijozlar (Bronlar)", "Sklad (Mahsulotlar)"], horizontal=True)
        if izoh_tanlov == "Mijozlar (Bronlar)":
            df_b = db.read_df("SELECT mijoz_id, mijoz, xona, izoh FROM bronlar WHERE holat!='Chiqib ketgan'")
            if not df_b.empty:
                with st.form("izoh_mijoz_form"):
                    t_mijoz = st.selectbox("Mijozni tanlang:", df_b['mijoz_id'] + " - " + df_b['mijoz'] + " (" + df_b['xona'] + ")")
                    yangi_izoh = st.text_area("Izoh yozing:")
                    if st.form_submit_button("Izohni Saqlash (Mijoz)"):
                        m_id_izoh = t_mijoz.split(" - ")[0]
                        db.execute("UPDATE bronlar SET izoh=? WHERE mijoz_id=?", (yangi_izoh, m_id_izoh))
                        jurnalga_yozish(m_id_izoh, xodim_ismi, "Maxfiy Izoh yozildi", f"Yangi izoh: {yangi_izoh}")
                        st.success("Mijozga izoh qo'shildi!")
                        st.rerun()
            else:
                st.info("Faol mijozlar yo'q.")
        else:
            df_m = db.read_df("SELECT id, nomi, hajmi, qoldiq, izoh FROM mahsulotlar")
            if not df_m.empty:
                with st.form("izoh_sklad_form"):
                    df_m['korsatkich'] = df_m['nomi'] + " " + df_m['hajmi'] + " (" + df_m['qoldiq'].astype(str) + " ta)"
                    t_mahs = st.selectbox("Mahsulotni tanlang:", df_m['korsatkich'])
                    yangi_izoh_m = st.text_area("Izoh yozing:")
                    if st.form_submit_button("Izohni Saqlash (Mahsulot)"):
                        m_id_m = df_m[df_m['korsatkich'] == t_mahs]['id'].values[0]
                        db.execute("UPDATE mahsulotlar SET izoh=? WHERE id=?", (yangi_izoh_m, int(m_id_m)))
                        jurnalga_yozish(f"Sklad (ID:{m_id_m})", xodim_ismi, "Maxfiy Izoh yozildi", f"Yangi izoh: {yangi_izoh_m}")
                        st.success("Mahsulotga izoh qo'shildi!")
                        st.rerun()
            else:
                st.info("Skladda mahsulot yo'q.")

    elif ceo_tanlov == "🗑️ O'chirish":
        st.error("🚨 XAVFLI ZONA: Bu yerdan o'chirilgan mijoz qayta tiklanmaydi!")
        if not df_admin.empty:
            with st.form("del_mijoz_form"):
                del_id = st.selectbox("O'chiriladigan ID:", df_admin['mijoz_id'] + " - " + df_admin['mijoz'])
                if st.form_submit_button("⚠️ Butunlay o'chirish"):
                    och_id = del_id.split(" - ")[0]
                    och_ism = del_id.split(" - ")[1]
                    db.execute("DELETE FROM bronlar WHERE mijoz_id = ?", (och_id,))
                    jurnalga_yozish(och_id, xodim_ismi, "O'chirish (Xavfli)", f"Mijoz ({och_ism}) bazadan o'chirildi")
                    tg_xabar_yubor("Mijoz bazadan o'chirildi!", f"🆔 <b>ID:</b> {och_id}\n👤 <b>Mijoz:</b> {och_ism}", xodim_ismi, muhim=True)
                    st.success("O'chirildi!")
                    st.rerun()
        else:
            st.info("Bazada ma'lumot yo'q.")