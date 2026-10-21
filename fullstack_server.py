import os
import re
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import io

from database import (
    db, XONALAR, XONA_TOMON_MAP, toshkent_vaqti, xona_sigimini_ol,
    xonadagi_band_joyni_hisobla, xona_jinsini_tekshir, id_yaratish,
    jurnalga_yozish, haftalik_hisobot_yuklash
)
from tg_bot import tg_xabar_yubor

app = FastAPI(title="Y.S.H. ERP | Fullstack SaaS v4.0")

# ==================== REQUEST MODELLARI ====================
class LoginReq(BaseModel):
    login: str
    parol: str

class YangiBronReq(BaseModel):
    mijoz: str
    telefon: Optional[str] = ""
    jinsi: str = "Erkak"
    toifa: str = "O'zbekiston fuqarosi"
    xona: str
    odam_soni: int = 1
    krovatlar: List[str] = []
    vikup: bool = False
    kirish_sanasi: Optional[str] = ""
    kirish_soati: Optional[str] = ""
    kunlar: int = 1
    chegirma_foiz: int = 0
    tolangan: float = 0
    tolov_tafsiloti: str = "Naqd"
    bron_turi: str = "Hozir kirish"
    izoh: Optional[str] = ""
    xodim: str = "CEO (Web UI)"

class TahrirBronReq(BaseModel):
    mijoz_id: str
    mijoz: str
    toifa: str
    xona: str
    odam_soni: int
    krovatlar: List[str] = []
    vikup: bool = False
    kirish_sanasi: str
    kirish_soati: str
    kunlar: int
    faktik_narx: float
    tolagan_summa: float
    izoh: Optional[str] = ""
    avto_qayta_hisob: bool = False
    xodim: str = "CEO (Web UI)"

class CheckoutReq(BaseModel):
    mijoz_id: str
    yashagan_kun: Optional[int] = None
    vozvrat_summa: float = 0
    kassa: str = "Naqd"
    xodim: str = "CEO (Web UI)"
    majburiy_qarz_bilan: bool = False

class QarzYopishReq(BaseModel):
    mijoz_id: str
    summa: float
    kassa: str = "Naqd"
    xodim: str = "CEO (Web UI)"

class MuddatChozishReq(BaseModel):
    mijoz_id: str
    qoshimcha_kun: int
    qoshimcha_summa: float
    tolangan_summa: float = 0
    kassa: str = "Naqd"
    xodim: str = "CEO (Web UI)"

class XonaKochirishReq(BaseModel):
    mijoz_id: str
    yangi_xona: str
    yangi_krovatlar: List[str] = []
    vikup: bool = False
    xodim: str = "CEO (Web UI)"

class MarketSavdoReq(BaseModel):
    mahsulot_id: int
    miqdor: int = 1
    tolov_turi: str = "Darhol"
    kassa: str = "Naqd"
    mijoz_id: Optional[str] = ""
    xodim: str = "CEO (Web UI)"

class YangiTovarReq(BaseModel):
    nomi: str
    hajmi: Optional[str] = ""
    kategoriya: str = "Ichimliklar"
    tannarx: float = 0
    narxi: float
    qoldiq: int = 1
    xodim: str = "CEO (Web UI)"

class XarajatReq(BaseModel):
    kategoriya: str
    summa: float
    tolov_turi: str = "Naqd"
    izoh: str
    xodim: str = "CEO (Web UI)"

class SmenaYopishReq(BaseModel):
    izoh: Optional[str] = ""
    xodim: str = "CEO (Web UI)"

class TozalikReq(BaseModel):
    xona: str
    holat: str
    xodim: str = "Web UI"

class XodimReq(BaseModel):
    login: str
    parol: str
    ism: str
    role: str = "admin"
    xodim: str = "CEO"

# ==================== YORDAMCHI FUNKSIYALAR ====================
def _krovat_ajrat(x_tur, izoh):
    m = re.search(r'\[🛏️ (.*?)\]', f"{x_tur or ''} {izoh or ''}")
    if m:
        return m.group(1).replace("Chapdan ", "").replace("O'ngdan ", "").strip()
    return ""

def _tozalik_ol_direct():
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

def _bron_shu_kunda_faolmi(k_s, ch_s, holat, tekshir_sana):
    if holat == "Chiqib ketgan" or not k_s or not ch_s:
        return False
    if k_s == ch_s:
        return k_s == tekshir_sana
    return k_s <= tekshir_sana < ch_s

# ==================== API ENDPOINTLAR ====================
@app.post("/api/login")
def api_login(req: LoginReq):
    u = db.fetchone("SELECT role, ism, login FROM xodimlar WHERE login=? AND parol=?", (req.login.strip(), req.parol.strip()))
    if not u:
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri!")
    return {"role": _s(u[0], "admin"), "ism": _s(u[1]) or _s(u[2]).upper(), "login": _s(u[2])}

@app.get("/api/excel-export")
def api_excel_export(bosh_sana: Optional[str] = None, tugash_sana: Optional[str] = None):
    excel_bytes = haftalik_hisobot_yuklash(bosh_sana if bosh_sana else None, tugash_sana if tugash_sana else None)
    davr_nom = f"{bosh_sana}_{tugash_sana}" if (bosh_sana and tugash_sana) else toshkent_vaqti().strftime("%Y-%m-%d")
    headers = {"Content-Disposition": f'attachment; filename="YSH_ERP_Hisobot_{davr_nom}.xlsx"'}
    return StreamingResponse(io.BytesIO(excel_bytes), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)

@app.get("/api/dashboard")
def api_dashboard(bosh_sana: Optional[str] = None, tugash_sana: Optional[str] = None):
    uz_now = toshkent_vaqti()
    bugun = uz_now.strftime("%Y-%m-%d")

    try: df_b = db.read_df("SELECT * FROM bronlar ORDER BY id DESC")
    except Exception: df_b = pd.DataFrame()
    try: df_t = db.read_df("SELECT * FROM tolovlar_tarixi ORDER BY id DESC")
    except Exception: df_t = pd.DataFrame()
    try: df_x = db.read_df("SELECT * FROM xarajatlar ORDER BY id DESC")
    except Exception: df_x = pd.DataFrame()
    try: df_m = db.read_df("SELECT * FROM mahsulotlar ORDER BY qoldiq ASC")
    except Exception: df_m = pd.DataFrame()
    try: df_s = db.read_df("SELECT * FROM savdolar ORDER BY id DESC LIMIT 80")
    except Exception: df_s = pd.DataFrame()
    try: df_u = db.read_df("SELECT login, ism, role FROM xodimlar")
    except Exception: df_u = pd.DataFrame()
    try: df_aud = db.read_df("SELECT vaqt, mijoz_id, xodim, harakat, tafsilot FROM audit_log ORDER BY id DESC LIMIT 80")
    except Exception: df_aud = pd.DataFrame()

    df_tg_list = []
    try:
        df_tg = db.read_df("SELECT vaqt, sarlavha, qabul_qiluvchi, xodim, holat, matn FROM tg_xabarlar_log ORDER BY id DESC LIMIT 60")
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
            kun_r = int(_f(r.get('kunlar'), 1))
            fak_r = _f(r.get('faktik_narx'), 0.0)
            kunlik_r = _f(r.get('kunlik_narx'), fak_r / max(1, kun_r))
            qol = _f(r.get('qoldiq'), 0.0)
            joy = _krovat_ajrat(_s(r.get('xona_turi')), _s(r.get('izoh')))
            x_nom_r = _s(r.get('xona'))
            sana_v = _s(r.get('sana')) or k_s
            soat_v = sana_v.split("(")[1].replace(")", "") if "(" in sana_v else "14:00"

            is_active_today = _bron_shu_kunda_faolmi(k_s, ch_s, hol, bugun)
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
                "toifa": _s(r.get('toifa'), "O'zbekiston fuqarosi"),
                "xona": x_nom_r,
                "tomon": _s(r.get('tomon')) or XONA_TOMON_MAP.get(x_nom_r, ""),
                "joy": joy,
                "odam_soni": odam,
                "kunlar": kun_r,
                "kunlik_narx": kunlik_r,
                "faktik_narx": fak_r,
                "tolagan_summa": _f(r.get('tolagan_summa'), 0.0),
                "qoldiq": qol,
                "tolov_tafsiloti": _s(r.get('tolov_tafsiloti'), "Naqd"),
                "kirish_vaqti": sana_v,
                "kirish_sanasi": k_s,
                "kirish_soati": soat_v,
                "chiqish_sanasi": ch_s,
                "bron_turi": _s(r.get('bron_turi'), "Hozir kirish"),
                "holat": hol,
                "izoh": _s(r.get('izoh'))
            }
            barcha_list.append(item)
            if hol != 'Chiqib ketgan':
                faol_list.append(item)

    # 7 kunlik prognoz va 10 kunlik Timeline Shaxmatka sanalari
    kun_qisqa = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    prognoz_7_kun = []
    timeline_sanalar = []
    for i in range(10):
        d_obj = uz_now.date() + timedelta(days=i)
        d_str = d_obj.strftime("%Y-%m-%d")
        k_nom = kun_qisqa[d_obj.weekday()]
        timeline_sanalar.append({"sana": d_str, "label": f"{k_nom} {d_obj.strftime('%d.%m')}"})
        if i < 7:
            d_xonalar = set()
            d_odam = 0
            for m in faol_list:
                if _bron_shu_kunda_faolmi(m['kirish_sanasi'], m['chiqish_sanasi'], m['holat'], d_str):
                    d_xonalar.add(m['xona'])
                    d_odam += m['odam_soni']
            foiz = int(round((len(d_xonalar) / 36.0) * 100))
            prognoz_7_kun.append({"kun": k_nom, "sana": d_obj.strftime("%d.%m"), "foiz": foiz, "odam": d_odam, "xona_soni": len(d_xonalar)})

    xonalar_xaritasi = []
    for tomon, x_dict in XONALAR.items():
        for x_nom, (sigim, narx) in x_dict.items():
            krovatlar_holati = {}
            x_jins = ""
            vikup = False
            x_odam = 0
            kunlik_bandlik = {}
            for ts in timeline_sanalar:
                ts_sana = ts["sana"]
                ts_odam = 0
                ts_mijozlar = []
                for m in faol_list:
                    if m['xona'] == x_nom and _bron_shu_kunda_faolmi(m['kirish_sanasi'], m['chiqish_sanasi'], m['holat'], ts_sana):
                        ts_odam += sigim if ("Barcha joylar" in m['joy'] or tomon == "O'rtadagi") else m['odam_soni']
                        ts_mijozlar.append(f"{m['mijoz']} ({m['joy'] or '1-joy'})")
                kunlik_bandlik[ts_sana] = {"band": min(sigim, ts_odam), "bosh": max(0, sigim - ts_odam), "mijozlar": ", ".join(ts_mijozlar)}

            for m in faol_list:
                if m['xona'] == x_nom and _bron_shu_kunda_faolmi(m['kirish_sanasi'], m['chiqish_sanasi'], m['holat'], bugun):
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
                "krovatlar": krovatlar_holati,
                "timeline": kunlik_bandlik
            })

    yotoq_kirim, market_kirim, naqd_kirim, karta_kirim = 0.0, 0.0, 0.0, 0.0
    if not df_t.empty:
        for _, tr in df_t.iterrows():
            s_d = _s(tr.get('sana'))
            if (not bosh_sana or not tugash_sana) or (b_s <= s_d <= t_s):
                sum_v = _f(tr.get('summa'), 0.0)
                if _s(tr.get('manba')) == 'Market Savdo':
                    market_kirim += sum_v
                else:
                    yotoq_kirim += sum_v
                if _s(tr.get('tolov_tafsiloti')) == 'Naqd':
                    naqd_kirim += sum_v
                else:
                    karta_kirim += sum_v

    xarajat_sum, naqd_xar, karta_xar = 0.0, 0.0, 0.0
    xarajat_list = []
    if not df_x.empty:
        for _, xr in df_x.iterrows():
            s_d = _s(xr.get('sana'))
            if (not bosh_sana or not tugash_sana) or (b_s <= s_d <= t_s):
                sv = _f(xr.get('summa'), 0.0)
                xarajat_sum += sv
                if _s(xr.get('tolov_turi')) == 'Naqd':
                    naqd_xar += sv
                else:
                    karta_xar += sv
                if len(xarajat_list) < 50:
                    xarajat_list.append({
                        "vaqt": _s(xr.get("vaqt")) or s_d,
                        "kategoriya": _s(xr.get("kategoriya")),
                        "summa": sv,
                        "tolov_turi": _s(xr.get("tolov_turi")),
                        "izoh": _s(xr.get("izoh")),
                        "xodim": _s(xr.get("xodim"))
                    })

    mahsulotlar_list = []
    if not df_m.empty:
        for _, mr in df_m.iterrows():
            mahsulotlar_list.append({
                "id": int(_f(mr.get("id"), 0)),
                "nomi": _s(mr.get("nomi")),
                "hajmi": _s(mr.get("hajmi")),
                "kategoriya": _s(mr.get("kategoriya")),
                "tannarx": _f(mr.get("tannarx"), 0.0),
                "narxi": _f(mr.get("narxi"), 0.0),
                "qoldiq": int(_f(mr.get("qoldiq"), 0))
            })

    xodimlar_list = []
    if not df_u.empty:
        for _, ur in df_u.iterrows():
            xodimlar_list.append({"login": _s(ur.get("login")), "ism": _s(ur.get("ism")), "role": _s(ur.get("role"))})

    audit_list = []
    if not df_aud.empty:
        for _, ar in df_aud.iterrows():
            audit_list.append({
                "vaqt": _s(ar.get("vaqt")),
                "obyekt": _s(ar.get("mijoz_id")),
                "xodim": _s(ar.get("xodim")),
                "harakat": _s(ar.get("harakat")),
                "tafsilot": _s(ar.get("tafsilot"))
            })

    tozalash_soni = sum(1 for h in toz_map.values() if h == "Tozalash kerak")

    return {
        "vaqt": uz_now.strftime("%d.%m.%Y %H:%M"),
        "bugun": bugun,
        "soat": uz_now.strftime("%H:%M"),
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
            "sof_naqd": naqd_kirim - naqd_xar,
            "sof_karta": karta_kirim - karta_xar,
            "umumiy_qarz": umumiy_qarz
        },
        "prognoz_7_kun": prognoz_7_kun,
        "timeline_sanalar": timeline_sanalar,
        "faol_mehmonlar": faol_list,
        "barcha_mehmonlar": barcha_list[:150],
        "xonalar": xonalar_xaritasi,
        "mahsulotlar": mahsulotlar_list,
        "xarajatlar": xarajat_list,
        "xodimlar": xodimlar_list,
        "audit_log": audit_list,
        "tg_log": df_tg_list
    }

