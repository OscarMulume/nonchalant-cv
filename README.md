# nonchalant-cv

**The lazy job seeker's assistant.** Paste a job offer, point it at your CV, go make coffee.
A local open-weight model reads both and hands you back what an applicant tracking system (ATS)
will look for.

Built for the DEV Hacktoberfest 2026 Open-Source AI Challenge, Week 3: *Slow and Steady*.

## What you get

For each offer, `nonchalant-cv` writes a `report.md` with:

1. **ATS keyword match**: a score, the keywords your CV already shows, and the ones it is missing.
2. **Three CV bullets** rewritten for this offer, using only facts already in your CV.
3. **A cover letter draft** in the offer's language (French or English).

## How it works

1. **Read the offer.** The model lists the skills and certifications the offer asks for. Python then keeps only the words that really appear in the offer, so a small model cannot invent or translate keywords.
2. **Compare with your CV.** Plain Python checks each keyword against your CV (case, accents and plurals ignored) and computes the match score.
3. **Tune three bullets.** Python picks the three CV bullets that share the most keywords with the offer. The model rewrites each one. If a rewrite adds a tool your CV does not show, the original bullet is kept.
4. **Draft the letter.** The model gets the list of skills you have and the list you do not have. If the letter still claims a missing skill or keeps a `[placeholder]`, the report warns you.

## Why local and open

- **Your CV stays on your machine.** It holds your phone number, address and work history. Nothing is sent to a cloud API.
- **It costs nothing per offer.** Apply to fifty jobs, pay nothing.
- **It works on a weak connection.** After one ~1 GB model download, no internet is needed.
- **You choose the model.** Start with `qwen2.5:1.5b` (1 GB). For better letters, use `qwen2.5:3b` (2 GB) with `--model`.

## Setup (Windows, macOS or Linux)

1. Install [Ollama](https://ollama.com/download).
2. Download a small open-weight model:
   ```
   ollama pull qwen2.5:1.5b
   ```
3. Python 3.9 or newer. No other dependency.

## Use

```
python nonchalant_cv.py --cv samples/cv.txt --offer samples/offer.txt
```

Options:

| Option | What it does |
| --- | --- |
| `--cv` | Your CV as a `.txt` or `.md` file (copy-paste it from Word or PDF) |
| `--offer` | The job offer as a `.txt` file |
| `--model` | Any Ollama model, default `qwen2.5:1.5b` (try `qwen2.5:3b` or `gemma3` for better writing) |
| `--out` | Where to save the report, default `report.md` |
| `--no-ai` | Keyword check only, instant, no model needed |

The files in `samples/` are fictional. Use your own CV and a real offer.

## Honesty rule

The prompts tell the model never to invent experience, tools or results. Small models still make
mistakes, so read every line before you send anything. A missing keyword is not something to
paste in: if it is not true for you, it is a skill to learn.

## Tests

```
python -m unittest discover tests
```

The tests replace Ollama with a fake, so they run without a model.

## License

MIT
