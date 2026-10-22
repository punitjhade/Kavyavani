"""Database layer for Kavyavani: SQLite by default, Oracle when ORACLE_DSN is set.

The app's SQL is written once, in SQLite style (``?`` placeholders, ``LIMIT n``,
``INSERT OR IGNORE``). With Oracle, every statement goes through ``translate()``.

Oracle settings (environment variables):
    ORACLE_DSN       e.g. localhost:1521/XEPDB1
    ORACLE_USER      e.g. kavyavani
    ORACLE_PASSWORD  the schema user's password
Needs Oracle Database 12c or newer (XE 18c / 21c / 23ai) and ``pip install oracledb``.
"""
import os, re, sqlite3
from datetime import datetime

ORACLE_DSN = os.environ.get("ORACLE_DSN", "").strip()
USE_ORACLE = bool(ORACLE_DSN)

_TS_FMT = "%Y-%m-%d %H:%M:%S"


# ─── SQLite → Oracle SQL translation ─────────────────────────────────────────

_LITERAL = re.compile(r"('(?:[^']|'')*')")          # single-quoted SQL strings


def translate(sql):
    """Return (oracle_sql, is_insert, ignore_duplicates)."""
    s = sql.strip().rstrip(";").strip()

    ignore = bool(re.match(r"INSERT\s+OR\s+IGNORE\s+INTO", s, re.I))
    s = re.sub(r"^INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", s, flags=re.I)
    is_insert = bool(re.match(r"INSERT\s+INTO", s, re.I))

    # trailing "LIMIT n"  ->  FETCH FIRST n ROWS ONLY
    s = re.sub(r"\s+LIMIT\s+(\d+)\s*$", r" FETCH FIRST \1 ROWS ONLY", s, flags=re.I)

    counter = [0]

    def outside_literals(chunk):
        # DATE(col) -> text 'YYYY-MM-DD' (SQLite returns text too)
        chunk = re.sub(r"\bDATE\(\s*([\w.]+)\s*\)", r"TO_CHAR(\1,'YYYY-MM-DD')", chunk, flags=re.I)
        # aliases that are Oracle keywords: quote them (Oracle returns them upper-case, we lower-case them again)
        chunk = re.sub(r"\bAS\s+(count|day)\b", lambda m: f'AS "{m.group(1).upper()}"', chunk, flags=re.I)
        # SQLite LIKE ignores case, Oracle's does not
        chunk = re.sub(r"([\w.]+)\s+LIKE\s+\?", r"UPPER(\1) LIKE UPPER(?)", chunk, flags=re.I)

        def bind(_m):
            counter[0] += 1
            return f":{counter[0]}"
        return re.sub(r"\?", bind, chunk)

    parts = _LITERAL.split(s)
    for i in range(0, len(parts), 2):               # even parts are outside quotes
        parts[i] = outside_literals(parts[i])
    s = "".join(parts)

    if is_insert:                                    # lets us return the new id
        s += f" RETURNING id INTO :{counter[0] + 1}"
    return s, is_insert, ignore


_TS_PARAM = re.compile(r"^\d{4}-\d\d-\d\d[ T]\d\d:\d\d(:\d\d)?$")


def _param(v):
    """Oracle will not compare TIMESTAMP columns with text, so timestamp-looking text becomes datetime."""
    if isinstance(v, str) and _TS_PARAM.match(v):
        t = v.replace("T", " ")
        try:
            return datetime.strptime(t, _TS_FMT if t.count(":") == 2 else "%Y-%m-%d %H:%M")
        except ValueError:
            return v
    return v


# ─── Oracle adapter (looks like the small part of sqlite3 the app uses) ──────

class Row:
    """Read-only row: row['name'], row[0], row.keys(), dict(row) - like sqlite3.Row."""
    __slots__ = ("_d", "_t")

    def __init__(self, names, values):
        self._t = tuple(values)
        self._d = dict(zip(names, values))

    def __getitem__(self, k):
        return self._t[k] if isinstance(k, (int, slice)) else self._d[k]

    def keys(self):
        return list(self._d.keys())

    def get(self, k, default=None):
        return self._d.get(k, default)

    def __iter__(self):
        return iter(self._t)

    def __len__(self):
        return len(self._t)


