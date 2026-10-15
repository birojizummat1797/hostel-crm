import streamlit as st
import requests
import os
from datetime import datetime

def get_tg_credentials():
    token, chat_id = None, None
    try:
        if "TG_BOT_TOKEN" in st.secrets:
            token = st.secrets["TG_BOT_TOKEN"]
        if "TG_CHAT_ID" in st.secrets:
            chat_id = st.secrets["TG_CHAT_ID"]
    except Exception:
        pass
    if not token:
        token = os.environ.get("TG_BOT_TOKEN")
    if not chat_id:
        chat_id = os.environ.get("TG_CHAT_ID")
    return token, chat_id

def tg_xabar_yubor(sarlavha, tafsilotlar, xodim, muhim=False):
    """CEO Telegramiga chiroyli formatda tezkor bildirishnoma yuborish"""
    token, chat_id = get_tg_credentials()
    if not token or not chat_id:
        return False

    hozir = datetime.now().strftime("%d.%m.%Y | %H:%M")
    belgi = "🚨" if muhim else "🔔"
    
    matn = (
        f"{belgi} <b>YSH CRM: {sarlavha}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{tafsilotlar}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {xodim}\n"
        f"🕒 <b>Vaqt:</b> {hozir}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        res = requests.post(
            url, 
            json={"chat_id": str(chat_id).strip(), "text": matn, "parse_mode": "HTML"}, 
            timeout=10
        )
        return res.status_code == 200
    except Exception:
        return False