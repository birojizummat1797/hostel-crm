import sqlite3

conn = sqlite3.connect('hostel_crm.db')
c = conn.cursor()

# Mijozlar va o'zgarishlar tarixini butunlay tozalaymiz
c.execute("DELETE FROM bronlar")
c.execute("DELETE FROM audit_log")

# ID raqamlarni (tartibni) yana 1 dan boshlash uchun ketma-ketlikni nolga tushiramiz
c.execute("DELETE FROM sqlite_sequence WHERE name='bronlar'")
c.execute("DELETE FROM sqlite_sequence WHERE name='audit_log'")

conn.commit()
conn.close()

print("✅ Test ma'lumotlari tozalandi! Login va parollar o'z o'rnida qoldi.")