class _Result:
    def __init__(self, rows, lastrowid=None):
        self._rows, self.lastrowid = rows, lastrowid

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _ora():
    try:
        import oracledb
    except ImportError as e:
        raise RuntimeError("ORACLE_DSN is set but the 'oracledb' package is missing. Run: pip install oracledb") from e
    return oracledb


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        ora = _ora()
        ora.defaults.fetch_lobs = False              # CLOB columns come back as plain str
        user, pw = os.environ.get("ORACLE_USER"), os.environ.get("ORACLE_PASSWORD")
        if not user or not pw:
            raise RuntimeError("Set ORACLE_USER and ORACLE_PASSWORD (and ORACLE_DSN) to use Oracle.")
        _pool = ora.create_pool(user=user, password=pw, dsn=ORACLE_DSN, min=1, max=8, increment=1)
    return _pool


class OracleDB:
    def __init__(self, pool, conn):
        self._pool, self.conn = pool, conn
        ora = _ora()
        self._str_types = {ora.DB_TYPE_VARCHAR, ora.DB_TYPE_NVARCHAR, ora.DB_TYPE_CHAR,
                           ora.DB_TYPE_NCHAR, ora.DB_TYPE_CLOB, ora.DB_TYPE_NCLOB, ora.DB_TYPE_LONG}

    def _row(self, cur, values):
        names = [d[0].lower() for d in cur.description]
        out = []
        for v, d in zip(values, cur.description):
            if v is None and d[1] in self._str_types:
                v = ""                               # Oracle stores '' as NULL; the app expects ''
            elif isinstance(v, datetime):
                v = v.strftime(_TS_FMT)              # the app handles timestamps as text
            elif isinstance(v, float) and v.is_integer():
                v = int(v)
            out.append(v)
        return Row(names, out)

    def execute(self, sql, args=()):
        osql, is_insert, ignore = translate(sql)
        params = [_param(a) for a in args]
        cur = self.conn.cursor()
        try:
            out = None
            if is_insert:
                out = cur.var(_ora().NUMBER)
                params.append(out)
            cur.execute(osql, params)
            if cur.description:
                return _Result([self._row(cur, r) for r in cur.fetchall()])
            lastid = None
            if out is not None:
                v = out.getvalue()
                v = v[0] if isinstance(v, list) and v else v
                lastid = int(v) if v is not None else None
            return _Result([], lastid)
        except _ora().IntegrityError:
            if ignore:                                # INSERT OR IGNORE
                return _Result([], None)
            raise
        finally:
            cur.close()

    def ddl(self, sql):
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
        finally:
            cur.close()

    def commit(self):
        self.conn.commit()

    def close(self):
        try:
            self._pool.release(self.conn)
        except Exception:
            pass


def connect(sqlite_path):
    """A connection for the current backend."""
    if USE_ORACLE:
        pool = _get_pool()
        return OracleDB(pool, pool.acquire())
    db = sqlite3.connect(sqlite_path)
    db.row_factory = sqlite3.Row
    return db


def integrity_errors():
    """Exceptions meaning 'duplicate / constraint violated' for the active backend."""
    return (_ora().IntegrityError,) if USE_ORACLE else (sqlite3.IntegrityError,)


# ─── Oracle schema (relational: primary keys, foreign keys, unique keys, indexes) ──

_ID = "id NUMBER(10) GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
_NOW = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL"

