# Collecting AI answers by hand

Use this when Cituna is not connected. The goal is a file, `ai-answers.json`, holding what each AI
assistant answered for each buyer question: the full text, every business it named, and every link it showed.

## 1. The questions

Three to five questions a buyer asks before choosing, in their words, without the user's business name in them.
Mix the kinds: "best <thing> for <who>", "<well-known rival> alternative", "how do I <the job the product does>",
"<thing> in <place>" for a local business. One question per line. Show them to the user and carry on; change them
only if the user objects.

Write them the way a buyer who has never seen the user's website would. Do not lift the phrases from the site's own
headline: a question that repeats the site's wording finds the site, and the result flatters the user.

## 2. Your own answer first (no waiting on the user)

For each question, get the answer a stranger would get from an AI assistant with web search:

- Best: hand the question to a fresh helper that knows nothing about the user (a subagent, when you can start one).
  Give it only the question and this instruction: "Answer this as you would for anyone, using web search. Name the
  businesses you would recommend, in order, and list every page you read."
- Otherwise search it yourself, exactly as written. Do not add the user's name to the search. Open the four to six
  results an answer would rest on and read them. Then write the answer you would give a stranger: the businesses you
  would recommend, in order. Do not add the user because you know them: if their business did not come up, it did
  not come up. Say in the report that you answered with the user's business already in mind, which makes this a
  weaker reading than a fresh assistant's.

Record it as assistant `Claude`, with today's date: `text` is the answer you wrote, `sources` the pages you opened
(not every search result). This alone is a real result: one assistant, one moment.

## 3. The other assistants (the user does this, two minutes each)

Ask the user to paste each question, exactly as written, into the assistants their buyers use, and paste back the
whole answer with the links under it. Give them these steps:

- **ChatGPT**: start a temporary chat (so memory of who you are does not change the answer). Make sure search is on.
- **Perplexity**: a new thread, signed out or in a private window.
- **Gemini**: a new chat, in a private window if you can.
- **Google**: search the question in a private window. Copy the AI Overview at the top if one shows, and say if
  none did. For AI Mode, click the AI Mode tab and copy that answer as a separate one.
- **Grok**: optional, a new chat.

One assistant beyond your own answer is enough to start. Do not hold the result back waiting for all of them: show
what you have, then add answers as the user pastes them. If nobody is there to paste, report your own answers and
list the assistants that were not asked.

## 4. Write the file

```json
{
  "brand": "Acme",
  "also_called": ["Acme CRM"],
  "domain": "acme.example",
  "answers": [
    {
      "question": "best CRM for a small law firm",
      "assistant": "ChatGPT",
      "date": "2026-11-12",
      "text": "the whole answer, as pasted",
      "brands": ["Rival One", "Rival Two", "Rival Three"],
      "sources": ["https://example.com/best-legal-crm"]
    }
  ]
}
```

- `brands`: every business or product the answer offers the buyer as a choice, in the order it names them. Include
  the user's business when the answer names it as a choice. Leave out: sites it only links as a source, the product
  the question is about ("Google Analytics" in "Google Analytics alternative"), and names it mentions only in
  passing. The count trusts this list and its order; it does not search the text for names.
- `sources`: every link the answer showed (for your own answer, every page you opened). If a pasted answer has none,
  leave it out and say that answer showed no sources.
- `also_called`: other spellings of the user's business name. Not the website address.
- Use the same spelling for the same business across answers, so the counts add up.
- Save the file in the user's working folder.

## 5. Say what this is

Every table from this file is one reading: these questions, these assistants, this day. The same question asked
again can name different businesses. Say so once, next to the numbers.
