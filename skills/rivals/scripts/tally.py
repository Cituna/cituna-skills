#!/usr/bin/env python3
"""Count who each AI assistant named, and which sites it read, from the answers you collected.

    python3 tally.py ai-answers.json

The file (collect.md says how to fill it):

    {"brand": "Acme", "also_called": ["Acme CRM"], "domain": "acme.example",
     "answers": [{"question": "...", "assistant": "ChatGPT", "date": "2026-11-12",
                  "text": "the whole answer", "brands": ["Rival One", "Acme", "Rival Two"], "sources": ["https://..."]}]}

`brands` is every business the answer recommends, in the order it names them, including yours when it is
named. The count trusts that list and never searches the answer text for names: a brand called "Plausible"
would otherwise be found in "the most plausible choice". `sources` is every link the answer showed, or
every page read; when it is missing, links are taken from the text. Standard library only.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit


def host_of(url):
    h = (urlsplit(url if "//" in url else "//" + url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        data = json.load(open(sys.argv[1], encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"Could not read {sys.argv[1]}: {e}")
    if not data.get("brand") or not data.get("answers"):
        sys.exit('The file needs "brand" and at least one entry in "answers". See collect.md.')
    brand = data["brand"]
    you = {n.lower() for n in [brand] + list(data.get("also_called", []))}
    domain = host_of(data.get("domain", ""))
    mine = lambda h: bool(domain) and (h == domain or h.endswith("." + domain))

    # one answer per question and assistant: a later entry replaces an earlier one
    latest, replaced = {}, 0
    for i, a in enumerate(data["answers"]):
        if not a.get("question") or not a.get("assistant"):
            sys.exit(f'Answer {i + 1} needs both "question" and "assistant".')
        key = (a["question"], a["assistant"])
        replaced += key in latest
        latest[key] = a
    answers = list(latest.values())

    questions, assistants, spelling = [], [], {}
    grid, named_in, read_by = {}, Counter(), defaultdict(set)
    host_answers, your_pages, dates = Counter(), Counter(), set()
    for a in answers:
        q, who = a["question"], a["assistant"]
        if q not in questions:
            questions.append(q)
        if who not in assistants:
            assistants.append(who)
        if a.get("date"):
            dates.add(a["date"])
        order = []
        for b in a.get("brands", []):
            name = brand if b.lower() in you else spelling.setdefault(b.lower(), b)  # one spelling per business
            if name not in order:
                order.append(name)
        for b in order:
            named_in[b] += 1
        urls = [u.rstrip(".,;") for u in (a.get("sources") or re.findall(r"https?://[^\s)\]>\"']+", a.get("text", "")))]
        hosts = sorted({host_of(u) for u in urls} - {""})
        for h in hosts:
            host_answers[h] += 1
            read_by[h].add(who)
        for u in urls:
            if mine(host_of(u)):
                s = urlsplit(u)
                your_pages[f"{host_of(u)}{s.path.rstrip('/')}"] += 1
        grid[(q, who)] = {"position": order.index(brand) + 1 if brand in order else None, "named": len(order),
                          "others": [b for b in order if b != brand], "hosts": hosts, "read_you": any(mine(h) for h in hosts)}

    n = len(answers)
    hits = sum(1 for g in grid.values() if g["position"])
    when = f", {min(dates)}" + (f" to {max(dates)}" if len(dates) > 1 else "") if dates else ""
    print("# Who AI names for your questions\n")
    print(f"Scope: {len(questions)} question(s), {len(assistants)} assistant(s) ({', '.join(assistants)}), {n} answers{when}. "
          f"{brand} is named in {hits} of {n}. Answers change from one ask to the next: this is one reading.")
    if replaced:
        print(f"{replaced} earlier answer(s) to the same question from the same assistant were replaced by the later one.")
    for q in questions:
        print(f"\n## {q}\n")
        print("| Assistant | You | Others named | Sites it read |")
        print("|---|---|---|---|")
        for who in assistants:
            g = grid.get((q, who))
            if not g:
                print(f"| {who} | not asked | | |")
                continue
            pos = f"named, #{g['position']} of {g['named']}" if g["position"] else "not named"
            others = ", ".join(g["others"][:6]) + (f" and {len(g['others']) - 6} more" if len(g["others"]) > 6 else "")
            sites = ", ".join(h + (" (yours)" if mine(h) else "") for h in g["hosts"][:8]) + (f" and {len(g['hosts']) - 8} more" if len(g["hosts"]) > 8 else "")
            print(f"| {who} | {pos} | {others or '-'} | {sites or 'none shown'} |")
    print("\n## Named most often\n")
    print("| Business | Answers naming it |")
    print("|---|---|")
    for b, c in sorted(named_in.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:12]:
        print(f"| {b}{' (you)' if b == brand else ''} | {c} of {n} |")
    if brand not in named_in:
        print(f"| {brand} (you) | 0 of {n} |")
    if host_answers:
        print("\n## Sites the answers read most\n")
        print("| Site | Answers that read it | Assistants |")
        print("|---|---|---|")
        for h, c in sorted(host_answers.items(), key=lambda kv: (-kv[1], kv[0]))[:15]:
            print(f"| {h}{' (yours)' if mine(h) else ''} | {c} of {n} | {', '.join(sorted(read_by[h]))} |")
        if domain and not your_pages:
            print(f"\nNo answer read a page on {domain}.")
        elif your_pages:
            print("\nYour pages they read: " + "; ".join(f"{u} ({c})" for u, c in sorted(your_pages.items(), key=lambda kv: (-kv[1], kv[0]))[:5]))
    else:
        print("\nNo answer showed its sources. Ask again with web search switched on, and copy the links under each answer.")


if __name__ == "__main__":
    main()
