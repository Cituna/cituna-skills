#!/usr/bin/env python3
"""Check a website's own pages: titles, headings, canonical tags, the sitemap, and robots.txt,
including whether AI crawlers are shut out.

    python3 audit.py example.com                 # home page plus a spread of 25 sitemap pages
    python3 audit.py example.com --pages 60      # a bigger sample (one request a second)
    python3 audit.py --html saved-page.html --url https://example.com/pricing    # no network: a saved page

Standard library only. Writes the report to the screen; --json FILE also saves every finding.
"""
import argparse
import datetime
import json
import re
import sys
import time
from collections import Counter, defaultdict
from urllib.parse import urlsplit

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import pagefacts as pf  # noqa: E402

# The readers each AI assistant sends when a person asks it a question, and the search crawlers behind them.
ANSWER_BOTS = [
    ("Googlebot", "Google Search and Google's AI answers"),
    ("Bingbot", "Bing, and the index ChatGPT and Copilot search"),
    ("OAI-SearchBot", "ChatGPT search"),
    ("ChatGPT-User", "ChatGPT opening a page for a user"),
    ("PerplexityBot", "Perplexity"),
    ("Perplexity-User", "Perplexity opening a page for a user"),
    ("Claude-SearchBot", "Claude search"),
    ("Claude-User", "Claude opening a page for a user"),
]
# Crawlers that collect text to train models. Blocking them is the owner's choice and does not change search.
TRAINING_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Applebot-Extended", "Bytespider", "meta-externalagent"]

FIRST, WORTH, ASK, FYI = "Fix first", "Worth fixing", "Check with the owner", "Good to know"


def parse_robots(txt):
    groups, sitemaps, agents, last_was_agent = [], [], None, False
    for raw in txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "sitemap":
            sitemaps.append(val)
        elif key == "user-agent":
            if not last_was_agent:
                agents = {"agents": [], "rules": []}
                groups.append(agents)
            agents["agents"].append(val.lower())
            last_was_agent = True
            continue
        elif key in ("allow", "disallow") and agents is not None:
            agents["rules"].append((key, val))
        last_was_agent = False
    return {"groups": groups, "sitemaps": sitemaps}


def _rule_matches(pattern, path):
    rx = re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.match(rx, path) is not None


def allowed(robots, bot, path="/"):
    """Google's rules: the most specific user-agent group applies, the longest matching rule wins, allow wins a tie."""
    bot = bot.lower()
    named = [g for g in robots["groups"] if any(a != "*" and a in bot for a in g["agents"])]
    groups = named or [g for g in robots["groups"] if "*" in g["agents"]]
    best = (-1, True)
    for g in groups:
        for kind, pat in g["rules"]:
            if pat and _rule_matches(pat, path):
                cand = (len(pat), kind == "allow")
                if cand[0] > best[0] or (cand[0] == best[0] and cand[1]):
                    best = cand
    return best[1]


def read_sitemaps(start, delay, limit_files=20, limit_urls=50000):
    files, entries, queue, seen = [], [], list(start), set()
    while queue and len(files) < limit_files and len(entries) < limit_urls:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        res = pf.fetch(u)
        xml = pf.text_of(res) if res["body"] else ""
        locs = [m.replace("&amp;", "&").strip() for m in re.findall(r"<loc>\s*(?:<!\[CDATA\[)?([^<\]]+)", xml)]
        if re.search(r"<sitemapindex", xml, re.I):
            files.append({"url": u, "status": res["status"], "index": True, "children": len(locs)})
            queue.extend(locs)
        else:
            rows = []
            for block in re.findall(r"<url>([\s\S]*?)</url>", xml):
                loc = re.search(r"<loc>\s*(?:<!\[CDATA\[)?([^<\]]+)", block)
                mod = re.search(r"<lastmod>\s*([^<]+?)\s*</lastmod>", block)
                if loc:
                    rows.append({"url": loc.group(1).replace("&amp;", "&").strip(), "lastmod": mod.group(1) if mod else ""})
            files.append({"url": u, "status": res["status"], "urls": len(rows), "parsed": bool(re.search(r"<urlset", xml, re.I))})
            entries.extend(rows)
        if queue:
            time.sleep(delay)
    return files, entries[:limit_urls], bool(queue)


