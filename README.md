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

### Languages

Mosala is Congolese first. The language menu is grouped:

- **National languages of the DR Congo:** Lingala, Kiswahili, Kikongo, Tshiluba.
- **Other languages of the DR Congo:** Kiluba, Otetela, Lomongo, Kinande, Mashi, Pazande.
- **Other African languages (27):** Kinyarwanda, Kirundi, Luganda, Amharic, Oromo, Somali, Tigrinya, Hausa, Yoruba, Igbo, Twi, Ewe, Wolof, Pulaar, Bambara, Sango, Umbundu, isiZulu, isiXhosa, Afrikaans, Sesotho, Setswana, chiShona, Chichewa, Bemba, Malagasy, Tamazight.
- **World languages:** French, English, Spanish, Portuguese, Arabic, Mandarin, Hindi, Bengali, Russian, Urdu.

Each language shows the quality to expect from small open models today (good, medium or experimental),
so nobody is misled. CVs can be written in French, English, Swahili, Spanish or Portuguese.

The page also offers **guided questions** (trade, years, where, tasks, tools, one achievement, languages,
training) for people who do not know what to write, and a **Copy for WhatsApp** button, because in the
DR Congo a CV is often shared on WhatsApp first.

## Quick start

1. Install [Ollama](https://ollama.com/download) and Python 3.9 or newer. No other dependency.
2. Download a model (about 2 GB, once):
   ```
   ollama pull qwen2.5:3b
   ```
3. **Open the web page** (easiest):
   ```
   python app.py
   ```
   Your browser opens `http://localhost:8000`. On Windows you can also double-click `start_mosala.bat`.
   The page works in French, English, Swahili and Lingala, and nothing leaves your computer: the page
   talks only to a small server on your machine, which talks only to Ollama.
4. Or use the command line with the samples:
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

## More tools in the same page

- **Job titles recruiters search for.** Mosala recognises everyday trade words in French, Swahili,
  Lingala and English (*fundi wa simu*, *wewa*, *sentinelle*, *motongi*…) and suggests the formal title
  used in job offers, such as "Technicien en réparation de téléphones" or "Solar PV Installer".
- **Training centre / NGO mode.** Load a CSV (one row per person: name, city, phone, email, story,
  cv_lang). Mosala writes every CV and prints them all at once, one per page. A template is provided.
- **Community messages.** Health centres, NGOs and local authorities write a message once (a
  vaccination day, a safety notice) and get it in Lingala, Swahili, Kikongo, Tshiluba or any listed
  language. Mosala flags any number (date, phone, dose) missing from a translation, and the Copy
  button stays locked until someone ticks "Checked by a speaker". Command line: `python mosala.py alert --message msg.txt`.
- **Voice.** "Listen" reads results aloud with the voices installed on the computer, for people who
  read with difficulty. "Dictate" lets people speak their story in French, English or Swahili; it uses
  the browser's online speech service, which the page says clearly. No open model handles spoken
  Lingala offline yet.
- **Phones on the same Wi-Fi.** A training centre with one computer can serve a whole room:
  `python app.py --lan` prints an address that phones on the same Wi-Fi can open. Use it only on a
  network you trust.

## Roadmap

- **Offline speech for Congolese languages**, when open speech models support them well.
- **An Android app** that runs a small model on the phone itself.
- **Public services**: how to get a passport, a birth certificate or a business licence, explained in your language.
- **Language learning**: daily Lingala and Swahili phrases.
- **Market prices for farmers**, in their language.

## Tests

```
python -m unittest discover tests
```

The tests replace Ollama with a fake, so they run without a model.

## License

MIT
