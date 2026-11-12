"""Fetch a web page and read the facts on it.

Standard library only (Python 3.8+), so it runs in Claude Code and in the
Claude apps without installing anything. The same file ships in several
skills; build.sh checks the copies stay identical.
"""
import gzip
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

UA = "Mozilla/5.0 (compatible; CitunaSkills/1.0; +https://github.com/cituna/cituna-skills)"
MAX_BYTES = 3_000_000
SKIP_TEXT = {"script", "style", "noscript", "template", "svg"}
CHROME = {"nav", "header", "footer", "aside"}
STOP = set(
    "a an and are as at be best by for from how in into is it its of on or our that the their this to top vs "
    "we what when which who why with you your".split()
)


def host_of(url):
    """Host in lower case without a leading www."""
    h = (urlsplit(url if "//" in url else "//" + url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def same_page(a, b):
    """True when two URLs name the same page, ignoring scheme, www, a trailing slash and the fragment."""
    def key(u):
        s = urlsplit(u)
        return (host_of(u), s.path.rstrip("/") or "/", s.query)
    return key(a) == key(b)


def _curl(url, timeout):
    if not shutil.which("curl"):
        return None
    mark = "\n__FACTS__"
    try:
        out = subprocess.run(
            ["curl", "-sL", "--compressed", "-m", str(timeout), "-A", UA, "-w", mark + "%{http_code} %{url_effective}", url],
            capture_output=True, timeout=timeout + 5,
        ).stdout
    except Exception:
        return None
    body, _, tail = out.rpartition(mark.encode())
    parts = tail.decode("utf-8", "replace").split(" ", 1)
    if len(parts) != 2 or not parts[0].isdigit():
        return None
    return {"status": int(parts[0]), "final_url": parts[1].strip(), "body": body[:MAX_BYTES], "headers": {}}


def fetch(url, timeout=20):
    """GET a URL. Returns status (0 when nothing answered), final_url, headers, body bytes and an error string."""
    res = {"url": url, "final_url": url, "status": 0, "headers": {}, "body": b"", "error": ""}
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res.update(status=r.status, final_url=r.geturl(), headers={k.lower(): v for k, v in r.headers.items()}, body=r.read(MAX_BYTES))
    except urllib.error.HTTPError as e:
        res.update(status=e.code, final_url=e.geturl() or url, headers={k.lower(): v for k, v in (e.headers or {}).items()})
        try:
            res["body"] = e.read(MAX_BYTES)
        except Exception:
            pass
    except Exception as e:  # DNS, TLS, timeout. Some Python installs lack root certificates: curl has its own.
        res["error"] = str(getattr(e, "reason", e))[:200]
        alt = _curl(url, timeout)
        if alt and alt["status"]:
            res.update(alt, error="")
    if res["body"][:2] == b"\x1f\x8b":
        try:
            res["body"] = gzip.decompress(res["body"])
        except Exception:
            pass
    return res


def text_of(res):
    """Decode a fetch result to text using the declared charset, else UTF-8."""
    m = re.search(r"charset=([\w-]+)", res["headers"].get("content-type", ""), re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", res["body"][:4000], re.I)
        enc = m.group(1).decode("ascii", "replace") if m else "utf-8"
    try:
        return res["body"].decode(enc, "replace")
    except LookupError:
        return res["body"].decode("utf-8", "replace")


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.f = {
            "lang": "", "titles": [], "descriptions": [], "robots": "", "viewport": False, "canonicals": [],
            "og": {}, "twitter_card": "", "author": "", "modified": "", "headings": [], "links": [], "images": 0,
            "images_no_alt": 0, "images_empty_alt": 0, "image_srcs": [], "quotes": 0, "tables": 0, "list_items": 0, "videos": 0, "scripts": 0, "jsonld": [],
        }
        self.text, self.main_text = [], []
        self._skip = self._chrome = 0
        self._in_title = self._in_head = False
        self._heading = self._link = self._ld = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        f = self.f
        if tag == "html":
            f["lang"] = a.get("lang", "")
        elif tag == "head":
            self._in_head = True
        elif tag == "title" and not self._skip:
            self._in_title, self._buf = True, []
        elif tag == "meta":
            name, prop, content = a.get("name", "").lower(), a.get("property", "").lower(), a.get("content", "").strip()
            if name == "description":
                f["descriptions"].append(content)
            elif name in ("robots", "googlebot"):
                f["robots"] = (f["robots"] + "," + content.lower()).strip(",")
            elif name == "viewport":
                f["viewport"] = True
            elif name == "author":
                f["author"] = content
            elif name == "twitter:card":
                f["twitter_card"] = content
            elif prop.startswith("og:"):
                f["og"].setdefault(prop[3:], content)
            elif prop == "article:modified_time" or (prop == "article:published_time" and not f["modified"]):
                f["modified"] = content
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            f["canonicals"].append(a.get("href", "").strip())
        elif tag == "script":
            f["scripts"] += 1
            if "ld+json" in a.get("type", "").lower():
                self._ld = []
            self._skip += 1
        elif tag in SKIP_TEXT:
            self._skip += 1
        elif tag in CHROME:
            self._chrome += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self._heading, self._buf = int(tag[1]), []
        elif tag == "a" and a.get("href"):
            self._link = {"href": a["href"].strip(), "text": "", "rel": a.get("rel", "").lower(), "chrome": self._chrome > 0}
        elif tag == "blockquote" and not self._chrome:
            f["quotes"] += 1
        elif tag == "img":
            f["images"] += 1
            f["image_srcs"].append((a.get("src") or a.get("data-src") or "") + " " + a.get("alt", ""))
            if "alt" not in a:
                f["images_no_alt"] += 1
            elif not a["alt"].strip():
                f["images_empty_alt"] += 1  # alt="" marks a picture as decoration
            if self._link is not None and a.get("alt"):
                self._link["text"] += " " + a["alt"]
        elif tag == "table":
            f["tables"] += 1
        elif tag == "li" and not self._chrome:
            f["list_items"] += 1
        elif tag in ("video", "iframe"):
            f["videos"] += 1

    def handle_endtag(self, tag):
        f = self.f
        if tag == "head":
            self._in_head = False
        elif tag == "title" and self._in_title:
            self._in_title = False
            f["titles"].append(" ".join("".join(self._buf).split()))
        elif tag == "script":
            if self._ld is not None:
                f["jsonld"].append("".join(self._ld))
                self._ld = None
            self._skip = max(0, self._skip - 1)
        elif tag in SKIP_TEXT:
            self._skip = max(0, self._skip - 1)
        elif tag in CHROME:
            self._chrome = max(0, self._chrome - 1)
        elif re.fullmatch(r"h[1-6]", tag) and self._heading:
            t = " ".join("".join(self._buf).split())
            f["headings"].append({"level": self._heading, "text": t, "chrome": self._chrome > 0})
            self._heading = None
        elif tag == "a" and self._link is not None:
            self._link["text"] = " ".join(self._link["text"].split())
            f["links"].append(self._link)
            self._link = None

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
            return
        if self._in_title:
            self._buf.append(data)
            return
        if self._skip:
            return
        if self._heading:
            self._buf.append(data)
        if self._link is not None:
            self._link["text"] += data
        self.text.append(data)
        if not self._chrome:
            self.main_text.append(data)


def _walk_ld(node, types, facts):
    if isinstance(node, list):
        for n in node:
            _walk_ld(n, types, facts)
    elif isinstance(node, dict):
        t = node.get("@type")
        for x in t if isinstance(t, list) else [t]:
            if isinstance(x, str) and x not in types:
                types.append(x)
        for k in ("dateModified", "datePublished"):
            if isinstance(node.get(k), str) and (k == "dateModified" or not facts.get("modified")):
                facts["modified"] = node[k]
        au = node.get("author")
        au = au[0] if isinstance(au, list) and au else au
        if isinstance(au, dict) and isinstance(au.get("name"), str) and not facts.get("author"):
            facts["author"] = au["name"]
        for v in node.values():
            if isinstance(v, (dict, list)):
                _walk_ld(v, types, facts)


def read_html(html, url):
    """Parse one page's HTML into a flat dict of facts."""
    p = _Reader()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    f = p.f
    text = " ".join(" ".join(p.text).split())
    main = " ".join(" ".join(p.main_text).split())
    types = []
    for block in f["jsonld"]:
        try:
            _walk_ld(json.loads(block), types, f)
        except Exception:
            pass
    host = host_of(url)
    internal, external = [], []
    for l in f["links"]:
        href = l["href"]
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full = urljoin(url, href).split("#")[0]
        if not full.startswith("http"):
            continue
        (internal if host_of(full) == host else external).append({"url": full, "text": l["text"], "chrome": l["chrome"]})
    body_heads = [h for h in f["headings"] if not h["chrome"]]
    return {
        "url": url,
        "lang": f["lang"],
        "title": f["titles"][0] if f["titles"] else "",
        "title_count": len(f["titles"]),
        "description": f["descriptions"][0] if f["descriptions"] else "",
        "description_count": len(f["descriptions"]),
        "robots": f["robots"],
        "viewport": f["viewport"],
        "canonicals": [urljoin(url, c) for c in f["canonicals"] if c],
        "og_image": f["og"].get("image", ""),
        "og_title": f["og"].get("title", ""),
        "twitter_card": f["twitter_card"],
        "author": f["author"],
        "modified": f["modified"][:10] if re.match(r"\d{4}-\d{2}-\d{2}", f["modified"]) else f["modified"][:30],
        "h1": [h["text"] for h in f["headings"] if h["level"] == 1 and h["text"]],
        "h2": [h["text"] for h in body_heads if h["level"] == 2 and h["text"]],
        "h3": [h["text"] for h in body_heads if h["level"] == 3 and h["text"]],
        "words": len(main.split()) if len(main.split()) >= 30 else len(text.split()),
        "text": text,
        "main_text": main,  # the text outside the site's menu, header, footer and sidebars
        "images": f["images"],
        "images_no_alt": f["images_no_alt"],
        "images_empty_alt": f["images_empty_alt"],
        "app_root": bool(re.search(r"<div[^>]+id=[\"'](root|app|__next|__nuxt)[\"'][^>]*>\s*</div>", html)),
        # pictures that carry content: one per address, without logos, icons, avatars and inline placeholders
        "pictures": len({x.split(" ")[0] for x in f["image_srcs"]
                         if x.strip() and not x.startswith("data:") and not re.search(r"logo|icon|avatar|sprite|badge", x, re.I)}),
        "quotes": f["quotes"],
        "tables": f["tables"],
        "list_items": f["list_items"],
        "videos": f["videos"],
        "scripts": f["scripts"],
        "schema_types": types,
        "mailtos": sorted({l["href"][7:].split("?")[0] for l in f["links"] if l["href"].lower().startswith("mailto:")} - {""}),
        "internal_links": internal,
        "external_links": external,
    }


def page(url, timeout=20):
    """Fetch and read one page. Adds status, final_url, redirected, error and the X-Robots-Tag header."""
    res = fetch(url, timeout)
    facts = read_html(text_of(res), res["final_url"]) if res["body"] else read_html("", url)
    facts.update(
        requested=url, status=res["status"], final_url=res["final_url"], error=res["error"],
        redirected=not same_page(url, res["final_url"]),
        x_robots=res["headers"].get("x-robots-tag", "").lower(),
    )
    return facts


def topic_words(s):
    """Lower-case words that carry meaning, for comparing a title with a heading."""
    return {w for w in re.findall(r"[^\W_]{3,}", s.lower()) if w not in STOP}
