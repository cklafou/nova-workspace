# Last updated: 2026-07-19 16:16:48
import sqlite3
conn = sqlite3.connect('memory/nova_memories.db')
c = conn.cursor()
for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    print(t[0])
print('---')
for col in c.execute('PRAGMA table_info(nova_memories)').fetchall():
    print(col)
conn.close()
