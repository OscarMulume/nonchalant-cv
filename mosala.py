"""Mosala: tell your work in your own language, get a professional CV.

"Mosala" means "work" in Lingala. Many skilled workers in the DR Congo
(electricians, mechanics, phone repairers, masons) never wrote a CV, and
most job offers are only in French or English. Mosala closes that gap
with a local open-weight model running through Ollama:

  cv     Describe your work in Lingala, Swahili, Kikongo, Tshiluba, French,
         English or another language. Get a CV in French or English.
  offer  Paste a job offer. Get it explained in plain words, in your language.
  match  Compare your CV with an offer (ATS keywords, tuned bullets, letter).

Everything runs on your machine. Nothing is sent to a server.

Examples:
    python mosala.py cv --story samples/story_ln.txt --to fr --name "Jean Mbuyi" --phone "+243 000 000 000"
    python mosala.py offer --offer samples/offer.txt --lang ln
    python mosala.py match --cv samples/cv.txt --offer samples/offer.txt
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

import africa
import nonchalant_cv as core

DEFAULT_MODEL = "qwen2.5:3b"

# Languages people can speak to Mosala and receive explanations in. Mosala is Congolese first:
# the DR Congo's four national languages, then other widely spoken Congolese languages, then
# other African languages and the world's most spoken languages as options.
# Each entry: code, English name (for the model), native name (for people), where spoken, tier.
# Tier is the quality to expect from small open models today: "good", "medium" or "experimental".
LANGUAGE_GROUPS = [
    ("drc_national", [
        ("ln", "Lingala", "Lingála", "DR Congo, Congo", "experimental"),
        ("sw", "Congolese Swahili", "Kiswahili", "DR Congo (east), East Africa", "medium"),
        ("kg", "Kikongo (Kituba)", "Kikongo", "DR Congo (west), Congo, Angola", "experimental"),
        ("lua", "Tshiluba (Luba-Kasai)", "Tshiluba", "DR Congo (Kasai)", "experimental"),
    ]),
    ("drc_other", [
        ("lu", "Kiluba (Luba-Katanga)", "Kiluba", "DR Congo (Katanga)", "experimental"),
        ("tll", "Otetela", "Otetela", "DR Congo (Sankuru, Maniema)", "experimental"),
        ("lol", "Lomongo", "Lomongo", "DR Congo (Équateur)", "experimental"),
        ("nnb", "Kinande", "Kinande", "DR Congo (North Kivu)", "experimental"),
        ("shr", "Mashi", "Mashi", "DR Congo (South Kivu)", "experimental"),
        ("zne", "Zande", "Pazande", "DR Congo (north), South Sudan, CAR", "experimental"),
    ]),
    ("africa", [
        ("rw", "Kinyarwanda", "Ikinyarwanda", "Rwanda, DR Congo (Kivu)", "experimental"),
        ("rn", "Kirundi", "Ikirundi", "Burundi", "experimental"),
        ("lg", "Luganda", "Luganda", "Uganda", "experimental"),
        ("am", "Amharic", "አማርኛ", "Ethiopia", "medium"),
        ("om", "Oromo", "Afaan Oromoo", "Ethiopia, Kenya", "experimental"),
        ("so", "Somali", "Soomaali", "Somalia, Djibouti, Ethiopia, Kenya", "medium"),
        ("ti", "Tigrinya", "ትግርኛ", "Eritrea, Ethiopia", "experimental"),
        ("ha", "Hausa", "Hausa", "Nigeria, Niger, Ghana", "medium"),
        ("yo", "Yoruba", "Yorùbá", "Nigeria, Benin", "medium"),
        ("ig", "Igbo", "Igbo", "Nigeria", "medium"),
        ("ak", "Twi (Akan)", "Twi", "Ghana", "experimental"),
        ("ee", "Ewe", "Eʋegbe", "Ghana, Togo", "experimental"),
        ("wo", "Wolof", "Wolof", "Senegal, Gambia", "experimental"),
        ("ff", "Fula (Pulaar)", "Pulaar", "West and Central Africa", "experimental"),
        ("bm", "Bambara", "Bamanankan", "Mali", "experimental"),
        ("sg", "Sango", "Sängö", "Central African Republic", "experimental"),
        ("umb", "Umbundu", "Umbundu", "Angola", "experimental"),
        ("zu", "Zulu", "isiZulu", "South Africa", "medium"),
        ("xh", "Xhosa", "isiXhosa", "South Africa", "medium"),
        ("af", "Afrikaans", "Afrikaans", "South Africa, Namibia", "good"),
        ("st", "Sesotho", "Sesotho", "Lesotho, South Africa", "experimental"),
        ("tn", "Setswana", "Setswana", "Botswana, South Africa", "experimental"),
        ("sn", "Shona", "chiShona", "Zimbabwe", "experimental"),
        ("ny", "Chichewa", "Chichewa", "Malawi, Zambia", "experimental"),
        ("bem", "Bemba", "Ichibemba", "Zambia, DR Congo (Katanga)", "experimental"),
        ("mg", "Malagasy", "Malagasy", "Madagascar", "medium"),
        ("ber", "Tamazight (Berber)", "Tamaziɣt", "Morocco, Algeria", "experimental"),
    ]),
    ("world", [
        ("fr", "French", "Français", "", "good"), ("en", "English", "English", "", "good"),
        ("es", "Spanish", "Español", "", "good"), ("pt", "Portuguese", "Português", "", "good"),
        ("ar", "Arabic", "العربية", "", "good"), ("zh", "Mandarin Chinese", "中文", "", "good"),
        ("hi", "Hindi", "हिन्दी", "", "good"), ("bn", "Bengali", "বাংলা", "", "good"),
        ("ru", "Russian", "Русский", "", "good"), ("ur", "Urdu", "اردو", "", "good"),
    ]),
]
# Every other language from the country-by-country catalogue (africa.py).
LANGUAGE_GROUPS.append(("africa_more", [
    (code, name, native, ", ".join(africa.countries_of(code)), tier)
    for code, (name, native, tier) in africa.LANGS.items()
]))
LANG_INFO = {code: {"name": name, "native": native, "where": where, "tier": tier, "group": group}
             for group, items in LANGUAGE_GROUPS for code, name, native, where, tier in items}
LANGUAGES = {code: info["name"] for code, info in LANG_INFO.items()}
# Explanations in these languages get a "please check" note: models are less reliable there.
LOCAL = {code for code, info in LANG_INFO.items() if info["tier"] != "good"}


def language_for_prompt(code: str) -> str:
    info = LANG_INFO[code]
    return f"{info['name']} (as spoken in {info['where']})" if info["where"] else info["name"]


# CV output languages, with section titles written by hand (not by the model).
CV_LABELS = {
    "fr": {"summary": "Profil", "experience": "Expérience professionnelle", "skills": "Compétences",
           "tools": "Outils et équipements", "languages": "Langues", "education": "Formation"},
    "en": {"summary": "Professional Summary", "experience": "Professional Experience", "skills": "Skills",
           "tools": "Tools and Equipment", "languages": "Languages", "education": "Education"},
    "es": {"summary": "Perfil", "experience": "Experiencia profesional", "skills": "Competencias",
           "tools": "Herramientas y equipos", "languages": "Idiomas", "education": "Formación"},
    "pt": {"summary": "Perfil", "experience": "Experiência profissional", "skills": "Competências",
           "tools": "Ferramentas e equipamentos", "languages": "Idiomas", "education": "Formação"},
    "sw": {"summary": "Wasifu kwa ufupi", "experience": "Uzoefu wa kazi", "skills": "Ujuzi",
           "tools": "Zana na vifaa", "languages": "Lugha", "education": "Elimu"},
}

NUMBER = re.compile(r"\d+")
NUMBER_WORDS = {  # so "six years" written as a word in the story still counts as said
    "1": ["one", "un", "moja", "moko"], "2": ["two", "deux", "mbili", "miwili", "mibale"],
    "3": ["three", "trois", "tatu", "mitatu", "misato"], "4": ["four", "quatre", "nne", "minne", "minei"],
    "5": ["five", "cinq", "tano", "mitano"], "6": ["six", "sita", "motoba", "mitoba"],
    "7": ["seven", "sept", "saba", "nsambo"], "8": ["eight", "huit", "nane", "mwambe"],
    "9": ["nine", "neuf", "tisa", "libwa"], "10": ["ten", "dix", "kumi", "zomi"],
    "50": ["fifty", "cinquante", "hamsini", "ntuku mitano"],
}


def numbers_said(story: str) -> set[str]:
    norm = core.normalize(story)
    said = set(NUMBER.findall(norm))
    for digit, words in NUMBER_WORDS.items():
        if any(core.contains_term(norm, w) for w in words):
            said.add(digit)
    return said


WARNING_TEXT = {
    "number_removed": 'Removed a detail with a number not in your story ({numbers}): "{text}"',
    "no_details": "The model could not find work details. Add more about what you do and where.",
}


def warning_text(w: dict) -> str:
    return WARNING_TEXT[w["kind"]].format(**w)


def strip_unsaid_numbers(text: str, said: set[str], warnings: list[dict]) -> str:
    """Remove a line's claim if it contains a number the person never said."""
    bad = [n for n in NUMBER.findall(text) if n not in said]
    if bad:
        warnings.append({"kind": "number_removed", "numbers": ", ".join(bad), "text": text})
        return ""
    return text


