import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from database import (
    db, jurnalga_yozish, haftalik_hisobot_yuklash, avto_kenglik_sozla,
    toshkent_vaqti, xona_tozalik_ozgartir, kunlik_svodka_yubor
)
from tg_bot import tg_xabar_yubor

def render_xarajatlar_va_smena(xodim_ismi, bugungi_sana, g_bosh_sana=None, g_tugash_sana=None, g_davr_nomi="Barcha vaqt"):
    st.header("💸 Xarajatlar va Smena Topshirish")
    tanlov = st.radio(
        "Bo'limni tanlang:",
        ["➖ Yangi Xarajat kiritish", "🔄 Smenani yopish (Z-Hisobot)", "📋 Xarajatlar va Smenalar tarixi"],
        horizontal=True
    )
    st.markdown("---")

    if tanlov == "➖ Yangi Xarajat kiritish":
        with st.form("xarajat_form", clear_on_submit=True, enter_to_submit=False):
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                kat = st.selectbox(
                    "Xarajat turi:",
                    [
                        "Xo'jalik va Tozalik vositalari",
                        "Kommunal to'lovlar",
                        "Oziq-ovqat (Non, choy...)",
                        "Ta'mirlash (Santexnik, usta...)",
                        "Xodimlar avansi / maoshi",
                        "Boshqa xarajat"
                    ]
                )
                summa = st.number_input("Xarajat summasi (UZS):", min_value=1000, step=5000)
            with c2:
                tolov_turi = st.selectbox("Qaysi kassadan olindi?", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])
                izoh = st.text_input("Batafsil izoh (Nima olindi yoki kimga berildi?):", placeholder="Masalan: Kir yuvish kukuni 3 kg...")

            if st.form_submit_button("➖ Xarajatni tasdiqlash", type="primary", use_container_width=True):
                if not izoh.strip():
                    st.error("Iltimos, xarajat sababini (izohni) yozing!")
                else:
                    hozir = toshkent_vaqti().strftime("%Y-%m-%d %H:%M:%S")
                    db.execute(
                        "INSERT INTO xarajatlar (vaqt, sana, kategoriya, summa, tolov_turi, izoh, xodim) VALUES (?,?,?,?,?,?,?)",
                        (hozir, bugungi_sana, kat, summa, tolov_turi, izoh.strip(), xodim_ismi)
                    )
                    jurnalga_yozish("Kassa (Xarajat)", xodim_ismi, "Xarajat qilindi", f"{kat}: {summa:,.0f} UZS ({tolov_turi}) - {izoh.strip()}")
                    # FAQAT CEO GA BORADI (kanal='ceo')
                    tg_xabar_yubor(
                        "Kassadan Xarajat qilindi",
                        f"📂 <b>Kategoriya:</b> {kat}\n"
                        f"💸 <b>Summa:</b> -{summa:,.0f} UZS ({tolov_turi})\n"
                        f"📝 <b>Izoh:</b> {izoh.strip()}",
                        xodim_ismi,
                        kanal="ceo"
                    )
                    st.success("✅ Xarajat bazaga kiritildi va CEO Telegramiga yuborildi!")
                    st.rerun()

    elif tanlov == "🔄 Smenani yopish (Z-Hisobot)":
        st.subheader(f"📊 Bugungi smena hisoboti ({bugungi_sana})")
        df_tol = db.read_df("SELECT * FROM tolovlar_tarixi WHERE sana=?", (bugungi_sana,))
        df_xar = db.read_df("SELECT * FROM xarajatlar WHERE sana=?", (bugungi_sana,))

        naqd_tushum = float(df_tol[df_tol['tolov_tafsiloti'] == 'Naqd']['summa'].fillna(0).sum()) if not df_tol.empty else 0.0
        karta_tushum = float(df_tol[df_tol['tolov_tafsiloti'] != 'Naqd']['summa'].fillna(0).sum()) if not df_tol.empty else 0.0
        jami_tushum = naqd_tushum + karta_tushum

        naqd_xarajat = float(df_xar[df_xar['tolov_turi'] == 'Naqd']['summa'].fillna(0).sum()) if not df_xar.empty else 0.0
        karta_xarajat = float(df_xar[df_xar['tolov_turi'] != 'Naqd']['summa'].fillna(0).sum()) if not df_xar.empty else 0.0
        umumiy_xarajat = naqd_xarajat + karta_xarajat

        sof_naqd_kassa = naqd_tushum - naqd_xarajat
        sof_karta_kassa = karta_tushum - karta_xarajat
        umumiy_sof_balans = jami_tushum - umumiy_xarajat

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("💵 Naqd Kirim", f"{naqd_tushum:,.0f} UZS", f"Xarajat: -{naqd_xarajat:,.0f}")
        k2.metric("💳 Karta/Onlayn Kirim", f"{karta_tushum:,.0f} UZS", f"Xarajat: -{karta_xarajat:,.0f}")
        k3.metric("🏦 Sof Naqd Qoldiq", f"{sof_naqd_kassa:,.0f} UZS")
        k4.metric("💳 Sof Karta/Onlayn", f"{sof_karta_kassa:,.0f} UZS")
        k5.metric("💰 Umumiy Sof Balans", f"{umumiy_sof_balans:,.0f} UZS")

        with st.form("smena_form", clear_on_submit=True, enter_to_submit=False):
            smena_izoh = st.text_area("Smena bo'yicha izoh (ixtiyoriy):", placeholder="Smena tinch o'tdi, kalitlar va kassa topshirildi...")
            if st.form_submit_button("✅ Smenani yopish va Hisobotga saqlash", type="primary", use_container_width=True):
                hozir = toshkent_vaqti().strftime("%Y-%m-%d %H:%M:%S")
                izoh_toliq = f"[Sof Naqd: {sof_naqd_kassa:,.0f} | Sof Karta: {sof_karta_kassa:,.0f}] {smena_izoh.strip()}".strip()
                db.execute(
                    "INSERT INTO smenalar (vaqt, xodim, naqd_tushum, karta_tushum, xarajatlar_sum, sof_kassa, izoh) VALUES (?,?,?,?,?,?,?)",
                    (hozir, xodim_ismi, naqd_tushum, karta_tushum, umumiy_xarajat, umumiy_sof_balans, izoh_toliq)
                )
                jurnalga_yozish(
                    "Smena (Z-Hisobot)",
                    xodim_ismi,
                    "Smena yopildi",
                    f"Naqd kirim: {naqd_tushum:,.0f}, Karta kirim: {karta_tushum:,.0f}, Xarajat: {umumiy_xarajat:,.0f}, Sof Naqd: {sof_naqd_kassa:,.0f}, Umumiy Sof: {umumiy_sof_balans:,.0f}"
                )
                tg_xabar_yubor(
                    "Smena Yopildi (Z-Hisobot)",
                    f"💵 <b>Naqd kirim:</b> {naqd_tushum:,.0f} UZS (Sof naqd: <b>{sof_naqd_kassa:,.0f} UZS</b>)\n"
                    f"💳 <b>Karta/Onlayn kirim:</b> {karta_tushum:,.0f} UZS (Sof karta: <b>{sof_karta_kassa:,.0f} UZS</b>)\n"
                    f"➖ <b>Jami Xarajatlar:</b> -{umumiy_xarajat:,.0f} UZS\n"
                    f"💰 <b>Umumiy Sof Balans:</b> <b>{umumiy_sof_balans:,.0f} UZS</b>\n"
                    f"📝 <b>Izoh:</b> {smena_izoh.strip() or '—'}",
                    xodim_ismi,
                    kanal="ceo"
                )
                kunlik_svodka_yubor(xodim_ismi, "Smena yakuni bo'yicha Svodka")
                st.success("🎉 Smena muvaffaqiyatli yopildi va Svodka Telegramga yuborildi!")
                st.rerun()

    else:
        st.info(f"📅 Ko'rsatilayotgan davr: **{g_davr_nomi}**")
        if g_bosh_sana and g_tugash_sana:
            df_x = db.read_df(
                "SELECT vaqt, kategoriya, summa, tolov_turi, izoh, xodim FROM xarajatlar WHERE sana >= ? AND sana <= ? ORDER BY id DESC",
                (g_bosh_sana, g_tugash_sana)
            )
            df_s = db.read_df(
                "SELECT vaqt, xodim, naqd_tushum, karta_tushum, xarajatlar_sum, sof_kassa, izoh FROM smenalar WHERE vaqt >= ? AND vaqt <= ? ORDER BY id DESC",
                (g_bosh_sana + " 00:00:00", g_tugash_sana + " 23:59:59")
            )
        else:
            df_x = db.read_df("SELECT vaqt, kategoriya, summa, tolov_turi, izoh, xodim FROM xarajatlar ORDER BY id DESC")
            df_s = db.read_df("SELECT vaqt, xodim, naqd_tushum, karta_tushum, xarajatlar_sum, sof_kassa, izoh FROM smenalar ORDER BY id DESC")

        jami_x_sum = df_x['summa'].fillna(0).sum() if not df_x.empty else 0
        st.markdown(f"##### 💸 Xarajatlar ro'yxati ({len(df_x)} ta — Jami: {jami_x_sum:,.0f} UZS)")
        if not df_x.empty:
            df_x.columns = ["Vaqt", "Kategoriya", "Summa", "Kassa", "Izoh", "Xodim"]
            df_x["Summa"] = df_x["Summa"].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_x, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_x))
        else:
            st.info("Tanlangan davrda xarajatlar kiritilmagan.")

        st.markdown("---")
        st.markdown(f"##### 🔄 Topshirilgan Smenalar ({len(df_s)} ta)")
        if not df_s.empty:
            df_s.columns = ["Vaqt", "Xodim", "Naqd Kirim", "Karta Kirim", "Jami Xarajat", "Umumiy Sof Balans", "Izoh"]
            for col in ["Naqd Kirim", "Karta Kirim", "Jami Xarajat", "Umumiy Sof Balans"]:
                df_s[col] = df_s[col].apply(lambda x: f"{int(x or 0):,} UZS")
            st.dataframe(df_s, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_s))
        else:
            st.info("Tanlangan davrda smenalar yopilmagan.")


