# Mosala

**Your work, your language, your CV.** *Mosala* means "work" in Lingala.

In the DR Congo, many skilled workers (electricians, mechanics, phone repairers, masons, solar
installers) never wrote a CV. Most job offers are only in French or English, while millions of people
live their working life in Lingala, Swahili, Kikongo or Tshiluba. Mosala lets them describe their
work the way they would tell a friend, in their own language, and does the slow, boring part for them.

Mosala grew into a language bridge for Africa: there is no Google Translate for most African
languages, so Mosala lists every African country with at least three of its languages, and lets two
people who share no language **talk to each other by voice**, each in their own.

It runs entirely on your own computer with a local open-weight model through [Ollama](https://ollama.com).

Built for the DEV Hacktoberfest 2026 Open-Source AI Challenge, Week 3: *Slow and Steady*.

## What it does

| Command | You give | You get |
| --- | --- | --- |
| `cv` | A few lines about your work, in Lingala, Swahili, Kikongo, Tshiluba, French, English or another language | A professional CV in French, English, Spanish or Portuguese (Markdown + a printable HTML page) |
| `offer` | A job offer in French or English | The offer explained in simple words, in your language |
| `match` | Your CV and a job offer | ATS keyword score, missing keywords, three tuned CV bullets and a cover letter draft |
| Conversation (web page) | Two people, two languages, speaking or typing | Each one reads, and hears, the other in their own language |

### Languages

Mosala is Congolese first. The language menu is grouped:

- **National languages of the DR Congo:** Lingala, Kiswahili, Kikongo, Tshiluba.
- **Other languages of the DR Congo:** Kiluba, Otetela, Lomongo, Kinande, Mashi, Pazande.
- **Other African languages (27):** Kinyarwanda, Kirundi, Luganda, Amharic, Oromo, Somali, Tigrinya, Hausa, Yoruba, Igbo, Twi, Ewe, Wolof, Pulaar, Bambara, Sango, Umbundu, isiZulu, isiXhosa, Afrikaans, Sesotho, Setswana, chiShona, Chichewa, Bemba, Malagasy, Tamazight.
- **African languages, by country:** all 54 African countries, each with at least three languages
  (African languages first, then the official ones), about 150 languages in total: Fon and Bariba in
  Benin, Mooré and Dioula in Burkina Faso, Kikuyu, Dholuo and Luhya in Kenya, Naija and Tiv in Nigeria,
  Serer and Jola in Senegal, Krio, Mende and Temne in Sierra Leone, Darija and Tachelhit in Morocco,
  Dinka and Nuer in South Sudan… The list lives in [`africa.py`](africa.py) and is easy to correct.
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

## Conversation: two people, two languages

The **Conversation** tab removes the language barrier between two people.

- **On one phone, face to face.** Person A picks a country and a language, person B too. Each presses
  **Speak** (or types). Mosala translates and reads the translation aloud in the other person's
  language. Tick "Turn side B upside down" and lay the phone between you: each person reads their own
  half of the screen.
- **On two phones.** Run `python app.py --lan`. One person creates a room and gets a 4-digit code; the
  other opens the address on their own phone and joins with the code. Each one writes or speaks in
  their language and receives the other's messages, translated and read aloud, in theirs. Rooms live
  only in memory and disappear after six hours.
- **Check the meaning.** For languages marked experimental, "Check the meaning" translates the
  translation back into the speaker's language, so the speaker sees whether the message survived.
- **Numbers are protected.** If a time, a price or a phone number is missing from a translation,
  Mosala says so under the message.

What depends on the device: speech recognition comes from the browser's online service and knows
only some languages (French, English, Swahili, Arabic, Amharic, isiZulu, Afrikaans and a few more);
for the others, people type. Reading aloud needs a voice for that language on the device; when there
is none, Mosala says "show the screen".

## Roadmap

- **Offline speech for African languages**, with open speech models (such as Meta's MMS) as they improve.
- **Corrections from speakers** for each country's list and for each translation.
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
