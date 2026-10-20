import os
import re
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

# Mavjud tizimdan faqat toza obyektlar va konstantalarni olamiz
from database import (
    db, XONALAR, XONA_TOMON_MAP, toshkent_vaqti, xona_sigimini_ol,
    xonadagi_band_joyni_hisobla, xona_jinsini_tekshir, id_yaratish,
    jurnalga_yozish
)
from tg_bot import tg_xabar_yubor

app = FastAPI(title="Y.S.H. ERP | Next-Gen Fullstack API")

class YangiBronReq(BaseModel):
    mijoz: str
    telefon: Optional[str] = ""
    jinsi: str = "Erkak"
    toifa: str = "O'zbekiston fuqarosi"
    xona: str
    odam_soni: int = 1
    krovatlar: List[str] = []
    vikup: bool = False
    kunlar: int = 1
    tolangan: float = 0
    tolov_tafsiloti: str = "Naqd"
    izoh: Optional[str] = ""
    xodim: str = "CEO (Web UI)"

class CheckoutReq(BaseModel):
    mijoz_id: str
    vozvrat_summa: float = 0
    kassa: str = "Naqd"
    xodim: str = "CEO (Web UI)"
    majburiy_qarz_bilan: bool = False

class TozalikReq(BaseModel):
    xona: str
    holat: str
    xodim: str = "Web UI"

def _krovat_ajrat(x_tur, izoh):
    m = re.search(r'\[🛏️ (.*?)\]', f"{x_tur or ''} {izoh or ''}")
    if m:
        return m.group(1).replace("Chapdan ", "").replace("O'ngdan ", "").strip()
    return ""

def _tozalik_ol_direct():
    """Streamlit @st.cache_data ni chetlab o'tib, to'g'ridan-to'g'ri bazadan o'qiydi"""
    try:
        rows = db.fetchall("SELECT xona, holat FROM xona_tozalik")
        return {str(r[0]): str(r[1]) for r in rows}
    except Exception:
        return {}

def _tozalik_ozgartir_direct(xona_nomi, yangi_holat="Tozalash kerak"):
    hozir = toshkent_vaqti().strftime("%Y-%m-%d %H:%M")
    try:
        mavjud = db.fetchone("SELECT xona FROM xona_tozalik WHERE xona=?", (xona_nomi,))
        if mavjud:
            db.execute("UPDATE xona_tozalik SET holat=?, vaqt=? WHERE xona=?", (yangi_holat, hozir, xona_nomi))
        else:
            db.execute("INSERT INTO xona_tozalik (xona, holat, vaqt) VALUES (?,?,?)", (xona_nomi, yangi_holat, hozir))
    except Exception:
        pass

def _s(val, default=""):
    if val is None or pd.isna(val):
        return default
    return str(val)

