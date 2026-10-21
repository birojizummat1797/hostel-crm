import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SESSIYA_MUDDATI = 12 * 3600
PBKDF2_ITER = 200_000
_PREFIKS = "pbkdf2_sha256"
_kalit_kesh = None


def parol_hash(parol):
    tuz = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", parol.encode("utf-8"), tuz.encode("utf-8"), PBKDF2_ITER).hex()
    return f"{_PREFIKS}${PBKDF2_ITER}${tuz}${h}"


def parol_tekshir(parol, saqlangan):
    saqlangan = str(saqlangan or "")
    if saqlangan.startswith(_PREFIKS + "$"):
        try:
            _, iter_s, tuz, h = saqlangan.split("$")
            yangi = hashlib.pbkdf2_hmac("sha256", parol.encode("utf-8"), tuz.encode("utf-8"), int(iter_s)).hex()
            return hmac.compare_digest(yangi, h)
        except Exception:
            return False
    # eski (hash qilinmagan) parollar: tekshiriladi, kirishda avtomatik hash'ga o'tkaziladi
    return hmac.compare_digest(saqlangan.encode("utf-8"), parol.encode("utf-8"))


def _kalit(db):
    global _kalit_kesh
    if _kalit_kesh:
        return _kalit_kesh
    k = os.environ.get("SECRET_KEY")
    if not k:
        r = db.fetchone("SELECT qiymat FROM tizim_sozlamalari WHERE kalit='sessiya_kaliti'")
        if r and r[0]:
            k = r[0]
        else:
            k = secrets.token_hex(32)
            db.execute("INSERT INTO tizim_sozlamalari (kalit, qiymat) VALUES ('sessiya_kaliti', ?)", (k,))
    _kalit_kesh = k.encode("utf-8")
    return _kalit_kesh


def token_yarat(db, login):
    payload = base64.urlsafe_b64encode(json.dumps({"l": login, "e": int(time.time()) + SESSIYA_MUDDATI}).encode()).decode()
    imzo = hmac.new(_kalit(db), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{imzo}"


def token_tekshir(db, token):
    """Token to'g'ri va muddati o'tmagan bo'lsa login qaytaradi, aks holda None."""
    try:
        payload, imzo = str(token).rsplit(".", 1)
        kutilgan = hmac.new(_kalit(db), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(kutilgan, imzo):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data["e"] < time.time():
            return None
        return data["l"]
    except Exception:
        return None


def kirish_tekshir(db, login, parol):
    """(role, ism, login) qaytaradi yoki None. Eski ochiq parolni hash'ga o'tkazadi."""
    r = db.fetchone("SELECT role, ism, login, parol FROM xodimlar WHERE login=?", (login.strip(),))
    if not r or not parol_tekshir(parol.strip(), r[3]):
        return None
    if not str(r[3]).startswith(_PREFIKS + "$"):
        db.execute("UPDATE xodimlar SET parol=? WHERE login=?", (parol_hash(parol.strip()), r[2]))
    return r[0], r[1], r[2]


def xodim_ol(db, login):
    return db.fetchone("SELECT role, ism, login FROM xodimlar WHERE login=?", (login,))
