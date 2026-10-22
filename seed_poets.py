"""Load poets from data/poets_*.txt into the poets table (safe to re-run).

Line format (pipe separated, '#' starts a comment):
    Name | Native name | born | died | one-line bio | work 1; work 2; work 3
The language comes from the file name: poets_hindi.txt, poets_urdu.txt, poets_english.txt
"""
<<<<<<< HEAD
import glob, os, re, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, "sukhan.db")
=======
import glob, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
>>>>>>> origin/oracle-update


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
<<<<<<< HEAD
    import app  # makes sure tables exist
    app.init_db()
    db = sqlite3.connect(DB)
    added = updated = 0
    for path in sorted(glob.glob(os.path.join(BASE, "data", "poets_*.txt"))):
        language = os.path.basename(path)[6:-4].capitalize()
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) != 6:
                    print(f"skip {os.path.basename(path)}:{n} (expected 6 fields)")
                    continue
                name, native, born, died, bio, works = parts
                slug = slugify(name)
                cur = db.execute("SELECT id FROM poets WHERE slug=?", (slug,)).fetchone()
                if cur:
                    db.execute("UPDATE poets SET name=?,name_native=?,language=?,born=?,died=?,bio=?,notable_works=? WHERE id=?",
                               (name, native, language, born, died, bio, works, cur[0]))
                    updated += 1
                else:
                    db.execute("INSERT INTO poets (slug,name,name_native,language,born,died,bio,notable_works) VALUES (?,?,?,?,?,?,?,?)",
                               (slug, name, native, language, born, died, bio, works))
                    added += 1
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM poets").fetchone()[0]
=======
    import app  # picks SQLite or Oracle exactly like the website does
    app.init_db()
    added = updated = 0
    with app.app.app_context():
        for path in sorted(glob.glob(os.path.join(BASE, "data", "poets_*.txt"))):
            language = os.path.basename(path)[6:-4].capitalize()
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) != 6:
                        print(f"skip {os.path.basename(path)}:{n} (expected 6 fields)")
                        continue
                    name, native, born, died, bio, works = parts
                    slug = slugify(name)
                    cur = app.query("SELECT id FROM poets WHERE slug=?", (slug,), one=True)
                    if cur:
                        app.execute("UPDATE poets SET name=?,name_native=?,language=?,born=?,died=?,bio=?,notable_works=? WHERE id=?",
                                    (name, native, language, born, died, bio, works, cur["id"]))
                        updated += 1
                    else:
                        app.execute("INSERT INTO poets (slug,name,name_native,language,born,died,bio,notable_works) VALUES (?,?,?,?,?,?,?,?)",
                                    (slug, name, native, language, born, died, bio, works))
                        added += 1
        total = app.query("SELECT COUNT(*) AS c FROM poets", one=True)["c"]
>>>>>>> origin/oracle-update
    print(f"added {added}, updated {updated}, total poets {total}")


if __name__ == "__main__":
    main()