# --- Informal trades -> job titles recruiters search for -----------------------
# Each entry: words people use (French, Swahili, Lingala, English), then the French and
# English titles found in job offers. Extend it: corrections from the field are welcome.
TRADES = [
    (["fundi wa simu", "réparateur de téléphone", "reparateur de telephone", "kobongisa telephone", "phone repair"],
     "Technicien en réparation de téléphones", "Mobile Phone Repair Technician"),
    (["kompyuta", "réparation d'ordinateur", "maintenance informatique", "computer repair"],
     "Technicien de maintenance informatique", "IT Support Technician"),
    (["électricien", "electricien", "fundi wa umeme", "courant", "electrician"],
     "Électricien du bâtiment", "Building Electrician"),
    (["panneau solaire", "panneaux solaires", "solaire", "solar"],
     "Installateur photovoltaïque", "Solar PV Installer"),
    (["mécanicien", "mecanicien", "fundi wa magari", "mobongisi ya mituka", "garage", "mechanic"],
     "Mécanicien automobile", "Automotive Mechanic"),
    (["maçon", "macon", "fundi wa nyumba", "motongi", "construction", "mason"],
     "Maçon", "Mason"),
    (["menuisier", "seremala", "fundi wa mbao", "carpenter"],
     "Menuisier", "Carpenter"),
    (["soudeur", "soudure", "welding", "welder"],
     "Soudeur", "Welder"),
    (["plombier", "fundi wa bomba", "plumber"],
     "Plombier", "Plumber"),
    (["frigoriste", "climatisation", "frigo", "air conditioning"],
     "Technicien frigoriste et climatisation", "Refrigeration and AC Technician"),
    (["couturier", "couturière", "tailleur", "fundi wa nguo", "cherehani", "tailor"],
     "Couturier / Tailleur", "Tailor"),
    (["coiffeur", "coiffeuse", "kinyozi", "barber", "hairdresser"],
     "Coiffeur", "Hairdresser"),
    (["chauffeur", "dereva", "motari", "driver"],
     "Chauffeur", "Driver"),
    (["wewa", "moto-taxi", "taxi-moto", "boda boda", "bodaboda"],
     "Chauffeur-livreur moto", "Motorcycle Delivery Rider"),
    (["sentinelle", "gardien", "agent de sécurité", "mlinzi", "security guard"],
     "Agent de sécurité", "Security Guard"),
    (["cuisinier", "cuisinière", "mpishi", "cook"],
     "Cuisinier", "Cook"),
    (["vendeur", "vendeuse", "commerçant", "muuzaji", "shop", "boutique"],
     "Vendeur / Commerçant", "Sales Assistant"),
    (["agriculteur", "mkulima", "élevage", "elevage", "farmer"],
     "Agriculteur / Éleveur", "Farmer"),
    (["infirmier", "infirmière", "muuguzi", "nurse"],
     "Infirmier", "Nurse"),
    (["enseignant", "mwalimu", "molakisi", "teacher"],
     "Enseignant", "Teacher"),
]


