---
name: stop-slop
description: Enforces ASD-STE100, British English, no emojis, no em-dashes, no en-dashes and no banned AI vocabulary. Use before writing or editing any prose, README, SVG text or commit message.
---

# stop-slop

## Rules

1. Write British English: colour, licence (noun), organise, behaviour, catalogue.
2. Use active voice and imperative verbs for instructions.
3. Keep sentences under 20 words. Give one idea per sentence.
4. Use one word for one meaning. Do not vary terms for style.
5. Use zero emojis, zero em-dashes (U+2014) and zero en-dashes (U+2013).
6. Use a comma, colon, full stop or the word "to" in place of a dash.
7. Write numeric ranges as "5 to 10".

## Banned vocabulary

delve, leverage, tapestry, testament, seamless, seamlessly, cutting-edge, game-changer, unlock, unleash, elevate, foster, realm, paradigm, beacon, underscore, pivotal, meticulous, embark, symphony, robust.

## Replacements

| Banned | Use |
|---|---|
| leverage | use |
| seamless | smooth, or state the fact |
| robust | tested, or state the limit |
| unlock | enable |
| elevate | improve |
| foster | support |
| pivotal | key |

## Structural checks (merged from hardikpandya/stop-slop)

1. Cut throat-clearing openers such as "here is the thing".
2. Skip binary contrasts ("not X, but Y"). State Y.
3. Name the person doing the action. Avoid things doing human verbs.
4. Replace vague declaratives with the specific fact.
5. Avoid lazy extremes: every, always, never.
6. Vary sentence length. End paragraphs in different ways.
7. Cut any line that reads like a pull-quote.
8. Trust the reader. Skip softening and hand-holding.

## Enforcement

1. The guard-prose hook blocks these terms in *.md, *.svg and *.html.
2. Rewrite the sentence. Do not hunt for a synonym.
3. Add no attribution to any AI tool in repo files or commits.
