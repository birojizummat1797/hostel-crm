import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from database import db, jurnalga_yozish, haftalik_hisobot_yuklash, avto_kenglik_sozla, toshkent_vaqti, xona_tozalik_ozgartir, XONALAR
from tg_bot import tg_xabar_yubor
from auth import parol_hash

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
                    tg_xabar_yubor(
                        "Xarajat qilindi",
                        f"📂 <b>Kategoriya:</b> {kat}\n➖ <b>Summa:</b> {summa:,.0f} UZS ({tolov_turi})\n📝 <b>Izoh:</b> {izoh.strip()}",
                        xodim_ismi
                    )
                    st.success("✅ Xarajat bazaga kiritildi va hisobotga qo'shildi!")
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
                    "Smena yopildi (Z-Hisobot)",
                    f"💵 <b>Naqd kirim:</b> {naqd_tushum:,.0f} UZS\n"
                    f"💳 <b>Karta/Onlayn kirim:</b> {karta_tushum:,.0f} UZS\n"
                    f"➖ <b>Jami xarajat:</b> {umumiy_xarajat:,.0f} UZS\n"
                    f"🏦 <b>Sof Naqd Kassa:</b> {sof_naqd_kassa:,.0f} UZS\n"
                    f"💰 <b>Umumiy Sof Balans:</b> {umumiy_sof_balans:,.0f} UZS\n"
                    f"📝 <b>Izoh:</b> {smena_izoh.strip() or '—'}",
                    xodim_ismi
                )
                st.success("🎉 Smena muvaffaqiyatli yopildi va bazaga saqlandi!")
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
            "🚪 Checkout, Qayta Hisob & Tuzatish",
            "📲 Telegram Xabarlar",
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

        st.download_button(
            label=f"📥 Tanlangan davr ({g_davr_nomi}) bo'yicha To'liq Hisobotni Yuklab Olish (Excel)",
            data=haftalik_hisobot_yuklash(g_bosh_sana, g_tugash_sana),
            file_name=f"Y.S.H._Hisobot_{fayl_davr}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

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

    elif ceo_tanlov == "🚪 Checkout, Qayta Hisob & Tuzatish":
        if not df_admin.empty:
            faollar = df_admin[df_admin['holat'] != 'Chiqib ketgan'].copy()
            arxivdagilar = df_admin[df_admin['holat'] == 'Chiqib ketgan'].copy()
            if g_bosh_sana and g_tugash_sana and not arxivdagilar.empty:
                arxivdagilar = arxivdagilar[(arxivdagilar['chiqish_sanasi'] >= g_bosh_sana) & (arxivdagilar['chiqish_sanasi'] <= g_tugash_sana)]

            st.subheader("👑 CEO Maxsus Checkout, Muddatidan oldin ketish (Avto-Vozvrat) va Tuzatish")
            if not faollar.empty:
                korsatkich = (
                    faollar['mijoz_id'] + " - " + faollar['mijoz'] +
                    " (" + faollar['xona'] + " | " + faollar['kunlar'].astype(str) + " sutka | To'lagan: " +
                    faollar['tolagan_summa'].fillna(0).astype(int).astype(str) + " | Qarz: " +
                    faollar['qoldiq'].fillna(0).astype(int).astype(str) + ")"
                )
                chiq_id_toliq = st.selectbox("Mehmonni tanlang:", korsatkich.tolist())
                c_id = chiq_id_toliq.split(" - ")[0]
                mijoz_qator = faollar[faollar['mijoz_id'] == c_id].iloc[0]

                reja_sutka = int(mijoz_qator.get('kunlar', 1) or 1)
                eski_jami = float(mijoz_qator.get('faktik_narx', 0) or 0)
                eski_tolagan = float(mijoz_qator.get('tolagan_summa', 0) or 0)
                eski_qoldiq = float(mijoz_qator.get('qoldiq', 0) or 0)
                kunlik_st = float(mijoz_qator.get('kunlik_narx', 0) or (eski_jami / max(1, reja_sutka)))

                try:
                    k_dt = datetime.strptime(str(mijoz_qator['kirish_sanasi']), "%Y-%m-%d").date()
                    bugun_dt = toshkent_vaqti().date()
                    haqiqiy_otgan = max(1, min(reja_sutka, (bugun_dt - k_dt).days if (bugun_dt - k_dt).days > 0 else 1))
                except Exception:
                    haqiqiy_otgan = reja_sutka

                with st.container(border=True):
                    st.markdown(
                        f"👤 **Mehmon:** `{mijoz_qator['mijoz']}` ({mijoz_qator['odam_soni']} kishi) &nbsp;|&nbsp; "
                        f"🛏️ **Xona:** `{mijoz_qator['xona']}` &nbsp;|&nbsp; "
                        f"📅 **Bron qilingan:** `{reja_sutka} sutka` ({mijoz_qator['kirish_sanasi']} ➔ {mijoz_qator['chiqish_sanasi']})"
                    )
                    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
                    c_m1.metric("💰 Jami hisoblangan", f"{eski_jami:,.0f} UZS")
                    c_m2.metric("✅ To'lagan summasi", f"{eski_tolagan:,.0f} UZS")
                    c_m3.metric("⚠️ Joriy qoldiq qarz", f"{max(0, eski_qoldiq):,.0f} UZS")
                    c_m4.metric("🏷️ 1 sutka stavkasi", f"{kunlik_st:,.0f} UZS")

                    st.markdown("---")
                    ceo_amal_turi = st.radio(
                        "📌 Qanday amal bajarasiz?",
                        [
                            "🧮 1. Muddatidan oldin chiqarish / Qayta hisob-kitob va Vozvrat (masalan: 10 kunga to'lab 5 kunda ketsa)",
                            "🚨 2. Qarzini kechish (Spisaniya / Xato yozilgan qarzni bekor qilish) va Checkout",
                            "✅ 3. Oddiy Checkout (O'z vaqtida chiqarish)"
                        ]
                    )

                    if ceo_amal_turi.startswith("🧮 1."):
                        rc1, rc2, rc3 = st.columns(3, gap="medium")
                        with rc1:
                            yashagan_sutka = st.number_input("🌙 Haqiqiy yashagan sutkasi:", min_value=0, max_value=365, value=haqiqiy_otgan)
                        with rc2:
                            custom_kunlik = st.number_input("💵 1 sutkalik hisob stavkasi (UZS):", min_value=0, value=int(kunlik_st), step=5000)
                        with rc3:
                            vozvrat_kassa = st.selectbox("🏦 Qaysi kassadan Vozvrat beriladi / olinadi?", ["Naqd", "Click", "Uzcard", "Humo", "Terminal", "Boshqa"])

                        yangi_hisob_jami = float(yashagan_sutka * custom_kunlik)
                        farq_balans = eski_tolagan - yangi_hisob_jami
                        tavsiya_vozvrat = int(max(0.0, farq_balans))
                        qolgan_qarz_yangi = int(max(0.0, yangi_hisob_jami - eski_tolagan))

                        if farq_balans > 0:
                            st.success(
                                f"📊 **Qayta hisob natijasi:** {yashagan_sutka} sutka × {custom_kunlik:,.0f} = **{yangi_hisob_jami:,.0f} UZS**.\n\n"
                                f"⏪ Mijoz **{eski_tolagan:,.0f} UZS** to'lagan. Mijozga qaytarilishi kerak bo'lgan **Vozvrat summasi: {tavsiya_vozvrat:,.0f} UZS**"
                            )
                        elif farq_balans < 0:
                            st.warning(
                                f"📊 **Qayta hisob natijasi:** {yashagan_sutka} sutka × {custom_kunlik:,.0f} = **{yangi_hisob_jami:,.0f} UZS**.\n\n"
                                f"⚠️ Mijoz **{eski_tolagan:,.0f} UZS** to'lagan. Mijoz yana **{qolgan_qarz_yangi:,.0f} UZS** qo'shimcha to'lashi kerak."
                            )
                        else:
                            st.info(f"📊 **Qayta hisob natijasi:** Hisob va to'lov teng (**{yangi_hisob_jami:,.0f} UZS**). Vozvrat talab etilmaydi (0 UZS).")

                        with st.form("ceo_recalc_checkout_form", enter_to_submit=False):
                            f_v1, f_v2 = st.columns(2, gap="medium")
                            with f_v1:
                                tasdiq_vozvrat = st.number_input("⏪ Mijozga haqiqatda qaytarilgan Vozvrat summasi (UZS):", min_value=0, value=tavsiya_vozvrat, step=5000)
                            with f_v2:
                                tasdiq_qoshimcha_tolov = st.number_input("➕ Yoki mijozdan olingan qo'shimcha to'lov (UZS):", min_value=0, value=qolgan_qarz_yangi, step=5000)
                            yakuniy_holat_tanlov = st.radio(
                                "Amaliyot yakuni:",
                                ["🚪 Xonani bo'shatish va Arxivga chiqarish (Checkout)", "🛏️ Mehmon xonada qoladi (Faqat kun va summani tuzatish)"],
                                horizontal=True
                            )
                            ceo_izoh = st.text_input("Izoh:", placeholder="Masalan: 10 kun o'rniga 5 kun yashadi, 5 kunlik puli qaytarildi...")

                            if st.form_submit_button("✅ Qayta hisob-kitobni tasdiqlash va Saqlash", type="primary", use_container_width=True):
                                sof_tolagan = eski_tolagan - tasdiq_vozvrat + tasdiq_qoshimcha_tolov
                                yangi_qoldiq = max(0.0, yangi_hisob_jami - sof_tolagan)
                                try:
                                    k_d = datetime.strptime(str(mijoz_qator['kirish_sanasi']), "%Y-%m-%d").date()
                                    yangi_ch_str = (k_d + timedelta(days=max(1, yashagan_sutka))).strftime("%Y-%m-%d")
                                except Exception:
                                    yangi_ch_str = bugungi_sana

                                is_checkout = yakuniy_holat_tanlov.startswith("🚪")
                                yangi_holat_db = "Chiqib ketgan" if is_checkout else ("To'langan" if yangi_qoldiq <= 0 else "Qarzdorlik")
                                ch_sana_db = bugungi_sana if is_checkout else yangi_ch_str

                                eski_iz = str(mijoz_qator.get('izoh', '') or '')
                                yangi_iz = f"{eski_iz} | CEO Qayta hisob: {reja_sutka}k->{yashagan_sutka}k, Vozvrat={tasdiq_vozvrat:,.0f} ({ceo_izoh.strip()})".strip(" |")

                                db.execute("""
                                    UPDATE bronlar SET 
                                        kunlar=?, muddat=?, kunlik_narx=?, jami_summa=?, faktik_narx=?,
                                        tolagan_summa=?, qoldiq=?, holat=?, chiqish_sanasi=?, izoh=?
                                    WHERE mijoz_id=?
                                """, (
                                    yashagan_sutka, f"{yashagan_sutka} sutka", custom_kunlik, yangi_hisob_jami, yangi_hisob_jami,
                                    sof_tolagan, 0 if is_checkout else yangi_qoldiq, yangi_holat_db, ch_sana_db, yangi_iz, c_id
                                ))

                                if tasdiq_vozvrat > 0:
                                    db.execute(
                                        "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                        (bugungi_sana, c_id, mijoz_qator['mijoz'], "Vozvrat (Qayta hisob)", -tasdiq_vozvrat, vozvrat_kassa, vozvrat_kassa, xodim_ismi)
                                    )
                                if tasdiq_qoshimcha_tolov > 0:
                                    db.execute(
                                        "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
                                        (bugungi_sana, c_id, mijoz_qator['mijoz'], "Qarz yopish (Qayta hisob)", tasdiq_qoshimcha_tolov, vozvrat_kassa, vozvrat_kassa, xodim_ismi)
                                    )

                                if is_checkout:
                                    xona_tozalik_ozgartir(mijoz_qator['xona'], "Tozalash kerak")

                                jurnalga_yozish(
                                    c_id, xodim_ismi, "CEO Qayta hisob / Vozvrat",
                                    f"{mijoz_qator['mijoz']}: {reja_sutka}k -> {yashagan_sutka}k. Yangi jami: {yangi_hisob_jami:,.0f}, Vozvrat: -{tasdiq_vozvrat:,.0f}, Holat: {yangi_holat_db}"
                                )
                                tg_xabar_yubor(
                                    "CEO Qayta hisob-kitob va Vozvrat",
                                    f"👤 <b>Mijoz:</b> {mijoz_qator['mijoz']} ({mijoz_qator['xona']})\n"
                                    f"🌙 <b>Sutka o'zgardi:</b> {reja_sutka} sutka ➡️ {yashagan_sutka} sutka\n"
                                    f"💰 <b>Yangi hisob:</b> {yangi_hisob_jami:,.0f} UZS\n"
                                    f"⏪ <b>Qaytarilgan Vozvrat:</b> -{tasdiq_vozvrat:,.0f} UZS ({vozvrat_kassa})\n"
                                    f"📌 <b>Holat:</b> {yangi_holat_db}",
                                    xodim_ismi, muhim=True
                                )
                                st.success("✅ Qayta hisob-kitob va kassa balansi muvaffaqiyatli bajarildi!")
                                st.rerun()

                    elif ceo_amal_turi.startswith("🚨 2."):
                        with st.form("ceo_force_checkout_form", enter_to_submit=False):
                            st.warning(f"⚠️ Diqqat: Mijozdagi **{max(0, eski_qoldiq):,.0f} UZS** qarz bekor qilinadi (faktik narx to'langan summaga tenglashtiriladi) va mijoz Arxivga chiqariladi.")
                            sabab_spis = st.text_input("Qarzni bekor qilish / Tuzatish sababi *:", placeholder="Masalan: Admin adashib ortiqcha kun yozib yuborgan...")
                            if st.form_submit_button("🚨 Qarzni 0 UZS qilib Majburiy Checkout qilish", type="primary", use_container_width=True):
                                if not sabab_spis.strip():
                                    st.error("Iltimos, sababini yozing!")
                                else:
                                    eski_iz = str(mijoz_qator.get('izoh', '') or '')
                                    yangi_iz = f"{eski_iz} | CEO Spisaniya (-{eski_qoldiq:,.0f} UZS): {sabab_spis.strip()}".strip(" |")
                                    db.execute(
                                        "UPDATE bronlar SET holat='Chiqib ketgan', chiqish_sanasi=?, faktik_narx=?, jami_summa=?, qoldiq=0, izoh=? WHERE mijoz_id=?",
                                        (bugungi_sana, eski_tolagan, eski_tolagan, yangi_iz, c_id)
                                    )
                                    xona_tozalik_ozgartir(mijoz_qator['xona'], "Tozalash kerak")
                                    jurnalga_yozish(c_id, xodim_ismi, "CEO Majburiy Checkout (Spisaniya)", f"{mijoz_qator['mijoz']} ({mijoz_qator['xona']}) qarzi ({eski_qoldiq:,.0f}) bekor qilinib chiqarildi. Sabab: {sabab_spis.strip()}")
                                    tg_xabar_yubor(
                                        "CEO Majburiy Checkout (Qarz bekor qilindi)",
                                        f"👤 <b>Mijoz:</b> {mijoz_qator['mijoz']} ({mijoz_qator['xona']})\n"
                                        f"💸 <b>Bekor qilingan qarz:</b> {eski_qoldiq:,.0f} UZS\n"
                                        f"📝 <b>Sabab:</b> {sabab_spis.strip()}",
                                        xodim_ismi, muhim=True
                                    )
                                    st.success("✅ Mijozning xato qarzi bekor qilindi va xona bo'shatildi!")
                                    st.rerun()

                    else:
                        with st.form("checkout_form", enter_to_submit=False):
                            ceo_tasdiq_oddiy = "Ha"
                            if eski_qoldiq > 0:
                                st.warning(f"⚠️ **DIQQAT:** Bu mijozda **{eski_qoldiq:,.0f} UZS** qarz bor! Haqiqatdan ham checkout qilishni xohlaysizmi?")
                                ceo_tasdiq_oddiy = st.radio(
                                    "Tasdiqlash:",
                                    ["Yo'q (Bekor qilish)", "Ha (Qarzdor bo'lsa ham Checkout qilinsin)"],
                                    index=0,
                                    horizontal=True
                                )
                            if st.form_submit_button("🚪 Mijozni chiqarish va Arxivlash", type="primary", use_container_width=True):
                                if eski_qoldiq > 0 and not ceo_tasdiq_oddiy.startswith("Ha"):
                                    st.warning("⚠️ Checkout qilinmadi («Yo'q» tanlangan). Chiqarish uchun «Ha (Qarzdor bo'lsa ham Checkout qilinsin)» ni belgilab bosing!")
                                else:
                                    db.execute("UPDATE bronlar SET holat = 'Chiqib ketgan', chiqish_sanasi = ? WHERE mijoz_id = ?", (bugungi_sana, c_id))
                                    xona_tozalik_ozgartir(mijoz_qator['xona'], "Tozalash kerak")
                                    jurnalga_yozish(c_id, xodim_ismi, "CEO Checkout", f"Mijoz ({mijoz_qator['mijoz']}) {mijoz_qator['xona']} ni topshirdi (Qoldiq: {eski_qoldiq:,.0f})")
                                    tg_xabar_yubor("Checkout (Mijoz chiqib ketdi)", f"👤 <b>Mijoz:</b> {mijoz_qator['mijoz']}\n🛏 <b>Xona:</b> {mijoz_qator['xona']} (🧹 Tozalashga berildi)\n⚠️ <b>Qoldiq:</b> {max(0, eski_qoldiq):,.0f} UZS", xodim_ismi, muhim=(eski_qoldiq > 0))
                                    st.success("✅ Mijoz hech qanday to'siqsiz arxivlandi va xona 'Tozalash kerak' ro'yxatiga tushdi!")
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
        st.subheader("👥 Barcha xodimlar va Rollar")
        c_u1, c_u2 = st.columns([1.2, 1], gap="medium")
        with c_u1:
            df_users = db.read_df("SELECT login, ism, role FROM xodimlar")
            df_users["Holat"] = "🟢 Faol"
            df_users.columns = ["Login", "Ism-Sharif (Foydalanuvchi)", "Rol", "Holat"]
            st.dataframe(df_users, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_users))

            och_royxat = [l for l in df_users["Login"].tolist() if l != 'ceo']
            if och_royxat:
                with st.form("del_user_form", enter_to_submit=False):
                    och_login = st.selectbox("Xodimni o'chirish (Loginni tanlang):", och_royxat)
                    if st.form_submit_button("🗑️ Tanlangan xodimni o'chirish"):
                        db.execute("DELETE FROM xodimlar WHERE login=?", (och_login,))
                        jurnalga_yozish("Xodimlar", xodim_ismi, "Xodim o'chirildi", f"Login: {och_login}")
                        st.success("Xodim o'chirildi!")
                        st.rerun()

            st.markdown("---")
            if st.button("📲 Telegram Bot aloqasini tekshirish (Test xabar)"):
                natija = tg_xabar_yubor("Aloqa tekshiruvi", "✅ Y.S.H. ERP: Telegram bot faol ishlamoqda!", xodim_ismi)
                if natija:
                    st.success("✅ Telegramingizga xabar yuborildi!")
                else:
                    st.error("⚠️ Xabar bormadi. Token va Chat ID ni tekshiring.")

        with c_u2:
            st.markdown("##### ➕ Yangi Xodim (Admin / Tozalik / CEO) qo'shish")
            with st.form("new_user_form", clear_on_submit=True, enter_to_submit=False):
                u_ism = st.text_input("Xodim Ism-Sharifi (masalan: Admin Sardor yoki Ozoda opa)")
                u_login = st.text_input("Kirish uchun Login (masalan: sardor)")
                u_parol = st.text_input("Parol")
                u_role = st.selectbox("Huquqi (Roli):", ["admin", "housekeeping", "ceo"])
                if st.form_submit_button("➕ Xodimni yaratish", type="primary", use_container_width=True):
                    if u_ism.strip() and u_login.strip() and u_parol.strip():
                        mavjud = db.fetchone("SELECT login FROM xodimlar WHERE login=?", (u_login.strip(),))
                        if mavjud:
                            st.error("Bunday login band! Boshqa login yozing.")
                        else:
                            db.execute(
                                "INSERT INTO xodimlar (login, role, parol, ism) VALUES (?,?,?,?)",
                                (u_login.strip(), u_role, parol_hash(u_parol.strip()), u_ism.strip())
                            )
                            jurnalga_yozish("Xodimlar", xodim_ismi, "Yangi xodim qo'shildi", f"{u_ism} ({u_login}) - {u_role}")
                            st.success(f"✅ {u_ism} tizimga qo'shildi!")
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
                    tg_xabar_yubor("Mijoz bazadan o'chirildi!", f"🆔 <b>ID:</b> {och_id}\n👤 <b>Mijoz:</b> {och_ism}", xodim_ismi, muhim=True)
                    st.success("Mijoz va uning to'lov tarixi o'chirildi!")
                    st.rerun()
        else:
            st.info("Bazada ma'lumot yo'q.")
    elif ceo_tanlov == "📲 Telegram Xabarlar":
        st.subheader("📲 Tizim tomonidan Telegramga yuborilgan xabarlar nazorati")
        st.caption("CEO va Mehmonxona Egasiga (Owner) bot orqali yuborilgan barcha xabarnomalar tarixi va holati")

        try:
            if g_bosh_sana and g_tugash_sana:
                df_tg = db.read_df(
                    "SELECT id, vaqt, sarlavha, qabul_qiluvchi, xodim, holat, matn FROM tg_xabarlar_log WHERE vaqt >= ? AND vaqt <= ? ORDER BY id DESC",
                    (g_bosh_sana + " 00:00:00", g_tugash_sana + " 23:59:59")
                )
            else:
                df_tg = db.read_df("SELECT id, vaqt, sarlavha, qabul_qiluvchi, xodim, holat, matn FROM tg_xabarlar_log ORDER BY id DESC LIMIT 200")
        except Exception:
            df_tg = pd.DataFrame()

        t_col1, t_col2 = st.columns([3, 1])
        with t_col1:
            qidir_tg = st.text_input("🔍 Xabarlar ichidan qidirish (Mijoz ismi, xona, amaliyot yoki xodim):", placeholder="Masalan: 19-xona, Checkout, Savdo...")
        with t_col2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("📲 Test xabar yuborib tekshirish", use_container_width=True):
                tg_xabar_yubor("Nazorat tekshiruvi", "✅ Telegram xabarlar jurnali faol ishlamoqda!", xodim_ismi)
                st.rerun()

        if not df_tg.empty:
            if qidir_tg:
                df_tg = df_tg[
                    df_tg['sarlavha'].str.contains(qidir_tg, case=False, na=False) |
                    df_tg['matn'].str.contains(qidir_tg, case=False, na=False) |
                    df_tg['xodim'].str.contains(qidir_tg, case=False, na=False)
                ]
            st.markdown(f"**Jami yuborilgan xabarlar ({g_davr_nomi}):** `{len(df_tg)} ta`")
            df_tg_view = df_tg[['vaqt', 'sarlavha', 'qabul_qiluvchi', 'xodim', 'holat', 'matn']].copy()
            df_tg_view.columns = ["Sana va Vaqt", "Amaliyot / Sarlavha", "Kimga Yuborildi", "Mas'ul Xodim", "Status", "Xabar Matni (To'liq)"]
            st.dataframe(df_tg_view, use_container_width=True, hide_index=True, column_config=avto_kenglik_sozla(df_tg_view))
        else:
            st.info("Hozircha Telegram xabarlar tarixi bo'sh. Yangi amaliyot bajarilishi yoki 'Test xabar yuborish' bosilishi bilan shu yerda paydo bo'ladi.")