def render_ceo_panel(xodim_ismi, bugungi_sana, g_bosh_sana=None, g_tugash_sana=None, g_davr_nomi="Barcha vaqt"):
    st.header("👑 CEO Boshqaruv Paneli (Y.S.H. ERP)")
    ceo_tanlov = st.radio(
        "Kerakli bo'limni tanlang:",
        [
            "📊 Davriy Hisobot (Sklad va Xarajat)",
            "🚪 Checkout (Va Arxiv)",
            "👥 Xodimlar va Rollar",
            "🕵️ Batafsil Audit",
            "📝 Maxsus Izohlar",
            "🗑️ O'chirish"
        ],
        horizontal=True
    )
    st.markdown("---")
    df_admin = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")

    if ceo_tanlov == "📊 Davriy Hisobot (Sklad va Xarajat)":
        st.subheader(f"📦 Sklad, Market Savdolar va Mayda Xarajatlar Hisoboti — {g_davr_nomi}")
        st.info(f"📅 Hisobot davri: **{g_davr_nomi}**")

        if g_bosh_sana and g_tugash_sana:
            df_h_savdo = db.read_df("SELECT * FROM savdolar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (g_bosh_sana, g_tugash_sana))
            df_h_xarajat = db.read_df("SELECT * FROM xarajatlar WHERE sana >= ? AND sana <= ? ORDER BY id DESC", (g_bosh_sana, g_tugash_sana))
            fayl_davr = f"{g_bosh_sana}_{g_tugash_sana}"
        else:
            df_h_savdo = db.read_df("SELECT * FROM savdolar ORDER BY id DESC")
            df_h_xarajat = db.read_df("SELECT * FROM xarajatlar ORDER BY id DESC")
            fayl_davr = "Barcha_vaqt"

        df_h_ombor = db.read_df("SELECT nomi, hajmi, kategoriya, tannarx, narxi, qoldiq FROM mahsulotlar ORDER BY qoldiq ASC")

        jami_savdo_sum = float(df_h_savdo['jami_summa'].fillna(0).sum()) if not df_h_savdo.empty else 0.0
        darhol_savdo_sum = float(df_h_savdo[df_h_savdo['tolov_turi'] == 'Darhol']['jami_summa'].fillna(0).sum()) if not df_h_savdo.empty else 0.0
        qarzga_savdo_sum = float(df_h_savdo[df_h_savdo['tolov_turi'] == 'Xona']['jami_summa'].fillna(0).sum()) if not df_h_savdo.empty else 0.0
        market_sof_foyda = float(df_h_savdo['sof_foyda'].fillna(0).sum()) if (not df_h_savdo.empty and 'sof_foyda' in df_h_savdo.columns) else 0.0
        jami_xarajat_sum = float(df_h_xarajat['summa'].fillna(0).sum()) if not df_h_xarajat.empty else 0.0
        ombor_qiymati = float((df_h_ombor['narxi'].fillna(0) * df_h_ombor['qoldiq'].fillna(0)).sum()) if not df_h_ombor.empty else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"🛒 Jami Market Savdo ({len(df_h_savdo)} ta)", f"{jami_savdo_sum:,.0f} UZS", f"Kassaga: {darhol_savdo_sum:,.0f} | Qarzga: {qarzga_savdo_sum:,.0f}")
        m2.metric("📈 Market Sof Foydasi (Marja)", f"{market_sof_foyda:,.0f} UZS")
        m3.metric(f"➖ Mayda Xarajatlar ({len(df_h_xarajat)} ta)", f"{jami_xarajat_sum:,.0f} UZS")
        m4.metric("📦 Skladdagi Tovarlar Qiymati", f"{ombor_qiymati:,.0f} UZS")

        b_d1, b_d2 = st.columns([2, 1], gap="medium")
        with b_d1:
            st.download_button(
                label=f"📥 Tanlangan davr ({g_davr_nomi}) bo'yicha To'liq Hisobotni Yuklab Olish (Excel)",
                data=haftalik_hisobot_yuklash(g_bosh_sana, g_tugash_sana),
                file_name=f"Y.S.H._Hisobot_{fayl_davr}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        with b_d2:
            if st.button("📲 24 soatlik Svodkani Telegramga yuborish", use_container_width=True):
                kunlik_svodka_yubor(xodim_ismi, "CEO Tezkor Svodkasi")
                st.success("✅ Svodka Egaga va CEO ga yuborildi!")

        st.markdown("---")
        st.markdown(f"##### 🛒 Market Savdolari ({g_davr_nomi})")
        if not df_h_savdo.empty:
            ustunlar_s = ['sana', 'mahsulot_nomi', 'xaridor', 'miqdor', 'jami_summa', 'sof_foyda', 'tolov_tafsiloti', 'xodim'] if 'sof_foyda' in df_h_savdo.columns else ['sana', 'mahsulot_nomi', 'xaridor', 'miqdor', 'jami_summa', 'tolov_tafsiloti', 'xodim']
            df_hs_view = df_h_savdo[ustunlar_s].copy()
            if 'sof_foyda' in df_hs_view.columns:
                df_hs_view.columns = ["Sana", "Mahsulot", "Xaridor", "Miqdor", "Jami Summa", "Sof Foyda", "To'lov Turi", "Xodim"]
                df_hs_view["Sof Foyda"] = df_hs_view["Sof Foyda"].fillna(0).apply(lambda x: f"{int(x):,} UZS")
            else:
                df_hs_view.columns = ["Sana", "Mahsulot", "Xaridor", "Miqdor", "Jami Summa", "To'lov Turi", "Xodim"]
            df_hs_view["Jami Summa"] = df_hs_view["Jami Summa"].fillna(0).apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_hs_view, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_hs_view))
        else:
            st.info("Tanlangan davrda savdo bo'lmagan.")

        st.markdown(f"##### 💸 Mayda-chuyda Xarajatlar ({g_davr_nomi})")
        if not df_h_xarajat.empty:
            df_hx_view = df_h_xarajat[['sana', 'kategoriya', 'summa', 'tolov_turi', 'izoh', 'xodim']].copy()
            df_hx_view.columns = ["Sana", "Kategoriya", "Summa", "Kassa", "Izoh", "Xodim"]
            df_hx_view["Summa"] = df_hx_view["Summa"].apply(lambda x: f"{int(x):,} UZS")
            st.dataframe(df_hx_view, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_hx_view))
        else:
            st.info("Tanlangan davrda xarajat kiritilmagan.")

    elif ceo_tanlov == "🚪 Checkout (Va Arxiv)":
        if not df_admin.empty:
            faollar = df_admin[df_admin['holat'] != 'Chiqib ketgan']
            arxivdagilar = df_admin[df_admin['holat'] == 'Chiqib ketgan']
            if g_bosh_sana and g_tugash_sana and not arxivdagilar.empty:
                arxivdagilar = arxivdagilar[(arxivdagilar['chiqish_sanasi'] >= g_bosh_sana) & (arxivdagilar['chiqish_sanasi'] <= g_tugash_sana)]

            if not faollar.empty:
                with st.form("checkout_form", enter_to_submit=False):
                    korsatkich = faollar['mijoz_id'] + " - " + faollar['mijoz'] + " (" + faollar['xona'] + " | Chiqish: " + faollar['chiqish_sanasi'] + " 12:00)"
                    chiq_id_toliq = st.selectbox("Muddatidan oldin yoki hozir xonani bo'shatadigan mijoz:", korsatkich)
                    if st.form_submit_button("🚪 Mijozni chiqarish va Arxivlash", type="primary"):
                        c_id = chiq_id_toliq.split(" - ")[0]
                        mijoz_qator = faollar[faollar['mijoz_id'] == c_id].iloc[0]
                        if mijoz_qator['qoldiq'] > 0:
                            st.error(f"⚠️ Mijozda {mijoz_qator['qoldiq']:,.0f} UZS qarz bor! Qarz yopilmaguncha chiqarolmaysiz.")
                        else:
                            db.execute("UPDATE bronlar SET holat = 'Chiqib ketgan', chiqish_sanasi = ? WHERE mijoz_id = ?", (bugungi_sana, c_id))
                            xona_tozalik_ozgartir(mijoz_qator['xona'], "Tozalash kerak")
                            jurnalga_yozish(c_id, xodim_ismi, "Checkout", f"Mijoz ({mijoz_qator['mijoz']}) {mijoz_qator['xona']} ni topshirdi")
                            tg_xabar_yubor("Checkout (Mijoz chiqib ketdi)", f"👤 <b>Mijoz:</b> {mijoz_qator['mijoz']} ({mijoz_qator['odam_soni']} kishi)\n🛏 <b>Xona:</b> {mijoz_qator['xona']} (🧹 Tozalashga berildi)", xodim_ismi, kanal="mijoz")
                            st.success("Mijoz arxivlandi va xona 'Tozalash kerak' ro'yxatiga tushdi!")
                            st.rerun()
            else:
                st.info("Hozircha faol mijozlar yo'q.")

            st.markdown("---")
            arx_odam_jami = int(arxivdagilar['odam_soni'].fillna(1).sum()) if not arxivdagilar.empty else 0
            st.subheader(f"🗄️ Arxivdagi (Chiqib ketgan) mijozlar — {g_davr_nomi} ({arx_odam_jami} kishi / {len(arxivdagilar)} ta bron)")
            if not arxivdagilar.empty:
                arx_view = arxivdagilar[['mijoz_id', 'mijoz', 'xona', 'odam_soni', 'kunlar', 'faktik_narx', 'tolagan_summa', 'sana', 'chiqish_sanasi', 'izoh']].copy()
                arx_view.columns = ["ID", "Mijoz", "Xona", "Odam", "Sutka", "Jami Summa", "To'langan", "Kirgan Vaqti", "Chiqib Ketgan Sana", "Izoh"]
                for col in ["Jami Summa", "To'langan"]:
                    arx_view[col] = arx_view[col].apply(lambda x: f"{int(x or 0):,} UZS")
                st.dataframe(arx_view, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(arx_view))
            else:
                st.info("Tanlangan davrda arxivlangan mijozlar yo'q.")
        else:
            st.info("Bazada ma'lumot yo'q.")

    elif ceo_tanlov == "👥 Xodimlar va Rollar":
        st.subheader("👥 Barcha xodimlar va Rollar (Admin, CEO va Tozalik xodimalari)")
        c_u1, c_u2 = st.columns([1.2, 1], gap="medium")
        with c_u1:
            df_users = db.read_df("SELECT login, ism, role, parol FROM xodimlar")
            rol_nomi_map = {"ceo": "👑 CEO (Boshqaruvchi)", "admin": "💼 Admin (Front-Ofis)", "housekeeping": "🧹 Xo'jalik / Tozalik"}
            df_users["Rol"] = df_users["role"].apply(lambda r: rol_nomi_map.get(r, r))
            df_users["Holat"] = "🟢 Faol"
            df_u_view = df_users[["login", "ism", "Rol", "parol", "Holat"]].copy()
            df_u_view.columns = ["Login", "Ism-Sharif (Foydalanuvchi)", "Huquqi (Rol)", "Parol", "Holat"]
            st.dataframe(df_u_view, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_u_view))

            och_royxat = [l for l in df_users["login"].tolist() if l != 'ceo']
            if och_royxat:
                with st.form("del_user_form", enter_to_submit=False):
                    och_login = st.selectbox("Xodimni o'chirish (Loginni tanlang):", och_royxat)
                    if st.form_submit_button("🗑️ Tanlangan xodimni o'chirish"):
                        db.execute("DELETE FROM xodimlar WHERE login=?", (och_login,))
                        jurnalga_yozish("Xodimlar", xodim_ismi, "Xodim o'chirildi", f"Login: {och_login}")
                        st.success("Xodim o'chirildi!")
                        st.rerun()

        with c_u2:
            st.markdown("##### ➕ Yangi Xodim (Admin / Tozalik bekasi / CEO) qo'shish")
            with st.form("new_user_form", clear_on_submit=True, enter_to_submit=False):
                u_ism = st.text_input("Xodim Ism-Sharifi (masalan: Dilnoza opa - Tozalik)")
                u_login = st.text_input("Kirish uchun Login (masalan: dilnoza)")
                u_parol = st.text_input("Parol")
                u_role_tanlov = st.selectbox(
                    "Huquqi (Roli):",
                    [
                        "admin — Front-Ofis Admini (Qabul, Kassa, Xonalar)",
                        "housekeeping — Xo'jalik / Tozalik bekasi (Faqat Xonalar xaritasi va Tozalash)",
                        "ceo — Boshqaruvchi (To'liq nazorat)"
                    ]
                )
                if st.form_submit_button("➕ Xodimni yaratish", type="primary", use_container_width=True):
                    if u_ism.strip() and u_login.strip() and u_parol.strip():
                        u_role = u_role_tanlov.split(" — ")[0].strip()
                        mavjud = db.fetchone("SELECT login FROM xodimlar WHERE login=?", (u_login.strip(),))
                        if mavjud:
                            st.error("Bunday login band! Boshqa login yozing.")
                        else:
                            db.execute(
                                "INSERT INTO xodimlar (login, role, parol, ism) VALUES (?,?,?,?)",
                                (u_login.strip(), u_role, u_parol.strip(), u_ism.strip())
                            )
                            jurnalga_yozish("Xodimlar", xodim_ismi, "Yangi xodim qo'shildi", f"{u_ism} ({u_login}) - {u_role}")
                            st.success(f"✅ {u_ism} ({u_role}) tizimga qo'shildi!")
                            st.rerun()
                    else:
                        st.error("Barcha maydonlarni to'ldiring!")

    elif ceo_tanlov == "🕵️ Batafsil Audit":
        st.info(f"📅 Ko'rsatilayotgan davr: **{g_davr_nomi}**")
        if g_bosh_sana and g_tugash_sana:
            df_audit = db.read_df(
                "SELECT * FROM audit_log WHERE vaqt >= ? AND vaqt <= ? ORDER BY id DESC",
                (g_bosh_sana + " 00:00:00", g_tugash_sana + " 23:59:59")
            )
        else:
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
            df_a_korsatish.columns = ["Sana va Vaqt", "Obyekt / ID", "Mas'ul Xodim", "Harakat Turi", "Batafsil ma'lumot (To'liq)"]
            st.dataframe(
                df_a_korsatish,
                use_container_width=True,
                hide_index=True,
                column_config=avto_kenglik_sozla(df_a_korsatish)
            )
        else:
            st.info("Tanlangan davrda tizimda o'zgarishlar qayd etilmagan.")

    elif ceo_tanlov == "📝 Maxsus Izohlar":
        st.markdown("Bu yerdagi izohlarni faqat CEO yoza oladi. Ular adminlarga asosiy jadvallarda ko'rinadi.")
        izoh_tanlov = st.radio("Qaysi bazaga izoh yozasiz?", ["Mijozlar (Bronlar)", "Sklad (Mahsulotlar)"], horizontal=True)
        if izoh_tanlov == "Mijozlar (Bronlar)":
            df_b = db.read_df("SELECT mijoz_id, mijoz, xona, izoh FROM bronlar WHERE holat!='Chiqib ketgan'")
            if not df_b.empty:
                t_mijoz = st.selectbox("Mijozni tanlang:", df_b['mijoz_id'] + " - " + df_b['mijoz'] + " (" + df_b['xona'] + ")")
                m_id_izoh = t_mijoz.split(" - ")[0]
                joriy_izoh = str(df_b[df_b['mijoz_id'] == m_id_izoh]['izoh'].values[0] or '')
                with st.form("izoh_mijoz_form", enter_to_submit=False):
                    yangi_izoh = st.text_area("Izoh yozing:", value=joriy_izoh)
                    if st.form_submit_button("💾 Izohni Saqlash (Mijoz)", type="primary"):
                        db.execute("UPDATE bronlar SET izoh=? WHERE mijoz_id=?", (yangi_izoh.strip(), m_id_izoh))
                        jurnalga_yozish(m_id_izoh, xodim_ismi, "Maxfiy Izoh yozildi", f"Yangi izoh: {yangi_izoh.strip()}")
                        st.success("Mijozga izoh saqlandi!")
                        st.rerun()
            else:
                st.info("Faol mijozlar yo'q.")
        else:
            df_m = db.read_df("SELECT id, nomi, hajmi, qoldiq, izoh FROM mahsulotlar")
            if not df_m.empty:
                df_m['korsatkich'] = df_m['nomi'] + " " + df_m['hajmi'] + " (" + df_m['qoldiq'].astype(str) + " ta)"
                t_mahs = st.selectbox("Mahsulotni tanlang:", df_m['korsatkich'])
                m_id_m = int(df_m[df_m['korsatkich'] == t_mahs]['id'].values[0])
                joriy_izoh_m = str(df_m[df_m['id'] == m_id_m]['izoh'].values[0] or '')
                with st.form("izoh_sklad_form", enter_to_submit=False):
                    yangi_izoh_m = st.text_area("Izoh yozing:", value=joriy_izoh_m)
                    if st.form_submit_button("💾 Izohni Saqlash (Mahsulot)", type="primary"):
                        db.execute("UPDATE mahsulotlar SET izoh=? WHERE id=?", (yangi_izoh_m.strip(), m_id_m))
                        jurnalga_yozish(f"Sklad (ID:{m_id_m})", xodim_ismi, "Maxfiy Izoh yozildi", f"Yangi izoh: {yangi_izoh_m.strip()}")
                        st.success("Mahsulotga izoh saqlandi!")
                        st.rerun()
            else:
                st.info("Skladda mahsulot yo'q.")

    elif ceo_tanlov == "🗑️ O'chirish":
        st.error("🚨 XAVFLI ZONA: Bu yerdan o'chirilgan mijoz qayta tiklanmaydi!")
        if not df_admin.empty:
            with st.form("del_mijoz_form", enter_to_submit=False):
                del_id = st.selectbox("O'chiriladigan ID:", df_admin['mijoz_id'] + " - " + df_admin['mijoz'])
                if st.form_submit_button("⚠️ Butunlay o'chirish"):
                    och_id = del_id.split(" - ")[0]
                    och_ism = del_id.split(" - ")[1]
                    db.execute("DELETE FROM bronlar WHERE mijoz_id = ?", (och_id,))
                    db.execute("DELETE FROM tolovlar_tarixi WHERE mijoz_id = ?", (och_id,))
                    jurnalga_yozish(och_id, xodim_ismi, "O'chirish (Xavfli)", f"Mijoz ({och_ism}) va uning to'lovlari bazadan o'chirildi")
                    tg_xabar_yubor("Mijoz bazadan o'chirildi!", f"🆔 <b>ID:</b> {och_id}\n👤 <b>Mijoz:</b> {och_ism}", xodim_ismi, muhim=True, kanal="mijoz")
                    st.success("Mijoz va uning to'lov tarixi o'chirildi!")
                    st.rerun()
        else:
            st.info("Bazada ma'lumot yo'q.")