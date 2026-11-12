# Testing

Each skill was run once, on 12 November 2026, by a fresh Claude agent that was given only the skill's folder and a
one-line request, as a new user's Claude would be. Cituna was treated as not connected, so every run below is the
no-account path. The agents were told to check the scripts' output against the real pages and to report anything
unclear or wrong.

The sites are public and were picked only because they are well known: basecamp.com and plausible.io. Neither has any
connection with Cituna. What the skills found on them is a snapshot of one day and says nothing about how those
companies are run.

Every test found faults. They are listed here with what was changed, and each fix was re-run on the same input.

## cited

**Request:** `cited plausible.io`, three questions.

**Returned:** a one-line summary (Plausible named in 3 of 3 answers, one assistant, 12 Nov 2026), a table per
question (position, the other businesses named, the sites read), a "named most often" table (Plausible 3 of 3, Fathom
and Simple Analytics 2 of 3, seven others once), a table of 13 sites behind the answers with whether Plausible was
on each, three suggested actions, and the two-minute steps for asking ChatGPT, Perplexity, Gemini and Google.

**Found and fixed:**
- The count searched the answer text for the brand, so a brand called "Plausible" was "named" by the sentence "the
  most plausible choice", and by a bare link to its site. The count now trusts only the list of businesses the
  answer recommends, in the order given.
- A page on a subdomain of the user's site (`ingest.plausible.io`) was not counted as the user's. It is now.
- The same question answered twice by one assistant was counted twice in one table and once in another. The later
  answer now replaces the earlier, and the output says so.
- Table rows changed order between runs. Ties are now sorted by name.
- The instructions did not say where to save the answers file, what counts as a recommended business, or that
  questions should not reuse the wording of the site's own headline (which tilts the result toward "named"). They do
  now. They also say what to report when the user is named first everywhere, instead of inventing problems.

**Limit that remains:** with no fresh helper available, the same Claude that read the user's site wrote the answers.
The skill now says so in the report. It is one assistant on one day.

## audit

**Request:** `audit basecamp.com`, default sample of 25 pages, plus one run on a saved page with no network.

**Returned:** a scope line (25 of 387 sitemap pages), a fix list in plain words, and the table of search and AI
readers allowed by robots.txt (all allowed). After the agent opened the examples, the confirmed findings were: book
pages with no canonical tag (a template fault, confirmed on three more pages), two long pages with no section
headings, one page marked noindex that the sitemap still lists (reported as a question), titles and descriptions
over the usual length, and screenshots marked as decoration.

**Found and fixed:**
- "Almost no text in the page" fired on a page that was simply short. The check now needs a second sign that scripts
  build the page (an empty app container, or no main heading).
- A noindex page was listed under "Fix first", against the skill's own instruction to ask. It is now under "Check
  with the owner", and the finding names the real contradiction: the sitemap lists a hidden page.
- The sample was the first 24 sections in alphabetical order and skipped 14 sections, including the largest. It now
  takes one page from each section, biggest first, names the sections it did not read, and prints the `--pages`
  number that covers them all.
- An empty `alt=""` (the correct mark for a decorative picture) was counted as missing alt text. The two are now
  separate findings.
- Running on a saved page without `--url` invented a "canonical points at another website" fault. Those checks are
  now skipped and the scope line says so.
- An unreachable site printed an empty error. It now says whether the site could not be reached or refused the read.
- Half the findings had no fix in the instructions. The script now prints a fix beside every finding.

**Limit that remains:** it reads pages as served, a sample at a time. It does not render pages in a browser, measure
speed, or follow links between pages.

## clicks

**Request:** `clicks` with a Search Console export for basecamp.com.

**About the input:** nobody's real Search Console data is public, so the export was a test file in Search Console's
real export layout (`Pages.csv`, `Queries.csv`, `Filters.csv` in a zip). The page addresses are real basecamp.com
pages and their live titles were read from the site. **The numbers in it were invented for the test.**

**Returned:** the click rate the site's own pages earn by position, two pages on page one with no clicks and one
clicked far less than its neighbours, each with an estimate of clicks missed, a new title and description for all
three (each fact checked on the live page first), and the pages a rewrite would not help, by cause. The agent checked
the split and every estimate by hand against the CSV: all correct.

**Found and fixed:**
- Given `Pages.csv` on its own, the script read it a second time as the searches table and listed page addresses as
  searches. It now reads the `Queries.csv` beside it, or none.
- The column headed "clicks at your usual rate" held clicks missed. Renamed.
- The date range was not printed, and the count of unclicked pages was not stated. Both are now in the scope line.
- Searches with a few clicks were left out of the list, so the under-clicked page had no search to aim at. Searches
  far below the site's usual rate are now listed too.
- Nothing let Claude confirm that a fact was on the page before putting it in a title. `--text` now prints the
  page's text and the instructions require the check.
