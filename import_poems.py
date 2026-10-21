"""Import poems you have the rights to into Kavyavani.

Put one poem per .txt file under data/poems/<poet-slug>/ (slug = poet page URL,
e.g. data/poems/mirza-ghalib/ghazal-1.txt). File format:

    title: <poem title>
    category: <optional, default सामान्य>
    ---
    <poem text, exactly as you want it displayed>

Run:  python import_poems.py          (add --dry-run to only check)
Re-running is safe: a poem with the same poet and title is skipped.
Poems are published under a 'library' user so they don't mix with member poems.
"""
import glob, os, sqlite3, sys
from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, "sukhan.db")


def parse(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    if "\n---" not in raw:
        raise ValueError("missing '---' separator")
    head, body = raw.split("\n---", 1)
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    if not meta.get("title"):
        raise ValueError("missing title")
    return meta["title"], meta.get("category", "सामान्य"), body.strip("\n")


def main():
    dry = "--dry-run" in sys.argv
    import app
    app.init_db()
    db = sqlite3.connect(DB)
    row = db.execute("SELECT id FROM users WHERE username='library'").fetchone()
    if not row and not dry:
        db.execute("INSERT INTO users (username,email,password_hash,role,bio) VALUES (?,?,?,?,?)",
                   ("library", "library@kavyavani.local", generate_password_hash(os.urandom(16).hex()),
                    "user", "Poems from the Kavyavani library"))
        db.commit()
        row = db.execute("SELECT id FROM users WHERE username='library'").fetchone()
    uid = row[0] if row else 0

    added = skipped = bad = 0
    for path in sorted(glob.glob(os.path.join(BASE, "data", "poems", "*", "*.txt"))):
        slug = os.path.basename(os.path.dirname(path))
        poet = db.execute("SELECT id, language FROM poets WHERE slug=?", (slug,)).fetchone()
        if not poet:
            print(f"unknown poet folder '{slug}' -> run seed_poets.py or fix the folder name"); bad += 1; continue
        try:
            title, category, content = parse(path)
        except ValueError as e:
            print(f"{path}: {e}"); bad += 1; continue
        if db.execute("SELECT 1 FROM poems WHERE poet_id=? AND title=?", (poet[0], title)).fetchone():
            skipped += 1; continue
        if not dry:
            db.execute("INSERT INTO poems (title,content,category,language,user_id,poet_id) VALUES (?,?,?,?,?,?)",
                       (title, content, category, poet[1], uid, poet[0]))
        added += 1
    if not dry:
        db.commit()
    print(f"{'would add' if dry else 'added'} {added}, skipped {skipped}, problems {bad}")


if __name__ == "__main__":
    main()
