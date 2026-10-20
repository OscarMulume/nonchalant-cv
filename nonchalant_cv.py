"""nonchalant-cv: the lazy job seeker's assistant.

Paste a job offer, point it at your CV, and go make coffee. A local
open-weight model (through Ollama) reads both, then you get back:

  1. a match score and the ATS keywords your CV is missing,
  2. three CV bullet rewrites aimed at this offer,
  3. a short cover letter draft in the offer's language.

Everything runs on your own machine. Your CV never leaves it.

Usage:
    python nonchalant_cv.py --cv samples/cv.txt --offer samples/offer.txt
    python nonchalant_cv.py --cv my_cv.txt --offer offer.txt --model qwen2.5:3b --out report.md
    python nonchalant_cv.py --cv samples/cv.txt --offer samples/offer.txt --no-ai   # keywords only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:1.5b"

# Skills an ATS commonly screens for in IT offers. The model adds offer-specific
# ones on top; this list keeps the score useful even with --no-ai.
KNOWN_SKILLS = [
    "python", "javascript", "typescript", "java", "c#", "go", "bash", "powershell", "sql",
    "postgresql", "mysql", "mongodb", "redis", "node.js", "nestjs", "react", "next.js",
    "flutter", "dart", "django", "flask", "fastapi", "docker", "kubernetes", "terraform",
    "ansible", "git", "github actions", "ci/cd", "aws", "azure", "gcp", "linux", "windows server",
    "active directory", "tcp/ip", "dns", "dhcp", "vlan", "vpn", "routing", "switching",
    "firewall", "cisco", "fortinet", "palo alto", "huawei", "aruba", "wi-fi", "ccna", "ccnp",
    "itil", "sla", "incident management", "change management", "monitoring", "backup",
    "disaster recovery", "siem", "soc", "vulnerability assessment", "penetration testing",
    "iso 27001", "owasp", "jwt", "oauth", "api", "rest", "microservices", "rabbitmq", "prisma",
    "jira", "agile", "scrum", "project management", "procurement", "logistics", "supply chain",
    "inventory", "fleet management", "excel", "power bi", "kobocollect", "french", "english",
    "swahili", "lingala",
]


def normalize(text: str) -> str:
    """Lowercase and strip accents so 'Réseau' matches 'reseau'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def contains_term(haystack_norm: str, term: str) -> bool:
    """True if the term appears as a whole word or phrase (not inside another word)."""
    t = re.escape(normalize(term).strip())
    if not t:
        return False
    if not t[-1].isalnum() or t.endswith("s"):
        pattern = rf"(?<![a-z0-9]){t}(?![a-z0-9])"
    else:  # let "vlan" match "VLANs" and "vpn" match "VPNs"
        pattern = rf"(?<![a-z0-9]){t}s?(?![a-z0-9])"
    return re.search(pattern, haystack_norm) is not None


def known_skills_in(text: str) -> list[str]:
    norm = normalize(text)
    return [s for s in KNOWN_SKILLS if contains_term(norm, s)]


@dataclass
class Match:
    required: list[str]
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return round(100 * len(self.matched) / len(self.required)) if self.required else 0


def compare(required: list[str], cv_text: str) -> Match:
    cv_norm = normalize(cv_text)
    seen, ordered = set(), []
    for term in required:
        key = normalize(term).strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(term.strip())
    m = Match(required=ordered)
    for term in ordered:
        (m.matched if contains_term(cv_norm, term) else m.missing).append(term)
    return m


# --- Ollama -------------------------------------------------------------------

class OllamaError(RuntimeError):
    pass


def ollama_chat(model: str, system: str, user: str, as_json: bool = False, url: str = OLLAMA_URL) -> str:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    if as_json:
        body["format"] = "json"
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read())["message"]["content"]
    except urllib.error.URLError as e:
        raise OllamaError(
            "Cannot reach Ollama at localhost:11434. Start it (open the Ollama app or run "
            f"'ollama serve'), then check the model with 'ollama pull {model}'."
        ) from e