ORACLE_TABLES = [
    ("users", f"""CREATE TABLE users (
    {_ID},
    username      VARCHAR2(100 CHAR) NOT NULL UNIQUE,
    email         VARCHAR2(255 CHAR) NOT NULL UNIQUE,
    password_hash VARCHAR2(255 CHAR) NOT NULL,
    bio           CLOB,
    profile_pic   VARCHAR2(255 CHAR),
    cover_pic     VARCHAR2(255 CHAR),
    role          VARCHAR2(20 CHAR) DEFAULT 'user' NOT NULL,
    is_banned     NUMBER(1) DEFAULT 0 NOT NULL,
    poet_of_week  NUMBER(1) DEFAULT 0 NOT NULL,
    joined_at     {_NOW},
    language_pref VARCHAR2(10 CHAR) DEFAULT 'hi'
)"""),
    ("categories", f"""CREATE TABLE categories (
    {_ID},
    name        VARCHAR2(100 CHAR) NOT NULL UNIQUE,
    description VARCHAR2(500 CHAR)
)"""),
    ("poets", f"""CREATE TABLE poets (
    {_ID},
    slug          VARCHAR2(200 CHAR) NOT NULL UNIQUE,
    name          VARCHAR2(200 CHAR) NOT NULL,
    name_native   VARCHAR2(200 CHAR),
    language      VARCHAR2(20 CHAR) NOT NULL,
    born          VARCHAR2(20 CHAR),
    died          VARCHAR2(20 CHAR),
    bio           VARCHAR2(1000 CHAR),
    notable_works VARCHAR2(1300 CHAR)
)"""),
    ("poems", f"""CREATE TABLE poems (
    {_ID},
    title        VARCHAR2(500 CHAR) NOT NULL,
    content      CLOB NOT NULL,
    category     VARCHAR2(100 CHAR) DEFAULT 'सामान्य',
    language     VARCHAR2(20 CHAR) DEFAULT 'Hindi',
    theme        VARCHAR2(50 CHAR) DEFAULT 'default',
    font         VARCHAR2(50 CHAR) DEFAULT 'garamond',
    dedicated_to VARCHAR2(200 CHAR),
    user_id      NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    views        NUMBER(10) DEFAULT 0 NOT NULL,
    is_featured  NUMBER(1) DEFAULT 0 NOT NULL,
    is_draft     NUMBER(1) DEFAULT 0 NOT NULL,
    created_at   {_NOW},
    poet_id      NUMBER(10) REFERENCES poets(id) ON DELETE SET NULL
)"""),
    ("likes", f"""CREATE TABLE likes (
    {_ID},
    user_id NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    poem_id NUMBER(10) NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
    CONSTRAINT uq_likes UNIQUE (user_id, poem_id)
)"""),
    ("comments", f"""CREATE TABLE comments (
    {_ID},
    content    CLOB NOT NULL,
    user_id    NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    poem_id    NUMBER(10) NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
    parent_id  NUMBER(10) REFERENCES comments(id) ON DELETE CASCADE,
    created_at {_NOW}
)"""),
    ("follows", f"""CREATE TABLE follows (
    {_ID},
    follower_id  NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    following_id NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_follows UNIQUE (follower_id, following_id)
)"""),
    ("bookmarks", f"""CREATE TABLE bookmarks (
    {_ID},
    user_id    NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    poem_id    NUMBER(10) NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
    created_at {_NOW},
    CONSTRAINT uq_bookmarks UNIQUE (user_id, poem_id)
)"""),
    ("collections", f"""CREATE TABLE collections (
    {_ID},
    name       VARCHAR2(200 CHAR) NOT NULL,
    user_id    NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at {_NOW}
)"""),
    ("collection_poems", f"""CREATE TABLE collection_poems (
    {_ID},
    collection_id NUMBER(10) NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    poem_id       NUMBER(10) NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
    CONSTRAINT uq_collection_poems UNIQUE (collection_id, poem_id)
)"""),
    ("notifications", f"""CREATE TABLE notifications (
    {_ID},
    user_id    NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message    VARCHAR2(1000 CHAR) NOT NULL,
    link       VARCHAR2(500 CHAR),
    is_read    NUMBER(1) DEFAULT 0 NOT NULL,
    created_at {_NOW}
)"""),
    ("reports", f"""CREATE TABLE reports (
    {_ID},
    reporter_id NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    poem_id     NUMBER(10) REFERENCES poems(id) ON DELETE CASCADE,
    reason      VARCHAR2(1000 CHAR) NOT NULL,
    status      VARCHAR2(20 CHAR) DEFAULT 'pending' NOT NULL,
    created_at  {_NOW}
)"""),
    ("announcements", f"""CREATE TABLE announcements (
    {_ID},
    title       VARCHAR2(300 CHAR) NOT NULL,
    message     CLOB NOT NULL,
    admin_id    NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    schedule_at TIMESTAMP,
    created_at  {_NOW}
)"""),
    ("badges", f"""CREATE TABLE badges (
    {_ID},
    user_id   NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_key VARCHAR2(50 CHAR) NOT NULL,
    earned_at {_NOW},
    CONSTRAINT uq_badges UNIQUE (user_id, badge_key)
)"""),
    ("messages", f"""CREATE TABLE messages (
    {_ID},
    sender_id   NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id NUMBER(10) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content     CLOB,
    file_path   VARCHAR2(500 CHAR),
    file_type   VARCHAR2(50 CHAR),
    is_read     NUMBER(1) DEFAULT 0 NOT NULL,
    created_at  {_NOW}
)"""),
    ("poem_views", f"""CREATE TABLE poem_views (
    {_ID},
    poem_id   NUMBER(10) NOT NULL REFERENCES poems(id) ON DELETE CASCADE,
    viewer_id NUMBER(10) REFERENCES users(id) ON DELETE SET NULL,
    viewed_at {_NOW}
)"""),
]

