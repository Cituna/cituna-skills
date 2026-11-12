#!/usr/bin/env python3
"""Open the pages AI assistants read for a question and say, for each, whether your business is on it
and where to ask to be added.

    python3 sources.py --brand "Acme" --domain acme.example --answers ai-answers.json --rivals "Rival One, Rival Two"
    python3 sources.py --brand "Acme" --domain acme.example --answers ai-answers.json URL [URL ...]
    python3 sources.py --brand "Acme" --domain acme.example URL [URL ...]

Pages named in --answers count as read by an answer. Addresses given directly (or in --file) are extra
pages, such as search results, and are marked as such. Standard library only. One request a second.

It reads each page once, as served, and matches patterns, so it can be wrong: a page that has moved, a
link that goes through the site's own redirect, a name that sits only in a menu. It says when it sees
one of these. Open the pages you plan to act on. A page that cannot be read is never reported as a gap.
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from urllib.parse import urlsplit

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import pagefacts as pf  # noqa: E402

KINDS = [
    ("forum", r"(^|\.)(reddit|quora|stackexchange|stackoverflow)\.com$|news\.ycombinator\.com$|(^|\.)indiehackers\.com$"),
    ("review site", r"(^|\.)(g2|capterra|trustpilot|trustradius|getapp|softwareadvice|producthunt|yelp|tripadvisor|clutch|sitejabber|gartner)\.(com|co)$"),
    ("video", r"(^|\.)(youtube|vimeo|tiktok)\.com$|^youtu\.be$"),
    ("encyclopedia", r"(^|\.)wikipedia\.org$"),
    ("social", r"(^|\.)(linkedin|facebook|instagram|x|twitter|medium|substack)\.com$"),
]
LISTY = re.compile(r"\b(best|top \d+|\d+ best|alternatives?|vs\.?|versus|compared?|comparison|review(s|ed)?|ranked|roundup)\b", re.I)
ASK = re.compile(
    r"^(contact( us)?|about( us)?|about the author|write for us|contribut\w*|submit[\w ]{0,25}|advertis\w*( with us)?|"
    r"add (your|a) [\w ]{1,25}|suggest[\w ]{0,25}|get listed|list your [\w ]{1,25}|claim[\w ]{0,25}|editorial[\w ]{0,20}|press|corrections?)$", re.I)
PERSON = re.compile(r"^[A-Z][\w.'-]+( [A-Z][\w.'-]+){1,3}$")

HOW = {
    "forum": "Answer the thread yourself, honestly and as the business. Say who you are. Never post through other accounts.",
    "review site": "Claim or create your free profile, fill it in, and ask real customers for reviews.",
    "video": "You cannot be added to this one. Offer the creator a demo or a free account for their next video.",
    "encyclopedia": "Not a place to add yourself. Leave it.",
    "social": "Reply as the business where it helps the reader. Low priority.",
    "list": "Email the author with one line: what you do, who it is for, and the one fact that earns a place on the list.",
    "directory": "Check whether the site already has a profile for you to claim. If not, use its submit or add-a-listing form.",
    "article": "Email the author or editor: offer a fact, a number or a quote that improves the article, and say where you fit.",
}
NOT_TARGETS = ("rival's own site", "your own site", "a copy of your own page", "encyclopedia")
MENU = "named only in the site's menu or footer"
ORDER = {"not on the page": 0, "named, no link": 1, MENU: 2, "named, linked indirectly": 3,
         "linked": 4, "moved": 5, "unread": 6}


def squash(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def page_key(url):
    """One key per page: no scheme, www, trailing slash or fragment."""
    s = urlsplit(url)
    return pf.host_of(url) + (s.path.rstrip("/") or "/") + ("?" + s.query if s.query else "")


def named(text, name):
    """A whole-word match in the spelling given. A name typed in lower case matches any case; a capitalised
    one must be capitalised on the page, so a brand called Plausible is not found in 'a plausible choice'."""
    return re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text, re.I if name == name.lower() else 0) is not None


def is_rival_site(host, rival_hosts, rival_names):
    if any(host == h or host.endswith("." + h) for h in rival_hosts):
        return True
    label = squash(host.rsplit(".", 1)[0])
    return any(len(squash(n)) >= 4 and squash(n) in label for n in rival_names)


def kind_of(host, title, url, f, own, rival_hosts, rival_names):
    if host == own or host.endswith("." + own):
        return "your own site"
    if any(pf.host_of(c) == own or pf.host_of(c).endswith("." + own) for c in f["canonicals"]):
        return "a copy of your own page"
    if is_rival_site(host, rival_hosts, rival_names):
        return "rival's own site"
    for name, rx in KINDS:
        if re.search(rx, host):
            return name
    path = urlsplit(url).path
    if re.search(r"director(y|ies)|listing", path + " " + title, re.I):
        return "directory"
    if LISTY.search(title) or LISTY.search(path.replace("-", " ")):
        return "list"
    if re.search(r"/(tools?|apps?|products?|software|companies|startups)/[^/]+/?$", path):
        return "directory"
    return "article"


def check(url, brand_names, domain, rival_names, rival_hosts):
    f = pf.page(url)
    if f["status"] == 421 and not urlsplit(url).netloc.startswith("www."):  # the bare host is not served: try www
        s = urlsplit(url)
        f = pf.page(f"{s.scheme}://www.{s.netloc}{s.path}" + (f"?{s.query}" if s.query else ""))
    final = f["final_url"] or url
    host, own = pf.host_of(final), pf.host_of(domain)
    row = {"url": url, "host": pf.host_of(url), "status": f["status"], "title": f["title"], "dated": f["modified"], "author": f["author"]}
    row["kind"] = kind_of(pf.host_of(url), f["title"], url, f, own, rival_hosts, rival_names)
    asked, got = urlsplit(url), urlsplit(final)
    if f["status"] == 200 and (host != pf.host_of(url) or (asked.path.strip("/") and not got.path.strip("/"))):
        row.update(you="moved", note=f"the address now leads to {final}, so the page that was read is gone")
        return row
    if f["status"] != 200 or f["words"] < 80:
        row.update(you="unread", note=f"HTTP {f['status']}" if f["status"] else (f["error"] or "no answer"))
        if f["status"] == 200:
            row["note"] = f"only {f['words']} words came back (the page may load its text with scripts or refuse automated reads)"
        return row
    row["same_as"] = page_key(f["canonicals"][0]) if f["canonicals"] else page_key(final)
    links = f["external_links"] + f["internal_links"]
    slugs = [squash(n) for n in brand_names if len(squash(n)) >= 4]
    direct = [l for l in links if pf.host_of(l["url"]) == own or pf.host_of(l["url"]).endswith("." + own)]
    indirect = [l for l in links if not l["chrome"] and l not in direct
                and (any(named(l["text"], n) for n in brand_names) or any(s in squash(urlsplit(l["url"]).path) for s in slugs))]
    if direct:
        row["you"] = "linked"
    elif any(named(f["main_text"], n) for n in brand_names):
        row["you"] = "named, linked indirectly" if indirect else "named, no link"
        if indirect:
            row["note"] = f"a link on your name goes to {indirect[0]['url']}: open it to see whether it reaches your site"
    elif any(named(f["text"], n) for n in brand_names):
        row["you"] = MENU
    else:
        row["you"] = "not on the page"
    row["rivals_named"] = [r for r in rival_names if named(f["main_text"], r)]
    routes, seen = [], set()
    for l in f["internal_links"]:
        text, key = l["text"].strip(), l["url"].rstrip("/")
        is_author = bool(re.search(r"/authors?/", l["url"])) and not l["chrome"] and (text == f["author"] or PERSON.match(text))
        if (ASK.match(text) or is_author) and key not in seen:
            seen.add(key)
            routes.append({"text": ("author page: " if is_author else "") + text, "url": l["url"]})
    row["contact"] = {"emails": f["mailtos"][:3], "links": routes[:5]}
    row["how"] = HOW.get(row["kind"], "")
    return row


def from_answers(path):
    """{page key: (url, set of answer numbers)} for every page the collected answers read."""
    data = json.load(open(path, encoding="utf-8"))
    pages = {}
    for i, a in enumerate(data.get("answers", [])):
        for u in a.get("sources") or re.findall(r"https?://[^\s)\]>\"']+", a.get("text", "")):
            u = u.rstrip(".,;")
            pages.setdefault(page_key(u), (u, set()))[1].add(i)
    return pages, len(data.get("answers", []))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="extra pages to check, such as search results")
    ap.add_argument("--brand", required=True, help="your business name as it is written; separate other spellings with commas")
    ap.add_argument("--domain", required=True, help="your website, e.g. acme.example")
    ap.add_argument("--rivals", default="", help="rival names, comma separated; their websites too if the name is not in the address")
    ap.add_argument("--answers", help="ai-answers.json from the answers you collected: reads every page they read")
    ap.add_argument("--file", help="a text file of extra pages, one address per line")
    ap.add_argument("--max", type=int, default=60, help="read at most this many pages (default 60)")
    ap.add_argument("--json", help="also write the result to this file")
    a = ap.parse_args()

    pages, n_answers = from_answers(a.answers) if a.answers else ({}, 0)
    for u in a.urls + ([l.strip() for l in open(a.file, encoding="utf-8") if l.strip()] if a.file else []):
        pages.setdefault(page_key(u), (u, set()))
    if not pages:
        ap.error("no addresses: pass them, or --answers, or --file")
    brand_names = [b.strip() for b in a.brand.split(",") if b.strip()]
    rivals = [r.strip() for r in a.rivals.split(",") if r.strip()]
    rival_hosts = {pf.host_of(r) for r in rivals if "." in r and " " not in r}
    rival_names = [r for r in rivals if pf.host_of(r) not in rival_hosts or " " in r]

    site_answers = defaultdict(set)
    for u, who in pages.values():
        site_answers[pf.host_of(u)] |= who
    ordered = sorted(pages.values(), key=lambda p: (-len(site_answers[pf.host_of(p[0])]), -len(p[1])))[: a.max]

    rows, seen_pages, merged = [], set(), 0
    for i, (u, who) in enumerate(ordered):
        if i:
            time.sleep(1.0)
        row = check(u, brand_names, a.domain, rival_names, rival_hosts)
        row["answers"], row["site_answers"] = len(who), len(site_answers[row["host"]])
        if row.get("same_as") in seen_pages:  # the same page under a second address
            merged += 1
            continue
        seen_pages.add(row.get("same_as"))
        rows.append(row)
        print(f"  read {i + 1}/{len(ordered)}", file=sys.stderr, end="\r")
    rows.sort(key=lambda r: (ORDER[r["you"]], -r["site_answers"], r["host"]))

    def reach(r):
        return f"{r['site_answers']} of {n_answers}" if r["site_answers"] else "search result only"

    print(f"# The pages AI read, and whether {brand_names[0]} is on them\n")
    hosts = {r["host"] for r in rows}
    count = lambda v: sum(1 for r in rows if r["you"] == v)
    print(f"Scope: {len(rows)} pages on {len(hosts)} sites" + (f" ({merged} more were the same page under another address)" if merged else "")
          + (f" (of {len(pages)} found; raise --max to read the rest)" if len(pages) > len(ordered) else "")
          + (f", from {n_answers} answers" if n_answers else "") + ". "
          + " ".join(f"{label}: {count(v)}." for label, v in [
              ("Not on the page", "not on the page"), ("Named without a link", "named, no link"), ("Named only in a menu or footer", MENU),
              ("Linked indirectly", "named, linked indirectly"), ("Linked", "linked"), ("Moved", "moved"), ("Could not be read", "unread")]) + "\n")
    print("| Site | Kind | Answers that read the site | You | Rivals on it | Page |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['host']} | {r['kind']} | {reach(r)} | {r['you']} | {', '.join(r.get('rivals_named', [])) or '-'} | {r['url']} |")

    targets = [r for r in rows if r["you"] in ("not on the page", "named, no link", "named, linked indirectly") and r["kind"] not in NOT_TARGETS]
    if targets:
        print(f"\n## Where to ask: {len(targets)} pages\nSites more answers read come first. Rivals' own sites and your own pages are left out.")
        for r in targets[:20]:
            print(f"\n### {r['host']} ({r['kind']}; {reach(r)})\n{r['url']}")
            print(f"- Title: {r['title'] or 'none'}" + (f" (dated {r['dated']})" if r["dated"] else "") + (f", by {r['author']}" if r["author"] else ""))
            print(f"- You: {r['you']}." + (f" Rivals on it: {', '.join(r['rivals_named'])}." if r.get("rivals_named") else "")
                  + (f" Note: {r['note']}." if r.get("note") else ""))
            print(f"- How: {r['how']}")
            c = r["contact"]
            if c["emails"] or c["links"]:
                print("- Where: " + "; ".join(c["emails"] + [f"{l['text']} ({l['url']})" for l in c["links"]]))
            else:
                print("- Where: no contact route found on the page.")
        if len(targets) > 20:
            print(f"\nand {len(targets) - 20} more in the table above.")
    skipped = [r for r in rows if r["you"] in ("moved", "unread")]
    if skipped:
        print("\n## Moved or could not be read\nOpen these yourself. None of them counts as a page you are missing from.")
        for r in skipped:
            print(f"- {r['url']}: {r['note']}")
    if a.json:
        json.dump({"answers": n_answers, "pages": rows}, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