@app.post("/api/qabul")
def api_yangi_qabul(req: YangiBronReq):
    uz_now = toshkent_vaqti()
    k_sana_str = req.kirish_sanasi.strip() if req.kirish_sanasi else uz_now.strftime("%Y-%m-%d")
    soat_str = req.kirish_soati.strip() if req.kirish_soati else uz_now.strftime("%H:%M")
    tomon = XONA_TOMON_MAP.get(req.xona, "Chap tomon")
    sigim, baz_narx = XONALAR[tomon][req.xona]

    try:
        k_dt = datetime.strptime(k_sana_str, "%Y-%m-%d").date()
        soat_h = int(soat_str.split(":")[0])
    except Exception:
        k_dt = uz_now.date()
        soat_h = uz_now.hour

    chiqish_dt = k_dt + timedelta(days=max(0, req.kunlar - 1) if soat_h < 12 else req.kunlar)
    chiqish_str = chiqish_dt.strftime("%Y-%m-%d")

    band = xonadagi_band_joyni_hisobla(req.xona, k_sana_str, chiqish_str)
    kerak = sigim if req.vikup else req.odam_soni
    if kerak > (sigim - band):
        raise HTTPException(status_code=400, detail=f"{req.xona} da bo'sh joy yetarli emas!")

    zid = None if (req.vikup or tomon == "O'rtadagi") else xona_jinsini_tekshir(req.xona, k_sana_str, chiqish_str, req.jinsi)
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
    if req.chegirma_foiz > 0:
        jami = round(jami * ((100.0 - float(req.chegirma_foiz)) / 100.0))

    qoldiq = jami - req.tolangan
    holat = "To'langan" if qoldiq <= 0 else "Qarzdorlik"
    yangi_id = id_yaratish(req.jinsi, k_dt, req.toifa)

    if tomon == "O'rtadagi":
        kr_yorliq = "Dvuxspalniy"
    elif req.vikup or req.odam_soni == sigim:
        kr_yorliq = f"Barcha joylar (1-{sigim}-joy)"
    else:
        kr_yorliq = ", ".join(req.krovatlar) if req.krovatlar else "1-joy"

    baz_tur = "Dvuxspalniy" if tomon == "O'rtadagi" else f"{sigim} kishilik"
    x_turi = f"To'liq band ({baz_tur}) [🛏️ {kr_yorliq}]" if (req.vikup or tomon == "O'rtadagi") else f"{baz_tur} [🛏️ {kr_yorliq}]"
    sana_toliq = f"{k_sana_str} ({soat_str})"
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
        k_sana_str, chiqish_str, req.bron_turi, izoh_yak, req.telefon.strip()
    ))
    _tozalik_ozgartir_direct(req.xona, "Toza")
    if req.tolangan > 0:
        db.execute(
            "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
            (uz_now.strftime("%Y-%m-%d"), yangi_id, req.mijoz.strip(), "Yotoq (Qabul)", req.tolangan, "Naqd", req.tolov_tafsiloti, req.xodim)
        )
    jurnalga_yozish(yangi_id, req.xodim, "Yangi Qabul (Web UI)", f"{req.mijoz} ({req.odam_soni}k) -> {req.xona} ({kr_yorliq}), Kirish: {sana_toliq}, Jami: {jami:,.0f}")
    tg_xabar_yubor(
        "Yangi Qabul (Fullstack Web UI)",
        f"👤 <b>Mijoz:</b> {req.mijoz} ({req.odam_soni} kishi | {req.toifa})\n"
        f"🛏 <b>Xona va Joy:</b> {req.xona} — <b>{kr_yorliq}</b>\n"
        f"🕒 <b>Kirish:</b> {sana_toliq} ➡️ <b>Chiqish:</b> {chiqish_str} 12:00 ({req.kunlar} sutka)\n"
        f"💰 <b>Jami:</b> {jami:,.0f} UZS | <b>To'ladi:</b> {req.tolangan:,.0f} UZS",
        req.xodim
    )
    return {"ok": True, "mijoz_id": yangi_id, "jami": jami}

@app.post("/api/tahrir")
def api_tahrir(req: TahrirBronReq):
    uz_now = toshkent_vaqti()
    bugun_str = uz_now.strftime("%Y-%m-%d")
    es_row = db.fetchone("SELECT tolagan_summa, tolov_tafsiloti FROM bronlar WHERE mijoz_id=?", (req.mijoz_id,))
    if not es_row:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    eski_tolagan = _f(es_row[0], 0.0)
    eski_kassa = _s(es_row[1], "Naqd")

    y_tomon = XONA_TOMON_MAP.get(req.xona, "Chap tomon")
    y_sigim, baz_narx = XONALAR[y_tomon][req.xona]
    if y_tomon == "O'rtadagi":
        kr_yorliq = "Dvuxspalniy"
    elif req.vikup or req.odam_soni >= y_sigim:
        kr_yorliq = f"Barcha joylar (1-{y_sigim}-joy)"
    else:
        kr_yorliq = ", ".join(req.krovatlar) if req.krovatlar else "1-joy"

    baz_tur = "Dvuxspalniy" if y_tomon == "O'rtadagi" else f"{y_sigim} kishilik"
    y_xona_turi = f"To'liq band ({baz_tur}) [🛏️ {kr_yorliq}]" if (req.vikup or y_tomon == "O'rtadagi") else f"{baz_tur} [🛏️ {kr_yorliq}]"
    sana_toliq = f"{req.kirish_sanasi} ({req.kirish_soati})"

    try:
        k_dt = datetime.strptime(req.kirish_sanasi, "%Y-%m-%d").date()
        soat_h = int(req.kirish_soati.split(":")[0])
        chiq_str = (k_dt + timedelta(days=max(0, req.kunlar - 1) if soat_h < 12 else req.kunlar)).strftime("%Y-%m-%d")
    except Exception:
        chiq_str = bugun_str

    if req.avto_qayta_hisob:
        hisob_odam = y_sigim if req.vikup else req.odam_soni
        if y_tomon == "O'rtadagi":
            kunlik = 300000 if req.toifa == "Chet el fuqarosi" else 250000
        else:
            kunlik = ((baz_narx + 50000) if req.toifa == "Chet el fuqarosi" else (baz_narx * 0.5 if req.toifa == "Talaba (Student)" else baz_narx)) * hisob_odam
        y_faktik = kunlik * req.kunlar
        if req.kunlar >= 7:
            y_faktik = y_faktik * 0.9
    else:
        y_faktik = req.faktik_narx
        kunlik = round(y_faktik / max(1, req.kunlar))

    y_qoldiq = y_faktik - req.tolagan_summa
    y_holat = "To'langan" if y_qoldiq <= 0 else "Qarzdorlik"
    toza_izoh = re.sub(r'\[🛏️ .*?\]', '', req.izoh or '').strip()
    yak_izoh = f"[🛏️ {kr_yorliq}] {toza_izoh}".strip()

    db.execute("""
        UPDATE bronlar SET
            mijoz=?, toifa=?, tomon=?, xona=?, xona_turi=?, odam_soni=?, sana=?, kirish_sanasi=?, chiqish_sanasi=?,
            kunlar=?, muddat=?, kunlik_narx=?, faktik_narx=?, jami_summa=?, tolagan_summa=?, qoldiq=?, holat=?, izoh=?
        WHERE mijoz_id=?
    """, (
        req.mijoz.strip(), req.toifa, y_tomon, req.xona, y_xona_turi, req.odam_soni, sana_toliq, req.kirish_sanasi, chiq_str,
        req.kunlar, f"{req.kunlar} sutka", kunlik, y_faktik, y_faktik, req.tolagan_summa, y_qoldiq, y_holat, yak_izoh, req.mijoz_id
    ))

    farq = req.tolagan_summa - eski_tolagan
    if farq != 0:
        manba = "Vozvrat (Tahrirlash)" if farq < 0 else "Tahrirlash (Kassa tuzatish)"
        db.execute(
            "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
            (bugun_str, req.mijoz_id, req.mijoz.strip(), manba, farq, eski_kassa, eski_kassa, req.xodim)
        )
    jurnalga_yozish(req.mijoz_id, req.xodim, "Mijoz tahrirlandi (Web UI)", f"{req.mijoz}: {req.xona} ({kr_yorliq}), {req.kunlar} sutka, Jami: {y_faktik:,.0f}")
    tg_xabar_yubor("Mijoz tahrirlandi (Web UI)", f"👤 <b>Mijoz:</b> {req.mijoz} ({req.xona} — {kr_yorliq})\n🌙 <b>Sutka:</b> {req.kunlar} sutka | <b>Yangi jami:</b> {y_faktik:,.0f} UZS", req.xodim, muhim=True)
    return {"ok": True}

