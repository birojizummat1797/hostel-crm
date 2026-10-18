import streamlit as st
import urllib.request
import urllib.parse
import json
import os
from datetime import datetime, timedelta, timezone

DEFAULT_BOT_TOKEN = "8642661945:AAH62xM_jM6n-vB8yP8U5pL3_w8G-Y8k3s0"
DEFAULT_CEO_CHAT_ID = "6126259824"

def _toshkent_vaqti_str():
    uz_vaqt = datetime.now(timezone.utc) + timedelta(hours=5)
    return uz_vaqt.strftime("%d.%m.%Y | %H:%M")

def _get_bot_credentials():
    bot_token = DEFAULT_BOT_TOKEN
    ceo_ids = []
    owner_ids = []

    try:
        if "TG_BOT_TOKEN" in st.secrets:
            bot_token = str(st.secrets["TG_BOT_TOKEN"]).strip()
        if "TG_CHAT_ID" in st.secrets:
            ceo_ids.append(str(st.secrets["TG_CHAT_ID"]).strip())
        if "TG_OWNER_CHAT_ID" in st.secrets:
            owner_ids.append(str(st.secrets["TG_OWNER_CHAT_ID"]).strip())
    except Exception:
        pass

    if os.environ.get("TG_BOT_TOKEN"):
        bot_token = os.environ.get("TG_BOT_TOKEN").strip()
    if os.environ.get("TG_CHAT_ID"):
        ceo_ids.append(os.environ.get("TG_CHAT_ID").strip())
    if os.environ.get("TG_OWNER_CHAT_ID"):
        owner_ids.append(os.environ.get("TG_OWNER_CHAT_ID").strip())

    # Bazadagi dinamik sozlamalardan CEO va Ega (Owner) Chat ID larni o'qish
    try:
        from database import db
        rows = db.fetchall("SELECT kalit, qiymat FROM tizim_sozlamalari WHERE kalit IN ('tg_bot_token', 'tg_ceo_chat_id', 'tg_owner_chat_id')")
        soz_map = {r[0]: str(r[1] or '').strip() for r in rows}
        if soz_map.get("tg_bot_token"):
            bot_token = soz_map["tg_bot_token"]
        if soz_map.get("tg_ceo_chat_id"):
            for cid in soz_map["tg_ceo_chat_id"].replace(";", ",").split(","):
                if cid.strip():
                    ceo_ids.append(cid.strip())
        if soz_map.get("tg_owner_chat_id"):
            for oid in soz_map["tg_owner_chat_id"].replace(";", ",").split(","):
                if oid.strip():
                    owner_ids.append(oid.strip())
    except Exception:
        pass

    if not ceo_ids and DEFAULT_CEO_CHAT_ID:
        ceo_ids.append(DEFAULT_CEO_CHAT_ID)

    ceo_unique = []
    for c in ceo_ids:
        if c and c not in ceo_unique:
            ceo_unique.append(c)

    owner_unique = []
    for o in owner_ids:
        if o and o not in owner_unique:
            owner_unique.append(o)

    return bot_token, ceo_unique, owner_unique

def _send_raw_telegram(bot_token, chat_id, text_html):
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": str(chat_id).strip(),
        "text": text_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return bool(res.get("ok"))
    except Exception:
        return False

def tg_xabar_yubor(sarlavha, matn, xodim="Tizim", muhim=False, kanal="mijoz"):
    """
    kanal turlari:
      - 'mijoz' : Ham CEO ga, ham Mehmonxona Egasiga (Owner) boradi (Mijoz kirish-chiqishi, yotoq to'lovi, muddat cho'zish, ko'chirish).
      - 'ceo'   : Faqat CEO ga boradi (Market savdo, Sklad kirim/tahrir, Xarajatlar, Smena Z-hisoboti, Tariflar).
      - 'egasi' : Faqat Mehmonxona Egasiga boradi (Maxsus mijozlar svodkasi).
    """
    bot_token, ceo_ids, owner_ids = _get_bot_credentials()
    vaqt_str = _toshkent_vaqti_str()
    belgi = "🚨 <b>MUHIM O'ZGARISH / NAZORAT</b>\n" if muhim else ""

    to_liq_xabar = (
        f"{belgi}"
        f"🏨 <b>Y.S.H. ERP | {sarlavha}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{matn}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mas'ul:</b> {xodim}\n"
        f"🕒 <b>Vaqt:</b> {vaqt_str}"
    )

    qabul_qiluvchilar = []
    if kanal == "ceo":
        qabul_qiluvchilar = list(ceo_ids)
    elif kanal == "egasi":
        qabul_qiluvchilar = list(owner_ids)
    else:
        # 'mijoz' kanali: Ham CEO ga, ham Egaga boradi (agar ikkalasi bitta ID bo'lsa, faqat 1 marta boradi)
        qabul_qiluvchilar = list(ceo_ids)
        for o_id in owner_ids:
            if o_id not in qabul_qiluvchilar:
                qabul_qiluvchilar.append(o_id)

    muvaffaqiyat = False
    for chat_id in qabul_qiluvchilar:
        if _send_raw_telegram(bot_token, chat_id, to_liq_xabar):
            muvaffaqiyat = True
    return muvaffaqiyat