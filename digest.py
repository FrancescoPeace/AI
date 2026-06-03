import os
import re
import json
import smtplib
import ssl
import urllib.request
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# ── Configurazione ────────────────────────────────────────────────────────────
EMAIL_FROM      = os.environ["EMAIL_FROM"]
EMAIL_TO        = os.environ["EMAIL_TO"]
EMAIL_PASSWORD  = os.environ["EMAIL_PASSWORD"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]   # ← nuovo secret da aggiungere

RSS_FEEDS = {
    "Anthropic": [
        "https://www.anthropic.com/rss.xml",
        "https://www.anthropic.com/news/rss.xml",
    ],
    "OpenAI": [
        "https://openai.com/news/rss.xml",
        "https://community.openai.com/latest.rss",
    ],
    "Google AI / Gemini": [
        "https://blog.google/technology/ai/rss/",
        "https://developers.googleblog.com/feeds/posts/default",
    ],
}

KEYWORDS = [
    "code", "coding", "codebase",
    "developer", "development",
    "programming", "programmer",
    "api", "sdk", "library", "framework",
    "ide", "plugin", "extension",
    "cli", "command line", "terminal",
    "repository", "github", "git",
    "ci/cd", "pipeline", "devops",
    "deployment", "container", "docker",
    "codex", "o3", "gpt-4o",
    "claude code", "claude sonnet", "claude opus",
    "gemini code assist", "gemini flash", "gemini pro",
    "agent", "agents", "agentic",
    "mcp", "model context protocol",
    "tool use", "tool calling", "function calling",
    "rag", "retrieval", "embedding",
    "fine-tun", "finetuning", "fine tuning",
    "release", "launch", "update", "changelog",
    "benchmark", "evals", "evaluation",
    "context window", "token", "rate limit",
    "software", "open source", "open-source",
]

LOOKBACK_DAYS = 2

BRAND = {
    "Anthropic": {
        "color": "#CC785C", "border": "#CC785C",
        "emoji": "🟠",     "label":  "Anthropic",
    },
    "OpenAI": {
        "color": "#10A37F", "border": "#10A37F",
        "emoji": "🟢",     "label":  "OpenAI",
    },
    "Google AI / Gemini": {
        "color": "#4285F4", "border": "#4285F4",
        "emoji": "🔵",     "label":  "Google AI · Gemini",
    },
}

# ── Traduzione via Claude API ─────────────────────────────────────────────────
def translate_items(items: list[dict]) -> list[dict]:
    """Traduce in italiano titoli e sommari di tutti gli item in una sola chiamata."""
    if not items:
        return items

    # Costruiamo un payload JSON compatto da tradurre
    payload = [
        {"id": i, "title": it["title"], "summary": it["summary"]}
        for i, it in enumerate(items)
    ]
    prompt = (
        "Traduci in italiano i seguenti titoli e sommari di articoli tech su AI e coding. "
        "Mantieni i nomi propri, le sigle tecniche (API, SDK, MCP, CLI, RAG…) e i nomi di prodotto invariati. "
        "Rispondi SOLO con un array JSON valido, senza testo aggiuntivo, con la stessa struttura: "
        '[{"id":0,"title":"...","summary":"..."},...]\\n\\n'
        + json.dumps(payload, ensure_ascii=False)
    )

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data     = json.loads(resp.read())
            raw_text = data["content"][0]["text"].strip()
            # Rimuove eventuali backtick markdown
            raw_text = re.sub(r"^```json|^```|```$", "", raw_text, flags=re.MULTILINE).strip()
            translated = json.loads(raw_text)
            by_id = {t["id"]: t for t in translated}
            for i, it in enumerate(items):
                if i in by_id:
                    it["title"]   = by_id[i].get("title",   it["title"])
                    it["summary"] = by_id[i].get("summary", it["summary"])
    except Exception as e:
        print(f"  ⚠️  Traduzione fallita ({e}), uso titoli originali.")

    return items


