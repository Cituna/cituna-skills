# Cituna skills for Claude

Five free skills that show a founder or marketer how their business appears in AI answers and on Google, and what to fix. Each one works on its own, with no account. Each one does more when [Cituna's MCP server](https://github.com/cituna/cituna-mcp) is connected.

| Skill | Ask Claude | What you get |
|---|---|---|
| [`cited`](#cited) | "Who does AI name for my business?" | Who each AI assistant names for your buyers' questions, and which sites it read |
| [`audit`](#audit) | "Check my site" | The faults on your own pages, and whether AI readers are shut out |
| [`clicks`](#clicks) | "Which pages get shown but not clicked?" | Pages Google shows that nobody clicks, with new titles |
| [`sources`](#sources) | "Which sites does AI read for my question?" | The sites behind the answers, whether you are on them, and how to get listed |
| [`rivals`](#rivals) | "Who does AI recommend instead of us?" | Who is named instead of you, and what their pages have that yours lacks |

The skills only read. They never change your site, send a message or post anything.

## What Cituna's MCP server is

[Cituna](https://cituna.com) asks your buyers' questions on seven AI assistants every day (ChatGPT, Perplexity, Gemini, Claude, Grok, Google AI Overviews and Google AI Mode) and keeps every answer: who was named, in what order, and which pages were read. It joins that with your Google Search Console data.

The MCP server puts that record inside Claude. Instead of opening a dashboard you ask, and Claude reads the answers, the sites and your search numbers directly. These skills use it when it is there:

| Skill | On its own | With Cituna connected |
|---|---|---|
| `cited` | Claude answers your questions with web search, then walks you through asking the other assistants and counts the results | Reads the stored daily answers from all seven assistants |
| `audit` | Reads your robots.txt, sitemap and a sample of pages | Orders the fixes by how many people see each page on Google, and adds pages Google never shows |
| `clicks` | Works from a Search Console export | Reads Search Console directly, with the exact searches behind each page and your brand-name searches set aside |
| `sources` | Opens the pages behind a few answers and checks each for your name | Uses the full list of sites the seven assistants read, each already checked |
| `rivals` | Counts who is named in a few answers and compares pages | Uses the daily record, and finds rivals you are not yet watching |

## Connect Cituna's MCP server

The server is hosted. There is nothing to install.

```
https://mcp.cituna.com/mcp
```

**Claude on the web, desktop or phone**

1. Open **Customize**, then **Connectors**, click **Add**, then **Add custom connector**.
2. Name it Cituna and paste the address above.
3. Claude sends you to Cituna to sign in. Approve the connection.
4. In a chat, switch Cituna on from the **+** menu.

**Claude Code**

```bash
claude mcp add --transport http cituna https://mcp.cituna.com/mcp
```

Then type `/mcp`, pick **cituna** and choose **Authenticate**.

You need a paid Cituna plan with at least one brand added. Reading works from the Starter plan; the free trial does not include the MCP server. Current plans are at [cituna.com/pricing](https://cituna.com/pricing). Every other client, the API-key route and the full tool list are in the server's own README: [github.com/cituna/cituna-mcp](https://github.com/cituna/cituna-mcp).

## Install a skill

**In Claude Code**, run the line under the skill you want, then start a new session and type its name, for example `/cited yoursite.com`. To install all five:

```bash
mkdir -p ~/.claude/skills && curl -sL https://github.com/cituna/cituna-skills/archive/refs/heads/main.tar.gz | tar -xz -C ~/.claude/skills --strip-components=2 cituna-skills-main/skills
```

**In the Claude apps** (web and desktop):

1. Download the skill's zip from the link under it.
2. In Claude open **Customize**, then **Skills**, click **+**, then **Create skill**, then **Upload a skill**, and choose the zip.
3. Skills run code, so **Code execution and file creation** must be on under **Settings**, then **Capabilities**.
4. Ask in plain words, for example "check who AI names for yoursite.com".

`audit`, `clicks`, `sources` and `rivals` open web pages from code. In the Claude apps that needs network access allowed for code execution, in the same Capabilities screen. Without it each skill falls back to Claude's own web tool, and says what it could not check.

The scripts need Python 3.8 or later and nothing else.

## cited

Asks your buyers' questions and shows, per question, which AI assistants name your business, who they name instead and which sites they read.

```bash
mkdir -p ~/.claude/skills && curl -sL https://github.com/cituna/cituna-skills/archive/refs/heads/main.tar.gz | tar -xz -C ~/.claude/skills --strip-components=2 cituna-skills-main/skills/cited
```

Claude apps: [cited.zip](https://github.com/cituna/cituna-skills/raw/main/dist/cited.zip)

## audit

Checks your own pages (titles, descriptions, headings, canonical tags, the sitemap) and your robots.txt, including whether the readers ChatGPT, Perplexity, Claude and Google send are shut out.

```bash
mkdir -p ~/.claude/skills && curl -sL https://github.com/cituna/cituna-skills/archive/refs/heads/main.tar.gz | tar -xz -C ~/.claude/skills --strip-components=2 cituna-skills-main/skills/audit
```

Claude apps: [audit.zip](https://github.com/cituna/cituna-skills/raw/main/dist/audit.zip)

## clicks

Finds the pages Google shows and nobody clicks, separates the ones a new title can fix from the ones it cannot, and writes the new title and description.

```bash
mkdir -p ~/.claude/skills && curl -sL https://github.com/cituna/cituna-skills/archive/refs/heads/main.tar.gz | tar -xz -C ~/.claude/skills --strip-components=2 cituna-skills-main/skills/clicks
```

Claude apps: [clicks.zip](https://github.com/cituna/cituna-skills/raw/main/dist/clicks.zip)

## sources

Lists the sites AI assistants read for your question, checks each page for your name, and says how to get listed on the ones you are missing from.

```bash
mkdir -p ~/.claude/skills && curl -sL https://github.com/cituna/cituna-skills/archive/refs/heads/main.tar.gz | tar -xz -C ~/.claude/skills --strip-components=2 cituna-skills-main/skills/sources
```

Claude apps: [sources.zip](https://github.com/cituna/cituna-skills/raw/main/dist/sources.zip)

## rivals

Shows who AI assistants name instead of you, then puts your page next to theirs and lists what theirs have that yours lacks.

```bash
mkdir -p ~/.claude/skills && curl -sL https://github.com/cituna/cituna-skills/archive/refs/heads/main.tar.gz | tar -xz -C ~/.claude/skills --strip-components=2 cituna-skills-main/skills/rivals
```

Claude apps: [rivals.zip](https://github.com/cituna/cituna-skills/raw/main/dist/rivals.zip)

## What is in this repository

- `skills/<name>/SKILL.md`: the instructions Claude follows. `scripts/` beside it holds the small Python scripts the skill runs.
- `dist/<name>.zip`: the same skill, packed for upload to the Claude apps. `bash build.sh` rebuilds them.
- [`TESTING.md`](TESTING.md): what each skill returned when run against a public website.

## Links

- Cituna: [cituna.com](https://cituna.com)
- The MCP server, with every client's setup and the full tool list: [github.com/cituna/cituna-mcp](https://github.com/cituna/cituna-mcp) and [cituna.com/mcp](https://cituna.com/mcp)
- Plans: [cituna.com/pricing](https://cituna.com/pricing)

## License

MIT. The skills are free to use and change. Cituna itself is a paid service.
