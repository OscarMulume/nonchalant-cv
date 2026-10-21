"""Mosala web app: the same tools as mosala.py, in a simple page in your browser.

Run:
    python app.py
Then your browser opens http://localhost:8000. Everything stays on your computer:
the page talks only to this small server, and the server talks only to Ollama.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import mosala
import nonchalant_cv as core

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 200_000  # characters; a CV or an offer is far smaller


def installed_models() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            return sorted(m["name"] for m in json.loads(r.read()).get("models", []))
    except Exception:
        return []


def make_chat(model: str):
    return lambda system, user, as_json: core.ollama_chat(model, system, user, as_json)


def handle_cv(data: dict, chat) -> dict:
    story = (data.get("story") or "").strip()
    if not story:
        return {"error": "empty_story"}
    target = data.get("to") if data.get("to") in mosala.CV_LABELS else "fr"
    contact = {k: (data.get(k) or "").strip() for k in ("name", "phone", "email", "city")}
    md, profile, warnings = mosala.make_cv(story, target, contact, chat)
    return {"markdown": md, "html": mosala.render_html(md, contact["name"] or "CV"),
            "facts": profile, "warnings": warnings, "titles": mosala.suggest_titles(story)}


def handle_alert(data: dict, chat) -> dict:
    message = (data.get("message") or "").strip()
    langs = [l for l in data.get("langs") or [] if l in mosala.LANG_INFO][:12]
    if not message or not langs:
        return {"error": "empty_alert"}
    return {"translations": mosala.translate_to_many(message, langs, chat)}


def handle_offer(data: dict, chat) -> dict:
    offer = (data.get("offer") or "").strip()
    if not offer:
        return {"error": "empty_offer"}
    lang = data.get("lang") if data.get("lang") in mosala.LANGUAGES else "ln"
    text = mosala.explain_offer(offer, lang, chat)
    return {"text": text, "keywords": core.known_skills_in(offer), "local": lang in mosala.LOCAL}


def handle_match(data: dict, chat) -> dict:
    cv, offer = (data.get("cv") or "").strip(), (data.get("offer") or "").strip()
    if not cv or not offer:
        return {"error": "empty_match"}
    return {"markdown": core.run(cv, offer, chat)}


ROUTES = {"/api/cv": handle_cv, "/api/offer": handle_offer, "/api/match": handle_match, "/api/alert": handle_alert}


def lan_address() -> str:
    """This computer's address on the local network (Wi-Fi), for phones to connect."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this only picks the right interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "Mosala"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            models = installed_models()
            return self.send_json({"ollama": bool(models), "models": models,
                                   "default": mosala.DEFAULT_MODEL,
                                   "groups": [{"id": g, "langs": [{"code": c, "native": n, "where": w, "tier": t}
                                                                  for c, _, n, w, t in items]}
                                              for g, items in mosala.LANGUAGE_GROUPS],
                                   "cv_languages": sorted(mosala.CV_LABELS)})
        path = "index.html" if self.path in ("/", "/index.html") else None
        if not path:
            self.send_error(404)
            return
        body = (STATIC / path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        route = ROUTES.get(self.path)
        if not route:
            return self.send_json({"error": "not_found"}, 404)
        # Only accept requests from this page, not from other websites open in the browser.
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        if origin and origin != f"http://{host}" and not origin.startswith(("http://localhost", "http://127.0.0.1")):
            return self.send_json({"error": "forbidden"}, 403)
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY * 4:
            return self.send_json({"error": "too_long"}, 413)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send_json({"error": "bad_request"}, 400)
        model = data.get("model") or mosala.DEFAULT_MODEL
        try:
            result = route(data, make_chat(model))
        except core.OllamaError:
            return self.send_json({"error": "ollama_down"}, 503)
        self.send_json(result, 400 if "error" in result else 200)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Open Mosala in your browser.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--lan", action="store_true",
                   help="let phones on the same Wi-Fi use Mosala (only on a network you trust)")
    a = p.parse_args(argv)
    server = ThreadingHTTPServer(("0.0.0.0" if a.lan else "127.0.0.1", a.port), Handler)
    url = f"http://localhost:{a.port}"
    print(f"Mosala is running at {url}  (press Ctrl+C to stop)")
    if a.lan:
        print(f"Phones on the same Wi-Fi can open: http://{lan_address()}:{a.port}")
        print("Anyone on this network can use it while it runs. Use it only on a network you trust.")
    if not installed_models():
        print("Note: Ollama is not answering. Open the Ollama app, then reload the page.")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
