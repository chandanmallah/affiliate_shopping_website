"""
wipe_db.py — permanently delete ALL data from your PostgreSQL (Render) database.

This removes every row from every LedgerBook table (transactions, clients,
users, meta). After this, opening the app against this database shows the
"Create account" screen again, as if it were brand new.

  *** THERE IS NO UNDO. ***
  Run inspect_db.py first if you might want the data later.

Two modes:
  - Default: empties the tables (keeps the empty tables in place).
  - --drop : also drops the tables entirely (the app recreates them on next run).

Usage
-----
    pip install "psycopg[binary]"
    python wipe_db.py            # empty the tables
    python wipe_db.py --drop     # drop the tables completely
"""

from __future__ import annotations

import sys

TABLES_IN_ORDER = ["transactions", "clients", "users", "meta"]  # children first


def connect(url):
    try:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"),
                               row_factory=dict_row, autocommit=True)
    except ImportError:
        try:
            import psycopg2
            conn = psycopg2.connect(url)
            conn.autocommit = True
            return conn
        except ImportError:
            print('\n! PostgreSQL driver missing:\n    pip install "psycopg[binary]"')
            sys.exit(1)


def count(cur, table):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        return list(row.values())[0] if isinstance(row, dict) else row[0]
    except Exception:
        return None  # table doesn't exist


def main():
    drop = "--drop" in sys.argv

    print("=" * 64)
    print(" WIPE PostgreSQL database  —  THIS CANNOT BE UNDONE")
    print("=" * 64)

    url = input("\nPostgreSQL URL (Render EXTERNAL):\n> ").strip()
    if not url.startswith("postgres"):
        print("! That doesn't look like a postgresql:// URL.")
        sys.exit(1)
    if "sslmode" not in url and "render.com" in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"

    conn = connect(url)
    cur = conn.cursor()

    # show what's there now
    print("\nCurrent contents:")
    found_any = False
    for t in TABLES_IN_ORDER:
        n = count(cur, t)
        if n is not None:
            found_any = True
            print(f"    {t:14} {n} row(s)")
    if not found_any:
        print("    (no LedgerBook tables found — nothing to wipe)")
        return

    action = "DROP (delete tables entirely)" if drop else "EMPTY (delete all rows)"
    print(f"\nAbout to: {action}")
    print("This will permanently destroy the data above.")
    confirm = input('\nType exactly  DELETE ALL  to proceed: ')
    if confirm.strip() != "DELETE ALL":
        print("\nCancelled. Nothing was changed.")
        return

    if drop:
        for t in TABLES_IN_ORDER:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
                print(f"  dropped {t}")
            except Exception as e:
                print(f"  ! {t}: {e}")
    else:
        for t in TABLES_IN_ORDER:
            try:
                # TRUNCATE ... CASCADE clears rows and resets id sequences.
                cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
                print(f"  emptied {t}")
            except Exception as e:
                print(f"  ! {t}: {e}")

    # confirm result
    print("\nAfter wipe:")
    for t in TABLES_IN_ORDER:
        n = count(cur, t)
        print(f"    {t:14} {'(dropped)' if n is None else str(n) + ' row(s)'}")

    try:
        conn.close()
    except Exception:
        pass

    print("\n" + "=" * 64)
    print(" Done. Open the app against this database to start fresh")
    print(" (you'll get the 'Create account' screen).")
    print("=" * 64)


if __name__ == "__main__":
    main()