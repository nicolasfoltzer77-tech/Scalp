#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from pathlib import Path

ROOT = Path('/opt/scalp/project')
DB_GEST = ROOT / 'data/gest.db'
DB_TRIG = ROOT / 'data/triggers.db'
DB_DEC = ROOT / 'data/dec.db'


def conn(path):
    c = sqlite3.connect(str(path), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL;')
    c.execute('PRAGMA busy_timeout=10000;')
    return c


def table_columns(c, table):
    return {r['name'] for r in c.execute(f'PRAGMA table_info({table})').fetchall()}


def rget(row, col, default=None):
    try:
        return row[col]
    except Exception:
        return default


def clamp01(v, default=0.0):
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = float(default)
    return max(0.0, min(1.0, x))


def ensure_columns(g):
    cols = table_columns(g, 'gest')
    required = {
        'score_C': 'REAL',
        'score_S': 'REAL',
        'score_H': 'REAL',
        'score_M': 'REAL',
        'score_of': 'REAL',
        'score_mo': 'REAL',
        'score_br': 'REAL',
        'score_force': 'REAL',
    }
    for col, typ in required.items():
        if col not in cols:
            g.execute(f'ALTER TABLE gest ADD COLUMN {col} {typ}')


def load_dec(d, uid, inst_id):
    objs = {r['name'] for r in d.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()}
    if 'v_dec_score_s' not in objs:
        return None
    cols = table_columns(d, 'v_dec_score_s')
    wanted = [
        'uid', 'instId', 'score_C', 'score_S', 's_struct', 's_quality', 's_vol', 's_confirm',
        'dec_mode', 'ctx', 'momentum_ok', 'prebreak_ok', 'pullback_ok', 'compression_ok'
    ]
    select_cols = [c for c in wanted if c in cols]
    if not select_cols:
        return None
    q = f"SELECT {', '.join(select_cols)} FROM v_dec_score_s WHERE uid=? LIMIT 1"
    row = d.execute(q, (uid,)).fetchone()
    if row:
        return row
    if 'instId' in cols:
        q = f"SELECT {', '.join(select_cols)} FROM v_dec_score_s WHERE instId=? ORDER BY COALESCE(ts_updated,0) DESC LIMIT 1"
        return d.execute(q, (inst_id,)).fetchone()
    return None


def resolve_h(t, inst_id, trigger_type, dec_mode):
    objs = {r['name'] for r in t.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()}
    if 'historical_scores_v2' in objs:
        cols = table_columns(t, 'historical_scores_v2')
        h_col = 'score_H' if 'score_H' in cols else ('score_H_final' if 'score_H_final' in cols else None)
        if h_col and all(c in cols for c in ('instId', 'type_signal', 'ctx')):
            row = t.execute(
                f'''SELECT {h_col} AS score_H FROM historical_scores_v2
                    WHERE instId=? AND type_signal=? AND ctx=?
                    ORDER BY COALESCE(ts_updated,0) DESC LIMIT 1''',
                (inst_id, trigger_type, dec_mode),
            ).fetchone()
            if row and row['score_H'] is not None:
                return clamp01(row['score_H'], default=0.5)

    if 'v_score_H' in objs:
        cols = table_columns(t, 'v_score_H')
        if 'score_H' in cols:
            filters, params = [], []
            if 'instId' in cols:
                filters.append('instId=?'); params.append(inst_id)
            if 'trigger_type' in cols:
                filters.append('trigger_type=?'); params.append(trigger_type)
            if 'dec_mode' in cols:
                filters.append('dec_mode=?'); params.append(dec_mode)
            where = (' WHERE ' + ' AND '.join(filters)) if filters else ''
            row = t.execute(f'SELECT score_H FROM v_score_H{where} LIMIT 1', tuple(params)).fetchone()
            if row and row['score_H'] is not None:
                return clamp01(row['score_H'], default=0.5)

    return 0.5


def main():
    g = conn(DB_GEST)
    t = conn(DB_TRIG)
    d = conn(DB_DEC)

    ensure_columns(g)

    rows = g.execute('''
        SELECT uid, instId, score_C, score_S, score_H, score_M,
               score_of, score_mo, score_br, score_force,
               trigger_type, dec_mode
        FROM gest
    ''').fetchall()

    updated = 0
    for r in rows:
        uid = r['uid']
        trig = t.execute('SELECT * FROM triggers WHERE uid=? LIMIT 1', (uid,)).fetchone()
        dec = load_dec(d, uid, r['instId'])

        score_c = r['score_C']
        score_s = r['score_S']
        score_h = r['score_H']
        score_m = r['score_M']
        score_of = r['score_of']
        score_mo = r['score_mo']
        score_br = r['score_br']
        score_force = r['score_force']
        trigger_type = r['trigger_type']
        dec_mode = r['dec_mode']

        if trig:
            score_c = score_c if score_c is not None else rget(trig, 'score_C', rget(trig, 'dec_score_C'))
            score_of = score_of if score_of is not None else rget(trig, 'score_of')
            score_mo = score_mo if score_mo is not None else rget(trig, 'score_mo')
            score_br = score_br if score_br is not None else rget(trig, 'score_br')
            score_force = score_force if score_force is not None else rget(trig, 'score_force')
            score_m = score_m if score_m is not None else rget(trig, 'score_M', 0.5)
            trigger_type = trigger_type or rget(trig, 'trigger_type') or rget(trig, 'type_signal') or rget(trig, 'phase')
            dec_mode = dec_mode or rget(trig, 'dec_mode')

        if dec:
            score_c = score_c if score_c is not None else rget(dec, 'score_C')
            dec_mode = dec_mode or rget(dec, 'dec_mode')

        if score_s is None:
            if trig and rget(trig, 'score_S') is not None:
                score_s = rget(trig, 'score_S')
            elif dec and rget(dec, 'score_S') is not None:
                score_s = rget(dec, 'score_S')
            else:
                s_struct = rget(trig, 's_struct', rget(dec, 's_struct', 0.0))
                s_quality = rget(trig, 's_quality', rget(dec, 's_quality', 0.0))
                s_vol = rget(trig, 's_vol', rget(dec, 's_vol', 0.0))
                s_confirm = rget(trig, 's_confirm', rget(dec, 's_confirm', 0.0))
                score_s = 0.40 * float(s_struct or 0.0) + 0.30 * float(s_quality or 0.0) + 0.20 * float(s_vol or 0.0) + 0.10 * float(s_confirm or 0.0)

        score_s = clamp01(score_s, default=0.0)
        score_h = clamp01(score_h if score_h is not None else resolve_h(t, r['instId'], trigger_type, dec_mode), default=0.5)
        score_m = clamp01(score_m, default=0.5)

        g.execute('''
            UPDATE gest
            SET score_C=?, score_S=?, score_H=?, score_M=?,
                score_of=?, score_mo=?, score_br=?, score_force=?,
                trigger_type=COALESCE(trigger_type, ?),
                dec_mode=COALESCE(dec_mode, ?)
            WHERE uid=?
        ''', (
            score_c, score_s, score_h, score_m,
            score_of, score_mo, score_br, score_force,
            trigger_type, dec_mode,
            uid,
        ))
        updated += 1

    g.commit()
    print(f'backfill complete: updated={updated}')


if __name__ == '__main__':
    main()