# ── Fetch RSS ─────────────────────────────────────────────────────────────────
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
                continue

            for entry in feed.entries:
                title   = entry.get("title",   "").strip()
                summary = entry.get("summary", "").strip()
                link    = entry.get("link",    "").strip()

                if link in seen_links:
                    continue
                seen_links.add(link)

                if not is_relevant(f"{title} {summary}"):
                    continue

                published = entry.get("published_parsed")
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_date < cutoff:
                        continue

                pub_str = ""
                if published:
                    pub_str = datetime(*published[:6]).strftime("%-d %b")

                company_items.append({
                    "title":   title,
                    "link":    link,
                    "pub_str": pub_str,
                    "summary": summary[:200] if summary else "",
                })

        # Traduci tutti gli articoli dell'azienda in una sola chiamata
        print(f"  🌐 Traduco {len(company_items)} articoli per {company}…")
        company_items = translate_items(company_items)
        results[company] = company_items

    return results


# ── HTML ──────────────────────────────────────────────────────────────────────
def card_html(item: dict, brand: dict) -> str:
    pub_tag = (
        f'<span style="font-size:11px;color:#4A6272;margin-left:8px;">{item["pub_str"]}</span>'
        if item["pub_str"] else ""
    )
    summary_tag = (
        f'<p style="margin:6px 0 0;font-size:13px;color:#7A9AAA;line-height:1.55;">'
        f'{item["summary"]}…</p>'
        if item["summary"] else ""
    )
    return (
        f'<a href="{item["link"]}" target="_blank" style="text-decoration:none;display:block;margin-bottom:10px;">'
        f'<div style="background:#1C2B34;border:1px solid rgba(255,255,255,0.07);'
        f'border-left:4px solid {brand["color"]};border-radius:10px;padding:14px 16px;">'
        f'<span style="font-family:Georgia,serif;font-size:14.5px;font-weight:600;'
        f'color:#E8EFF3;line-height:1.4;">{item["title"]}</span>'
        f'{pub_tag}'
        f'{summary_tag}'
        f'<p style="margin:8px 0 0;font-size:12px;color:{brand["color"]};font-weight:600;">'
        f'Leggi l\'articolo →</p>'
        f'</div></a>'
    )


def section_html(company: str, items: list[dict]) -> str:
    brand = BRAND[company]
    count = len(items)
    count_tag = (
        f'<span style="background:{brand["color"]};color:#fff;border-radius:20px;'
        f'padding:2px 10px;font-size:11px;font-weight:700;margin-left:8px;">{count}</span>'
        if count else
        '<span style="color:#4A6272;font-size:12px;margin-left:8px;">nessuna novità</span>'
    )
    cards = "".join(card_html(i, brand) for i in items) if items else (
        '<p style="color:#4A6272;font-size:13px;font-style:italic;padding:8px 0;">'
        '💤 Nessun aggiornamento nelle ultime 48 ore.</p>'
    )
    return (
        f'<div style="margin-bottom:28px;">'
        f'<div style="background:#1C2B34;border-radius:10px 10px 0 0;padding:12px 16px;'
        f'border-bottom:2px solid {brand["color"]};">'
        f'<span style="font-size:18px;margin-right:8px;">{brand["emoji"]}</span>'
        f'<span style="font-family:Georgia,serif;font-size:16px;font-weight:700;'
        f'color:{brand["color"]};letter-spacing:.3px;">{brand["label"]}</span>'
        f'{count_tag}'
        f'</div>'
        f'<div style="padding:12px 0 0;">{cards}</div>'
        f'</div>'
    )