def _f(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    try:
        return float(val)
    except Exception:
        return default

@app.get("/api/dashboard")
def api_dashboard(bosh_sana: Optional[str] = None, tugash_sana: Optional[str] = None):
    uz_now = toshkent_vaqti()
    bugun = uz_now.strftime("%Y-%m-%d")

    try:
        df_b = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")
    except Exception:
        df_b = pd.DataFrame()

    try:
        df_t = db.read_df("SELECT * FROM tolovlar_tarixi ORDER BY id DESC")
    except Exception:
        df_t = pd.DataFrame()

    try:
        df_x = db.read_df("SELECT * FROM xarajatlar ORDER BY id DESC")
    except Exception:
        df_x = pd.DataFrame()

    df_tg_list = []
    try:
        df_tg = db.read_df("SELECT vaqt, sarlavha, qabul_qiluvchi, xodim, holat, matn FROM tg_xabarlar_log ORDER BY id DESC LIMIT 50")
        if not df_tg.empty:
            for _, tr in df_tg.iterrows():
                df_tg_list.append({
                    "vaqt": _s(tr.get("vaqt")),
                    "sarlavha": _s(tr.get("sarlavha")),
                    "qabul_qiluvchi": _s(tr.get("qabul_qiluvchi")),
                    "xodim": _s(tr.get("xodim")),
                    "holat": _s(tr.get("holat")),
                    "matn": _s(tr.get("matn"))
                })
    except Exception:
        pass

    toz_map = _tozalik_ol_direct()

    b_s = bosh_sana if bosh_sana else bugun
    t_s = tugash_sana if tugash_sana else bugun

    faol_list, barcha_list = [], []
    band_xonalar = set()
    faol_odam = 0
    kirgan_odam, chiqqan_odam = 0, 0
    umumiy_qarz = 0.0

    if not df_b.empty:
        for _, r in df_b.iterrows():
            k_s = _s(r.get('kirish_sanasi'))
            ch_s = _s(r.get('chiqish_sanasi'))
            hol = _s(r.get('holat'))
            odam = int(_f(r.get('odam_soni'), 1))
            qol = _f(r.get('qoldiq'), 0.0)
            joy = _krovat_ajrat(_s(r.get('xona_turi')), _s(r.get('izoh')))
            x_nom_r = _s(r.get('xona'))

            is_active_today = (hol != 'Chiqib ketgan') and ((k_s == ch_s and k_s == bugun) or (k_s <= bugun and ch_s > bugun))
            if is_active_today:
                band_xonalar.add(x_nom_r)
                faol_odam += odam
            if hol != 'Chiqib ketgan' and qol > 0:
                umumiy_qarz += qol
            if b_s <= k_s <= t_s:
                kirgan_odam += odam
            if b_s <= ch_s <= t_s:
                chiqqan_odam += odam

            item = {
                "mijoz_id": _s(r.get('mijoz_id')),
                "mijoz": _s(r.get('mijoz')),
                "telefon": _s(r.get('telefon')),
                "jinsi": _s(r.get('jinsi'), "Erkak"),
                "toifa": _s(r.get('toifa')),
                "xona": x_nom_r,
                "tomon": _s(r.get('tomon')) or XONA_TOMON_MAP.get(x_nom_r, ""),
                "joy": joy,
                "odam_soni": odam,
                "kunlar": int(_f(r.get('kunlar'), 1)),
                "faktik_narx": _f(r.get('faktik_narx'), 0.0),
                "tolagan_summa": _f(r.get('tolagan_summa'), 0.0),
                "qoldiq": qol,
                "kirish_vaqti": _s(r.get('sana')) or k_s,
                "kirish_sanasi": k_s,
                "chiqish_sanasi": ch_s,
                "holat": hol,
                "izoh": _s(r.get('izoh'))
            }
            barcha_list.append(item)
            if hol != 'Chiqib ketgan':
                faol_list.append(item)

    xonalar_xaritasi = []
    for tomon, x_dict in XONALAR.items():
        for x_nom, (sigim, narx) in x_dict.items():
            krovatlar_holati = {}
            x_jins = ""
            vikup = False
            x_odam = 0
            for m in faol_list:
                if m['xona'] == x_nom and ((m['kirish_sanasi'] <= bugun and m['chiqish_sanasi'] > bugun) or m['kirish_sanasi'] == bugun):
                    x_odam += m['odam_soni']
                    if not x_jins:
                        x_jins = m['jinsi']
                    if "Barcha joylar" in m['joy'] or tomon == "O'rtadagi":
                        vikup = True
                        for k_i in range(1, sigim + 1):
                            krovatlar_holati[str(k_i)] = m['mijoz']
                    else:
                        for raq in re.findall(r'(\d)-joy', m['joy']):
                            krovatlar_holati[raq] = m['mijoz']

            bosh_joy = 0 if vikup else max(0, sigim - x_odam)
            xonalar_xaritasi.append({
                "xona": x_nom,
                "tomon": tomon,
                "sigim": int(sigim),
                "narx": float(narx),
                "tozalik": toz_map.get(x_nom, "Toza"),
                "band_odam": int(x_odam),
                "bosh_joy": int(bosh_joy),
                "jinsi": x_jins,
                "krovatlar": krovatlar_holati
            })

    yotoq_kirim, market_kirim = 0.0, 0.0
    if not df_t.empty:
        for _, tr in df_t.iterrows():
            s_d = _s(tr.get('sana'))
            if (not bosh_sana or not tugash_sana) or (b_s <= s_d <= t_s):
                sum_v = _f(tr.get('summa'), 0.0)
                if _s(tr.get('manba')) == 'Market Savdo':
                    market_kirim += sum_v
                else:
                    yotoq_kirim += sum_v

    xarajat_sum = 0.0
    if not df_x.empty:
        for _, xr in df_x.iterrows():
            s_d = _s(xr.get('sana'))
            if (not bosh_sana or not tugash_sana) or (b_s <= s_d <= t_s):
                xarajat_sum += _f(xr.get('summa'), 0.0)

    tozalash_soni = sum(1 for h in toz_map.values() if h == "Tozalash kerak")

    return {
        "vaqt": uz_now.strftime("%d.%m.%Y %H:%M"),
        "bugun": bugun,
        "kpi": {
            "band_xonalar": len(band_xonalar),
            "bosh_xonalar": max(0, 36 - len(band_xonalar) - tozalash_soni),
            "tozalash_kerak": tozalash_soni,
            "faol_mehmon": faol_odam,
            "kirgan_odam": kirgan_odam,
            "chiqqan_odam": chiqqan_odam,
            "yotoq_kirim": yotoq_kirim,
            "market_kirim": market_kirim,
            "xarajat": xarajat_sum,
            "sof_balans": (yotoq_kirim + market_kirim) - xarajat_sum,
            "umumiy_qarz": umumiy_qarz
        },
        "faol_mehmonlar": faol_list,
        "barcha_mehmonlar": barcha_list[:150],
        "xonalar": xonalar_xaritasi,
        "tg_log": df_tg_list
    }

@app.post("/api/qabul")
def api_yangi_qabul(req: YangiBronReq):
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")
    soat_str = uz_now.strftime("%H:%M")
    tomon = XONA_TOMON_MAP.get(req.xona, "Chap tomon")
    sigim, baz_narx = XONALAR[tomon][req.xona]

    chiqish_dt = uz_now.date() + timedelta(days=max(0, req.kunlar - 1) if uz_now.hour < 12 else req.kunlar)
    chiqish_str = chiqish_dt.strftime("%Y-%m-%d")

    band = xonadagi_band_joyni_hisobla(req.xona, bugun_str, chiqish_str)
    kerak = sigim if req.vikup else req.odam_soni
    if kerak > (sigim - band):
        raise HTTPException(status_code=400, detail=f"{req.xona} da bo'sh joy yetarli emas!")

    zid = None if (req.vikup or tomon == "O'rtadagi") else xona_jinsini_tekshir(req.xona, bugun_str, chiqish_str, req.jinsi)
    if zid:
        raise HTTPException(status_code=400, detail=f"{req.xona} da {zid} mehmon bor! {req.jinsi} qo'shib bo'lmaydi.")

    hisob_odam = sigim if req.vikup else req.odam_soni
    if tomon == "O'rtadagi":
        kunlik = 300000 if req.toifa == "Chet el fuqarosi" else 250000
    else:
        if req.toifa == "Chet el fuqarosi":
            kunlik = (baz_narx + 50000) * hisob_odam
        elif req.toifa == "Talaba (Student)":
            kunlik = (baz_narx * 0.5) * hisob_odam
        else:
            kunlik = baz_narx * hisob_odam

    jami = kunlik * req.kunlar
    if req.kunlar >= 7:
        jami = jami * 0.9

    qoldiq = jami - req.tolangan
    holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"
    yangi_id = id_yaratish(req.jinsi, uz_now.date(), req.toifa)

    if tomon == "O'rtadagi":
        kr_yorliq = "Dvuxspalniy"
    elif req.vikup or req.odam_soni == sigim:
        kr_yorliq = f"Barcha joylar (1-{sigim}-joy)"
    else:
        kr_yorliq = ", ".join(req.krovatlar) if req.krovatlar else "1-joy"

    baz_tur = "Dvuxspalniy" if tomon == "O'rtadagi" else f"{sigim} kishilik"
    x_turi = f"To'liq band ({baz_tur}) [🛏️ {kr_yorliq}]" if (req.vikup or tomon == "O'rtadagi") else f"{baz_tur} [🛏️ {kr_yorliq}]"
    sana_toliq = f"{bugun_str} ({soat_str})"
    izoh_yak = f"[🛏️ {kr_yorliq}] {req.izoh or ''}".strip()

    db.execute("""
        INSERT INTO bronlar (
            mijoz_id, jinsi, sana, tomon, xona, xona_turi, mijoz, toifa, odam_soni, muddat, kunlar,
            kunlik_narx, jami_summa, faktik_narx, tolagan_summa, qoldiq, tolov_turi, tolov_tafsiloti,
            holat, kirish_sanasi, chiqish_sanasi, bron_turi, izoh, telefon
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        yangi_id, req.jinsi, sana_toliq, tomon, req.xona, x_turi, req.mijoz.strip(), req.toifa,
        req.odam_soni, f"{req.kunlar} sutka", req.kunlar, kunlik, jami, jami, req.tolangan, qoldiq,
        "Naqd" if req.tolov_tafsiloti == "Naqd" else "Karta", req.tolov_tafsiloti, holat,
        bugun_str, chiqish_str, "Hozir kirish", izoh_yak, req.telefon.strip()
    ))
    _tozalik_ozgartir_direct(req.xona, "Toza")
    if req.tolangan > 0:
        db.execute(
            "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
            (bugun_str, yangi_id, req.mijoz.strip(), "Yotoq (Qabul)", req.tolangan, "Naqd", req.tolov_tafsiloti, req.xodim)
        )
    jurnalga_yozish(yangi_id, req.xodim, "Yangi Hozir kirish (Web UI)", f"{req.mijoz} ({req.odam_soni}k) -> {req.xona} ({kr_yorliq}), Jami: {jami:,.0f}")
    tg_xabar_yubor(
        "Yangi Qabul (Fullstack Web UI)",
        f"👤 <b>Mijoz:</b> {req.mijoz} ({req.odam_soni} kishi | {req.toifa})\n"
        f"🛏 <b>Xona va Joy:</b> {req.xona} — <b>{kr_yorliq}</b> ({req.kunlar} sutka)\n"
        f"💰 <b>Jami:</b> {jami:,.0f} UZS | <b>To'ladi:</b> {req.tolangan:,.0f} UZS",
        req.xodim
    )
    return {"ok": True, "mijoz_id": yangi_id, "jami": jami}

@app.post("/api/checkout")
def api_checkout(req: CheckoutReq):
    bugun_str = toshkent_vaqti().strftime("%Y-%m-%d")
    row = db.fetchone("SELECT mijoz, xona, tolagan_summa, faktik_narx, qoldiq, odam_soni FROM bronlar WHERE mijoz_id=?", (req.mijoz_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    m_ism, m_xona, es_tol, es_fak, es_qol, m_odam = row[0], row[1], _f(row[2]), _f(row[3]), _f(row[4]), int(_f(row[5], 1))

    if es_qol > 0 and req.vozvrat_summa == 0 and not req.majburiy_qarz_bilan:
        raise HTTPException(status_code=400, detail=f"QARZDOR:{int(es_qol)}")

    yangi_tol = es_tol - req.vozvrat_summa
    yangi_fak = yangi_tol if req.vozvrat_summa > 0 else es_fak
    db.execute(
        "UPDATE bronlar SET holat='Chiqib ketgan', chiqish_sanasi=?, tolagan_summa=?, faktik_narx=?, jami_summa=?, qoldiq=0 WHERE mijoz_id=?",
        (bugun_str, yangi_tol, yangi_fak, yangi_fak, req.mijoz_id)
    )
    _tozalik_ozgartir_direct(m_xona, "Tozalash kerak")
    if req.vozvrat_summa > 0:
        db.execute(
            "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
            (bugun_str, req.mijoz_id, m_ism, "Vozvrat (Web UI)", -req.vozvrat_summa, req.kassa, req.kassa, req.xodim)
        )
    jurnalga_yozish(req.mijoz_id, req.xodim, "Checkout (Web UI)", f"{m_ism} ({m_xona}) chiqarildi. Vozvrat: -{req.vozvrat_summa:,.0f}")
    tg_xabar_yubor("Checkout (Fullstack Web UI)", f"👤 <b>Mijoz:</b> {m_ism} ({m_odam} kishi)\n🛏 <b>Bo'shagan xona:</b> {m_xona}\n⏪ <b>Vozvrat:</b> -{req.vozvrat_summa:,.0f} UZS", req.xodim)
    return {"ok": True}

@app.post("/api/tozalik")
def api_tozalik(req: TozalikReq):
    _tozalik_ozgartir_direct(req.xona, req.holat)
    jurnalga_yozish("Housekeeping", req.xodim, "Xona tozaligi (Web UI)", f"{req.xona} -> {req.holat}")
    return {"ok": True}

FRONTEND_HTML = """
<!DOCTYPE html>
<html lang="uz" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Y.S.H. ERP | Fullstack SaaS Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0d14; color: #f8fafc; font-family: 'Inter', system-ui, sans-serif; }
        .pill-active { background: linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%); color: #fff; font-weight: 700; box-shadow: 0 4px 15px rgba(124,58,237,0.4); }
        .glass-card { background: #141724; border: 1px solid #262b40; border-radius: 16px; }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <nav class="sticky top-0 z-50 bg-[#111420]/95 backdrop-blur border-b border-[#22273b] px-4 py-3">
        <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-3">
                <span class="text-2xl">🏨</span>
                <div>
                    <h1 class="font-extrabold text-lg tracking-wide text-white">Y.S.H. ERP <span class="text-xs px-2 py-0.5 rounded-full bg-purple-600/30 text-purple-300 border border-purple-500/40">Fullstack v2.0</span></h1>
                    <p id="server-time" class="text-xs text-emerald-400 font-semibold">Bog'lanmoqda...</p>
                </div>
            </div>

            <div class="flex flex-wrap items-center gap-1.5 bg-[#171c2e] p-1.5 rounded-full border border-[#2a324b]">
                <button onclick="switchTab('dash')" id="tab-dash" class="px-4 py-1.5 rounded-full text-sm transition pill-active">🏠 Boshqaruv</button>
                <button onclick="switchTab('rooms')" id="tab-rooms" class="px-4 py-1.5 rounded-full text-sm text-slate-300 hover:text-white transition">🗺️ 2D Krovatlar Xaritasi</button>
                <button onclick="switchTab('guests')" id="tab-guests" class="px-4 py-1.5 rounded-full text-sm text-slate-300 hover:text-white transition">👥 Mehmonlar & Checkout</button>
                <button onclick="switchTab('tg')" id="tab-tg" class="px-4 py-1.5 rounded-full text-sm text-slate-300 hover:text-white transition">📲 Telegram Nazorati</button>
            </div>

            <div class="flex items-center gap-2">
                <input type="date" id="f-bosh" onchange="loadData()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-2.5 py-1.5 text-white">
                <span class="text-slate-500">➔</span>
                <input type="date" id="f-tugash" onchange="loadData()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-2.5 py-1.5 text-white">
                <button onclick="openModal()" class="bg-gradient-to-r from-emerald-500 to-teal-500 hover:opacity-95 text-white font-bold text-sm px-4 py-2 rounded-full shadow-lg">+ Yangi Qabul</button>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl w-full mx-auto p-4 flex-1 space-y-6">
        <div id="err-box" class="hidden p-4 rounded-xl bg-red-900/40 border border-red-500 text-red-200 text-sm"></div>

        <section id="sec-dash" class="space-y-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4" id="kpi-grid"></div>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4" id="finance-grid"></div>

            <div class="glass-card p-5">
                <h3 class="font-bold text-base mb-3 text-purple-300">🛎️ Faol Mehmonlar va Tezkor Checkout (CEO To'siqsiz Rejimi)</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-2">ID</th>
                                <th class="py-3 px-2">Mehmon</th>
                                <th class="py-3 px-2">Xona & Joy (2D)</th>
                                <th class="py-3 px-2">Odam / Sutka</th>
                                <th class="py-3 px-2">Jami / To'langan</th>
                                <th class="py-3 px-2">Qarz</th>
                                <th class="py-3 px-2">Kirish ➔ Chiqish</th>
                                <th class="py-3 px-2 text-right">Amal</th>
                            </tr>
                        </thead>
                        <tbody id="active-table-body" class="divide-y divide-slate-800/70"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <section id="sec-rooms" class="hidden space-y-4">
            <div class="flex flex-wrap justify-between items-center gap-2">
                <h2 class="text-xl font-bold">🛏️ 36 ta Xona va 2D Krovatlar Jonli Matritsasi (1 ➔ 2 | 3 ➔ 4)</h2>
                <div class="flex gap-2">
                    <button onclick="filterWing('ALL')" class="px-3 py-1 rounded-lg bg-slate-800 text-xs font-semibold">Barchasi (36)</button>
                    <button onclick="filterWing('Chap tomon')" class="px-3 py-1 rounded-lg bg-slate-800 text-xs font-semibold">Chap qanot (1-14)</button>
                    <button onclick="filterWing('O\\'rtadagi')" class="px-3 py-1 rounded-lg bg-slate-800 text-xs font-semibold">O'rta Lyuks (15-21)</button>
                    <button onclick="filterWing('O\\'ng tomon')" class="px-3 py-1 rounded-lg bg-slate-800 text-xs font-semibold">O'ng qanot (22-36)</button>
                </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" id="rooms-2d-grid"></div>
        </section>

        <section id="sec-guests" class="hidden space-y-4">
            <div class="glass-card p-5">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-bold">📋 Barcha Mehmonlar va Arxiv</h2>
                    <input type="text" id="search-guest" oninput="renderGuests()" placeholder="🔍 Ism, xona yoki ID qidirish..." class="bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 text-sm w-72 text-white">
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                            <tr>
                                <th class="py-2 px-2">ID</th>
                                <th class="py-2 px-2">Mehmon</th>
                                <th class="py-2 px-2">Xona & Joy</th>
                                <th class="py-2 px-2">Summa</th>
                                <th class="py-2 px-2">Qarz</th>
                                <th class="py-2 px-2">Sanalar</th>
                                <th class="py-2 px-2">Holat</th>
                            </tr>
                        </thead>
                        <tbody id="all-guests-body" class="divide-y divide-slate-800/60"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <section id="sec-tg" class="hidden space-y-4">
            <div class="glass-card p-5">
                <h2 class="text-lg font-bold mb-1">📲 Telegramga Yuborilgan Xabarlar Jurnali (CEO & Owner)</h2>
                <p class="text-xs text-slate-400 mb-4">Tizim tomonidan yuborilgan har bir bildirishnoma va uning yetkazilganlik statusi</p>
                <div id="tg-log-list" class="space-y-3"></div>
            </div>
        </section>
    </main>

    <div id="qabul-modal" class="fixed inset-0 bg-black/75 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="glass-card max-w-2xl w-full p-6 space-y-4 border border-purple-500/40">
            <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                <h3 class="text-lg font-bold text-white">➕ Yangi Mehmon Qabul Qilish (2D Joy Tanlash bilan)</h3>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="text-xs text-slate-300">👤 Mehmon F.I.O *</label>
                    <input id="m-ism" type="text" placeholder="Alisher Karimov" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">📞 Telefon raqami</label>
                    <input id="m-tel" type="text" placeholder="+998 90 123 45 67" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🛏️ Xonani tanlang</label>
                    <select id="m-xona" onchange="updateModalRoomBeds()" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"></select>
                </div>
                <div>
                    <label class="text-xs text-slate-300">🪪 Toifa</label>
                    <select id="m-toifa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option value="O'zbekiston fuqarosi">O'zbekiston fuqarosi</option>
                        <option value="Chet el fuqarosi">Chet el fuqarosi (+50k)</option>
                        <option value="Talaba (Student)">Talaba (-50%)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs text-slate-300">👥 Odam soni</label>
                    <input id="m-odam" type="number" value="1" min="1" max="4" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🌙 Sutka soni</label>
                    <input id="m-kun" type="number" value="1" min="1" max="365" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">💵 To'langan summa (UZS)</label>
                    <input id="m-tolov" type="number" value="100000" step="10000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🏦 Kassa</label>
                    <select id="m-kassa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option>Naqd</option><option>Click</option><option>Uzcard</option><option>Humo</option><option>Terminal</option>
                    </select>
                </div>
            </div>

            <div>
                <label class="text-xs text-purple-300 font-semibold">🧭 Yotoq o'rnini (Krovatni) ustiga bosib tanlang (1 ➔ 2 | 3 ➔ 4):</label>
                <div id="m-beds-grid" class="grid grid-cols-2 gap-2 mt-2"></div>
            </div>

            <div class="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button onclick="closeModal()" class="px-4 py-2 rounded-lg bg-slate-800 text-sm">Bekor qilish</button>
                <button onclick="submitQabul()" class="px-6 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-sm">✅ Bazaga Saqlash</button>
            </div>
        </div>
    </div>

<script>
let STATE = { xonalar: [], faol_mehmonlar: [], barcha_mehmonlar: [], tg_log: [], wingFilter: 'ALL', selectedBeds: [] };

async function loadData() {
    try {
        const b = document.getElementById('f-bosh').value;
        const t = document.getElementById('f-tugash').value;
        const q = (b && t) ? `?bosh_sana=${b}&tugash_sana=${t}` : '';
        const res = await fetch('/api/dashboard' + q);
        if (!res.ok) {
            const errTxt = await res.text();
            throw new Error("Server xatosi: " + errTxt);
        }
        const data = await res.json();
        STATE = { ...STATE, ...data };
        document.getElementById('err-box').classList.add('hidden');
        document.getElementById('server-time').innerText = `🟢 Jonli aloqa | Toshkent: ${data.vaqt}`;
        renderDashboard();
        renderRooms2D();
        renderGuests();
        renderTgLog();
    } catch (e) {
        const eb = document.getElementById('err-box');
        eb.innerText = "Xatolik yuz berdi: " + e.message;
        eb.classList.remove('hidden');
        document.getElementById('server-time').innerText = "⚠️ Aloqa xatosi";
    }
}

function switchTab(tab) {
    ['dash', 'rooms', 'guests', 'tg'].forEach(t => {
        document.getElementById('sec-' + t).classList.toggle('hidden', t !== tab);
        const btn = document.getElementById('tab-' + t);
        if (t === tab) btn.className = "px-4 py-1.5 rounded-full text-sm transition pill-active";
        else btn.className = "px-4 py-1.5 rounded-full text-sm text-slate-300 hover:text-white transition";
    });
}

function renderDashboard() {
    const k = STATE.kpi;
    document.getElementById('kpi-grid').innerHTML = `
        <div class="p-4 rounded-2xl bg-gradient-to-br from-purple-600 to-indigo-700 text-white shadow-lg">
            <div class="text-xs opacity-85">Band Xonalar</div>
            <div class="text-3xl font-extrabold my-1">${k.band_xonalar} <span class="text-lg opacity-75">/ 36</span></div>
            <div class="text-xs">Jami faol: <b>${k.faol_mehmon} kishi</b></div>
        </div>
        <div class="glass-card p-4">
            <div class="text-xs text-slate-400">Davr Kirishlar</div>
            <div class="text-2xl font-extrabold text-emerald-400 my-1">${k.kirgan_odam} kishi</div>
            <div class="text-xs text-slate-400">Bo'sh toza: ${k.bosh_xonalar} ta xona</div>
        </div>
        <div class="glass-card p-4">
            <div class="text-xs text-slate-400">Davr Chiqishlar</div>
            <div class="text-2xl font-extrabold text-amber-400 my-1">${k.chiqqan_odam} kishi</div>
            <div class="text-xs text-red-400">🧹 Tozalash kerak: ${k.tozalash_kerak} ta</div>
        </div>
        <div class="glass-card p-4">
            <div class="text-xs text-slate-400">Sof Kassa Balans</div>
            <div class="text-2xl font-extrabold text-cyan-400 my-1">${k.sof_balans.toLocaleString()} <span class="text-xs">UZS</span></div>
            <div class="text-xs text-red-400">Joriy qarzlar: ${k.umumiy_qarz.toLocaleString()} UZS</div>
        </div>
    `;

    document.getElementById('finance-grid').innerHTML = `
        <div class="glass-card p-3 border-t-4 border-amber-500"><div class="text-xs text-slate-400">💰 Yotoq Kirim</div><div class="text-lg font-bold mt-1">${k.yotoq_kirim.toLocaleString()} UZS</div></div>
        <div class="glass-card p-3 border-t-4 border-emerald-500"><div class="text-xs text-slate-400">🛒 Market Kirim</div><div class="text-lg font-bold mt-1">${k.market_kirim.toLocaleString()} UZS</div></div>
        <div class="glass-card p-3 border-t-4 border-slate-500"><div class="text-xs text-slate-400">➖ Xarajatlar</div><div class="text-lg font-bold mt-1">${k.xarajat.toLocaleString()} UZS</div></div>
        <div class="glass-card p-3 border-t-4 border-blue-500"><div class="text-xs text-slate-400">🏦 Sof Kassa</div><div class="text-lg font-bold mt-1">${k.sof_balans.toLocaleString()} UZS</div></div>
        <div class="glass-card p-3 border-t-4 border-red-500"><div class="text-xs text-slate-400">⚠️ Qarzlar</div><div class="text-lg font-bold mt-1">${k.umumiy_qarz.toLocaleString()} UZS</div></div>
    `;

    const tbody = document.getElementById('active-table-body');
    tbody.innerHTML = STATE.faol_mehmonlar.map(m => `
        <tr class="hover:bg-slate-800/40">
            <td class="py-2.5 px-2 font-mono text-xs text-slate-400">${m.mijoz_id}</td>
            <td class="py-2.5 px-2 font-bold text-white">${m.mijoz}</td>
            <td class="py-2.5 px-2"><span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-xs font-semibold">${m.xona} (${m.joy || 'Standart'})</span></td>
            <td class="py-2.5 px-2">${m.odam_soni} kishi / ${m.kunlar} kun</td>
            <td class="py-2.5 px-2">${m.faktik_narx.toLocaleString()} / <span class="text-emerald-400">${m.tolagan_summa.toLocaleString()}</span></td>
            <td class="py-2.5 px-2 ${m.qoldiq > 0 ? 'text-red-400 font-bold' : 'text-slate-400'}">${Math.max(0, m.qoldiq).toLocaleString()} UZS</td>
            <td class="py-2.5 px-2 text-xs text-slate-300">${m.kirish_vaqti} ➔ ${m.chiqish_sanasi}</td>
            <td class="py-2.5 px-2 text-right">
                <button onclick="doCheckout('${m.mijoz_id}', '${m.mijoz}', ${m.qoldiq})" class="px-3 py-1 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-semibold">🚪 Checkout</button>
            </td>
        </tr>
    `).join('') || '<tr><td colspan="8" class="text-center py-6 text-slate-500">Hozircha faol mehmonlar yo\'q (Yangi Qabul tugmasi orqali qo\'shib ko\'ring!)</td></tr>';
}

function filterWing(w) { STATE.wingFilter = w; renderRooms2D(); }

function renderRooms2D() {
    const container = document.getElementById('rooms-2d-grid');
    const list = STATE.xonalar.filter(r => STATE.wingFilter === 'ALL' || r.tomon === STATE.wingFilter);
    container.innerHTML = list.map(r => {
        let borderCol = r.tozalik === 'Tozalash kerak' ? 'border-red-500' : (r.bosh_joy === 0 ? 'border-purple-500' : (r.band_odam > 0 ? 'border-amber-500' : 'border-emerald-500'));
        let bedsHtml = '';
        if (r.tomon === "O'rtadagi") {
            const egasi = r.krovatlar['1'] || '';
            bedsHtml = egasi
                ? `<div class="p-2.5 rounded-lg bg-purple-500/20 border border-purple-500 text-center text-xs">🛌 <b>Dvuxspalniy:</b> ${egasi}</div>`
                : `<div class="p-2.5 rounded-lg bg-emerald-500/15 border border-emerald-500 text-center text-xs">🟢 <b>Dvuxspalniy:</b> BO'SH</div>`;
        } else {
            let cells = [];
            for (let i = 1; i <= r.sigim; i++) {
                const egasi = r.krovatlar[String(i)];
                if (egasi) {
                    cells.push(`<div class="p-2 rounded-lg bg-red-500/20 border border-red-500 text-center text-xs">🔴 <b>${i}-joy</b><br><span class="text-[11px] opacity-90">${egasi.slice(0,12)}</span></div>`);
                } else {
                    cells.push(`<div class="p-2 rounded-lg bg-emerald-500/15 border border-emerald-500 text-center text-xs">🟢 <b>${i}-joy</b><br><span class="text-[11px] opacity-80">BO'SH</span></div>`);
                }
            }
            if (r.sigim === 3) cells.push(`<div class="p-2 rounded-lg border border-dashed border-slate-700 text-center text-xs opacity-40">—</div>`);
            bedsHtml = `<div class="grid grid-cols-2 gap-2 mt-2">${cells.join('')}</div>`;
        }
        const nextClean = r.tozalik === 'Tozalash kerak' ? 'Toza' : 'Tozalash kerak';
        const cleanBtnTxt = r.tozalik === 'Tozalash kerak' ? '✨ Tozalandi deb belgilash' : '🧹 Tozalashga berish';
        return `
            <div class="glass-card p-4 border-2 ${borderCol} flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-center">
                        <span class="font-extrabold text-base">🛏️ ${r.xona}</span>
                        <span class="text-xs px-2 py-0.5 rounded-full bg-slate-800">${r.tozalik === 'Tozalash kerak' ? '🔴 Tozalash kk' : `Bo'sh: ${r.bosh_joy}/${r.sigim}`}</span>
                    </div>
                    <div class="text-xs text-slate-400 mt-0.5 mb-2">${r.tomon} • ${r.sigim} kishilik ${r.jinsi ? '• ' + r.jinsi : ''}</div>
                    ${bedsHtml}
                </div>
                <button onclick="toggleClean('${r.xona}', '${nextClean}')" class="mt-3 w-full py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold">${cleanBtnTxt}</button>
            </div>
        `;
    }).join('');
}

function renderGuests() {
    const q = (document.getElementById('search-guest').value || '').toLowerCase();
    const rows = STATE.barcha_mehmonlar.filter(m => m.mijoz.toLowerCase().includes(q) || m.xona.toLowerCase().includes(q) || m.mijoz_id.includes(q));
    document.getElementById('all-guests-body').innerHTML = rows.map(m => `
        <tr class="hover:bg-slate-800/40">
            <td class="py-2 px-2 font-mono text-xs">${m.mijoz_id}</td>
            <td class="py-2 px-2 font-semibold">${m.mijoz}</td>
            <td class="py-2 px-2">${m.xona} (${m.joy})</td>
            <td class="py-2 px-2">${m.faktik_narx.toLocaleString()} UZS</td>
            <td class="py-2 px-2 ${m.qoldiq > 0 ? 'text-red-400 font-bold' : ''}">${Math.max(0, m.qoldiq).toLocaleString()} UZS</td>
            <td class="py-2 px-2 text-xs">${m.kirish_vaqti} ➔ ${m.chiqish_sanasi}</td>
            <td class="py-2 px-2"><span class="px-2 py-0.5 rounded text-xs ${m.holat === 'Chiqib ketgan' ? 'bg-slate-800 text-slate-400' : 'bg-emerald-500/20 text-emerald-300'}">${m.holat}</span></td>
        </tr>
    `).join('');
}

function renderTgLog() {
    const box = document.getElementById('tg-log-list');
    box.innerHTML = STATE.tg_log.map(t => `
        <div class="p-3 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col md:flex-row justify-between gap-2">
            <div>
                <div class="flex items-center gap-2">
                    <span class="font-bold text-sm text-purple-300">${t.sarlavha}</span>
                    <span class="text-xs px-2 py-0.5 rounded bg-slate-800">${t.qabul_qiluvchi}</span>
                    <span class="text-xs">${t.holat}</span>
                </div>
                <p class="text-xs text-slate-300 mt-1 whitespace-pre-line">${t.matn}</p>
            </div>
            <div class="text-right text-xs text-slate-400 shrink-0">${t.vaqt}<br>👤 ${t.xodim}</div>
        </div>
    `).join('') || '<p class="text-sm text-slate-500">Hozircha Telegram xabarlar jurnali bo\'sh.</p>';
}

async function doCheckout(id, ism, qarz) {
    let majburiy = false;
    if (qarz > 0) {
        if (!confirm(`⚠️ DIQQAT (CEO): ${ism} da ${qarz.toLocaleString()} UZS qarz bor! Haqiqatdan ham qarzdor holatda checkout qilishni xohlaysizmi?`)) return;
        majburiy = true;
    }
    const vozv = prompt(`${ism} uchun qaytariladigan Vozvrat summasi (0 = vozvrat yo'q):`, "0");
    if (vozv === null) return;
    const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ mijoz_id: id, vozvrat_summa: parseFloat(vozv || 0), majburiy_qarz_bilan: majburiy })
    });
    if (res.ok) loadData();
    else alert("Xatolik: " + (await res.text()));
}

async function toggleClean(xona, holat) {
    await fetch('/api/tozalik', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ xona, holat })
    });
    loadData();
}