FRENCH_HINTS = {"le", "la", "les", "des", "une", "et", "pour", "nous", "vous", "avec", "poste", "ans", "expérience", "experience"}
ENGLISH_HINTS = {"the", "and", "for", "we", "you", "with", "role", "years", "experience", "our", "will"}


def detect_language(text: str) -> str:
    """'fr' or 'en', from common words. Cheap and more reliable than a small model."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    fr = sum(w in FRENCH_HINTS for w in words)
    en = sum(w in ENGLISH_HINTS for w in words)
    return "fr" if fr > en else "en"


def candidate_name(cv: str) -> str:
    """First non-empty line of the CV, without anything in brackets."""
    for line in cv.splitlines():
        line = re.sub(r"\(.*?\)", "", line).strip(" -–|#*")
        if line:
            return line
    return ""


def cv_bullets(cv: str) -> list[str]:
    """Bullet lines from the CV (lines starting with -, •, * or a number)."""
    out = []
    for line in cv.splitlines():
        m = re.match(r"^\s*(?:[-•*]|\d+[.)])\s+(.{20,})$", line)
        if m:
            out.append(m.group(1).strip())
    return out


def terms_in(text: str, terms: list[str]) -> list[str]:
    norm = normalize(text)
    return [t for t in terms if contains_term(norm, t)]


def extract_requirements(offer: str, chat) -> dict:
    system = (
        "You read job offers for an applicant tracking system. Reply with JSON only, shaped as "
        '{"job_title": str, "skills": [str], "certifications": [str], "years_experience": str}. '
        "Copy each skill, tool or keyword EXACTLY as it is written in the offer, in the offer's "
        "own language, 1 to 3 words each. Do not translate. Do not describe tasks."
    )
    raw = chat(system, offer, True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("job_title", "")
    data.setdefault("years_experience", "")

    def keep(items):
        # Guard against a small model inventing or translating keywords: keep only
        # terms that really appear in the offer text.
        items = [s for s in items or [] if isinstance(s, str) and 0 < len(s) <= 40]
        return terms_in(offer, items)

    data["skills"] = keep(data.get("skills"))
    data["certifications"] = keep(data.get("certifications"))
    return data


def pick_bullets(cv: str, offer_terms: list[str], n: int = 3) -> list[str]:
    """The CV bullets that share the most keywords with the offer."""
    bullets = cv_bullets(cv)
    scored = sorted(bullets, key=lambda b: len(terms_in(b, offer_terms)), reverse=True)
    return scored[:n]


def rewrite_bullets(cv: str, offer_terms: list[str], missing: list[str], lang: str, chat) -> list[tuple[str, str]]:
    """Returns (original, rewritten) pairs. Falls back to the original if the model adds unsupported claims."""
    language = "French" if lang == "fr" else "English"
    system = (
        f"You edit one CV bullet point. Rewrite it in {language} in one sentence of at most 30 words. "
        "Start with a strong action verb, keep every number, and keep the same facts. "
        "You may reuse wording from the keyword list only when the bullet already supports it. "
        "Never add a tool, product, certification or result that is not in the bullet. "
        "Reply with the rewritten bullet only."
    )
    pairs = []
    for original in pick_bullets(cv, offer_terms):
        user = f"Keywords from the job offer: {', '.join(offer_terms)}\n\nBullet: {original}"
        reply = chat(system, user, False).strip().strip("-•* ").splitlines()
        new = reply[0].strip() if reply else ""
        invented = [t for t in terms_in(new, missing) if not contains_term(normalize(original), t)]
        if not new or invented or len(new) > 300:
            new = original
        pairs.append((original, new))
    return pairs


def draft_letter(cv: str, offer: str, req: dict, matched: list[str], missing: list[str], lang: str, chat) -> str:
    language = "French" if lang == "fr" else "English"
    name = candidate_name(cv)
    greeting = "Madame, Monsieur," if lang == "fr" else "Dear Hiring Manager,"
    system = (
        f"Write a short cover letter email in {language}, 150 to 200 words. "
        f"Start directly with '{greeting}' (no address block, no date, no subject line). "
        "Use only facts that appear in the CV. Plain, confident tone, no clichés, no square-bracket placeholders. "
        f"End with the sign-off and the name '{name}'."
    )
    user = (
        f"JOB TITLE: {req.get('job_title', '')}\n\n"
        f"Skills the applicant really has (you may mention these): {', '.join(matched) or 'see CV'}\n"
        f"Skills the applicant does NOT have (never claim these): {', '.join(missing) or 'none'}\n\n"
        f"JOB OFFER:\n{offer}\n\nCV:\n{cv}"
    )
    return chat(system, user, False).strip()


# --- Report -------------------------------------------------------------------

def build_report(m: Match, req: dict | None, bullets, letter: str | None, warnings: list[str], seconds: float) -> str:
    lines = ["# nonchalant-cv report", ""]
    if req and req.get("job_title"):
        lines += [f"**Offer:** {req['job_title']}", ""]
    lines += [f"**ATS keyword match:** {m.score}% ({len(m.matched)} of {len(m.required)})", ""]
    lines += ["## Keywords your CV already shows", ""]
    lines += [f"- {k}" for k in m.matched] or ["- none"]
    lines += ["", "## Keywords missing from your CV", ""]
    lines += [f"- {k}" for k in m.missing] or ["- none, nice"]
    lines += ["", "> Add a missing keyword only if it is true for you. If it is not, it is a skill to learn.", ""]
    if req and req.get("years_experience"):
        lines += [f"**Experience asked:** {req['years_experience']}", ""]
    if bullets:
        lines += ["## CV bullets tuned for this offer", ""]
        for original, new in bullets:
            if new == original:
                lines += [f"- {original}  *(already good, kept as is)*"]
            else:
                lines += [f"- {new}", f"  - before: {original}"]
        lines += [""]
    if letter:
        lines += ["## Cover letter draft", "", letter, ""]
    if warnings:
        lines += ["## Check before sending", ""] + [f"- {w}" for w in warnings] + [""]
    lines += ["---", f"Generated locally in {seconds:.0f} s. Review every line before you send it."]
    return "\n".join(lines) + "\n"


def run(cv_text: str, offer_text: str, chat=None) -> str:
    """chat(system, user, as_json) -> str, or None to skip the model."""
    start = time.time()
    req = None
    required = known_skills_in(offer_text)
    if chat:
        req = extract_requirements(offer_text, chat)
        required = req["skills"] + req["certifications"] + required
    m = compare(required, cv_text)
    bullets, letter, warnings = None, None, []
    if chat:
        lang = detect_language(offer_text)
        bullets = rewrite_bullets(cv_text, m.required, m.missing, lang, chat)
        letter = draft_letter(cv_text, offer_text, req or {}, m.matched, m.missing, lang, chat)
        claimed = terms_in(letter, m.missing)
        if claimed:
            warnings.append(
                "The letter mentions " + ", ".join(claimed)
                + ", which your CV does not show. Remove it unless it is true."
            )
        if "[" in letter and "]" in letter:
            warnings.append("The letter still has a [placeholder]. Fill it in or delete it.")
    return build_report(m, req, bullets, letter, warnings, time.time() - start)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tune your CV to a job offer with a local open-weight model.")
    p.add_argument("--cv", required=True, type=Path, help="your CV as a .txt or .md file")
    p.add_argument("--offer", required=True, type=Path, help="the job offer as a .txt file")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    p.add_argument("--out", type=Path, default=Path("report.md"), help="where to write the report")
    p.add_argument("--no-ai", action="store_true", help="keyword check only, no model call")
    a = p.parse_args(argv)

    cv_text = a.cv.read_text(encoding="utf-8", errors="ignore")
    offer_text = a.offer.read_text(encoding="utf-8", errors="ignore")
    chat = None if a.no_ai else (lambda s, u, j: ollama_chat(a.model, s, u, j))

    print("Reading the offer and your CV. You can go relax." if chat else "Checking keywords...")
    try:
        report = run(cv_text, offer_text, chat)
    except OllamaError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    a.out.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