@app.post("/api/qarz-yopish")
def api_qarz_yopish(req: QarzYopishReq):
    bugun_str = toshkent_vaqti().strftime("%Y-%m-%d")
    r = db.fetchone("SELECT mijoz, xona, tolagan_summa, qoldiq FROM bronlar WHERE mijoz_id=?", (req.mijoz_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    m_ism, m_xona, es_tol, es_qol = r[0], r[1], _f(r[2]), _f(r[3])
    yangi_tol = es_tol + req.summa
    yangi_qol = es_qol - req.summa
    hol = "To'langan" if yangi_qol <= 0 else "Qarzdorlik"
    db.execute("UPDATE bronlar SET tolagan_summa=?, qoldiq=?, holat=? WHERE mijoz_id=?", (yangi_tol, yangi_qol, hol, req.mijoz_id))
    db.execute(
        "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
        (bugun_str, req.mijoz_id, m_ism, "Qarz yopish", req.summa, req.kassa, req.kassa, req.xodim)
    )
    jurnalga_yozish(req.mijoz_id, req.xodim, "Qarz yopish (Web UI)", f"{m_ism} ({m_xona}): +{req.summa:,.0f} UZS ({req.kassa})")
    tg_xabar_yubor("Qarz to'lovi qabul qilindi", f"👤 <b>Mijoz:</b> {m_ism} ({m_xona})\n💵 <b>To'landi:</b> +{req.summa:,.0f} UZS ({req.kassa})\n⚠️ <b>Qolgan qarz:</b> {max(0, yangi_qol):,.0f} UZS", req.xodim)
    return {"ok": True}

@app.post("/api/xona-kochirish")
def api_xona_kochirish(req: XonaKochirishReq):
    r = db.fetchone("SELECT mijoz, xona, odam_soni, izoh FROM bronlar WHERE mijoz_id=?", (req.mijoz_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    m_ism, es_xona, m_odam, es_izoh = r[0], r[1], int(_f(r[2], 1)), _s(r[3])
    y_tomon = XONA_TOMON_MAP.get(req.yangi_xona, "Chap tomon")
    y_sigim = XONALAR[y_tomon][req.yangi_xona][0]
    if y_tomon == "O'rtadagi":
        kr_yorliq = "Dvuxspalniy"
    elif req.vikup or m_odam >= y_sigim:
        kr_yorliq = f"Barcha joylar (1-{y_sigim}-joy)"
    else:
        kr_yorliq = ", ".join(req.yangi_krovatlar) if req.yangi_krovatlar else "1-joy"

    baz_tur = "Dvuxspalniy" if y_tomon == "O'rtadagi" else f"{y_sigim} kishilik"
    y_xona_turi = f"To'liq band ({baz_tur}) [🛏️ {kr_yorliq}]" if (req.vikup or y_tomon == "O'rtadagi") else f"{baz_tur} [🛏️ {kr_yorliq}]"
    toza_izoh = re.sub(r'\[🛏️ .*?\]', '', es_izoh).strip()
    yangi_izoh = f"[🛏️ {kr_yorliq}] {toza_izoh}".strip()

    db.execute("UPDATE bronlar SET tomon=?, xona=?, xona_turi=?, izoh=? WHERE mijoz_id=?", (y_tomon, req.yangi_xona, y_xona_turi, yangi_izoh, req.mijoz_id))
    if es_xona != req.yangi_xona:
        _tozalik_ozgartir_direct(es_xona, "Tozalash kerak")
    jurnalga_yozish(req.mijoz_id, req.xodim, "Xona/Joy ko'chirildi (Web UI)", f"{m_ism}: {es_xona} -> {req.yangi_xona} ({kr_yorliq})")
    tg_xabar_yubor("Xona / Joy almashtirildi", f"👤 <b>Mijoz:</b> {m_ism}\n🔄 <b>Ko'chirildi:</b> {es_xona} ➡️ {req.yangi_xona} (<b>{kr_yorliq}</b>)", req.xodim)
    return {"ok": True}

@app.post("/api/checkout")
def api_checkout(req: CheckoutReq):
    bugun_str = toshkent_vaqti().strftime("%Y-%m-%d")
    row = db.fetchone("SELECT mijoz, xona, tolagan_summa, faktik_narx, qoldiq, odam_soni, kunlar FROM bronlar WHERE mijoz_id=?", (req.mijoz_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    m_ism, m_xona, es_tol, es_fak, es_qol, m_odam, es_kun = row[0], row[1], _f(row[2]), _f(row[3]), _f(row[4]), int(_f(row[5], 1)), int(_f(row[6], 1))

    if es_qol > 0 and req.vozvrat_summa == 0 and not req.majburiy_qarz_bilan:
        raise HTTPException(status_code=400, detail=f"QARZDOR:{int(es_qol)}")

    yak_kun = req.yashagan_kun if req.yashagan_kun is not None else es_kun
    yangi_tol = es_tol - req.vozvrat_summa
    yangi_fak = yangi_tol if (req.vozvrat_summa > 0 or yak_kun != es_kun) else es_fak
    db.execute(
        "UPDATE bronlar SET holat='Chiqib ketgan', kunlar=?, muddat=?, chiqish_sanasi=?, tolagan_summa=?, faktik_narx=?, jami_summa=?, qoldiq=0 WHERE mijoz_id=?",
        (yak_kun, f"{yak_kun} sutka", bugun_str, yangi_tol, yangi_fak, yangi_fak, req.mijoz_id)
    )
    _tozalik_ozgartir_direct(m_xona, "Tozalash kerak")
    if req.vozvrat_summa > 0:
        db.execute(
            "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
            (bugun_str, req.mijoz_id, m_ism, "Vozvrat (Web UI)", -req.vozvrat_summa, req.kassa, req.kassa, req.xodim)
        )
    jurnalga_yozish(req.mijoz_id, req.xodim, "Checkout (Web UI)", f"{m_ism} ({m_xona}, {yak_kun} sutka) chiqarildi. Vozvrat: -{req.vozvrat_summa:,.0f}")
    tg_xabar_yubor("Checkout (Fullstack Web UI)", f"👤 <b>Mijoz:</b> {m_ism} ({m_odam} kishi)\n🛏 <b>Bo'shagan xona:</b> {m_xona} ({yak_kun} sutka)\n⏪ <b>Vozvrat:</b> -{req.vozvrat_summa:,.0f} UZS", req.xodim)
    return {"ok": True}

@app.post("/api/market-savdo")
def api_market_savdo(req: MarketSavdoReq):
    bugun_str = toshkent_vaqti().strftime("%Y-%m-%d")
    m_row = db.fetchone("SELECT nomi, hajmi, tannarx, narxi, qoldiq FROM mahsulotlar WHERE id=?", (req.mahsulot_id,))
    if not m_row:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    nomi, hajmi, tannarx, narxi, qoldiq = m_row[0], _s(m_row[1]), _f(m_row[2]), _f(m_row[3]), int(_f(m_row[4], 0))
    if req.miqdor > qoldiq:
        raise HTTPException(status_code=400, detail=f"Omborda faqat {qoldiq} ta qolgan!")

    jami_sum = narxi * req.miqdor
    sof_foyda = (narxi - tannarx) * req.miqdor
    toliq_nom = f"{nomi} {hajmi}".strip()
    db.execute("UPDATE mahsulotlar SET qoldiq = qoldiq - ? WHERE id=?", (req.miqdor, req.mahsulot_id))

    if req.tolov_turi == "Xona" and req.mijoz_id:
        b_row = db.fetchone("SELECT mijoz, xona FROM bronlar WHERE mijoz_id=?", (req.mijoz_id,))
        if not b_row:
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")
        xaridor_nom = f"{b_row[0]} ({b_row[1]})"
        db.execute(
            "UPDATE bronlar SET faktik_narx = faktik_narx + ?, jami_summa = jami_summa + ?, qoldiq = qoldiq + ?, holat='Qarzdorlik' WHERE mijoz_id=?",
            (jami_sum, jami_sum, jami_sum, req.mijoz_id)
        )
        t_taf = "Xona qarziga"
    else:
        xaridor_nom = "Tashqi mijoz (Darhol)"
        t_taf = req.kassa
        db.execute(
            "INSERT INTO tolovlar_tarixi (sana, mijoz_id, mijoz_ismi, manba, summa, tolov_shakli, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?)",
            (bugun_str, "MARKET", xaridor_nom, "Market Savdo", jami_sum, req.kassa, req.kassa, req.xodim)
        )

    db.execute(
        "INSERT INTO savdolar (sana, mahsulot_id, mahsulot_nomi, mijoz_id, xaridor, miqdor, jami_summa, tannarx_jami, sof_foyda, tolov_turi, tolov_tafsiloti, xodim) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (bugun_str, req.mahsulot_id, toliq_nom, req.mijoz_id or "MARKET", xaridor_nom, req.miqdor, jami_sum, tannarx * req.miqdor, sof_foyda, req.tolov_turi, t_taf, req.xodim)
    )
    jurnalga_yozish("Market (Web UI)", req.xodim, "Savdo qilindi", f"{toliq_nom} x{req.miqdor} = {jami_sum:,.0f} UZS ({t_taf})")
    tg_xabar_yubor("Market Savdo (Web UI)", f"🛒 <b>Mahsulot:</b> {toliq_nom} ({req.miqdor} ta)\n👤 <b>Xaridor:</b> {xaridor_nom}\n💰 <b>Summa:</b> {jami_sum:,.0f} UZS ({t_taf})", req.xodim)
    return {"ok": True}

@app.post("/api/sklad-kirim")
def api_sklad_kirim(req: YangiTovarReq):
    db.execute(
        "INSERT INTO mahsulotlar (nomi, hajmi, kategoriya, sub_kategoriya, tannarx, narxi, qoldiq, izoh) VALUES (?,?,?,?,?,?,?,?)",
        (req.nomi.strip(), req.hajmi.strip(), req.kategoriya, "Standart", req.tannarx, req.narxi, req.qoldiq, "")
    )
    jurnalga_yozish("Sklad (Web UI)", req.xodim, "Yangi tovar", f"{req.nomi} ({req.qoldiq} ta) - Sotuv: {req.narxi:,.0f}")
    return {"ok": True}

@app.post("/api/xarajat")
def api_xarajat(req: XarajatReq):
    uz_now = toshkent_vaqti()
    hozir = uz_now.strftime("%Y-%m-%d %H:%M:%S")
    bugun = uz_now.strftime("%Y-%m-%d")
    db.execute(
        "INSERT INTO xarajatlar (vaqt, sana, kategoriya, summa, tolov_turi, izoh, xodim) VALUES (?,?,?,?,?,?,?)",
        (hozir, bugun, req.kategoriya, req.summa, req.tolov_turi, req.izoh.strip(), req.xodim)
    )
    jurnalga_yozish("Kassa (Web UI)", req.xodim, "Xarajat qilindi", f"{req.kategoriya}: -{req.summa:,.0f} UZS ({req.tolov_turi}) - {req.izoh}")
    tg_xabar_yubor("Xarajat kiritildi (Web UI)", f"📂 <b>Kategoriya:</b> {req.kategoriya}\n➖ <b>Summa:</b> {req.summa:,.0f} UZS ({req.tolov_turi})\n📝 <b>Izoh:</b> {req.izoh}", req.xodim)
    return {"ok": True}

@app.post("/api/smena-yopish")
def api_smena_yopish(req: SmenaYopishReq):
    uz_now = toshkent_vaqti()
    hozir = uz_now.strftime("%Y-%m-%d %H:%M:%S")
    bugun = uz_now.strftime("%Y-%m-%d")
    d = api_dashboard(bugun, bugun)["kpi"]
    naqd_k, karta_k, xar_s, sof_b = d["sof_naqd"], d["sof_karta"], d["xarajat"], d["sof_balans"]
    db.execute(
        "INSERT INTO smenalar (vaqt, xodim, naqd_tushum, karta_tushum, xarajatlar_sum, sof_kassa, izoh) VALUES (?,?,?,?,?,?,?)",
        (hozir, req.xodim, naqd_k, karta_k, xar_s, sof_b, req.izoh or "Web UI Z-Hisobot")
    )
    tg_xabar_yubor("Smena yopildi (Z-Hisobot Web UI)", f"🏦 <b>Sof Naqd:</b> {naqd_k:,.0f} UZS\n💳 <b>Sof Karta:</b> {karta_k:,.0f} UZS\n➖ <b>Xarajat:</b> {xar_s:,.0f} UZS\n💰 <b>Umumiy Sof Balans:</b> {sof_b:,.0f} UZS", req.xodim)
    return {"ok": True}

@app.post("/api/tozalik")
def api_tozalik(req: TozalikReq):
    _tozalik_ozgartir_direct(req.xona, req.holat)
    jurnalga_yozish("Housekeeping", req.xodim, "Xona tozaligi (Web UI)", f"{req.xona} -> {req.holat}")
    return {"ok": True}

@app.post("/api/xodim-qoshish")
def api_xodim_qoshish(req: XodimReq):
    mavjud = db.fetchone("SELECT login FROM xodimlar WHERE login=?", (req.login.strip(),))
    if mavjud:
        raise HTTPException(status_code=400, detail="Bunday login band!")
    db.execute("INSERT INTO xodimlar (login, role, parol, ism) VALUES (?,?,?,?)", (req.login.strip(), req.role, req.parol.strip(), req.ism.strip()))
    jurnalga_yozish("Xodimlar", req.xodim, "Yangi xodim (Web UI)", f"{req.ism} ({req.login}) - {req.role}")
    return {"ok": True}
class SozlamaReq(BaseModel):
    tg_token: str
    ceo_chat_id: str
    owner_chat_id: str
    reglament: str
    xodim: str = "CEO"

@app.post("/api/checkin/{mijoz_id}")
def api_bron_checkin(mijoz_id: str, xodim: str = "Admin"):
    r = db.fetchone("SELECT mijoz, xona, odam_soni FROM bronlar WHERE mijoz_id=?", (mijoz_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Bron topilmadi")
    db.execute("UPDATE bronlar SET bron_turi='Hozir kirish' WHERE mijoz_id=?", (mijoz_id,))
    jurnalga_yozish(mijoz_id, xodim, "Check-in (Web UI)", f"Bron qilingan {r[0]} ({r[1]}) kelib joylashdi")
    tg_xabar_yubor("Bron Check-in (Mehmon keldi)", f"👤 <b>Mijoz:</b> {r[0]} ({r[2]} kishi)\n🛏 <b>Xona:</b> {r[1]}", xodim)
    return {"ok": True}

@app.delete("/api/mijoz/{mijoz_id}")
def api_delete_mijoz(mijoz_id: str, xodim: str = "CEO"):
    r = db.fetchone("SELECT mijoz, xona FROM bronlar WHERE mijoz_id=?", (mijoz_id,))
    if not r:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    db.execute("DELETE FROM bronlar WHERE mijoz_id=?", (mijoz_id,))
    db.execute("DELETE FROM tolovlar_tarixi WHERE mijoz_id=?", (mijoz_id,))
    jurnalga_yozish(mijoz_id, xodim, "O'chirish (Web UI)", f"Mijoz ({r[0]} - {r[1]}) bazadan butunlay o'chirildi")
    tg_xabar_yubor("Mijoz bazadan o'chirildi!", f"🆔 <b>ID:</b> {mijoz_id}\n👤 <b>Mijoz:</b> {r[0]} ({r[1]})", xodim, muhim=True)
    return {"ok": True}

@app.delete("/api/xodim/{login}")
def api_delete_xodim(login: str, xodim: str = "CEO"):
    if login == "ceo":
        raise HTTPException(status_code=400, detail="Asosiy CEO loginini o'chirib bo'lmaydi!")
    db.execute("DELETE FROM xodimlar WHERE login=?", (login,))
    jurnalga_yozish("Xodimlar", xodim, "Xodim o'chirildi (Web UI)", f"Login: {login}")
    return {"ok": True}

@app.post("/api/svodka-yubor")
def api_svodka_yubor(xodim: str = "CEO (Web UI)"):
    d = api_dashboard()
    k = d["kpi"]
    matn = (
        f"📊 <b>24 SOATLIK YIG'MA SVODKA ({d['vaqt']})</b>\n"
        f"🛏 <b>Band xonalar:</b> {k['band_xonalar']} / 36 ta ({k['faol_mehmon']} kishi)\n"
        f"🟢 <b>Bo'sh toza xonalar:</b> {k['bosh_xonalar']} ta | 🧹 <b>Tozalash kk:</b> {k['tozalash_kerak']} ta\n"
        f"📥 <b>Bugungi kirishlar:</b> {k['kirgan_odam']} kishi | 📤 <b>Chiqishlar:</b> {k['chiqqan_odam']} kishi\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Yotoq kirim:</b> {k['yotoq_kirim']:,.0f} UZS\n"
        f"🛒 <b>Market kirim:</b> {k['market_kirim']:,.0f} UZS\n"
        f"➖ <b>Xarajatlar:</b> {k['xarajat']:,.0f} UZS\n"
        f"🏦 <b>Sof Kassa Balans:</b> {k['sof_balans']:,.0f} UZS\n"
        f"⚠️ <b>Joriy qarzlar:</b> {k['umumiy_qarz']:,.0f} UZS"
    )
    ok = tg_xabar_yubor("24 Soatlik Kunlik Svodka", matn, xodim)
    return {"ok": ok}

@app.get("/api/sozlamalar")
def api_get_sozlamalar():
    rows = db.fetchall("SELECT kalit, qiymat FROM tizim_sozlamalari")
    mp = {str(r[0]): str(r[1]) for r in rows} if rows else {}
    return {
        "tg_token": mp.get("tg_token", ""),
        "ceo_chat_id": mp.get("ceo_chat_id", ""),
        "owner_chat_id": mp.get("owner_chat_id", ""),
        "reglament": mp.get("ichki_reglament", "1. Sutka hisobi soat 12:00 gacha.\n2. Xonada chekish va spirtli ichimlik taqiqlanadi.")
    }

@app.post("/api/sozlamalar")
def api_save_sozlamalar(req: SozlamaReq):
    for k, v in [("tg_token", req.tg_token), ("ceo_chat_id", req.ceo_chat_id), ("owner_chat_id", req.owner_chat_id), ("ichki_reglament", req.reglament)]:
        mav = db.fetchone("SELECT kalit FROM tizim_sozlamalari WHERE kalit=?", (k,))
        if mav:
            db.execute("UPDATE tizim_sozlamalari SET qiymat=? WHERE kalit=?", (v.strip(), k))
        else:
            db.execute("INSERT INTO tizim_sozlamalari (kalit, qiymat) VALUES (?,?)", (k, v.strip()))
    jurnalga_yozish("Sozlamalar", req.xodim, "Sozlamalar yangilandi (Web UI)", "Telegram va Reglament saqlandi")
    return {"ok": True}

@app.get("/api/mijoz-tarix/{mijoz_id}")
def api_mijoz_tarix(mijoz_id: str):
    tol_list, sav_list = [], []
    try:
        df_t = db.read_df("SELECT sana, manba, summa, tolov_tafsiloti, xodim FROM tolovlar_tarixi WHERE mijoz_id=? ORDER BY id DESC", (mijoz_id,))
        for _, r in df_t.iterrows():
            tol_list.append({
                "sana": _s(r.get("sana")),
                "manba": _s(r.get("manba")),
                "summa": _f(r.get("summa")),
                "kassa": _s(r.get("tolov_tafsiloti")),
                "xodim": _s(r.get("xodim"))
            })
    except Exception:
        pass

    try:
        df_s = db.read_df("SELECT sana, mahsulot_nomi, miqdor, jami_summa, tolov_tafsiloti, xodim FROM savdolar WHERE mijoz_id=? ORDER BY id DESC", (mijoz_id,))
        for _, r in df_s.iterrows():
            sav_list.append({
                "sana": _s(r.get("sana")),
                "mahsulot": _s(r.get("mahsulot_nomi")),
                "miqdor": int(_f(r.get("miqdor"), 1)),
                "summa": _f(r.get("jami_summa")),
                "holat": _s(r.get("tolov_tafsiloti")),
                "xodim": _s(r.get("xodim"))
            })
    except Exception:
        pass

    return {"tolovlar": tol_list, "savdolar": sav_list}
# ==================== FULLSTACK SPA FRONTEND v4.0 ====================
FRONTEND_HTML = r"""
<!DOCTYPE html>
<html lang="uz" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Y.S.H. ERP | Fullstack SaaS v4.0</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0d14; color: #f8fafc; font-family: 'Inter', system-ui, sans-serif; }
        .pill-active { background: linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%); color: #fff; font-weight: 700; box-shadow: 0 4px 15px rgba(124,58,237,0.4); }
        .glass-card { background: #141724; border: 1px solid #262b40; border-radius: 16px; }
        @media print {
            body * { visibility: hidden; }
            #print-receipt-area, #print-receipt-area * { visibility: visible; }
            #print-receipt-area { position: absolute; left: 0; top: 0; width: 100%; background: #fff !important; color: #000 !important; }
        }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- STARTUP-3 PILL NAVBAR -->
    <nav class="sticky top-0 z-50 bg-[#111420]/95 backdrop-blur border-b border-[#22273b] px-4 py-3">
        <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-3">
                <span class="text-2xl">🏨</span>
                <div>
                    <div class="flex items-center gap-2">
                        <h1 class="font-extrabold text-lg tracking-wide text-white">Y.S.H. ERP</h1>
                        <span id="user-badge" onclick="openLoginModal()" class="cursor-pointer text-xs px-2.5 py-0.5 rounded-full bg-purple-600/30 text-purple-200 border border-purple-500/40 hover:bg-purple-600/50">👑 CEO Rejimi (Almashtirish)</span>
                    </div>
                    <p id="server-time" class="text-xs text-emerald-400 font-semibold">🟢 Jonli aloqa faol</p>
                </div>
            </div>

            <div class="flex flex-wrap items-center gap-1 bg-[#171c2e] p-1.5 rounded-full border border-[#2a324b]">
                <button onclick="switchTab('dash')" id="tab-dash" class="px-3 py-1.5 rounded-full text-xs sm:text-sm transition pill-active">🏠 Boshqaruv</button>
                <button onclick="switchTab('timeline')" id="tab-timeline" class="px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition">📅 Shaxmatka</button>
                <button onclick="switchTab('rooms')" id="tab-rooms" class="px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition">🗺️ 2D Xarita</button>
                <button onclick="switchTab('guests')" id="tab-guests" class="px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition">👥 Mehmonlar</button>
                <button onclick="switchTab('market')" id="tab-market" class="px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition">🛒 POS & Sklad</button>
                <button onclick="switchTab('finance')" id="tab-finance" class="px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition">💸 Xarajat & Smena</button>
                <button onclick="switchTab('ceo')" id="tab-ceo" class="px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition">👑 CEO & TG</button>
            </div>

            <div class="flex items-center gap-2">
                <input type="date" id="f-bosh" onchange="loadData()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-2 py-1.5 text-white">
                <span class="text-slate-500">➔</span>
                <input type="date" id="f-tugash" onchange="loadData()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-2 py-1.5 text-white">
<button onclick="sendSvodka()" title="24 soatlik Svodkani Telegramga yuborish" class="bg-slate-800 hover:bg-slate-700 text-purple-300 border border-purple-500/40 font-bold text-xs px-3 py-2 rounded-full">📲 Svodka</button>
<button onclick="downloadExcel()" title="Excel Hisobot yuklab olish" class="bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/40 font-bold text-xs px-3 py-2 rounded-full">📥 Excel</button>                <button onclick="openModal()" class="bg-gradient-to-r from-emerald-500 to-teal-500 hover:opacity-95 text-white font-bold text-xs sm:text-sm px-4 py-2 rounded-full shadow-lg">+ Yangi Qabul</button>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl w-full mx-auto p-4 flex-1 space-y-6">
        <div id="err-box" class="hidden p-4 rounded-xl bg-red-900/40 border border-red-500 text-red-200 text-sm"></div>

        <!-- TAB 1: DASHBOARD -->
        <section id="sec-dash" class="space-y-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4" id="kpi-grid"></div>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4" id="finance-grid"></div>

            <!-- 7 KUNLIK BANDLIK PROGNOZI (MOBILDA HAM 1 QATORDA!) -->
            <div class="glass-card p-5">
                <h3 class="font-bold text-sm mb-3 text-slate-300">📊 Yaqin 7 kunlik bandlik prognozi</h3>
                <div id="forecast-7-grid" class="grid grid-cols-7 gap-2 pt-2"></div>
            </div>

            <div class="glass-card p-5">
                <h3 class="font-bold text-base mb-3 text-purple-300">🛎️ Faol Mehmonlar Boshqaruvi (Chek, Tahrirlash, Qarz yopish, 2D Ko'chirish va Avto-Vozvrat Checkout)</h3>
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
                                <th class="py-3 px-2 text-right">Tezkor Amallar</th>
                            </tr>
                        </thead>
                        <tbody id="active-table-body" class="divide-y divide-slate-800/70"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 2: TIMELINE & SHAXMATKA (10 KUNLIK KALENDAR MATRITSA) -->
        <section id="sec-timeline" class="hidden space-y-4">
            <div class="glass-card p-5">
                <h2 class="text-lg font-bold mb-1">📅 10 Kunlik Xonalar Shaxmatkasi (Timeline Matrix)</h2>
                <p class="text-xs text-slate-400 mb-4">Katakcha ustiga sichqonchani olib borsangiz o'sha kunda xonada kimlar yashayotgani ko'rinadi</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-center text-xs border-collapse" id="timeline-table"></table>
                </div>
            </div>
        </section>

        <!-- TAB 3: 2D KROVATLAR XARITASI -->
        <section id="sec-rooms" class="hidden space-y-4">
            <div class="flex flex-wrap justify-between items-center gap-2">
                <h2 class="text-xl font-bold">🛏️ 36 ta Xona va 2D Krovatlar Jonli Matritsasi (1 ➔ 2 | 3 ➔ 4)</h2>
                <div class="flex gap-2">
                    <button onclick="filterWing('ALL')" class="px-3 py-1 rounded-lg bg-slate-800 hover:bg-purple-600 text-xs font-semibold">Barchasi (36)</button>
                    <button onclick="filterWing('Chap tomon')" class="px-3 py-1 rounded-lg bg-slate-800 hover:bg-purple-600 text-xs font-semibold">Chap qanot (1-14)</button>
                    <button onclick="filterWing('ORTA')" class="px-3 py-1 rounded-lg bg-slate-800 hover:bg-purple-600 text-xs font-semibold">O'rta Lyuks (15-21)</button>
                    <button onclick="filterWing('ONG')" class="px-3 py-1 rounded-lg bg-slate-800 hover:bg-purple-600 text-xs font-semibold">O'ng qanot (22-36)</button>
                </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" id="rooms-2d-grid"></div>
        </section>

        <!-- TAB 4: BARCHA MEHMONLAR VA ARXIV -->
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
                                <th class="py-2 px-2 text-right">Chek / Tahrir</th>
                            </tr>
                        </thead>
                        <tbody id="all-guests-body" class="divide-y divide-slate-800/60"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 5: POS MARKET & SKLAD -->
        <section id="sec-market" class="hidden space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="glass-card p-5 space-y-4">
                    <h3 class="text-lg font-bold text-emerald-400">🛒 Kassa (POS Market Savdo)</h3>
                    <div class="grid grid-cols-2 gap-3">
                        <div class="col-span-2">
                            <label class="text-xs text-slate-300">📦 Mahsulotni tanlang</label>
                            <select id="pos-mahs" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"></select>
                        </div>
                        <div>
                            <label class="text-xs text-slate-300">🔢 Soni</label>
                            <input id="pos-soni" type="number" value="1" min="1" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <div>
                            <label class="text-xs text-slate-300">💳 To'lov usuli</label>
                            <select id="pos-tur" onchange="togglePosGuest()" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                                <option value="Darhol">💵 Darhol to'lov (Kassaga)</option>
                                <option value="Xona">🛏️ Mehmon xona qarziga</option>
                            </select>
                        </div>
                        <div id="pos-kassa-wrap" class="col-span-2">
                            <label class="text-xs text-slate-300">🏦 Qaysi kassaga?</label>
                            <select id="pos-kassa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                                <option>Naqd</option><option>Click</option><option>Uzcard</option><option>Humo</option><option>Terminal</option>
                            </select>
                        </div>
                        <div id="pos-mijoz-wrap" class="col-span-2 hidden">
                            <label class="text-xs text-slate-300">👤 Qaysi mehmonga yozamiz?</label>
                            <select id="pos-mijoz" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"></select>
                        </div>
                    </div>
                    <button onclick="submitMarketSavdo()" class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-bold text-sm">✅ Savdoni Tasdiqlash</button>
                </div>

                <div class="glass-card p-5 space-y-4">
                    <h3 class="text-lg font-bold text-purple-300">➕ Skladga Yangi Tovar Kirim Qilish</h3>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="text-xs text-slate-300">Nomi *</label>
                            <input id="sk-nom" type="text" placeholder="Coca-Cola" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <div>
                            <label class="text-xs text-slate-300">Hajmi</label>
                            <input id="sk-hajm" type="text" placeholder="1.5 L" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <div>
                            <label class="text-xs text-slate-300">Tannarxi (Xarid UZS)</label>
                            <input id="sk-tan" type="number" value="10000" step="1000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <div>
                            <label class="text-xs text-slate-300">Sotuv Narxi (UZS)</label>
                            <input id="sk-narx" type="number" value="15000" step="1000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <div class="col-span-2">
                            <label class="text-xs text-slate-300">Boshlang'ich Qoldiq Soni</label>
                            <input id="sk-qol" type="number" value="10" min="1" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                    </div>
                    <button onclick="submitSkladKirim()" class="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 font-bold text-sm">📦 Omborga Qo'shish</button>
                </div>
            </div>

            <div class="glass-card p-5">
                <h3 class="font-bold text-base mb-3">📦 Ombordagi Mahsulotlar Qoldig'i</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                            <tr><th class="py-2 px-2">Nomi</th><th class="py-2 px-2">Hajmi</th><th class="py-2 px-2">Tannarxi</th><th class="py-2 px-2">Sotuv Narxi</th><th class="py-2 px-2">Qoldiq</th></tr>
                        </thead>
                        <tbody id="sklad-table-body" class="divide-y divide-slate-800/60"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 6: XARAJATLAR & Z-SMENA -->
        <section id="sec-finance" class="hidden space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="glass-card p-5 space-y-4">
                    <h3 class="text-lg font-bold text-rose-400">➖ Yangi Xarajat Kiritish</h3>
                    <div class="space-y-3">
                        <div>
                            <label class="text-xs text-slate-300">Kategoriya</label>
                            <select id="xar-kat" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                                <option>Xo'jalik va Tozalik vositalari</option>
                                <option>Kommunal to'lovlar</option>
                                <option>Oziq-ovqat (Non, choy...)</option>
                                <option>Ta'mirlash (Santexnik, usta...)</option>
                                <option>Xodimlar avansi / maoshi</option>
                                <option>Boshqa xarajat</option>
                            </select>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="text-xs text-slate-300">Summa (UZS)</label>
                                <input id="xar-sum" type="number" value="20000" step="5000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                            </div>
                            <div>
                                <label class="text-xs text-slate-300">Qaysi kassadan?</label>
                                <select id="xar-kassa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                                    <option>Naqd</option><option>Click</option><option>Uzcard</option><option>Humo</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="text-xs text-slate-300">Batafsil izoh *</label>
                            <input id="xar-izoh" type="text" placeholder="Nima olindi yoki kimga berildi?" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        </div>
                        <button onclick="submitXarajat()" class="w-full py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 font-bold text-sm">➖ Xarajatni Tasdiqlash</button>
                    </div>
                </div>

                <div class="glass-card p-5 space-y-4">
                    <h3 class="text-lg font-bold text-cyan-400">🔄 Smenani Yopish (Z-Hisobot)</h3>
                    <div id="z-report-box" class="grid grid-cols-2 gap-3"></div>
                    <input id="z-izoh" type="text" placeholder="Smena bo'yicha izoh..." class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                    <button onclick="submitSmena()" class="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 font-bold text-sm">✅ Smenani Yopish va Telegramga Yuborish</button>
                </div>
            </div>

            <div class="glass-card p-5">
                <h3 class="font-bold text-base mb-3">💸 So'nggi Xarajatlar Tarixi</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                            <tr><th class="py-2 px-2">Vaqt</th><th class="py-2 px-2">Kategoriya</th><th class="py-2 px-2">Summa</th><th class="py-2 px-2">Kassa</th><th class="py-2 px-2">Izoh</th></tr>
                        </thead>
                        <tbody id="xar-table-body" class="divide-y divide-slate-800/60"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 7: CEO BOSHQARUVI, SOZLAMALAR, XODIMLAR, AUDIT VA TELEGRAM NAZORATI -->
        <section id="sec-ceo" class="hidden space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- 1. XODIMLAR -->
                <div class="glass-card p-5 space-y-4">
                    <h3 class="text-base font-bold text-purple-300">👥 Xodimlar va Rollar</h3>
                    <div class="grid grid-cols-2 gap-2">
                        <input id="u-ism" type="text" placeholder="Xodim F.I.O" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                        <input id="u-login" type="text" placeholder="Login" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                        <input id="u-parol" type="text" placeholder="Parol" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                        <select id="u-role" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white">
                            <option value="admin">Admin</option><option value="housekeeping">Tozalik</option><option value="ceo">CEO</option>
                        </select>
                    </div>
                    <button onclick="submitNewUser()" class="w-full py-2 rounded-xl bg-purple-600 hover:bg-purple-500 font-bold text-xs">➕ Xodim Qo'shish</button>
                    <div id="users-list-box" class="space-y-1.5 pt-2 max-h-48 overflow-y-auto"></div>
                </div>

                <!-- 2. TELEGRAM VA REGLAMENT SOZLAMALARI -->
                <div class="glass-card p-5 space-y-3">
                    <h3 class="text-base font-bold text-cyan-400">⚙️ Telegram Bot & Reglament</h3>
                    <div class="space-y-2 text-xs">
                        <div>
                            <label class="text-slate-400">🤖 Bot Token:</label>
                            <input id="set-token" type="text" class="w-full mt-0.5 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white">
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="text-slate-400">👑 CEO Chat ID:</label>
                                <input id="set-ceoid" type="text" class="w-full mt-0.5 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white">
                            </div>
                            <div>
                                <label class="text-slate-400">🏛️ Owner Chat ID:</label>
                                <input id="set-ownerid" type="text" class="w-full mt-0.5 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white">
                            </div>
                        </div>
                        <div>
                            <label class="text-slate-400">📜 Ichki Reglament:</label>
                            <textarea id="set-reglament" rows="3" class="w-full mt-0.5 bg-slate-900 border border-slate-700 rounded-lg p-2 text-white"></textarea>
                        </div>
                        <button onclick="saveSettings()" class="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 font-bold text-xs">💾 Sozlamalarni Saqlash</button>
                    </div>
                </div>

                <!-- 3. AUDIT LOG -->
                <div class="glass-card p-5 space-y-3">
                    <h3 class="text-base font-bold text-amber-400">🕵️ Tizim Xavfsizlik Auditi</h3>
                    <div id="audit-list-box" class="space-y-2 max-h-72 overflow-y-auto pr-1"></div>
                </div>
            </div>

            <div class="glass-card p-5">
                <h2 class="text-lg font-bold mb-1">📲 Telegramga Yuborilgan Xabarlar Jurnali (CEO & Owner)</h2>
                <p class="text-xs text-slate-400 mb-4">Tizim tomonidan yuborilgan har bir bildirishnoma va uning yetkazilganlik statusi</p>
                <div id="tg-log-list" class="space-y-3"></div>
            </div>
        </section>
    </main>

    <!-- MODAL 1: YANGI QABUL (SANA, SOAT, CHEGIRMA VA 2D JOY TANLASH BILAN) -->
    <div id="qabul-modal" class="fixed inset-0 bg-black/75 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="glass-card max-w-2xl w-full p-6 space-y-4 border border-purple-500/40 max-h-[92vh] overflow-y-auto">
            <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                <h3 class="text-lg font-bold text-white">➕ Yangi Mehmon Qabul Qilish (2D Joy va Aniq Vaqt bilan)</h3>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div class="md:col-span-2">
                    <label class="text-xs text-slate-300">👤 Mehmon F.I.O *</label>
                    <input id="m-ism" type="text" placeholder="Alisher Karimov" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">📞 Telefon raqami</label>
                    <input id="m-tel" type="text" placeholder="+998 90 123 45 67" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🚻 Jinsi</label>
                    <select id="m-jins" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option value="Erkak">👨 Erkak</option><option value="Ayol">👩 Ayol</option>
                    </select>
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
                    <label class="text-xs text-slate-300">📌 Qabul turi</label>
                    <select id="m-bronturi" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option value="Hozir kirish">🟢 Hozir kirish (Check-in)</option>
                        <option value="Bron">🟠 Oldindan Bron</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="text-xs text-slate-300">🛏️ Xonani tanlang</label>
                    <select id="m-xona" onchange="updateModalRoomBeds()" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"></select>
                </div>
                <div>
                    <label class="text-xs text-slate-300">👥 Odam soni</label>
                    <input id="m-odam" type="number" value="1" min="1" max="4" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">📅 Kirish sanasi</label>
                    <input id="m-ksana" type="date" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🕒 Kirish soati (masalan 15:05)</label>
                    <input id="m-ksoat" type="time" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🌙 Sutka soni</label>
                    <input id="m-kun" type="number" value="1" min="1" max="365" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">🏷️ Chegirma % (0-100)</label>
                    <input id="m-cheg" type="number" value="0" min="0" max="100" step="5" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
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

    <!-- MODAL 2: MEHMON TEZKOR AMALLARI (TAHRIRLASH, CHEK/KVITANSIYA, VOZVRAT CHECKOUT, QARZ, KO'CHIRISH) -->
    <div id="action-modal" class="fixed inset-0 bg-black/75 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="glass-card max-w-2xl w-full p-6 space-y-4 border border-cyan-500/40 max-h-[92vh] overflow-y-auto">
            <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                <h3 id="act-title" class="text-lg font-bold text-white">🛠️ Mehmon Amallari</h3>
                <button onclick="closeActionModal()" class="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>
            <div id="act-body" class="space-y-4"></div>
        </div>
    </div>

    <!-- MODAL 3: LOGIN / ROL ALMASHTIRISH -->
    <div id="login-modal" class="fixed inset-0 bg-black/75 backdrop-blur-sm hidden z-50 flex items-center justify-center p-4">
        <div class="glass-card max-w-sm w-full p-6 space-y-4 border border-purple-500/40">
            <h3 class="text-lg font-bold text-white">🔐 Xodim Avtorizatsiyasi</h3>
            <input id="l-user" type="text" placeholder="Login (masalan: ceo yoki admin)" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
            <input id="l-pass" type="password" placeholder="Parol" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
            <div class="flex justify-end gap-2">
                <button onclick="document.getElementById('login-modal').classList.add('hidden')" class="px-4 py-2 rounded-lg bg-slate-800 text-xs">Yopish</button>
                <button onclick="doLogin()" class="px-5 py-2 rounded-lg bg-purple-600 font-bold text-xs">Kirish</button>
            </div>
        </div>
    </div>

<script>
let STATE = __INITIAL_STATE_JSON__;
STATE.wingFilter = 'ALL';
STATE.selectedBeds = [];
STATE.moveSelectedBeds = [];
STATE.editSelectedBeds = [];
STATE.currentUser = { role: 'ceo', ism: 'Botir Hakimov (CEO)', login: 'ceo' };

function applyState(data) {
    STATE = { ...STATE, ...data };
    document.getElementById('err-box').classList.add('hidden');
    document.getElementById('server-time').innerText = `🟢 Jonli aloqa | Toshkent: ${STATE.vaqt}`;
    renderDashboard();
    renderTimeline();
    renderRooms2D();
    renderGuests();
    renderMarketAndFinance();
    renderCeoAndTg();
}

async function loadData() {
    try {
        const b = document.getElementById('f-bosh').value;
        const t = document.getElementById('f-tugash').value;
        const q = (b && t) ? `?bosh_sana=${b}&tugash_sana=${t}` : '';
        const res = await fetch('/api/dashboard' + q);
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        applyState(data);
    } catch (e) {
        const eb = document.getElementById('err-box');
        eb.innerText = "Xatolik: " + e.message;
        eb.classList.remove('hidden');
    }
}

function downloadExcel() {
    const b = document.getElementById('f-bosh').value;
    const t = document.getElementById('f-tugash').value;
    const q = (b && t) ? `?bosh_sana=${b}&tugash_sana=${t}` : '';
    window.location.href = '/api/excel-export' + q;
}

function switchTab(tab) {
    ['dash', 'timeline', 'rooms', 'guests', 'market', 'finance', 'ceo'].forEach(t => {
        document.getElementById('sec-' + t).classList.toggle('hidden', t !== tab);
        const btn = document.getElementById('tab-' + t);
        if (t === tab) btn.className = "px-3 py-1.5 rounded-full text-xs sm:text-sm transition pill-active";
        else btn.className = "px-3 py-1.5 rounded-full text-xs sm:text-sm text-slate-300 hover:text-white transition";
    });
}

function openLoginModal() { document.getElementById('login-modal').classList.remove('hidden'); }
async function doLogin() {
    const login = document.getElementById('l-user').value;
    const parol = document.getElementById('l-pass').value;
    const res = await fetch('/api/login', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({login, parol}) });
    if (res.ok) {
        STATE.currentUser = await res.json();
        document.getElementById('user-badge').innerText = `👤 ${STATE.currentUser.ism} (${STATE.currentUser.role.toUpperCase()})`;
        document.getElementById('login-modal').classList.add('hidden');
    } else alert("Login yoki parol xato!");
}

function applyRolePermissions() {
    const r = STATE.currentUser.role;
    // Tozalik xodimi uchun faqat 2D Xarita ko'rinadi
    document.getElementById('tab-dash').classList.toggle('hidden', r === 'housekeeping');
    document.getElementById('tab-timeline').classList.toggle('hidden', r === 'housekeeping');
    document.getElementById('tab-guests').classList.toggle('hidden', r === 'housekeeping');
    document.getElementById('tab-market').classList.toggle('hidden', r === 'housekeeping');
    document.getElementById('tab-finance').classList.toggle('hidden', r === 'housekeeping');
    document.getElementById('tab-ceo').classList.toggle('hidden', r !== 'ceo');
    if (r === 'housekeeping') switchTab('rooms');
}

async function sendSvodka() {
    const res = await fetch('/api/svodka-yubor?xodim=' + encodeURIComponent(STATE.currentUser.ism), { method: 'POST' });
    if (res.ok) alert("✅ 24 soatlik Svodka Telegramga muvaffaqiyatli yuborildi!");
}

async function checkInGuest(id) {
    const res = await fetch(`/api/checkin/${id}?xodim=` + encodeURIComponent(STATE.currentUser.ism), { method: 'POST' });
    if (res.ok) loadData();
}

async function deleteGuest(id, ism) {
    if (STATE.currentUser.role !== 'ceo') { alert("⚠️ Faqat CEO mijozni bazadan butunlay o'chira oladi!"); return; }
    if (!confirm(`🚨 DIQQAT: ${ism} (${id}) va uning to'lov tarixini bazadan BUTUNLAY o'chirib tashlashni tasdiqlaysizmi?`)) return;
    const res = await fetch(`/api/mijoz/${id}?xodim=` + encodeURIComponent(STATE.currentUser.ism), { method: 'DELETE' });
    if (res.ok) loadData();
}

async function deleteUser(login) {
    if (STATE.currentUser.role !== 'ceo') return;
    if (!confirm(`${login} xodimini o'chirasizmi?`)) return;
    const res = await fetch(`/api/xodim/${login}?xodim=` + encodeURIComponent(STATE.currentUser.ism), { method: 'DELETE' });
    if (res.ok) loadData();
}

async function submitExtend(id) {
    const qoshimcha_kun = parseInt(document.getElementById('act-ext-kun').value || 1);
    const qoshimcha_summa = parseFloat(document.getElementById('act-ext-sum').value || 0);
    const tolangan_summa = parseFloat(document.getElementById('act-ext-tol').value || 0);
    const kassa = document.getElementById('act-ext-kassa').value;
    const res = await fetch('/api/muddat-chozish', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ mijoz_id: id, qoshimcha_kun, qoshimcha_summa, tolangan_summa, kassa, xodim: STATE.currentUser.ism })
    });
    if (res.ok) { closeActionModal(); loadData(); }
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

    document.getElementById('forecast-7-grid').innerHTML = (STATE.prognoz_7_kun || []).map((d, idx) => `
        <div class="text-center">
            <div class="text-[11px] font-bold text-purple-300 mb-1">${d.foiz}% (${d.odam}k)</div>
            <div class="h-24 w-7 sm:w-9 mx-auto rounded-lg bg-purple-950/50 border border-purple-800/40 flex items-end overflow-hidden">
                <div style="height:${Math.max(8, d.foiz)}%" class="w-full ${idx === 0 ? 'bg-gradient-to-t from-purple-600 to-cyan-400' : 'bg-indigo-500'} rounded-t"></div>
            </div>
            <div class="text-xs font-semibold mt-1.5">${d.kun}<br><span class="text-[10px] text-slate-400">${d.sana}</span></div>
        </div>
    `).join('');

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
            <td class="py-2.5 px-2 text-right space-x-1 whitespace-nowrap">
                ${m.bron_turi === 'Bron' ? `<button onclick="checkInGuest('${m.mijoz_id}')" title="Check-in (Keldi)" class="px-2 py-1 rounded-lg bg-amber-500 text-black font-bold text-xs">🔑</button>` : ''}
                <button onclick="openActionModal('${m.mijoz_id}', 'receipt')" title="Kvitansiya / Chek chop etish" class="px-2 py-1 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-xs">🖨️</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'edit')" title="To'liq Tahrirlash (2D Joy va Vaqt)" class="px-2 py-1 rounded-lg bg-amber-600/80 hover:bg-amber-600 text-white text-xs">✏️</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'pay')" title="Qarz yopish" class="px-2 py-1 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 text-white text-xs">💳</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'extend')" title="Muddatni cho'zish (+Kun)" class="px-2 py-1 rounded-lg bg-teal-600/80 hover:bg-teal-600 text-white text-xs">➕</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'move')" title="2D Xona / Krovat ko'chirish" class="px-2 py-1 rounded-lg bg-indigo-600/80 hover:bg-indigo-600 text-white text-xs">🛏️</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'checkout')" title="Avto-Vozvrat va Checkout" class="px-2.5 py-1 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white text-xs font-semibold">🚪</button>
            </td>
        </tr>
    `).join('') || '<tr><td colspan="8" class="text-center py-6 text-slate-400">Hozircha faol mehmonlar yo\'q</td></tr>';
}

function renderTimeline() {
    const sanalar = STATE.timeline_sanalar || [];
    let html = `<thead><tr class="border-b border-slate-800 text-slate-300"><th class="p-2 text-left">Xona (Sig'im)</th>`;
    sanalar.forEach(s => { html += `<th class="p-2 border-l border-slate-800">${s.label}</th>`; });
    html += `</tr></thead><tbody class="divide-y divide-slate-800/60">`;
    (STATE.xonalar || []).forEach(r => {
        html += `<tr class="hover:bg-slate-800/30"><td class="p-2 text-left font-bold whitespace-nowrap">🛏️ ${r.xona} <span class="text-slate-400 font-normal">(${r.sigim}k)</span></td>`;
        sanalar.forEach(s => {
            const cell = (r.timeline && r.timeline[s.sana]) || {band: 0, bosh: r.sigim, mijozlar: ''};
            const bg = cell.bosh === 0 ? 'bg-purple-600/40 text-purple-200 border-purple-500' : (cell.band > 0 ? 'bg-amber-500/30 text-amber-200 border-amber-500' : 'bg-emerald-950/30 text-emerald-400');
            html += `<td title="${cell.mijozlar || 'Bo\'sh'}" class="p-1.5 border-l border-slate-800 ${bg} font-semibold cursor-help">${cell.bosh === 0 ? '🔒 Band' : `🟢 ${cell.bosh} bo'sh`}</td>`;
        });
        html += `</tr>`;
    });
    html += `</tbody>`;
    document.getElementById('timeline-table').innerHTML = html;
}

function openActionModal(id, mode) {
    const m = STATE.barcha_mehmonlar.find(x => x.mijoz_id === id);
    if (!m) return;
    const modal = document.getElementById('action-modal');
    const title = document.getElementById('act-title');
    const body = document.getElementById('act-body');
    modal.classList.remove('hidden');

    if (mode === 'receipt') {
        title.innerText = `🖨️ Ichki Kvitansiya / Chek — ${m.mijoz}`;
        body.innerHTML = `
            <div id="print-receipt-area" class="bg-white text-slate-900 p-6 rounded-xl border-2 border-dashed border-slate-400 font-mono text-xs space-y-2">
                <div class="text-center font-extrabold text-base">🏨 YANGI SERGELI HOSTEL (Y.S.H.)</div>
                <div class="text-center text-slate-600">Ichki Hisob-kitob Cheki № ${m.mijoz_id}</div>
                <hr class="border-slate-300">
                <div><b>Mehmon:</b> ${m.mijoz} (${m.odam_soni} kishi | ${m.toifa})</div>
                <div><b>Telefon:</b> ${m.telefon || '—'}</div>
                <div><b>Joylashgan xona va joy:</b> ${m.xona} — ${m.joy || 'Standart'}</div>
                <div><b>Kirish vaqti:</b> ${m.kirish_vaqti}</div>
                <div><b>Chiqish vaqti:</b> ${m.chiqish_sanasi} (soat 12:00)</div>
                <div><b>Yashash muddati:</b> ${m.kunlar} sutka</div>
                <hr class="border-slate-300">
                <div class="text-sm"><b>Jami hisoblangan summa:</b> ${m.faktik_narx.toLocaleString()} UZS</div>
                <div class="text-sm"><b>To'langan summa:</b> ${m.tolagan_summa.toLocaleString()} UZS (${m.tolov_tafsiloti})</div>
                <div class="text-sm"><b>Qoldiq qarz:</b> ${Math.max(0, m.qoldiq).toLocaleString()} UZS</div>
                <hr class="border-slate-300">
                <div class="text-[11px] text-slate-500">Mas'ul: ${STATE.currentUser.ism} | Vaqt: ${STATE.vaqt}</div>
            </div>
            <button onclick="window.print()" class="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 font-bold text-sm">🖨️ Printerda Chop Etish (Print)</button>
        `;
    } else if (mode === 'edit') {
        title.innerText = `✏️ Mehmon Ma'lumotlarini To'liq Tahrirlash — ${m.mijoz}`;
        const roomOpts = STATE.xonalar.map(r => `<option value="${r.xona}" ${r.xona === m.xona ? 'selected' : ''}>${r.xona} (${r.tomon} — ${r.sigim} kishilik)</option>`).join('');
        body.innerHTML = `
            <div class="grid grid-cols-2 gap-3 text-xs">
                <div>
                    <label class="text-slate-300">Mehmon F.I.O</label>
                    <input id="ed-ism" type="text" value="${m.mijoz}" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">Toifa</label>
                    <select id="ed-toifa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                        <option value="O'zbekiston fuqarosi" ${m.toifa.includes("O'zbek") ? 'selected':''}>O'zbekiston fuqarosi</option>
                        <option value="Chet el fuqarosi" ${m.toifa.includes("Chet") ? 'selected':''}>Chet el fuqarosi</option>
                        <option value="Talaba (Student)" ${m.toifa.includes("Talaba") ? 'selected':''}>Talaba (Student)</option>
                    </select>
                </div>
                <div>
                    <label class="text-slate-300">Xona (o'zgarsa 2D sxema yangilanadi)</label>
                    <select id="ed-xona" onchange="renderEditBeds('${m.mijoz_id}')" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">${roomOpts}</select>
                </div>
                <div>
                    <label class="text-slate-300">Mehmonlar soni</label>
                    <input id="ed-odam" type="number" value="${m.odam_soni}" min="1" max="6" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">Kirish sanasi</label>
                    <input id="ed-ksana" type="date" value="${m.kirish_sanasi}" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">Kirish soati</label>
                    <input id="ed-ksoat" type="time" value="${m.kirish_soati}" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">Yashash sutkasi</label>
                    <input id="ed-kun" type="number" value="${m.kunlar}" min="1" max="365" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">Jami hisoblangan summa (UZS)</label>
                    <input id="ed-faktik" type="number" value="${m.faktik_narx}" step="10000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">To'lagan summasi (Kassa UZS)</label>
                    <input id="ed-tolagan" type="number" value="${m.tolagan_summa}" step="10000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">Izoh</label>
                    <input id="ed-izoh" type="text" value="${m.izoh}" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
            </div>
            <label class="flex items-center gap-2 text-xs text-amber-300 cursor-pointer">
                <input id="ed-recalc" type="checkbox" class="rounded"> 🔄 Standart tarif bo'yicha Jami summani avtomatik qayta hisoblash
            </label>
            <div>
                <label class="text-xs text-purple-300 font-semibold">🛏️ 2D Yotoq o'rnini (Krovatni) tanlang:</label>
                <div id="ed-beds-grid" class="grid grid-cols-2 gap-2 mt-2"></div>
            </div>
            <button onclick="submitEditGuest('${m.mijoz_id}')" class="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 font-bold text-sm">💾 O'zgarishlarni Saqlash</button>
        `;
        renderEditBeds(m.mijoz_id);
    } else if (mode === 'pay') {
        title.innerText = `💳 To'lov / Qarz yopish — ${m.mijoz} (${m.xona})`;
        body.innerHTML = `
            <div class="p-3 rounded-xl bg-slate-900 text-xs space-y-1">
                <div>Jami hisob: <b>${m.faktik_narx.toLocaleString()} UZS</b> | To'lagan: <b>${m.tolagan_summa.toLocaleString()} UZS</b></div>
                <div class="text-red-400 font-bold">Joriy qoldiq qarz: ${Math.max(0, m.qoldiq).toLocaleString()} UZS</div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-slate-300">Qabul qilingan summa (UZS)</label>
                    <input id="act-pay-sum" type="number" value="${Math.max(50000, m.qoldiq)}" step="10000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">Kassa</label>
                    <select id="act-pay-kassa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                        <option>Naqd</option><option>Click</option><option>Uzcard</option><option>Humo</option><option>Terminal</option>
                    </select>
                </div>
            </div>
            <button onclick="submitPay('${m.mijoz_id}')" class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-bold text-sm">✅ To'lovni Tasdiqlash</button>
        `;
    } else if (mode === 'move') {
        title.innerText = `🛏️ 2D Xona va Krovatni O'zgartirish — ${m.mijoz}`;
        const roomOpts = STATE.xonalar.map(r => `<option value="${r.xona}" ${r.xona === m.xona ? 'selected' : ''}>${r.xona} (${r.tomon} — Bo'sh: ${r.bosh_joy}/${r.sigim})</option>`).join('');
        body.innerHTML = `
            <div>
                <label class="text-xs text-slate-300">Yangi xonani tanlang:</label>
                <select id="act-move-xona" onchange="renderMoveBeds('${m.mijoz_id}')" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">${roomOpts}</select>
            </div>
            <div>
                <label class="text-xs text-purple-300 font-semibold">Yangi yotoq o'rnini (Krovatni) tanlang:</label>
                <div id="act-move-beds" class="grid grid-cols-2 gap-2 mt-2"></div>
            </div>
            <button onclick="submitMove('${m.mijoz_id}')" class="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 font-bold text-sm">🔄 Ko'chirishni Saqlash</button>
        `;
        renderMoveBeds(m.mijoz_id);
    } else if (mode === 'checkout') {
        title.innerText = `🚪 Checkout va Avto-Vozvrat Kalkulyatori — ${m.mijoz}`;
        const kunlikSt = Math.round(m.kunlik_narx || (m.faktik_narx / Math.max(1, m.kunlar)));
        body.innerHTML = `
            <div class="p-3 rounded-xl bg-slate-900 text-xs space-y-1">
                <div>Bron qilingan: <b>${m.kunlar} sutka</b> | 1 sutka stavkasi: <b>${kunlikSt.toLocaleString()} UZS</b></div>
                <div>To'lagan: <b class="text-emerald-400">${m.tolagan_summa.toLocaleString()} UZS</b> | Qarz: <b class="text-red-400">${Math.max(0, m.qoldiq).toLocaleString()} UZS</b></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="text-xs text-slate-300">🌙 Haqiqiy yashagan sutkasi:</label>
                    <input id="act-ch-kun" type="number" value="${m.kunlar}" min="0" max="${m.kunlar}" oninput="calcAutoVozvrat(${m.tolagan_summa}, ${kunlikSt})" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
                <div>
                    <label class="text-xs text-slate-300">⏪ Qaytariladigan Vozvrat (UZS):</label>
                    <input id="act-ch-vozv" type="number" value="0" step="5000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white">
                </div>
            </div>
            <div id="vozv-info" class="text-xs text-emerald-400 font-semibold"></div>
            <button onclick="submitCheckoutModal('${m.mijoz_id}', ${m.qoldiq})" class="w-full py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 font-bold text-sm">🚪 Xonani Bo'shatish (Checkout)</button>
        `;
    } else if (mode === 'extend') {
        const kunlikSt = Math.round(m.kunlik_narx || (m.faktik_narx / Math.max(1, m.kunlar)));
        title.innerText = `➕ Yashash Muddatini Cho'zish — ${m.mijoz} (${m.xona})`;
        body.innerHTML = `
            <div class="p-3 rounded-xl bg-slate-900 text-xs">Joriy muddat: <b>${m.kunlar} sutka</b> (Chiqish: ${m.chiqish_sanasi}) | 1 sutka stavkasi: <b>${kunlikSt.toLocaleString()} UZS</b></div>
            <div class="grid grid-cols-2 gap-3 text-xs">
                <div>
                    <label class="text-slate-300">➕ Necha sutka qo'shiladi?</label>
                    <input id="act-ext-kun" type="number" value="1" min="1" oninput="document.getElementById('act-ext-sum').value = this.value * ${kunlikSt}; document.getElementById('act-ext-tol').value = this.value * ${kunlikSt};" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">💰 Qo'shimcha hisoblangan summa</label>
                    <input id="act-ext-sum" type="number" value="${kunlikSt}" step="10000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">💵 Hozir to'lagan summasi</label>
                    <input id="act-ext-tol" type="number" value="${kunlikSt}" step="10000" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                </div>
                <div>
                    <label class="text-slate-300">🏦 Kassa</label>
                    <select id="act-ext-kassa" class="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white">
                        <option>Naqd</option><option>Click</option><option>Uzcard</option><option>Humo</option><option>Terminal</option>
                    </select>
                </div>
            </div>
            <button onclick="submitExtend('${m.mijoz_id}')" class="w-full py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 font-bold text-sm">➕ Muddatni Cho'zish</button>
        `;
    }
}

function closeActionModal() { document.getElementById('action-modal').classList.add('hidden'); }

function renderEditBeds(mijozId) {
    const m = STATE.barcha_mehmonlar.find(x => x.mijoz_id === mijozId);
    const xNom = document.getElementById('ed-xona').value;
    const r = STATE.xonalar.find(x => x.xona === xNom);
    if (!r) return;
    STATE.editSelectedBeds = [];
    const grid = document.getElementById('ed-beds-grid');
    if (r.tomon === "O'rtadagi") {
        grid.innerHTML = `<div class="col-span-2 p-3 rounded-lg bg-purple-600/20 border border-purple-500 text-center text-xs">🛌 Lyuks xona: Bitta Dvuxspalniy</div>`;
        return;
    }
    let html = '';
    for (let i = 1; i <= r.sigim; i++) {
        const egasi = r.krovatlar[String(i)];
        const ozinikimi = m && egasi === m.mijoz;
        if (egasi && !ozinikimi) {
            html += `<div class="p-2.5 rounded-lg bg-red-900/30 border border-red-600 text-center text-xs opacity-60">🔴 ${i}-joy (${egasi})</div>`;
        } else {
            if (ozinikimi || STATE.editSelectedBeds.length === 0) STATE.editSelectedBeds.push(`${i}-joy`);
            const isSel = STATE.editSelectedBeds.includes(`${i}-joy`);
            html += `<div onclick="toggleEditBed('${i}-joy')" id="ebed-${i}-joy" class="p-2.5 rounded-lg border text-center text-xs cursor-pointer ${isSel ? 'bg-amber-600 border-amber-300 font-bold text-white' : 'bg-emerald-950/40 border-emerald-600 text-emerald-300'}">🟢 ${i}-joy (Bo'sh)</div>`;
        }
    }
    grid.innerHTML = html;
}

function toggleEditBed(joy) {
    const idx = STATE.editSelectedBeds.indexOf(joy);
    if (idx >= 0) STATE.editSelectedBeds.splice(idx, 1);
    else STATE.editSelectedBeds.push(joy);
    const btn = document.getElementById('ebed-' + joy);
    if (btn) {
        const isSel = STATE.editSelectedBeds.includes(joy);
        btn.className = `p-2.5 rounded-lg border text-center text-xs cursor-pointer ${isSel ? 'bg-amber-600 border-amber-300 font-bold text-white' : 'bg-emerald-950/40 border-emerald-600 text-emerald-300'}`;
    }
}

async function submitEditGuest(id) {
    const body = {
        mijoz_id: id,
        mijoz: document.getElementById('ed-ism').value,
        toifa: document.getElementById('ed-toifa').value,
        xona: document.getElementById('ed-xona').value,
        odam_soni: parseInt(document.getElementById('ed-odam').value || 1),
        kirish_sanasi: document.getElementById('ed-ksana').value,
        kirish_soati: document.getElementById('ed-ksoat').value,
        kunlar: parseInt(document.getElementById('ed-kun').value || 1),
        faktik_narx: parseFloat(document.getElementById('ed-faktik').value || 0),
        tolagan_summa: parseFloat(document.getElementById('ed-tolagan').value || 0),
        izoh: document.getElementById('ed-izoh').value,
        avto_qayta_hisob: document.getElementById('ed-recalc').checked,
        krovatlar: STATE.editSelectedBeds,
        xodim: STATE.currentUser.ism
    };
    const res = await fetch('/api/tahrir', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    if (res.ok) { closeActionModal(); loadData(); }
    else alert("Xatolik: " + (await res.text()));
}

function calcAutoVozvrat(tolagan, stavka) {
    const kun = parseInt(document.getElementById('act-ch-kun').value || 0);
    const haqiqiySum = kun * stavka;
    const vozv = Math.max(0, tolagan - haqiqiySum);
    document.getElementById('act-ch-vozv').value = vozv;
    document.getElementById('vozv-info').innerText = `🧮 Avto-hisob: ${kun} sutka × ${stavka.toLocaleString()} = ${haqiqiySum.toLocaleString()} UZS ➔ Qaytariladigan Vozvrat: ${vozv.toLocaleString()} UZS`;
}

function renderMoveBeds(mijozId) {
    const xNom = document.getElementById('act-move-xona').value;
    const r = STATE.xonalar.find(x => x.xona === xNom);
    if (!r) return;
    STATE.moveSelectedBeds = [];
    const grid = document.getElementById('act-move-beds');
    if (r.tomon === "O'rtadagi") {
        grid.innerHTML = `<div class="col-span-2 p-3 rounded-lg bg-purple-600/20 border border-purple-500 text-center text-xs">🛌 Lyuks xona: Bitta Dvuxspalniy</div>`;
        return;
    }
    let html = '';
    for (let i = 1; i <= r.sigim; i++) {
        const band = r.krovatlar[String(i)];
        if (band) {
            html += `<div class="p-2.5 rounded-lg bg-red-900/30 border border-red-600 text-center text-xs opacity-60">🔴 ${i}-joy (${band})</div>`;
        } else {
            if (STATE.moveSelectedBeds.length === 0) STATE.moveSelectedBeds.push(`${i}-joy`);
            const isSel = STATE.moveSelectedBeds.includes(`${i}-joy`);
            html += `<div onclick="toggleMoveBed('${i}-joy')" id="mbed-${i}-joy" class="p-2.5 rounded-lg border text-center text-xs cursor-pointer ${isSel ? 'bg-indigo-600 border-indigo-300 font-bold text-white' : 'bg-emerald-950/40 border-emerald-600 text-emerald-300'}">🟢 ${i}-joy (Bo'sh)</div>`;
        }
    }
    grid.innerHTML = html;
}

function toggleMoveBed(joy) {
    const idx = STATE.moveSelectedBeds.indexOf(joy);
    if (idx >= 0) STATE.moveSelectedBeds.splice(idx, 1);
    else STATE.moveSelectedBeds.push(joy);
    const btn = document.getElementById('mbed-' + joy);
    if (btn) {
        const isSel = STATE.moveSelectedBeds.includes(joy);
        btn.className = `p-2.5 rounded-lg border text-center text-xs cursor-pointer ${isSel ? 'bg-indigo-600 border-indigo-300 font-bold text-white' : 'bg-emerald-950/40 border-emerald-600 text-emerald-300'}`;
    }
}

async function submitPay(id) {
    const summa = parseFloat(document.getElementById('act-pay-sum').value || 0);
    const kassa = document.getElementById('act-pay-kassa').value;
    const res = await fetch('/api/qarz-yopish', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ mijoz_id: id, summa, kassa, xodim: STATE.currentUser.ism })
    });
    if (res.ok) { closeActionModal(); loadData(); }
}

async function submitMove(id) {
    const yangi_xona = document.getElementById('act-move-xona').value;
    const res = await fetch('/api/xona-kochirish', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ mijoz_id: id, yangi_xona, yangi_krovatlar: STATE.moveSelectedBeds, xodim: STATE.currentUser.ism })
    });
    if (res.ok) { closeActionModal(); loadData(); }
}

async function submitCheckoutModal(id, qarz) {
    const yashagan_kun = parseInt(document.getElementById('act-ch-kun').value || 1);
    const vozvrat_summa = parseFloat(document.getElementById('act-ch-vozv').value || 0);
    let majburiy = false;
    if (qarz > 0 && vozvrat_summa === 0) {
        if (STATE.currentUser.role !== 'ceo') {
            alert("⚠️ Oddiy admin qarzdor mijozni chiqara olmaydi! Avval qarzni yoping yoki CEO rejimiga o'ting.");
            return;
        }
        if (!confirm(`⚠️ DIQQAT (CEO): Ushbu mijozda ${qarz.toLocaleString()} UZS qarz bor! Haqiqatdan ham qarzdor holatda checkout qilishni xohlaysizmi?`)) return;
        majburiy = true;
    }
    const res = await fetch('/api/checkout', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ mijoz_id: id, yashagan_kun, vozvrat_summa, majburiy_qarz_bilan: majburiy, xodim: STATE.currentUser.ism })
    });
    if (res.ok) { closeActionModal(); loadData(); }
    else alert("Xatolik: " + (await res.text()));
}

function renderMarketAndFinance() {
    const mSel = document.getElementById('pos-mahs');
    mSel.innerHTML = (STATE.mahsulotlar || []).map(p => `<option value="${p.id}">${p.nomi} ${p.hajmi} — ${p.narxi.toLocaleString()} UZS (Qoldiq: ${p.qoldiq} ta)</option>`).join('');
    const gSel = document.getElementById('pos-mijoz');
    gSel.innerHTML = (STATE.faol_mehmonlar || []).map(g => `<option value="${g.mijoz_id}">${g.mijoz} (${g.xona})</option>`).join('');

    document.getElementById('sklad-table-body').innerHTML = (STATE.mahsulotlar || []).map(p => `
        <tr class="hover:bg-slate-800/40">
            <td class="py-2 px-2 font-semibold">${p.nomi}</td>
            <td class="py-2 px-2 text-slate-400">${p.hajmi || '-'}</td>
            <td class="py-2 px-2">${p.tannarx.toLocaleString()} UZS</td>
            <td class="py-2 px-2 text-emerald-400 font-bold">${p.narxi.toLocaleString()} UZS</td>
            <td class="py-2 px-2 ${p.qoldiq <= 5 ? 'text-red-400 font-bold' : ''}">${p.qoldiq} ta</td>
        </tr>
    `).join('');

    const k = STATE.kpi;
    document.getElementById('z-report-box').innerHTML = `
        <div class="p-3 rounded-xl bg-slate-900"><div class="text-xs text-slate-400">💵 Sof Naqd Kassa</div><div class="text-lg font-bold text-emerald-400">${(k.sof_naqd || 0).toLocaleString()} UZS</div></div>
        <div class="p-3 rounded-xl bg-slate-900"><div class="text-xs text-slate-400">💳 Sof Karta/Onlayn</div><div class="text-lg font-bold text-cyan-400">${(k.sof_karta || 0).toLocaleString()} UZS</div></div>
    `;

    document.getElementById('xar-table-body').innerHTML = (STATE.xarajatlar || []).map(x => `
        <tr>
            <td class="py-2 px-2 text-xs text-slate-400">${x.vaqt}</td>
            <td class="py-2 px-2 font-semibold">${x.kategoriya}</td>
            <td class="py-2 px-2 text-rose-400 font-bold">-${x.summa.toLocaleString()} UZS</td>
            <td class="py-2 px-2">${x.tolov_turi}</td>
            <td class="py-2 px-2 text-slate-300">${x.izoh}</td>
        </tr>
    `).join('') || '<tr><td colspan="5" class="text-center py-4 text-slate-500">Xarajatlar yo\'q</td></tr>';
}

function togglePosGuest() {
    const tur = document.getElementById('pos-tur').value;
    document.getElementById('pos-kassa-wrap').classList.toggle('hidden', tur === 'Xona');
    document.getElementById('pos-mijoz-wrap').classList.toggle('hidden', tur !== 'Xona');
}

async function submitMarketSavdo() {
    const body = {
        mahsulot_id: parseInt(document.getElementById('pos-mahs').value),
        miqdor: parseInt(document.getElementById('pos-soni').value || 1),
        tolov_turi: document.getElementById('pos-tur').value,
        kassa: document.getElementById('pos-kassa').value,
        mijoz_id: document.getElementById('pos-mijoz').value,
        xodim: STATE.currentUser.ism
    };
    const res = await fetch('/api/market-savdo', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    if (res.ok) loadData();
    else alert("Xatolik: " + (await res.text()));
}

async function submitSkladKirim() {
    const body = {
        nomi: document.getElementById('sk-nom').value,
        hajmi: document.getElementById('sk-hajm').value,
        tannarx: parseFloat(document.getElementById('sk-tan').value || 0),
        narxi: parseFloat(document.getElementById('sk-narx').value || 0),
        qoldiq: parseInt(document.getElementById('sk-qol').value || 1),
        xodim: STATE.currentUser.ism
    };
    const res = await fetch('/api/sklad-kirim', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    if (res.ok) loadData();
}

async function submitXarajat() {
    const body = {
        kategoriya: document.getElementById('xar-kat').value,
        summa: parseFloat(document.getElementById('xar-sum').value || 0),
        tolov_turi: document.getElementById('xar-kassa').value,
        izoh: document.getElementById('xar-izoh').value,
        xodim: STATE.currentUser.ism
    };
    if (!body.izoh) { alert("Izoh yozing!"); return; }
    const res = await fetch('/api/xarajat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    if (res.ok) { document.getElementById('xar-izoh').value = ''; loadData(); }
}

async function submitSmena() {
    const izoh = document.getElementById('z-izoh').value;
    const res = await fetch('/api/smena-yopish', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ izoh, xodim: STATE.currentUser.ism }) });
    if (res.ok) { alert("✅ Smena yopildi va Z-Hisobot Telegramga yuborildi!"); loadData(); }
}

function filterWing(w) {
    if (w === 'ORTA') STATE.wingFilter = "O'rtadagi";
    else if (w === 'ONG') STATE.wingFilter = "O'ng tomon";
    else STATE.wingFilter = w;
    renderRooms2D();
}

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
            <td class="py-2 px-2 text-right space-x-1 whitespace-nowrap">
                <button onclick="openGuestHistory('${m.mijoz_id}', '${m.mijoz}')" title="To'lovlar va Market tarixi" class="px-2 py-1 rounded bg-cyan-700/80 hover:bg-cyan-600 text-xs">📜</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'receipt')" title="Chek" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs">🖨️</button>
                <button onclick="openActionModal('${m.mijoz_id}', 'edit')" title="Tahrirlash" class="px-2 py-1 rounded bg-amber-600/80 hover:bg-amber-600 text-xs">✏️</button>
                <button onclick="deleteGuest('${m.mijoz_id}', '${m.mijoz}')" title="Bazadan butunlay o'chirish (Faqat CEO)" class="px-2 py-1 rounded bg-red-900/70 hover:bg-red-600 text-xs">🗑️</button>
            </td>
        </tr>
    `).join('');
}

async function openGuestHistory(id, ism) {
    const modal = document.getElementById('action-modal');
    const title = document.getElementById('act-title');
    const body = document.getElementById('act-body');
    modal.classList.remove('hidden');
    title.innerText = `📜 Moliya va Market Tarixi — ${ism} (${id})`;
    body.innerHTML = `<div class="text-xs text-slate-400">Yuklanmoqda...</div>`;

    const res = await fetch('/api/mijoz-tarix/' + id);
    const data = await res.json();

    const tolHtml = (data.tolovlar || []).map(t => `
        <div class="flex justify-between p-2 rounded bg-slate-900 text-xs">
            <span><b>${t.manba}</b> (${t.kassa}) — <i class="text-slate-400">${t.sana}</i></span>
            <span class="${t.summa < 0 ? 'text-rose-400' : 'text-emerald-400'} font-bold">${t.summa > 0 ? '+' : ''}${t.summa.toLocaleString()} UZS</span>
        </div>
    `).join('') || '<div class="text-xs text-slate-500">To\'lovlar qayd etilmagan</div>';

    const savHtml = (data.savdolar || []).map(s => `
        <div class="flex justify-between p-2 rounded bg-slate-900 text-xs">
            <span>🛒 <b>${s.mahsulot}</b> (${s.miqdor} dona) — <i class="text-slate-400">${s.sana}</i></span>
            <span class="text-amber-300 font-bold">${s.summa.toLocaleString()} UZS (${s.holat})</span>
        </div>
    `).join('') || '<div class="text-xs text-slate-500">Market xaridlari yo\'q</div>';

    body.innerHTML = `
        <div class="space-y-3">
            <div><h4 class="text-xs font-bold text-emerald-400 mb-1.5">💵 To'lovlar va Vozvratlar tarixi:</h4><div class="space-y-1 max-h-44 overflow-y-auto">${tolHtml}</div></div>
            <div><h4 class="text-xs font-bold text-amber-400 mb-1.5">🛒 Marketdan olingan mahsulotlar:</h4><div class="space-y-1 max-h-44 overflow-y-auto">${savHtml}</div></div>
        </div>
    `;
}

function renderCeoAndTg() {
    document.getElementById('users-list-box').innerHTML = (STATE.xodimlar || []).map(u => `
        <div class="flex justify-between items-center p-2 rounded-lg bg-slate-900 text-xs">
            <span>👤 <b>${u.ism}</b> (${u.login})</span>
            <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold">${u.role.toUpperCase()}</span>
                ${u.login !== 'ceo' ? `<button onclick="deleteUser('${u.login}')" class="text-red-400 hover:text-red-300 font-bold">✕</button>` : ''}
            </div>
        </div>
    `).join('');

    document.getElementById('audit-list-box').innerHTML = (STATE.audit_log || []).map(a => `
        <div class="p-2 rounded-lg bg-slate-900 border border-slate-800 text-xs">
            <div class="flex justify-between text-amber-300 font-semibold"><span>${a.harakat} (${a.obyekt})</span><span class="text-slate-400">${a.vaqt}</span></div>
            <div class="text-slate-300 mt-0.5">${a.tafsilot} — <i>${a.xodim}</i></div>
        </div>
    `).join('');

    const box = document.getElementById('tg-log-list');
    box.innerHTML = (STATE.tg_log || []).map(t => `
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

async function loadSettings() {
    try {
        const res = await fetch('/api/sozlamalar');
        if (res.ok) {
            const s = await res.json();
            document.getElementById('set-token').value = s.tg_token || '';
            document.getElementById('set-ceoid').value = s.ceo_chat_id || '';
            document.getElementById('set-ownerid').value = s.owner_chat_id || '';
            document.getElementById('set-reglament').value = s.reglament || '';
        }
    } catch (e) {}
}

async function saveSettings() {
    const body = {
        tg_token: document.getElementById('set-token').value,
        ceo_chat_id: document.getElementById('set-ceoid').value,
        owner_chat_id: document.getElementById('set-ownerid').value,
        reglament: document.getElementById('set-reglament').value,
        xodim: STATE.currentUser.ism
    };
    const res = await fetch('/api/sozlamalar', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    if (res.ok) alert("✅ Sozlamalar muvaffaqiyatli saqlandi!");
}
loadSettings();

async function submitNewUser() {
    if (STATE.currentUser.role !== 'ceo') { alert("Faqat CEO yangi xodim qo'sha oladi!"); return; }
    const body = {
        ism: document.getElementById('u-ism').value,
        login: document.getElementById('u-login').value,
        parol: document.getElementById('u-parol').value,
        role: document.getElementById('u-role').value,
        xodim: STATE.currentUser.ism
    };
    const res = await fetch('/api/xodim-qoshish', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
    if (res.ok) loadData();
    else alert("Xatolik: " + (await res.text()));
}

async function toggleClean(xona, holat) {
    await fetch('/api/tozalik', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ xona, holat, xodim: STATE.currentUser.ism })
    });
    loadData();
}

function openModal() {
    const sel = document.getElementById('m-xona');
    sel.innerHTML = STATE.xonalar.map(r => `<option value="${r.xona}">${r.xona} (${r.tomon} — Bo'sh: ${r.bosh_joy}/${r.sigim})</option>`).join('');
    document.getElementById('m-ksana').value = STATE.bugun || '';
    document.getElementById('m-ksoat').value = STATE.soat || '14:00';
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
        jinsi: document.getElementById('m-jins').value,
        toifa: document.getElementById('m-toifa').value,
        bron_turi: document.getElementById('m-bronturi').value,
        xona: document.getElementById('m-xona').value,
        odam_soni: parseInt(document.getElementById('m-odam').value || 1),
        kirish_sanasi: document.getElementById('m-ksana').value,
        kirish_soati: document.getElementById('m-ksoat').value,
        kunlar: parseInt(document.getElementById('m-kun').value || 1),
        chegirma_foiz: parseInt(document.getElementById('m-cheg').value || 0),
        tolangan: parseFloat(document.getElementById('m-tolov').value || 0),
        tolov_tafsiloti: document.getElementById('m-kassa').value,
        krovatlar: STATE.selectedBeds,
        xodim: STATE.currentUser.ism
    };
    const res = await fetch('/api/qabul', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    });
    if (res.ok) { closeModal(); loadData(); }
    else { const err = await res.json(); alert("Xatolik: " + err.detail); }
}

applyState(STATE);
// Har 15 soniyada orqa fonda avtomatik sinxronizatsiya
setInterval(loadData, 15000);
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    init_data = api_dashboard()
    html_out = FRONTEND_HTML.replace("__INITIAL_STATE_JSON__", json.dumps(init_data, ensure_ascii=False))
    return html_out