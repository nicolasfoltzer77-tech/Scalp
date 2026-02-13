import ccxt, sqlite3

DBU = "/opt/scalp/project/data/u.db"
TOP = 20

exchange = ccxt.bitget()
markets = exchange.load_markets()

perps = []
for s,info in markets.items():
    if info.get('swap',False) and info['quote'] == 'USDT':
        inst = s.replace(":USDT","")  # -> BTC/USDT:USDT → BTC/USDT
        perps.append(inst)

perps = perps[:TOP]

con = sqlite3.connect(DBU, timeout=5)
con.execute("DELETE FROM v_universe_tradable;")
for inst in perps:
    con.execute("INSERT OR IGNORE INTO universe(instId) VALUES (?)", (inst,))
con.commit()
con.close()

print("[U] OK :", perps)