def suggest_titles(story: str) -> list[dict]:
    """Formal job titles whose everyday words appear in the story."""
    norm = core.normalize(story)
    found = []
    for words, fr, en in TRADES:
        if any(core.contains_term(norm, w) for w in words):
            found.append({"fr": fr, "en": en})
    return found


# --- Step 1: understand the story ---------------------------------------------

def understand(story: str, chat) -> dict:
    system = (
        "A worker describes their work, possibly in Lingala, Swahili, Kikongo, Tshiluba, another "
        "Congolese or African language, French or English. Understand it and reply in English with JSON only, shaped as "
        '{"spoken_language": str, "trade": str, "experiences": [{"role": str, "place": str, '
        '"period": str, "tasks": [str]}], "skills": [str], "tools": [str], "languages": [str], '
        '"education": [str]}. Use only facts the person said. If something is not said, use an '
        "empty string or an empty list. Never guess dates, numbers, employers or diplomas."
    )
    try:
        data = json.loads(chat(system, story, True))
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    for key in ("experiences", "skills", "tools", "languages", "education"):
        if not isinstance(data.get(key), list):
            data[key] = []
    data.setdefault("trade", "")
    data.setdefault("spoken_language", "")
    return data


# --- Step 2: write the CV in the target language ------------------------------

