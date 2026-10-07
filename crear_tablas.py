import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

with open(Path(__file__).parent / "schema.sql", encoding="utf-8") as f:
    sql = f.read()

conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=30)
cur = conn.cursor()
cur.execute(sql)
conn.commit()

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' ORDER BY table_name;
""")
print("Tablas en Neon:", [fila[0] for fila in cur.fetchall()])
conn.close()