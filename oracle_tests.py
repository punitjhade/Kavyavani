"""Kavyavani - Oracle test runner (functional, constraint violation, error handling).

Run after setting ORACLE_DSN, ORACLE_USER and ORACLE_PASSWORD:
    python oracle_tests.py
Prints PASS or FAIL for each case with the real Oracle message, and removes the
rows it creates. Copy the output into the project report.
"""
import os
import sys
import oracledb

DSN = os.environ.get("ORACLE_DSN", "")
USER = os.environ.get("ORACLE_USER", "")
PASSWORD = os.environ.get("ORACLE_PASSWORD", "")
if not (DSN and USER and PASSWORD):
    sys.exit("Set ORACLE_DSN, ORACLE_USER and ORACLE_PASSWORD first.")

results = []


def record(test_id, kind, name, ok, detail):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {test_id} ({kind}) {name}\n        {detail}")


def ora_code(exc):
    err = exc.args[0]
    return f"ORA-{err.code:05d}" if hasattr(err, "code") else str(err)


def expect_error(cur, conn, sql, params, code):
    """Run sql, expect an Oracle error with the given code. Returns (ok, detail)."""
    try:
        cur.execute(sql, params)
        conn.rollback()
        return False, "no error was raised"
    except oracledb.DatabaseError as exc:
        conn.rollback()
        got = ora_code(exc)
        return got == code, f"raised {got} (expected {code}): {str(exc.args[0]).splitlines()[0]}"


def scalar(cur, sql, params=None):
    cur.execute(sql, params or {})
    return cur.fetchone()[0]


def new_user(cur, name):
    out = cur.var(int)
    cur.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (:u, :e, 'x') RETURNING id INTO :id",
        {"u": name, "e": name + "@test.local", "id": out},
    )
    return out.getvalue()[0]


print(f"Connecting to {DSN} as {USER} ...")
conn = oracledb.connect(user=USER, password=PASSWORD, dsn=DSN)
cur = conn.cursor()
print("Connected:", conn.version, "\n")

# clean leftovers from an earlier run
cur.execute("DELETE FROM users WHERE username LIKE 'zz_test_%'")
conn.commit()

# ---- Functional (CRUD) --------------------------------------------------
try:
    uid = new_user(cur, "zz_test_a")
    conn.commit()
    n = scalar(cur, "SELECT COUNT(*) FROM users WHERE id = :i", {"i": uid})
    record("T2", "Functional", "Create a user", n == 1, f"user id {uid}, rows found {n}")

    pid_var = cur.var(int)
    cur.execute(
        "INSERT INTO poems (title, content, user_id) VALUES ('Test poem', 'line one', :u) RETURNING id INTO :id",
        {"u": uid, "id": pid_var},
    )
    pid = pid_var.getvalue()[0]
    conn.commit()
    record("C1", "Functional", "Create a poem", scalar(cur, "SELECT COUNT(*) FROM poems WHERE id=:i", {"i": pid}) == 1,
           f"poem id {pid}")

    cur.execute("SELECT p.title, u.username FROM poems p JOIN users u ON p.user_id = u.id WHERE p.id = :i", {"i": pid})
    row = cur.fetchone()
    record("C2", "Functional", "Read a poem with a join", row == ("Test poem", "zz_test_a"), f"row {row}")

    cur.execute("UPDATE poems SET title = 'Edited', views = views + 1 WHERE id = :i", {"i": pid})
    conn.commit()
    cur.execute("SELECT title, views FROM poems WHERE id = :i", {"i": pid})
    row = cur.fetchone()
    record("C3", "Functional", "Update a poem", row == ("Edited", 1), f"row {row}")

    cur.execute("INSERT INTO likes (user_id, poem_id) VALUES (:u, :p)", {"u": uid, "p": pid})
    conn.commit()

    # ---- Constraint violations ------------------------------------------
    ok, d = expect_error(cur, conn, "INSERT INTO users (username, email, password_hash) VALUES ('zz_test_a','b@test.local','x')",
                         {}, "ORA-00001")
    record("T3", "Constraint", "Duplicate username (UNIQUE)", ok, d)

    ok, d = expect_error(cur, conn, "INSERT INTO likes (user_id, poem_id) VALUES (:u, :p)", {"u": uid, "p": pid}, "ORA-00001")
    record("T4", "Constraint", "Like the same poem twice (UNIQUE)", ok, d)

    ok, d = expect_error(cur, conn, "INSERT INTO poems (title, content, user_id) VALUES ('Orphan','x', 99999999)", {}, "ORA-02291")
    record("T7", "Constraint", "Poem with a missing user (FOREIGN KEY)", ok, d)

    ok, d = expect_error(cur, conn, "INSERT INTO users (username, email, password_hash) VALUES (NULL,'n@test.local','x')", {}, "ORA-01400")
    record("T9", "Constraint", "NULL in a required column (NOT NULL)", ok, d)

    # cascade delete
    cur.execute("DELETE FROM users WHERE id = :i", {"i": uid})
    conn.commit()
    left = scalar(cur, "SELECT (SELECT COUNT(*) FROM poems WHERE user_id=:i) + (SELECT COUNT(*) FROM likes WHERE user_id=:i) FROM dual",
                  {"i": uid})
    record("T8", "Constraint", "Delete a user, poems and likes cascade", left == 0, f"rows left for that user: {left}")
except Exception as exc:  # unexpected problem: report, keep going to cleanup
    conn.rollback()
    record("ERR", "Runner", "Unexpected error", False, repr(exc))

# ---- Error handling -----------------------------------------------------
try:
    oracledb.connect(user=USER, password=PASSWORD + "_wrong", dsn=DSN)
    record("T10", "Error", "Wrong password is refused", False, "connection was accepted")
except oracledb.DatabaseError as exc:
    got = ora_code(exc)
    record("T10", "Error", "Wrong password is refused", got == "ORA-01017", f"raised {got}")

cur.execute("DELETE FROM users WHERE username LIKE 'zz_test_%'")
conn.commit()
conn.close()

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