def write_cv(profile: dict, target: str, chat, titles: list[dict] | None = None) -> dict:
    language = language_for_prompt(target)
    system = (
        f"You turn a worker's facts into professional CV content in {language}. Reply with JSON only, "
        'shaped as {"title": str, "summary": str, "experiences": [{"role": str, "place": str, '
        '"period": str, "bullets": [str]}], "skills": [str], "tools": [str], "languages": [str], '
        '"education": [str]}. The summary is two sentences. Each bullet starts with an action verb. '
        "Use only the facts given. Do not add numbers, employers, certificates or results that are "
        "not in the facts. Keep empty fields empty."
    )
    user = json.dumps(profile, ensure_ascii=False)
    if titles:
        key = "fr" if target == "fr" else "en"
        user += ("\n\nRecruiters search for these job titles; use the one that fits the facts as the title: "
                 + ", ".join(t[key] for t in titles))
    try:
        data = json.loads(chat(system, user, True))
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def clean_cv(cv: dict, said: set[str], warnings: list[dict]) -> dict:
    def text(v):
        return strip_unsaid_numbers(v.strip(), said, warnings) if isinstance(v, str) else ""

    def items(v):
        return [t for t in (text(x) for x in (v if isinstance(v, list) else [])) if t]

    out = {"title": text(cv.get("title", "")), "summary": text(cv.get("summary", ""))}
    out["experiences"] = []
    for e in cv.get("experiences", []) if isinstance(cv.get("experiences"), list) else []:
        if not isinstance(e, dict):
            continue
        exp = {"role": text(e.get("role", "")), "place": text(e.get("place", "")),
               "period": text(e.get("period", "")), "bullets": items(e.get("bullets"))}
        if exp["role"] or exp["bullets"]:
            out["experiences"].append(exp)
    for key in ("skills", "tools", "languages", "education"):
        out[key] = items(cv.get(key))
    return out


# --- Rendering ----------------------------------------------------------------

def render_markdown(cv: dict, target: str, contact: dict) -> str:
    L = CV_LABELS[target]
    lines = [f"# {contact['name']}", ""] if contact.get("name") else []
    if cv["title"]:
        lines += [f"**{cv['title']}**", ""]
    info = " · ".join(v for v in (contact.get("city"), contact.get("phone"), contact.get("email")) if v)
    if info:
        lines += [info, ""]
    if cv["summary"]:
        lines += [f"## {L['summary']}", "", cv["summary"], ""]
    if cv["experiences"]:
        lines += [f"## {L['experience']}", ""]
        for e in cv["experiences"]:
            head = " — ".join(x for x in (e["role"], e["place"]) if x)
            lines.append(f"**{head}**" + (f" | {e['period']}" if e["period"] else ""))
            lines += [f"- {b}" for b in e["bullets"]] + [""]
    for key in ("skills", "tools", "languages", "education"):
        if cv[key]:
            lines += [f"## {L[key]}", "", ", ".join(cv[key]) if key != "education" else "\n".join(f"- {x}" for x in cv[key]), ""]
    return "\n".join(lines).strip() + "\n"