def section_of(url):
    return urlsplit(url).path.strip("/").split("/")[0]


def pick_pages(home, entries, n):
    """The home page, then one page from each section in turn, biggest sections first, so every part of the
    site is sampled before any part is sampled twice. Returns the pages and the sections left unread."""
    sections = defaultdict(list)
    for e in entries:
        if not pf.same_page(e["url"], home):
            sections[section_of(e["url"])].append(e["url"])
    lists = sorted(sections.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    picked, i = [home], 0
    while len(picked) < n and any(i < len(l) for _, l in lists):
        for _, l in lists:
            if i < len(l) and len(picked) < n:
                picked.append(l[i])
        i += 1
    read = {section_of(u) for u in picked[1:]}
    return picked, [(name, len(l)) for name, l in lists if name not in read]


class Report:
    def __init__(self):
        self.items = []

    def add(self, tier, what, why, fix, hits, scope):
        """hits: list of (url, detail). Nothing is recorded when the list is empty."""
        if hits:
            self.items.append({"tier": tier, "what": what, "why": why, "fix": fix, "count": len(hits), "of": scope,
                               "examples": [{"url": u, "detail": d} for u, d in hits[:5]], "all": [u for u, _ in hits]})


def check_pages(pages, rep, from_sitemap):
    ok = [p for p in pages if p["status"] == 200]
    n = len(pages)
    listed = "the sitemap lists" if from_sitemap else "the site links to"
    rep.add(FIRST, f"Pages that do not load ({listed} them)", "A broken page cannot be shown by Google or read by an AI assistant.",
            "Restore the page, or redirect its address to the closest live page and take it out of the sitemap.",
            [(p["requested"], f"HTTP {p['status']}" if p["status"] else (p["error"] or "no answer")) for p in pages if p["status"] != 200], n)
    rep.add(WORTH, "Addresses that redirect somewhere else", "Every signal should point at one address per page.",
            "List and link the final address.",
            [(p["requested"], f"-> {p['final_url']}") for p in ok if p["redirected"]], n)
    m = len(ok)
    noindex = [p for p in ok if "noindex" in p["robots"] or "noindex" in p["x_robots"]]
    rep.add(ASK, "Pages marked 'noindex'" + (" that the sitemap lists" if from_sitemap else ""),
            "A noindex page is left out of Google and of Google's AI answers"
            + (", yet the sitemap is the list of pages you want found: the two disagree." if from_sitemap else "."),
            "If the page is meant to be hidden, take it out of the sitemap. If not, remove the noindex tag.",
            [(p["final_url"], p["robots"] or "X-Robots-Tag: " + p["x_robots"]) for p in noindex], m)
    idx = [p for p in ok if p not in noindex]
    k = len(idx)
    web = [p for p in idx if p["final_url"].startswith("http")]  # a saved page with no address cannot be compared with its canonical
    titles = Counter(p["title"] for p in idx if p["title"])
    descs = Counter(p["description"] for p in idx if p["description"])
    rep.add(FIRST, "No title", "The title is the line people click in Google and the label AI assistants show for the page.",
            "Give the page one specific title of up to about 60 characters.",
            [(p["final_url"], "") for p in idx if not p["title"]], k)
    rep.add(WORTH, "The same title on more than one page", "Google has to guess which page to show, and the result does not say what is different about each.",
            "Write a title for each page that says what it alone covers. If a template writes them, fix the template.",
            [(p["final_url"], f"{titles[p['title']]} pages: {p['title']}") for p in idx if titles[p["title"]] > 1], k)
    rep.add(FYI, "Title over 60 characters", "Google usually cuts a title at about 60 characters, so the end may not show.",
            "Put the words that matter first, or shorten it.",
            [(p["final_url"], f"{len(p['title'])}: {p['title']}") for p in idx if len(p["title"]) > 60], k)
    rep.add(FYI, "Very short title", "A title of one or two words says who you are but not what the page offers.",
            "Add what the page is: the product, the offer or the question it answers.",
            [(p["final_url"], p["title"]) for p in idx if 0 < len(p["title"]) < 15], k)
    rep.add(WORTH, "No description", "Without one, Google writes the text under your title itself, from whatever it finds on the page.",
            "Add one or two sentences, up to about 160 characters, saying what the page offers.",
            [(p["final_url"], "") for p in idx if not p["description"]], k)
    rep.add(WORTH, "The same description on more than one page", "Each result should say what that page alone offers.",
            "Write one per page. If a template writes them, fix the template.",
            [(p["final_url"], f"{descs[p['description']]} pages: {p['description'][:80]}") for p in idx if descs[p["description"]] > 1], k)
    rep.add(FYI, "Description over 160 characters", "Longer descriptions are usually cut in the results.",
            "Trim to one or two sentences with the point first.",
            [(p["final_url"], f"{len(p['description'])} characters") for p in idx if len(p["description"]) > 160], k)
    rep.add(WORTH, "No main heading (H1)", "The main heading tells a reader, and a machine, what the page is about.",
            "Mark the page's headline as its H1.",
            [(p["final_url"], "") for p in idx if not p["h1"]], k)
    rep.add(FYI, "More than one main heading (H1)", "Often a logo, a sidebar title or a card marked as H1. Harmless, but the real headline should be the only one.",
            "Keep H1 for the headline and mark the others as something else.",
            [(p["final_url"], " | ".join(p["h1"][:3])) for p in idx if len(p["h1"]) > 1], k)
    rep.add(FYI, "Title and main heading share no word", "The search result promises one thing and the page opens with another. A deliberate headline is fine.",
            "Use the title's key words in the heading, or the heading's in the title.",
            [(p["final_url"], f"title \"{p['title']}\" / heading \"{p['h1'][0]}\"") for p in idx
             if p["h1"] and p["title"] and pf.topic_words(p["h1"][0]) and not (pf.topic_words(p["h1"][0]) & pf.topic_words(p["title"]))], k)
    rep.add(WORTH, "Long page with no section headings (H2)", "Sections let people scan and let AI assistants lift the part that answers a question.",
            "Add a heading to each section.",
            [(p["final_url"], f"{p['words']} words") for p in idx if p["words"] > 500 and not p["h2"]], k)
    rep.add(FIRST, "The page arrives empty and is filled in by scripts", "Google usually copes. Most AI assistants do not run scripts, so they read an empty page.",
            "Send the text in the page itself (server rendering or a static build).",
            [(p["final_url"], f"{p['words']} words, {p['scripts']} scripts" + (", an empty app container" if p["app_root"] else ", no main heading"))
             for p in idx if p["words"] < 50 and p["scripts"] >= 3 and (p["app_root"] or not p["h1"])], k)
    rep.add(WORTH, "No canonical tag", "The canonical tag names the one true address of a page, so copies with tracking codes or a different slash do not compete with it.",
            "Add one canonical tag per page, pointing at the page's own https address. If a template is missing it, fix the template.",
            [(p["final_url"], "") for p in idx if not p["canonicals"]], k)
    rep.add(FIRST, "More than one canonical tag, and they disagree", "Google may ignore all of them.",
            "Keep one.",
            [(p["final_url"], " | ".join(p["canonicals"])) for p in idx if len(set(p["canonicals"])) > 1], k)
    rep.add(FIRST, "Canonical tag points at another website", "This tells Google the real page lives on a different domain (an old domain or a staging site?).",
            "Point it at this site's own address for the page.",
            [(p["final_url"], p["canonicals"][0]) for p in web if p["canonicals"] and pf.host_of(p["canonicals"][0]) != pf.host_of(p["final_url"])], k)
    rep.add(FIRST, "Canonical tag uses http://", "It points Google at the insecure address.",
            "Use the https address.",
            [(p["final_url"], p["canonicals"][0]) for p in idx if p["canonicals"] and p["canonicals"][0].startswith("http://")], k)
    rep.add(ASK, "Canonical tag points at a different page", "Fine when two pages are meant to count as one. If not, this page is telling Google to ignore it.",
            "If it is not deliberate, point the tag at the page's own address.",
            [(p["final_url"], "-> " + p["canonicals"][0]) for p in web
             if p["canonicals"] and pf.host_of(p["canonicals"][0]) == pf.host_of(p["final_url"]) and not pf.same_page(p["canonicals"][0], p["final_url"])], k)
    rep.add(WORTH, "Snippets switched off (nosnippet or max-snippet:0)", "Google then shows no text from the page, and leaves it out of its AI answers.",
            "Remove nosnippet and max-snippet:0 from the robots tag.",
            [(p["final_url"], p["robots"]) for p in idx if re.search(r"nosnippet|max-snippet:\s*0\b", p["robots"])], k)
    rep.add(WORTH, "No mobile viewport tag", "Google reads the mobile version of a page first.",
            "Add the standard viewport tag to the page head.",
            [(p["final_url"], "") for p in idx if not p["viewport"]], k)
    rep.add(FYI, "No share image (og:image)", "Links to the page in chat apps and social feeds show no picture.",
            "Add an og:image tag with a full https address.",
            [(p["final_url"], "") for p in idx if not p["og_image"]], k)
    rep.add(FYI, "No language set on the page", "It helps the right language version reach the right reader.",
            "Add a lang attribute to the html tag.",
            [(p["final_url"], "") for p in idx if not p["lang"]], k)
    rep.add(FYI, "Pictures with no alt text at all", "Alt text is what image search and screen readers read.",
            "Describe each picture that carries meaning; give decoration an empty alt.",
            [(p["final_url"], f"{p['images_no_alt']} of {p['images']} pictures") for p in idx if p["images"] >= 3 and p["images_no_alt"] / p["images"] > 0.5], k)
    rep.add(FYI, "Most pictures are marked as decoration (empty alt text)", "Right for decoration. Screenshots and product pictures marked this way are invisible to image search and screen readers.",
            "Describe the pictures that show the product or explain something.",
            [(p["final_url"], f"{p['images_empty_alt']} of {p['images']} pictures") for p in idx if p["images"] >= 3 and p["images_empty_alt"] / p["images"] > 0.5], k)


def check_site(origin, robots_res, robots, files, entries, truncated, rep):
    today = datetime.date.today().isoformat()
    rtxt = robots_res["status"] == 200
    if not rtxt:
        rep.add(FYI, "No robots.txt", "Without one every crawler is allowed, which is fine.",
                "Add one anyway: it is the place to name your sitemap.",
                [(origin + "/robots.txt", f"HTTP {robots_res['status']}" if robots_res["status"] else robots_res["error"])], 1)
    blocked = [(b, who) for b, who in ANSWER_BOTS if not allowed(robots, b)]
    rep.add(FIRST, "robots.txt shuts a search or AI reader out of the whole site", "A reader that is shut out cannot read, show or name any page.",
            "Remove the 'Disallow: /' that applies to that reader, or the blanket block it inherits.",
            [(origin + "/robots.txt", f"{b} ({who})") for b, who in blocked], len(ANSWER_BOTS))
    trained = [b for b in TRAINING_BOTS if not allowed(robots, b)]
    rep.add(FYI, "robots.txt blocks crawlers that collect text for AI training", "Your choice. It does not change how search or AI answers treat the site.",
            "Nothing to do unless you want your text used for training.",
            [(origin + "/robots.txt", b) for b in trained], len(TRAINING_BOTS))
    if not entries:
        rep.add(WORTH, "No sitemap found", "A sitemap is the list of pages you want found. Without it, new pages are found only by following links.",
                "Publish one at /sitemap.xml and name it in robots.txt.",
                [(f["url"], f"HTTP {f['status']}") for f in files] or [(origin + "/sitemap.xml", "not found")], 1)
        return
    if rtxt and not robots["sitemaps"]:
        rep.add(FYI, "robots.txt does not name the sitemap", "Naming it lets every crawler find it.",
                "Add one line: 'Sitemap: <the sitemap's address>'.", [(origin + "/robots.txt", "")], 1)
    n, host = len(entries), pf.host_of(origin)
    rep.add(FIRST, "Sitemap lists pages on another website", "Search engines ignore entries for a different domain.",
            "List only this site's pages.",
            [(e["url"], "") for e in entries if pf.host_of(e["url"]) != host], n)
    rep.add(FIRST, "Sitemap lists pages robots.txt blocks for Google", "The two files contradict each other.",
            "Unblock the pages, or take them out of the sitemap.",
            [(e["url"], "") for e in entries if not allowed(robots, "Googlebot", urlsplit(e["url"]).path or "/")], n)
    dup = Counter(e["url"].rstrip("/") for e in entries)
    rep.add(WORTH, "The same page listed more than once in the sitemap", "Usually the same page with and without a trailing slash.",
            "List each page once, at its final address.",
            [(u, f"{c} times") for u, c in dup.items() if c > 1], n)
    dated = [e for e in entries if e["lastmod"]]
    rep.add(FYI, "Sitemap pages with no 'last changed' date", "The date tells crawlers which pages to read again.",
            "Add a lastmod date to each entry, when the site can record real ones.",
            [(e["url"], "") for e in entries if not e["lastmod"]], n)
    rep.add(WORTH, "'Last changed' dates in the future", "A wrong date teaches crawlers to ignore all of them.",
            "Write the day the page really changed.",
            [(e["url"], e["lastmod"]) for e in dated if e["lastmod"][:10] > today], n)
    if len(dated) >= 20:
        day, c = Counter(e["lastmod"][:10] for e in dated).most_common(1)[0]
        if c / len(dated) >= 0.5:
            rep.add(WORTH, "Most sitemap pages carry the same 'last changed' day", "That is the day the site was rebuilt, not the day each page changed. Google uses the date only when it is accurate.",
                    "Write the day each page's content last changed.",
                    [(e["url"], day) for e in dated if e["lastmod"][:10] == day], n)


def render(site, scope, rep, robots, robots_ok):
    out = [f"# Site check: {site}", "", scope, ""]
    for tier in (FIRST, WORTH, ASK, FYI):
        items = [i for i in rep.items if i["tier"] == tier]
        if not items:
            continue
        out.append(f"## {tier}")
        for i in items:
            out.append(f"- **{i['what']}**: {i['count']} of {i['of']}. {i['why']} Fix: {i['fix']}")
            for e in i["examples"]:
                out.append(f"  - {e['url']}" + (f" ({e['detail']})" if e["detail"] else ""))
            if i["count"] > len(i["examples"]):
                out.append(f"  - and {i['count'] - len(i['examples'])} more")
        out.append("")
    if not rep.items:
        out += ["Nothing found in the pages checked.", ""]
    if robots is not None:
        out.append("## Who may read the site (robots.txt)")
        if not robots_ok:
            out.append("No robots.txt, so every reader below is allowed.")
        out.append("| Reader | Used by | Allowed |")
        out.append("|---|---|---|")
        for b, who in ANSWER_BOTS:
            out.append(f"| {b} | {who} | {'yes' if allowed(robots, b) else 'NO'} |")
        for b in TRAINING_BOTS:
            out.append(f"| {b} | collects text for AI training | {'yes' if allowed(robots, b) else 'no (your choice)'} |")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", nargs="?", help="domain or address, e.g. example.com")
    ap.add_argument("--pages", type=int, default=25, help="how many pages to read (default 25)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1)")
    ap.add_argument("--html", action="append", default=[], help="a saved page to check instead of fetching (repeatable)")
    ap.add_argument("--url", action="append", default=[], help="the address each --html file was saved from, in the same order")
    ap.add_argument("--json", help="also write every finding to this file")
    a = ap.parse_args()
    rep, today = Report(), datetime.date.today().isoformat()

    if a.html:
        pages = []
        for i, path in enumerate(a.html):
            url = a.url[i] if i < len(a.url) else "saved file " + path
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    f = pf.read_html(fh.read(), url)
            except OSError as e:
                sys.exit(f"Could not open {path}: {e.strerror}.")
            f.update(requested=url, status=200, final_url=url, error="", redirected=False, x_robots="", local=True)
            pages.append(f)
        check_pages(pages, rep, False)
        scope = (f"Scope: {len(pages)} saved page(s), {today}. robots.txt and the sitemap were not read."
                 + ("" if len(a.url) >= len(a.html) else " No --url given, so canonical tags were not compared with the page's address."))
        print(render(a.site or "saved pages", scope, rep, None, False))
    else:
        if not a.site:
            ap.error("give a site, or --html with a saved page")
        start = a.site if "//" in a.site else "https://" + a.site
        home = pf.page(start)
        if home["status"] == 0:
            sys.exit(f"Could not reach {start}: {home['error'] or 'no answer'}. Check the address, and that this "
                     "environment allows network access. Without it, save a page from your browser and run this with --html.")
        if home["status"] != 200:
            sys.exit(f"{start} answered HTTP {home['status']}: it refuses automated reads (some AI readers will be refused "
                     "the same way). Save a page from your browser and run this with --html.")
        parts = urlsplit(home["final_url"])
        origin = f"{parts.scheme}://{parts.netloc}"
        robots_res = pf.fetch(origin + "/robots.txt")
        looks_html = b"<html" in robots_res["body"][:500].lower()
        robots_ok = robots_res["status"] == 200 and not looks_html
        if not robots_ok and robots_res["status"] == 200:
            robots_res["status"] = 404  # a page served in place of the file is not a robots.txt
        robots = parse_robots(pf.text_of(robots_res) if robots_ok else "")
        time.sleep(a.delay)
        files, entries, truncated = read_sitemaps(robots["sitemaps"] or [origin + "/sitemap.xml"], a.delay)
        if not entries and not robots["sitemaps"]:
            time.sleep(a.delay)
            files2, entries, truncated = read_sitemaps([origin + "/sitemap_index.xml"], a.delay)
            files += files2
        check_site(origin, robots_res, robots, files, entries, truncated, rep)
        unread = []
        if entries:
            urls, unread = pick_pages(home["final_url"], [e for e in entries if pf.host_of(e["url"]) == pf.host_of(origin)], a.pages)
        else:
            seen, urls = set(), [home["final_url"]]
            for l in home["internal_links"]:
                key = l["url"].rstrip("/")
                if key not in seen and not pf.same_page(l["url"], home["final_url"]) and not re.search(r"\.(pdf|png|jpe?g|webp|svg|zip|xml|css|js)$", l["url"], re.I):
                    seen.add(key)
                    urls.append(l["url"])
            urls = urls[: a.pages]
        pages = [home]
        for u in urls[1:]:
            time.sleep(a.delay)
            pages.append(pf.page(u))
            print(f"  read {len(pages)}/{len(urls)}", file=sys.stderr, end="\r")
        check_pages(pages, rep, bool(entries))
        total = f"{len(entries)} pages in the sitemap" if entries else "no sitemap, so pages linked from the home page"
        scope = (f"Scope: {len(pages)} pages read of {total}{' (sitemap cut off at 20 files)' if truncated else ''}, {today}. "
                 f"{'A sample: counts are for the pages read, not the whole site.' if entries and len(pages) < len(entries) else ''}").strip()
        if unread:
            names = ", ".join(f"/{name} ({c})" for name, c in unread[:12]) + (f" and {len(unread) - 12} more" if len(unread) > 12 else "")
            scope += (f"\nSections with no page read: {names}. "
                      f"Run again with --pages {len(pages) + len(unread)} to read at least one page from every section.")
        print(render(pf.host_of(origin), scope, rep, robots, robots_ok))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"date": today, "scope": scope, "findings": rep.items,
                       "pages": [{k: v for k, v in p.items() if k not in ("text", "internal_links", "external_links")} for p in pages]}, fh, indent=1)
        print(f"Saved every finding to {a.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
