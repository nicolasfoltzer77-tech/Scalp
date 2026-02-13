#!/usr/bin/env python3
import sqlite3, time, logging, sys
from pathlib import Path

DB_BUDGET  = Path("/opt/scalp/project/data/budget.db")
DB_OPENER  = Path("/opt/scalp/project/data/opener.db")
DB_CLOSER  = Path("/opt/scalp/project/data/closer.db")
DB_REC     = Path("/opt/scalp/project/data/recorder.db")
LOG        = "/opt/scalp/project/logs/budget.log"

# -----------------------------------------------------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s BUDGET %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG), logging.StreamHandler(sys.stdout)],
        force=True,
    )

# -----------------------------------------------------
def connect(path):
    c = sqlite3.connect(path, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    return c

# -----------------------------------------------------
def get_margin_engaged(con_o):
    """Somme de la marge estimée sur les positions ouvertes/pending."""
    try:
        res = con_o.execute("""
            SELECT SUM(entry * qty / leverage)
            FROM trades_open_init
            WHERE status IN ('pending','open');
        """).fetchone()[0]
        return round(res or 0.0, 4)
    except Exception:
        return 0.0

def get_pnl_real(con_r):
    """Somme du PnL réalisé total depuis l’historique."""
    try:
        res = con_r.execute("SELECT SUM(pnl_net) FROM trades_recorded;").fetchone()[0]
        if res is None:
            res = con_r.execute("SELECT SUM(pnl) FROM trades_recorded;").fetchone()[0]
        return round(res or 0.0, 4)
    except Exception:
        return 0.0

def get_capital_initial(con_b):
    """Capital initial du budget (si non encore présent, crée 1000 USDT)."""
    con_b.execute("""
        CREATE TABLE IF NOT EXISTS budget_state(
            id INTEGER PRIMARY KEY CHECK (id=1),
            balance REAL DEFAULT 1000.0,
            margin REAL DEFAULT 0.0,
            pnl_real REAL DEFAULT 0.0,
            ts_update INTEGER
        );
    """)
    con_b.commit()
    row = con_b.execute("SELECT balance FROM budget_state WHERE id=1;").fetchone()
    if not row:
        con_b.execute("INSERT OR REPLACE INTO budget_state(id,balance,margin,pnl_real,ts_update) VALUES (1,1000.0,0.0,0.0,strftime('%s','now'));")
        con_b.commit()
        return 1000.0
    return float(row[0])

# -----------------------------------------------------
def update_budget():
    con_b = connect(DB_BUDGET)
    con_o = connect(DB_OPENER)
    con_r = connect(DB_REC)

    capital = get_capital_initial(con_b)
    margin  = get_margin_engaged(con_o)
    pnl_real = get_pnl_real(con_r)

    new_balance = capital + pnl_real
    ts_now = int(time.time())

    con_b.execute("""
        UPDATE budget_state
        SET balance=?, margin=?, pnl_real=?, ts_update=?
        WHERE id=1;
    """, (new_balance, margin, pnl_real, ts_now))
    con_b.commit()

    con_b.execute("""
        CREATE VIEW IF NOT EXISTS v_budget_overview AS
        SELECT
            ROUND(balance,4) AS balance,
            ROUND(margin,4)  AS margin,
            ROUND(pnl_real,4) AS pnl_real,
            datetime(ts_update,'unixepoch','localtime') AS ts_local
        FROM budget_state;
    """)
    con_b.commit()

    con_b.close(); con_o.close(); con_r.close()
    logging.info(f"MAJ budget → balance={new_balance:.2f} margin={margin:.2f} pnl_real={pnl_real:.2f}")

# -----------------------------------------------------
def main(_):
    setup_logging()
    logging.info("Budget updater started ✓")
    try:
        update_budget()
    except Exception as e:
        logging.exception(f"Erreur mise à jour budget: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

