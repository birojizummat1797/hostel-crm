import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

TG_BOT_TOKEN = "8542159383:AAH6-3BV3274-N84m6V6Q1_3C1bE78xX0fE"
TG_CEO_CHAT_ID = "6483211079"

def tg_log_saqla(vaqt, sarlavha, matn, qabul_qiluvchi, xodim, holat):
    try:
        from database import db
        db.execute("""
            CREATE TABLE IF NOT EXISTS tg_xabarlar_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vaqt TEXT,
                sarlavha TEXT,
                matn TEXT,
                qabul_qiluvchi TEXT,
                xodim TEXT,
                holat TEXT
            )
        """)
        toza_matn = str(matn).replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        db.execute(
            "INSERT INTO tg_xabarlar_log (vaqt, sarlavha, matn, qabul_qiluvchi, xodim, holat) VALUES (?,?,?,?,?,?)",
            (vaqt, sarlavha, toza_matn, qabul_qiluvchi, xodim, holat)
        )
    except Exception:
        pass

def tg_xabar_yubor(sarlavha, matn, xodim="Tizim", muhim=False, qabul_nomi="👑 CEO"):
    uz_vaqt = (datetime.now(timezone.utc) + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    belgi = "🚨 <b>[MUHIM O'ZGARISH]</b>\n" if muhim else "🏨 <b>Y.S.H. ERP Xabarnomasi</b>\n"
    xabar = (
        f"{belgi}"
        f"📌 <b>Amaliyot:</b> {sarlavha}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{matn}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mas'ul xodim:</b> {xodim}\n"
        f"🕒 <b>Vaqt:</b> {uz_vaqt}"
    )
    chat_id = TG_CEO_CHAT_ID
    token = TG_BOT_TOKEN
    try:
        from database import db
        r_tok = db.fetchone("SELECT qiymat FROM tizim_sozlamalari WHERE kalit='tg_token'")
        r_cid = db.fetchone("SELECT qiymat FROM tizim_sozlamalari WHERE kalit='ceo_chat_id'")
        if r_tok and r_tok[0]: token = r_tok[0]
        if r_cid and r_cid[0]: chat_id = r_cid[0]
    except Exception:
        pass

    holat_str = "❌ Xatolik"
    yuborildi = False
    try:
        url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": str(chat_id).strip(), "text": xabar, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                yuborildi = True
                holat_str = "✅ Yetkazildi"
    except Exception:
        holat_str = "⚠️ Internet / ID xatosi"

    tg_log_saqla(uz_vaqt, sarlavha, matn, qabul_nomi, xodim, holat_str)
    return yuborildi