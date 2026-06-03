import os
import smtplib
import ssl
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# ── Configurazione ──────────────────────────────────────────────────────────
EMAIL_FROM     = os.environ["EMAIL_FROM"]
EMAIL_TO       = os.environ["EMAIL_TO"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# Feed RSS per azienda. Aggiungine altri se li trovi attivi.
RSS_FEEDS = {
    "OpenAI": [
        "https://openai.com/news/rss.xml",
        # Feed community / developers (attivo se OpenAI lo espone)
        "https://community.openai.com/latest.rss",
    ],
    "Anthropic": [
        "https://www.anthropic.com/rss.xml",
        # Fallback (stesso contenuto, URL alternativo)
        "https://www.anthropic.com/news/rss.xml",
    ],
    "Google AI / Gemini": [
        "https://blog.google/technology/ai/rss/",
        "https://developers.googleblog.com/feeds/posts/default",
    ],
}

# Parole-chiave per filtrare contenuti orientati al coding / developer
KEYWORDS = [
    # Strumenti e workflow
    "code", "coding", "codebase",
    "developer", "development",
    "programming", "programmer",
    "api", "sdk", "library", "framework",
    "ide", "plugin", "extension",
    "cli", "command line", "terminal",
    "repository", "github", "git",
    "ci/cd", "pipeline", "devops",
    "deployment", "container", "docker",
    # Prodotti specifici
    "codex", "o3", "gpt-4o",
    "claude code", "claude sonnet", "claude opus",
    "gemini code assist", "gemini flash", "gemini pro",
    # Paradigmi AI per sviluppatori
    "agent", "agents", "agentic",
    "mcp", "model context protocol",
    "tool use", "tool calling", "function calling",
    "rag", "retrieval", "embedding",
    "fine-tun", "finetuning", "fine tuning",
    # Release / aggiornamenti tecnici
    "release", "launch", "update", "changelog",
    "benchmark", "evals", "evaluation",
    "context window", "token", "rate limit",
    "software", "open source", "open-source",
]

# Quanti giorni indietro cercare (2 = ultime 48h)
LOOKBACK_DAYS = 2

# ── Logica principale ────────────────────────────────────────────────────────
def is_relevant(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def fetch_updates() -> dict[str, list[dict]]:
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    results: dict[str, list[dict]] = {}

    for company, feeds in RSS_FEEDS.items():
        seen_links: set[str] = set()
        company_items: list[dict] = []

        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
            except Exception:
                continue  # feed non raggiungibile → skip silenzioso

            for entry in feed.entries:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()
                link    = entry.get("link", "").strip()

                # De-duplicate per URL
                if link in seen_links:
                    continue
                seen_links.add(link)

                # Filtro rilevanza
                if not is_relevant(f"{title} {summary}"):
                    continue

                # Filtro temporale (se il feed espone la data)
                published = entry.get("published_parsed")
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_date < cutoff:
                        continue

                company_items.append({"title": title, "link": link})

        results[company] = company_items

    return results


def build_email(data: dict[str, list[dict]]) -> str:
    today      = datetime.utcnow().strftime("%d/%m/%Y")
    total      = sum(len(v) for v in data.values())
    found_text = f"{total} aggiornamento{'i' if total != 1 else ''} trovato{'i' if total != 1 else ''}"

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <style>
    body       {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f4f6f9;
                  color:#1a1a2e; margin:0; padding:0; }}
    .wrapper   {{ max-width:600px; margin:32px auto; background:#ffffff;
                  border-radius:12px; overflow:hidden;
                  box-shadow:0 4px 24px rgba(0,0,0,.08); }}
    .header    {{ background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
                  color:#fff; padding:28px 32px; }}
    .header h1 {{ margin:0 0 4px; font-size:22px; letter-spacing:.5px; }}
    .header p  {{ margin:0; font-size:13px; opacity:.75; }}
    .badge     {{ display:inline-block; margin-top:10px; background:rgba(255,255,255,.15);
                  border-radius:20px; padding:3px 12px; font-size:12px; }}
    .body      {{ padding:28px 32px; }}
    h2         {{ font-size:16px; margin:24px 0 10px;
                  border-left:4px solid #302b63; padding-left:10px; }}
    ul         {{ list-style:none; padding:0; margin:0 0 8px; }}
    li         {{ padding:7px 0; border-bottom:1px solid #f0f0f0; font-size:14px; }}
    li:last-child {{ border-bottom:none; }}
    a          {{ color:#302b63; text-decoration:none; font-weight:500; }}
    a:hover    {{ text-decoration:underline; }}
    .empty     {{ color:#888; font-size:14px; font-style:italic; }}
    .footer    {{ background:#f8f8f8; padding:16px 32px;
                  font-size:12px; color:#999; text-align:center; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>🤖 AI Coding Digest</h1>
      <p>Aggiornamenti OpenAI · Anthropic · Gemini — orientati al coding</p>
      <span class="badge">📅 {today} &nbsp;·&nbsp; {found_text}</span>
    </div>
    <div class="body">
"""

    for company, items in data.items():
        html += f"      <h2>{company}</h2>\n"
        if not items:
            html += '      <p class="empty">Nessuna novità rilevante nelle ultime 48 ore.</p>\n'
        else:
            html += "      <ul>\n"
            for item in items:
                html += (
                    f'        <li><a href="{item["link"]}" target="_blank">'
                    f'{item["title"]}</a></li>\n'
                )
            html += "      </ul>\n"

    html += """    </div>
    <div class="footer">
      Generato automaticamente da <strong>AI Coding Digest</strong> via GitHub Actions.<br>
      Feed: OpenAI News · Anthropic News · Google AI Blog · Google Developers Blog
    </div>
  </div>
</body>
</html>"""

    return html


def send_email(html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Coding Digest – {datetime.utcnow().strftime('%d/%m/%Y')}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO

    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("✅ Email inviata con successo.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 Recupero aggiornamenti dai feed RSS…")
    updates = fetch_updates()

    for company, items in updates.items():
        print(f"  {company}: {len(items)} item(s) rilevanti")

    print("✉️  Costruzione email…")
    html = build_email(updates)

    print("📤 Invio email…")
    send_email(html)