def render_html(markdown: str, title: str) -> str:
    """A single-column, ATS-friendly printable page (open in a browser, print to PDF)."""
    body = []
    for line in markdown.splitlines():
        esc = html.escape(line)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        if line.startswith("# "):
            body.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("- "):
            body.append(f"<li>{esc[2:]}</li>")
        elif line.strip():
            body.append(f"<p>{esc}</p>")
    joined = re.sub(r"((?:<li>.*?</li>)+)", r"<ul>\1</ul>", "".join(body))
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
        "<style>body{font-family:Arial,Helvetica,sans-serif;max-width:760px;margin:32px auto;padding:0 20px;"
        "color:#1a1a1a;line-height:1.45}h1{color:#1f3864;margin:0 0 4px}h2{color:#1f3864;border-bottom:2px solid #1f3864;"
        "padding-bottom:3px;margin-top:22px;font-size:1.1em}p{margin:4px 0}ul{margin:4px 0 10px 18px;padding:0}"
        "@media print{body{margin:0}}</style></head><body>" + joined + "</body></html>\n"
    )


# --- Commands -----------------------------------------------------------------

def make_cv(story: str, target: str, contact: dict, chat) -> tuple[str, dict, list[dict]]:
    warnings: list[dict] = []
    profile = understand(story, chat)
    cv = clean_cv(write_cv(profile, target, chat, suggest_titles(story)), numbers_said(story), warnings)
    if not cv["experiences"] and not cv["skills"]:
        warnings.append({"kind": "no_details"})
    return render_markdown(cv, target, contact), profile, warnings


def explain_offer(offer: str, lang: str, chat) -> str:
    language = language_for_prompt(lang)
    system = (
        f"Explain this job offer in simple {language}, as you would to a friend who did not study "
        "much. Use short sentences and these parts: what the job is, where, what they ask for, "
        "what they offer (only if written), how and before when to apply (only if written). "
        "Do not add anything that is not in the offer. If you are unsure of a word in "
        f"{language}, keep the French or English word."
    )
    return chat(system, offer, False).strip()


def translate_message(message: str, lang: str, chat) -> str:
    """Translate a short community message (health, safety, public notice) for review by a speaker."""
    language = language_for_prompt(lang)
    system = (
        f"Translate this public message into simple {language} for people in the community. Keep every "
        "number, date, place, phone number and instruction exactly. Do not add advice that is not in "
        "the message. Use short sentences. If a medical or technical word has no common equivalent, "
        "keep the French word. Reply with the translation only."
    )
    return chat(system, message, False).strip()


def translate_to_many(message: str, langs: list[str], chat) -> list[dict]:
    out = []
    for lang in langs:
        if lang not in LANG_INFO:
            continue
        text = translate_message(message, lang, chat)
        # Numbers carry the critical facts (dates, doses, phone numbers): flag any that changed.
        lost = sorted(set(NUMBER.findall(message)) - set(NUMBER.findall(text)), key=int)
        out.append({"lang": lang, "native": LANG_INFO[lang]["native"], "text": text,
                    "tier": LANG_INFO[lang]["tier"], "missing_numbers": lost})
    return out


def interpret(text: str, src: str, dst: str, chat, check: bool = False) -> dict:
    """Translate one turn of a spoken conversation between two people.

    With check=True the translation is also translated back into the speaker's language, so the
    speaker can see whether the meaning survived (useful for languages marked experimental).
    """
    text = text.strip()
    if src == dst:
        return {"text": text, "back": None, "missing_numbers": []}
    system = (
        f"You are an interpreter helping two people talk face to face. Translate what the speaker said "
        f"from {language_for_prompt(src)} into {language_for_prompt(dst)}. Use simple, natural spoken "
        "words, as people really talk. Keep names, numbers, dates, prices and places exactly. Do not answer "
        "the speaker, do not add or explain anything. If a word has no common equivalent, keep the "
        "original word. Reply with the translation only."
    )
    out = chat(system, text, False).strip().strip('"')
    back = None
    if check:
        back_system = (
            f"Translate this from {language_for_prompt(dst)} into {language_for_prompt(src)}, word for "
            "word as far as possible, so the speaker can check the meaning. Reply with the translation only."
        )
        back = chat(back_system, out, False).strip().strip('"')
    lost = sorted(set(NUMBER.findall(text)) - set(NUMBER.findall(out)), key=int)
    return {"text": out, "back": back, "missing_numbers": lost}


