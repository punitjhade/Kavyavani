"""Load poets from data/poets_*.txt into the poets table (safe to re-run).

Line format (pipe separated, '#' starts a comment):
    Name | Native name | born | died | one-line bio | work 1; work 2; work 3
The language comes from the file name: poets_hindi.txt, poets_urdu.txt, poets_english.txt
"""
import glob, os, re

BASE = os.path.dirname(os.path.abspath(__file__))


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
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
    print(f"added {added}, updated {updated}, total poets {total}")


if __name__ == "__main__":
    main()