function openModal() {
    const sel = document.getElementById('m-xona');
    sel.innerHTML = STATE.xonalar.map(r => `<option value="${r.xona}">${r.xona} (${r.tomon} — Bo'sh: ${r.bosh_joy}/${r.sigim})</option>`).join('');
    updateModalRoomBeds();
    document.getElementById('qabul-modal').classList.remove('hidden');
}
function closeModal() { document.getElementById('qabul-modal').classList.add('hidden'); }

function updateModalRoomBeds() {
    const xNom = document.getElementById('m-xona').value;
    const r = STATE.xonalar.find(x => x.xona === xNom);
    if (!r) return;
    STATE.selectedBeds = [];
    const grid = document.getElementById('m-beds-grid');
    if (r.tomon === "O'rtadagi") {
        grid.innerHTML = `<div class="col-span-2 p-3 rounded-lg bg-purple-600/20 border border-purple-500 text-center text-xs">🛌 Lyuks xona: Bitta Dvuxspalniy</div>`;
        return;
    }
    let html = '';
    for (let i = 1; i <= r.sigim; i++) {
        const band = r.krovatlar[String(i)];
        if (band) {
            html += `<div class="p-2.5 rounded-lg bg-red-900/30 border border-red-600 text-center text-xs opacity-60 cursor-not-allowed">🔴 ${i}-joy (Band: ${band})</div>`;
        } else {
            if (STATE.selectedBeds.length === 0) STATE.selectedBeds.push(`${i}-joy`);
            const isSel = STATE.selectedBeds.includes(`${i}-joy`);
            html += `<div onclick="toggleBedSelect('${i}-joy')" id="bed-btn-${i}-joy" class="p-2.5 rounded-lg border text-center text-xs cursor-pointer transition ${isSel ? 'bg-purple-600 border-purple-300 font-bold text-white' : 'bg-emerald-950/40 border-emerald-600 text-emerald-300'}">🟢 ${i}-joy (Bo'sh)</div>`;
        }
    }
    grid.innerHTML = html;
}