def cmd_cv(a, chat) -> int:
    story = a.story.read_text(encoding="utf-8", errors="ignore")
    contact = {"name": a.name, "phone": a.phone, "email": a.email, "city": a.city}
    print("Listening to your story. Relax, Mosala is writing your CV...")
    md, profile, warnings = make_cv(story, a.to, contact, chat)
    out = a.out or Path(f"cv_{a.to}.md")
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".html").write_text(render_html(md, a.name or "CV"), encoding="utf-8")
    out.with_name(out.stem + "_facts.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)
    for w in warnings:
        print(f"Check: {warning_text(w)}")
    print(f"Saved {out}, {out.with_suffix('.html')} (open it and print to PDF) and the facts file.")
    print("Read your CV carefully: fix anything that is not exactly true.")
    return 0


def cmd_offer(a, chat) -> int:
    offer = a.offer.read_text(encoding="utf-8", errors="ignore")
    print(f"Reading the offer for you in {LANGUAGES[a.lang]}...")
    text = explain_offer(offer, a.lang, chat)
    keywords = core.known_skills_in(offer)
    out = a.out or Path(f"offer_{a.lang}.md")
    report = f"# {LANGUAGES[a.lang]}\n\n{text}\n"
    if keywords:
        report += "\n**Keywords:** " + ", ".join(keywords) + "\n"
    if a.lang in LOCAL:
        report += "\n> Machine translation into local languages can make mistakes. Check important details in the original offer.\n"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved {out}")
    return 0


def cmd_alert(a, chat) -> int:
    message = a.message.read_text(encoding="utf-8", errors="ignore")
    langs = a.langs.split(",")
    print("Translating the message. Every translation must be checked by a speaker before it is shared.")
    lines = []
    for r in translate_to_many(message, langs, chat):
        lines += [f"## {r['native']}", "", r["text"], ""]
        if r["missing_numbers"]:
            lines += [f"> Check: these numbers are missing from the translation: {', '.join(r['missing_numbers'])}", ""]
    report = "\n".join(lines)
    out = a.out or Path("message_translations.md")
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Mosala: your work, your language, your CV. Runs locally with Ollama.")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("cv", help="describe your work in any language, get a CV")
    c.add_argument("--story", required=True, type=Path, help="text file where you describe your work")
    c.add_argument("--to", default="fr", choices=sorted(CV_LABELS), help="CV language (default: fr)")
    c.add_argument("--name", default="")
    c.add_argument("--phone", default="")
    c.add_argument("--email", default="")
    c.add_argument("--city", default="")
    c.add_argument("--out", type=Path)

    o = sub.add_parser("offer", help="get a job offer explained in your language")
    o.add_argument("--offer", required=True, type=Path)
    o.add_argument("--lang", default="ln", choices=sorted(LANGUAGES), help="your language (default: ln)")
    o.add_argument("--out", type=Path)

    al = sub.add_parser("alert", help="translate a community message (health, safety) into several languages")
    al.add_argument("--message", required=True, type=Path, help="text file with the message, in French or English")
    al.add_argument("--langs", default="ln,sw,kg,lua", help="comma-separated codes (default: the 4 national languages)")
    al.add_argument("--out", type=Path)

    m = sub.add_parser("match", help="compare your CV with an offer (same as nonchalant_cv.py)")
    m.add_argument("--cv", required=True)
    m.add_argument("--offer", required=True)
    m.add_argument("--out", default="report.md")
    m.add_argument("--no-ai", action="store_true")

    a = p.parse_args(argv)
    if a.command == "match":
        args = ["--cv", a.cv, "--offer", a.offer, "--model", a.model, "--out", a.out] + (["--no-ai"] if a.no_ai else [])
        return core.main(args)

    chat = lambda s, u, j: core.ollama_chat(a.model, s, u, j)  # noqa: E731
    try:
        return {"cv": cmd_cv, "offer": cmd_offer, "alert": cmd_alert}[a.command](a, chat)
    except core.OllamaError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