def build_email(data: dict[str, list[dict]]) -> str:
    now_it = datetime.utcnow() + timedelta(hours=2)
    month_map = {
        "January":"gennaio","February":"febbraio","March":"marzo","April":"aprile",
        "May":"maggio","June":"giugno","July":"luglio","August":"agosto",
        "September":"settembre","October":"ottobre","November":"novembre","December":"dicembre"
    }
    today = now_it.strftime("%-d %B %Y")
    for en, it in month_map.items():
        today = today.replace(en, it)

    total    = sum(len(v) for v in data.values())
    subtitle = (
        f"{total} aggiornament{'i' if total != 1 else 'o'} selezionat{'i' if total != 1 else 'o'} per te"
        if total else "Nessuna novità rilevante oggi"
    )

    sections = "".join(section_html(company, items) for company, items in data.items())

    # bgcolor su <html> e <body> E su ogni cella: forza dark anche in Gmail
    return f"""<!DOCTYPE html>
<html lang="it" style="background:#0F1A1F;">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AI Coding Digest</title>
  <style>
    /* Forza dark mode anche nei client che ignorano inline styles */
    html, body, #__bg {{
      background-color: #0F1A1F !important;
    }}
    a {{ color: inherit; }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#0F1A1F !important;"
      bgcolor="#0F1A1F">

  <!-- outer table: fissa il dark bg anche in Gmail -->
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#0F1A1F"
         style="background-color:#0F1A1F;padding:32px 16px;">
    <tr>
      <td align="center" bgcolor="#0F1A1F" style="background-color:#0F1A1F;">

        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;">

          <!-- ══ HEADER ══════════════════════════════════════════════════ -->
          <tr>
            <td bgcolor="#0F2027"
                style="background:linear-gradient(160deg,#0F2027 0%,#1A3A4A 45%,#0F2A1F 100%);
                       border-radius:20px 20px 0 0;padding:40px 36px 32px;text-align:center;">

              <div style="font-size:26px;letter-spacing:10px;margin-bottom:18px;opacity:.9;">
                🤖&nbsp;🧠&nbsp;💻&nbsp;🔬&nbsp;⚙️
              </div>

              <h1 style="margin:0 0 8px;font-family:Georgia,'Times New Roman',serif;
                         font-size:30px;font-weight:700;color:#FFFFFF;letter-spacing:1px;">
                AI Coding Digest
              </h1>

              <p style="margin:0 0 22px;font-size:12px;letter-spacing:1.2px;text-transform:uppercase;">
                <span style="color:#E8896A;font-weight:600;">Anthropic</span>
                <span style="color:rgba(255,255,255,.3);margin:0 8px;">·</span>
                <span style="color:#5CD6AE;font-weight:600;">OpenAI</span>
                <span style="color:rgba(255,255,255,.3);margin:0 8px;">·</span>
                <span style="color:#7AB4F5;font-weight:600;">Google AI</span>
              </p>

              <table cellpadding="0" cellspacing="0" align="center">
                <tr>
                  <td style="background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);
                             border-radius:40px;padding:8px 22px;">
                    <span style="font-size:13px;color:#FFFFFF;font-weight:500;">
                      📆 {today}
                    </span>
                    <span style="color:rgba(255,255,255,.3);margin:0 10px;">|</span>
                    <span style="font-size:13px;color:#FFFFFF;font-weight:500;">
                      🔎 {subtitle}
                    </span>
                  </td>
                </tr>
              </table>

              <!-- accent line -->
              <div style="margin-top:28px;height:2px;border-radius:2px;opacity:.6;
                          background:linear-gradient(90deg,transparent,#E8896A 20%,#5CD6AE 50%,#7AB4F5 80%,transparent);">
              </div>
            </td>
          </tr>

          <!-- ══ BODY ════════════════════════════════════════════════════ -->
          <tr>
            <td bgcolor="#141E24"
                style="background-color:#141E24;border-radius:0 0 20px 20px;
                       padding:32px 32px 28px;">

              {sections}

              <!-- footer -->
              <div style="margin-top:24px;padding-top:20px;
                          border-top:1px solid rgba(255,255,255,.07);
                          text-align:center;font-size:11px;color:#4A6070;line-height:1.9;">
                🤖 Generato automaticamente ogni sera da
                <strong style="color:#5A7A8A;">AI Coding Digest</strong><br>
                ⚙️ GitHub Actions &nbsp;·&nbsp; 🐍 feedparser
                &nbsp;·&nbsp; 🧠 Claude AI &nbsp;·&nbsp; 📬 Gmail SMTP<br>
                <span style="color:#1E2E38;">──────────────────</span><br>
                📡 Fonti: Anthropic News · OpenAI News · Google AI Blog · Google Developers Blog
              </div>

            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


# ── Send ──────────────────────────────────────────────────────────────────────
def send_email(html: str) -> None:
    now_it  = datetime.utcnow() + timedelta(hours=2)
    subject = f"🤖💻 AI Coding Digest — {now_it.strftime('%-d/%m/%Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("✅ Email inviata con successo.")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 Recupero aggiornamenti dai feed RSS…")
    updates = fetch_updates()
    for company, items in updates.items():
        print(f"  {company}: {len(items)} item(s) rilevanti")
    print("✉️  Costruzione email…")
    html = build_email(updates)
    print("📤 Invio email…")
    send_email(html)