ORACLE_INDEXES = [
    ("idx_poems_user",       "CREATE INDEX idx_poems_user ON poems(user_id)"),
    ("idx_poems_poet",       "CREATE INDEX idx_poems_poet ON poems(poet_id)"),
    ("idx_poems_created",    "CREATE INDEX idx_poems_created ON poems(created_at)"),
    ("idx_likes_poem",       "CREATE INDEX idx_likes_poem ON likes(poem_id)"),
    ("idx_comments_poem",    "CREATE INDEX idx_comments_poem ON comments(poem_id)"),
    ("idx_comments_parent",  "CREATE INDEX idx_comments_parent ON comments(parent_id)"),
    ("idx_follows_following", "CREATE INDEX idx_follows_following ON follows(following_id)"),
    ("idx_messages_sender",  "CREATE INDEX idx_messages_sender ON messages(sender_id)"),
    ("idx_messages_receiver", "CREATE INDEX idx_messages_receiver ON messages(receiver_id)"),
    ("idx_notif_user",       "CREATE INDEX idx_notif_user ON notifications(user_id)"),
    ("idx_poets_language",   "CREATE INDEX idx_poets_language ON poets(language)"),
]


def init_oracle(db):
    """Create any missing tables and indexes (safe to run every start)."""
    have = {r[0].lower() for r in db.execute("SELECT table_name FROM user_tables").fetchall()}
    for name, ddl in ORACLE_TABLES:
        if name not in have:
            db.ddl(ddl)
    have_idx = {r[0].lower() for r in db.execute("SELECT index_name FROM user_indexes").fetchall()}
    for name, ddl in ORACLE_INDEXES:
        if name not in have_idx:
            db.ddl(ddl)


def schema_sql():
    """The same schema as a SQL*Plus / SQL Developer script."""
    lines = ["-- Kavyavani schema for Oracle Database 12c+ (XE 18c/21c/23ai)",
             "-- Run as the application user, e.g. in SQL Developer or SQL*Plus.", ""]
    for _, ddl in ORACLE_TABLES:
        lines.append(ddl + ";\n")
    for _, ddl in ORACLE_INDEXES:
        lines.append(ddl + ";")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    os.makedirs("oracle", exist_ok=True)
    with open(os.path.join("oracle", "schema.sql"), "w", encoding="utf-8") as f:
        f.write(schema_sql())
    print("wrote oracle/schema.sql")
