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

import nonchalant_cv as core

DEFAULT_MODEL = "qwen2.5:3b"

# Languages people can speak to Mosala and receive explanations in: the DR Congo's
# national languages first, then the most widely spoken languages in the world.
LANGUAGES = {
    "ln": "Lingala", "sw": "Swahili", "kg": "Kikongo", "lua": "Tshiluba",
    "fr": "French", "en": "English", "es": "Spanish", "pt": "Portuguese", "ar": "Arabic",
    "zh": "Mandarin Chinese", "hi": "Hindi", "bn": "Bengali", "ru": "Russian", "ur": "Urdu",
}
LOCAL = {"ln", "sw", "kg", "lua"}

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
}

NUMBER = re.compile(r"\d+")
NUMBER_WORDS = {  # so "six years" written as a word in the story still counts as said
    "1": ["one", "un", "moja", "moko"], "2": ["two", "deux", "mbili", "mibale"],
    "3": ["three", "trois", "tatu", "misato"], "4": ["four", "quatre", "nne", "minei"],
    "5": ["five", "cinq", "tano", "mitano"], "6": ["six", "sita", "motoba"],
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


def strip_unsaid_numbers(text: str, said: set[str], warnings: list[str]) -> str:
    """Remove a line's claim if it contains a number the person never said."""
    bad = [n for n in NUMBER.findall(text) if n not in said]
    if bad:
        warnings.append(f"Removed a detail with a number not in your story ({', '.join(bad)}): \"{text}\"")
        return ""
    return text


# --- Step 1: understand the story ---------------------------------------------

def understand(story: str, chat) -> dict:
    system = (
        "A worker describes their work, possibly in Lingala, Swahili, Kikongo, Tshiluba, French or "
        "English. Understand it and reply in English with JSON only, shaped as "
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

def write_cv(profile: dict, target: str, chat) -> dict:
    language = LANGUAGES[target]
    system = (
        f"You turn a worker's facts into professional CV content in {language}. Reply with JSON only, "
        'shaped as {"title": str, "summary": str, "experiences": [{"role": str, "place": str, '
        '"period": str, "bullets": [str]}], "skills": [str], "tools": [str], "languages": [str], '
        '"education": [str]}. The summary is two sentences. Each bullet starts with an action verb. '
        "Use only the facts given. Do not add numbers, employers, certificates or results that are "
        "not in the facts. Keep empty fields empty."
    )
    try:
        data = json.loads(chat(system, json.dumps(profile, ensure_ascii=False), True))
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def clean_cv(cv: dict, said: set[str], warnings: list[str]) -> dict:
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
    lines = [f"# {contact.get('name') or ''}".rstrip(), ""]
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

def make_cv(story: str, target: str, contact: dict, chat) -> tuple[str, dict, list[str]]:
    warnings: list[str] = []
    profile = understand(story, chat)
    cv = clean_cv(write_cv(profile, target, chat), numbers_said(story), warnings)
    if not cv["experiences"] and not cv["skills"]:
        warnings.append("The model could not find work details. Add more about what you do and where.")
    return render_markdown(cv, target, contact), profile, warnings


def explain_offer(offer: str, lang: str, chat) -> str:
    language = LANGUAGES[lang]
    system = (
        f"Explain this job offer in simple {language}, as you would to a friend who did not study "
        "much. Use short sentences and these parts: what the job is, where, what they ask for, "
        "what they offer (only if written), how and before when to apply (only if written). "
        "Do not add anything that is not in the offer. If you are unsure of a word in "
        f"{language}, keep the French or English word."
    )
    return chat(system, offer, False).strip()


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
        print(f"Check: {w}")
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
        return cmd_cv(a, chat) if a.command == "cv" else cmd_offer(a, chat)
    except core.OllamaError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
