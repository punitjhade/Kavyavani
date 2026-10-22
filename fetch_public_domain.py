"""Download public-domain poems from Wikisource into data/poems/<poet-slug>/*.txt

Run this on your own computer (it needs internet access), then run import_poems.py.

    python fetch_public_domain.py                 # every poet listed in data/sources.txt
    python fetch_public_domain.py william-blake   # only one poet
    python fetch_public_domain.py --max 40        # up to 40 poems per poet (default 25)

data/sources.txt line format (pipe separated, '#' = comment):
    poet-slug | wikisource language code | Author page title
e.g.  john-keats | en | Author:John Keats

Only add poets whose work is in the public domain in your country. Each fetched
poem is saved with its Wikisource page title so you can check the source later.
Standard library only; one request at a time with a short pause between requests.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "KavyavaniPoemFetcher/1.0 (educational poetry site; contact: site owner)"}
PAUSE = 2.5


def api(lang, **params):
    """One API call. On HTTP 429/503 it waits (Retry-After, else growing delays) and retries."""
    params["format"] = "json"
    url = f"https://{lang}.wikisource.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(PAUSE)
            return data
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == 7:
                raise
            try:
                wait = int(e.headers.get("Retry-After", ""))
            except (TypeError, ValueError):
                wait = min(10 * 2 ** attempt, 300)
            print(f"    rate limited, waiting {wait}s then retrying...")
            time.sleep(wait)


class PoemExtractor(HTMLParser):
    """Collects the text inside <div class="poem"> blocks, keeping line breaks."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # nesting depth inside a poem div (0 = outside)
        self.out = []
        self.skip = 0           # inside <sup>/<style>/<script> etc.

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "") or ""
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "poem" in cls.split():
                self.depth = 1
        elif self.depth:
            if tag in ("sup", "style", "script"):
                self.skip += 1
            elif tag == "br":
                self.out.append("\n")
            elif tag == "p":
                self.out.append("\n")

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self.out.append("\n\n")
        elif self.depth and tag in ("sup", "style", "script") and self.skip:
            self.skip -= 1
        elif self.depth and tag == "p":
            self.out.append("\n")

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.out.append(data)


class ParagraphExtractor(HTMLParser):
    """Fallback for pages without <div class="poem">: text of <p>/<dd>/<br>, skipping tables, notes and navigation."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("table", "sup", "style", "script", "ul", "ol", "h2", "h3"):
            self.skip += 1
        elif not self.skip and tag in ("br", "p", "dd", "div"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("table", "sup", "style", "script", "ul", "ol", "h2", "h3"):
            self.skip = max(0, self.skip - 1)
        elif not self.skip and tag in ("p", "dd"):
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def _clean(text):
    text = text.replace("\xa0", " ")
    text = "\n".join(ln.strip() for ln in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def poem_text(html):
    p = PoemExtractor()
    p.feed(html)
    text = _clean("".join(p.out))
    if text:
        return text
    # Fallback (common on Hindi/Urdu Wikisource): accept only if it looks like verse, i.e. short lines
    q = ParagraphExtractor()
    q.feed(html)
    text = _clean("".join(q.out))
    lines = [l for l in text.splitlines() if l.strip()]
    if lines and sum(len(l) for l in lines) / len(lines) <= 70:
        return text
    return ""


def resolve_author(lang, name):
    """'Author:John Keats' is used as given. A plain name (e.g. in Devanagari or Urdu script) is
    looked up in the wiki's own Author namespace, whatever it is called in that language."""
    if ":" in name and name.split(":", 1)[0].strip() in ("Author", "Page"):
        return name
    ns = api(lang, action="query", meta="siteinfo", siprop="namespaces")["query"]["namespaces"]
    ns_id = next((int(k) for k, v in ns.items() if v.get("canonical") == "Author"), 102)
    hits = api(lang, action="query", list="search", srsearch=name, srnamespace=ns_id, srlimit=5)["query"]["search"]
    return hits[0]["title"] if hits else None


def author_links(lang, author_title):
    """Main-namespace pages linked from the author page."""
    data = api(lang, action="parse", page=author_title, prop="links")
    links = data.get("parse", {}).get("links", [])
    titles = [l["*"] for l in links if l.get("ns") == 0 and l.get("exists") is not None]
    seen, out = set(), []
    for t in titles:
        if t not in seen:
            seen.add(t); out.append(t)
    return out


def safe_name(title):
    n = re.sub(r"[^\w\-]+", "-", title, flags=re.U).strip("-").lower()
    return (n or "poem")[:80]


def fetch_poet(slug, lang, author, max_poems):
    folder = os.path.join(BASE, "data", "poems", slug)
    os.makedirs(folder, exist_ok=True)
    saved = 0
    try:
        page = resolve_author(lang, author)
        if not page:
            print(f"  {slug}: no author page found for '{author}' on {lang}.wikisource.org")
            return 0
        titles = author_links(lang, page)
    except Exception as e:
        print(f"  {slug}: could not read '{author}' on {lang}.wikisource.org ({e})")
        return 0
    for title in titles:
        if saved >= max_poems:
            break
        path = os.path.join(folder, safe_name(title) + ".txt")
        if os.path.exists(path):
            saved += 1
            continue
        try:
            data = api(lang, action="parse", page=title, prop="text", redirects=1)
            html = data["parse"]["text"]["*"]
        except Exception:
            continue
        text = poem_text(html)
        n = len([l for l in text.splitlines() if l.strip()])
        if n < 4 or n > 150:     # skip non-poems, indexes and very long works
            continue
        shown = title.split("/")[-1]
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"title: {shown}\ncategory: सामान्य\nsource: {lang}.wikisource.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}\n---\n{text}\n")
        saved += 1
    print(f"  {slug}: {saved} poems")
    return saved


def main():
    args = sys.argv[1:]
    max_poems = 25
    if "--max" in args:
        i = args.index("--max"); max_poems = int(args[i + 1]); del args[i:i + 2]
    only = set(args)
    src = os.path.join(BASE, "data", "sources.txt")
    total = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3:
                continue
            slug, lang, author = parts
            if only and slug not in only:
                continue
            total += fetch_poet(slug, lang, author, max_poems)
    print(f"done: {total} poems in data/poems/. Now run: python import_poems.py")


if __name__ == "__main__":
    main()
