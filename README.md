# Mosala

**Your work, your language, your CV.** *Mosala* means "work" in Lingala.

In the DR Congo, many skilled workers (electricians, mechanics, phone repairers, masons, solar
installers) never wrote a CV. Most job offers are only in French or English, while millions of people
live their working life in Lingala, Swahili, Kikongo or Tshiluba. Mosala lets them describe their
work the way they would tell a friend, in their own language, and does the slow, boring part for them.

It runs entirely on your own computer with a local open-weight model through [Ollama](https://ollama.com).

Built for the DEV Hacktoberfest 2026 Open-Source AI Challenge, Week 3: *Slow and Steady*.

## What it does

| Command | You give | You get |
| --- | --- | --- |
| `cv` | A few lines about your work, in Lingala, Swahili, Kikongo, Tshiluba, French, English or another language | A professional CV in French, English, Spanish or Portuguese (Markdown + a printable HTML page) |
| `offer` | A job offer in French or English | The offer explained in simple words, in your language |
| `match` | Your CV and a job offer | ATS keyword score, missing keywords, three tuned CV bullets and a cover letter draft |

Languages you can use: Lingala, Swahili, Kikongo, Tshiluba (the four national languages of the DR Congo),
French, English, Spanish, Portuguese, Arabic, Mandarin, Hindi, Bengali, Russian and Urdu.

## Quick start

1. Install [Ollama](https://ollama.com/download) and Python 3.9 or newer. No other dependency.
2. Download a model (about 2 GB, once):
   ```
   ollama pull qwen2.5:3b
   ```
3. Try the samples:
   ```
   python mosala.py cv --story samples/story_ln.txt --to fr --name "Jean Mbuyi" --city Kinshasa
   python mosala.py cv --story samples/story_sw.txt --to en --name "Amina Bahati" --city Goma
   python mosala.py offer --offer samples/offer.txt --lang sw
   python mosala.py match --cv samples/cv.txt --offer samples/offer.txt
   ```
   Open the generated `cv_fr.html` in a browser and print it to PDF.

Use `--model gemma3:4b` (or any Ollama model) to compare models. The samples are fictional.

## How it keeps the CV honest

A CV that lies hurts the person who sends it. Mosala guards against a model that makes things up:

- **Two steps.** The model first extracts only the facts the person said (in English, saved to `*_facts.json` so you can check them), then writes the CV from those facts alone.
- **Number check.** Any number in the CV that the person never said (as digits or as a word such as *motoba*, *sita* or *six*) is removed, and Mosala tells you which line it removed.
- **Fixed section titles.** CV headings are written by hand for each language, not generated.
- **Keyword check.** In `match`, keywords are kept only if they appear in the offer, and the letter is flagged if it claims a skill your CV does not show.

## Why local and open

- **Private.** A CV holds a phone number, a home area and a work history. Nothing leaves the computer.
- **Works on a weak connection.** After one model download, no internet is needed, which matters where data is expensive.
- **Free to run.** No API bill, so a training centre or an NGO can run it for hundreds of people.
- **Open to improve.** Anyone can swap the model or improve the prompts for their own language.

## Limits, said plainly

Open models understand Swahili much better than Lingala, Kikongo or Tshiluba. For those languages,
results vary and a fluent speaker should review the output. Explanations in a local language say so
at the bottom. Help is welcome: corrections from native speakers are the most valuable contribution.

## Roadmap: one toolkit for everyday needs

Mosala starts with work because a job changes a family's life. The same local, multilingual approach can serve:

- **Voice input**, so people who do not write can speak their story.
- **Health and safety alerts for NGOs**, translated into the four national languages with human review before sending.
- **Public services**: how to get a passport, a birth certificate or a business licence, explained in your language.
- **Language learning**: daily Lingala and Swahili phrases for people who do not speak the national languages.
- **Market prices for farmers**, in their language.

## Tests

```
python -m unittest discover tests
```

The tests replace Ollama with a fake, so they run without a model.

## License

MIT
