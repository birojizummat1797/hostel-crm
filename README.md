# Y.S.H. ERP (hostel-crm)

Ishga tushirish: `Fullstack_Ochish.bat` (Web) yoki `Dasturni_Ochish.bat` (Streamlit).

## Xavfsizlik sozlamalari
- **Telegram:** bot tokeni kodda saqlanmaydi. CEO paneli -> Sozlamalar orqali kiriting yoki `TG_BOT_TOKEN` / `TG_CEO_CHAT_ID` muhit o'zgaruvchilarini bering.
- **Sessiya kaliti:** `SECRET_KEY` muhit o'zgaruvchisi (bo'lmasa avtomatik yaratilib bazada saqlanadi).
- **Parollar:** PBKDF2 bilan hash qilinadi. Eski ochiq parollar xodim birinchi marta kirganda avtomatik hash'ga o'tadi.
- **Yangi baza:** birinchi ishga tushishda tasodifiy parollar konsolga chiqariladi.
- `hostel_crm.db` git'ga qo'shilmaydi (`.gitignore`).
