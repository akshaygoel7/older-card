# Older Card

A later retelling of a memory can be vivid and still be the wrong line for an ofrenda. Older Card asks a local model for one remembrance sentence, then keeps it only when every content word already appears on the older card.

The four notes in `samples/pile.txt` are made up. Nothing in that file is a family record.

## Run

```bash
ollama pull gemma3:1b
python3 older_card.py samples/pile.txt --html docs/run.html
```

Tests do not need Ollama:

```bash
python3 -m unittest tests.test_older_card
```

## What gets kept

A model line stays only when all of these are true:

- every content word already appears on the older card
- it does not borrow a word that appears only in the later retelling
- a digit on the line, including a year, already appears on the card
- a number stays attached to the same word as on the card
- it still names something the card named

If any check fails, the line is thrown away and the card's first sentence stays.

Function words are allowed even when the card did not use them: a, an, the, to, of, and, or, for, in, on, at, into, with, from, before, after, about, where, when, she, he, her, his, it, was, were.