- The page-one boundary differed between the script and the instructions. Both now use position 10.
- The instructions now say how to treat a search that is the brand name plus a topic, and that the estimates rest on
  a handful of pages.

**Limit that remains:** an export keeps pages and searches in separate files, so matching a page to its searches is
a judgement, and the skill says so.

## sources

**Request:** which sites AI reads for "Google Analytics alternative" questions for Plausible Analytics, and how to
get on them. Three questions.

**Returned:** 66 pages on 52 sites opened; Plausible linked on 23, named without a link on 18, absent from 12, and 13
unreadable. A ranked list of six pages to ask (for example a "14 best alternatives" list with no cookieless tool
on it), each with the one-line ask and where to send it; five pages that name the business without linking it; and
the unreadable pages listed separately, not counted as gaps. The agent opened the pages by hand: the script's
verdict was right on 24 and wrong or misleading on 8, listed below.

**Found and fixed** (eight verdicts were wrong or misleading):
- Four pages had moved: the address now redirected to a home page, and the script reported the business as absent
  from the page it landed on. A redirect to another site or to a home page is now reported as "moved", never as a gap.
- A list that linked the business through the site's own redirect link was "named, no link". It is now "named,
  linked indirectly", with the link to follow.
- A name that appeared only in a site's menu was "named". It is now its own verdict.
- About twenty pages on rivals' own sites were offered as places to ask. A site with a rival's name in its address is
  now a rival's own site and left out of the list.
- Copies of the user's own pages on other addresses were treated as third-party lists. A page whose canonical tag
  points at the user's site is now "a copy of your own page".
- The same page under two addresses was listed twice. Pages are now merged by canonical address.
- Search-result pages were counted as read by an answer. They are now marked "search result only", and the table
  shows how many answers read each site.
- Contact links included a blank email, a blog template seller's "About us" and non-name "author" links. Only the
  site's own contact links, real addresses and author links that look like a person's name are kept.
- The instructions now tell Claude what to check by hand before reporting a target, where rival names come from,
  and to take the fact for each ask from the user's own site.

**Limit that remains:** forum threads (Reddit) and some news sites refuse automated reads from every tool tried. They
come back as "could not be read" and the user has to open them.

## rivals

**Request:** who AI recommends instead of Plausible Analytics, and what their pages have that Plausible's lacks.
Three questions.

**Returned:** Plausible was named in all three answers, so nobody was named instead; the skill reported the
businesses named alongside it (Matomo 3 of 3, Fathom, Umami and Simple Analytics 2 of 3). It then compared
Plausible's "vs Google Analytics" page with the matching pages of three rivals: a table of fifteen rows, six things
to add (a self-hosting section, feature rows in the comparison table, a price on the page, who owns the data, a short
questions block, a visible review date) and what only Plausible's page has.

**Found and fixed** (seven table cells were wrong on pages that had been read in full):
- "Updated date" read hidden page data, which on one site was the build time. The row now looks for a date beside
  words such as "updated" in the visible text.
- "Named author" accepted the company's name. It now needs a person.
- One price on a page was not enough to count; one now is. The "numbers" pattern missed common units.
- Pictures counted logos and lazy-load duplicates. Logos, icons and repeats are now left out.
- The page address printed was the one asked for, not the one reached after a redirect.
- The instructions had no path for a user who is named everywhere, did not say which question to compare for, and
  did not say what to do with a wrong cell. They now do, and they list the rows the script most often gets wrong so
  Claude corrects the table before reporting it.

**Limit that remains:** customer quotes laid out without quote markup are still missed by the script (true of the
test page). The instructions name this row as one to check by eye.

## Install commands

The Claude Code install lines in the README were run against a local archive of this folder with the same layout
GitHub serves: the single-skill line produced `cited/SKILL.md`, `cited/collect.md` and `cited/scripts/tally.py`; the
all-skills line produced the five folders. They have not been run against GitHub, because the repository was not
public at the time of testing.

The scripts were run on Python 3.9 and 3.14 on macOS.

## Not tested

- **The Cituna path of each skill, end to end.** The tool names, arguments and reply fields the skills rely on
  (`whoami`, `list_brands`, `get_visibility`, `get_engine_answers`, `list_citation_sources`, `gsc_status`,
  `gsc_zero_click_pages`, `gsc_query`) were checked against a live paid Cituna workspace. That data is private and
  is not recorded here. `competitor_discovery`, `gsc_coverage_gap` and `list_gaps` were not called.
- **Uploading the zips to the Claude apps.** The zips are built to the documented rules (the folder name equals the
  skill name, only the allowed front-matter keys, under the description limit), but none was uploaded.
- **The scripts inside the Claude apps' code sandbox**, where network access is off unless the user allows it. The
  saved-page route of `audit` was tested; the fallbacks of the other three were not.
- **Answers pasted from ChatGPT, Perplexity, Gemini or Google.** No person was in the loop, so every test used
  Claude's own web-search answers only.
- **Windows.**