function toggleBedSelect(joy) {
    const idx = STATE.selectedBeds.indexOf(joy);
    if (idx >= 0) STATE.selectedBeds.splice(idx, 1);
    else STATE.selectedBeds.push(joy);
    const btn = document.getElementById('bed-btn-' + joy);
    if (btn) {
        const isSel = STATE.selectedBeds.includes(joy);
        btn.className = `p-2.5 rounded-lg border text-center text-xs cursor-pointer transition ${isSel ? 'bg-purple-600 border-purple-300 font-bold text-white' : 'bg-emerald-950/40 border-emerald-600 text-emerald-300'}`;
    }
}

async function submitQabul() {
    const body = {
        mijoz: document.getElementById('m-ism').value,
        telefon: document.getElementById('m-tel').value,
        xona: document.getElementById('m-xona').value,
        toifa: document.getElementById('m-toifa').value,
        odam_soni: parseInt(document.getElementById('m-odam').value || 1),
        kunlar: parseInt(document.getElementById('m-kun').value || 1),
        tolangan: parseFloat(document.getElementById('m-tolov').value || 0),
        tolov_tafsiloti: document.getElementById('m-kassa').value,
        krovatlar: STATE.selectedBeds
    };
    const res = await fetch('/api/qabul', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    });
    if (res.ok) { closeModal(); loadData(); }
    else { const err = await res.json(); alert("Xatolik: " + err.detail); }
}

loadData();
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return FRONTEND_HTML