import os
import smtplib
import ssl
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# ── Configurazione ───────────────────────────────────────────────────────────
EMAIL_FROM     = os.environ["EMAIL_FROM"]
EMAIL_TO       = os.environ["EMAIL_TO"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# Ordine fisso: Anthropic → OpenAI → Gemini
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

# Dizionario traduzioni titoli comuni (fallback: titolo originale)
TRANSLATIONS = {
    # pattern semplici — integra pure con altri
}

# Brand colors e emoji per ogni azienda
BRAND = {
    "Anthropic": {
        "color":      "#CC785C",
        "light":      "#FDF3EE",
        "border":     "#E8A98A",
        "emoji":      "🟠",
        "label":      "Anthropic",
        "dot_color":  "#CC785C",
    },
    "OpenAI": {
        "color":      "#10A37F",
        "light":      "#EDFAF5",
        "border":     "#6DCFB3",
        "emoji":      "🟢",
        "label":      "OpenAI",
        "dot_color":  "#10A37F",
    },
    "Google AI / Gemini": {
        "color":      "#4285F4",
        "light":      "#EEF4FF",
        "border":     "#93B8F8",
        "emoji":      "🔵",
        "label":      "Google AI · Gemini",
        "dot_color":  "#4285F4",
    },
}

# ── Logica ───────────────────────────────────────────────────────────────────
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
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()
                link    = entry.get("link", "").strip()

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

                # Data leggibile
                pub_str = ""
                if published:
                    pub_str = datetime(*published[:6]).strftime("%-d %b")

                company_items.append({
                    "title":   title,
                    "link":    link,
                    "pub_str": pub_str,
                    "summary": summary[:160] if summary else "",
                })

        results[company] = company_items

    return results


def card_html(item: dict, brand: dict) -> str:
    pub_tag = (
        f'<span style="font-size:11px;color:#aaa;margin-left:8px;">'
        f'{item["pub_str"]}</span>'
        if item["pub_str"] else ""
    )
    summary_tag = (
        f'<p style="margin:6px 0 0;font-size:13px;color:#666;'
        f'line-height:1.5;">{item["summary"]}…</p>'
        if item["summary"] else ""
    )
    return f"""
      <a href="{item['link']}" target="_blank" style="text-decoration:none;display:block;">
        <div style="
          background:#ffffff;
          border:1px solid {brand['border']};
          border-left:4px solid {brand['color']};
          border-radius:10px;
          padding:14px 16px;
          margin-bottom:10px;
          transition:box-shadow .2s;
        ">
          <div style="display:flex;align-items:baseline;flex-wrap:wrap;">
            <span style="
              font-family:Georgia,'Times New Roman',serif;
              font-size:14.5px;
              font-weight:600;
              color:#1a1a2e;
              line-height:1.4;
            ">{item['title']}</span>
            {pub_tag}
          </div>
          {summary_tag}
          <p style="margin:8px 0 0;font-size:12px;color:{brand['color']};font-weight:600;">
            Leggi l'articolo →
          </p>
        </div>
      </a>"""


def build_email(data: dict[str, list[dict]]) -> str:
    now_it  = datetime.utcnow() + timedelta(hours=2)  # CEST
    today   = now_it.strftime("%-d %B %Y")
    weekday_map = {
        "Monday":"Lunedì","Tuesday":"Martedì","Wednesday":"Mercoledì",
        "Thursday":"Giovedì","Friday":"Venerdì","Saturday":"Sabato","Sunday":"Domenica"
    }
    month_map = {
        "January":"gennaio","February":"febbraio","March":"marzo",
        "April":"aprile","May":"maggio","June":"giugno","July":"luglio",
        "August":"agosto","September":"settembre","October":"ottobre",
        "November":"novembre","December":"dicembre"
    }
    for en, it in month_map.items():
        today = today.replace(en, it)

    total = sum(len(v) for v in data.values())
    subtitle = (
        f"{total} aggiornament{'i' if total != 1 else 'o'} selezionat{'i' if total != 1 else 'o'} per te"
        if total else "Nessuna novità rilevante oggi"
    )

    # ── Sezioni per azienda ──────────────────────────────────────────────────
    sections = ""
    for company, items in data.items():
        brand = BRAND[company]
        header_bg  = brand["light"]
        header_col = brand["color"]
        label      = brand["label"]
        count      = len(items)
        count_tag  = (
            f'<span style="background:{brand["color"]};color:#fff;'
            f'border-radius:20px;padding:2px 10px;font-size:11px;'
            f'font-weight:700;margin-left:8px;">{count}</span>'
            if count else
            '<span style="color:#bbb;font-size:12px;margin-left:8px;">nessuna novità</span>'
        )

        cards = "".join(card_html(i, brand) for i in items) if items else (
            '<p style="color:#bbb;font-size:13px;font-style:italic;padding:8px 0;">'
            'Nessun aggiornamento rilevante nelle ultime 48 ore.</p>'
        )

        sections += f"""
    <!-- {company} -->
    <div style="margin-bottom:32px;">
      <div style="
        background:{header_bg};
        border-radius:10px 10px 0 0;
        padding:12px 16px;
        display:flex;
        align-items:center;
        border-bottom:2px solid {brand['border']};
      ">
        <span style="font-size:18px;margin-right:8px;">{brand['emoji']}</span>
        <span style="
          font-family:Georgia,'Times New Roman',serif;
          font-size:16px;
          font-weight:700;
          color:{header_col};
          letter-spacing:.3px;
        ">{label}</span>
        {count_tag}
      </div>
      <div style="padding:14px 4px 0;">
        {cards}
      </div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AI Coding Digest</title>
</head>
<body style="margin:0;padding:0;background:#F0F2F5;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F2F5;padding:32px 16px;">
    <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

      <!-- HEADER -->
      <tr><td style="
        background:linear-gradient(135deg,#0D0D1A 0%,#1A1040 50%,#0D1F3C 100%);
        border-radius:16px 16px 0 0;
        padding:36px 36px 28px;
        text-align:center;
      ">
        <div style="font-size:32px;margin-bottom:8px;">⚡</div>
        <h1 style="
          margin:0 0 6px;
          font-family:Georgia,'Times New Roman',serif;
          font-size:26px;
          font-weight:700;
          color:#FFFFFF;
          letter-spacing:.5px;
        ">AI Coding Digest</h1>
        <p style="margin:0 0 16px;font-size:13px;color:rgba(255,255,255,.55);letter-spacing:.8px;text-transform:uppercase;">
          Anthropic · OpenAI · Google AI
        </p>
        <div style="
          display:inline-block;
          background:rgba(255,255,255,.1);
          border:1px solid rgba(255,255,255,.2);
          border-radius:30px;
          padding:6px 18px;
          font-size:13px;
          color:rgba(255,255,255,.8);
        ">📅 {today} &nbsp;·&nbsp; {subtitle}</div>
      </td></tr>

      <!-- BODY -->
      <tr><td style="
        background:#FFFFFF;
        border-radius:0 0 16px 16px;
        padding:32px 32px 24px;
        box-shadow:0 8px 32px rgba(0,0,0,.08);
      ">
        {sections}

        <!-- FOOTER -->
        <div style="
          margin-top:24px;
          padding-top:20px;
          border-top:1px solid #EFEFEF;
          text-align:center;
          font-size:11px;
          color:#BBBBBB;
          line-height:1.8;
        ">
          Generato automaticamente ogni sera da <strong style="color:#888;">AI Coding Digest</strong><br>
          via GitHub Actions · feedparser · Gmail SMTP<br>
          <span style="color:#DDD;">──────────────────</span><br>
          Fonti: Anthropic News · OpenAI News · Google AI Blog · Google Developers Blog
        </div>
      </td></tr>

    </table>
    </td></tr>
  </table>

</body>
</html>"""


def send_email(html: str) -> None:
    now_it  = datetime.utcnow() + timedelta(hours=2)
    subject = f"⚡ AI Coding Digest — {now_it.strftime('%-d/%m/%Y')}"

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


if __name__ == "__main__":
    print("🔍 Recupero aggiornamenti dai feed RSS…")
    updates = fetch_updates()
    for company, items in updates.items():
        print(f"  {company}: {len(items)} item(s) rilevanti")
    print("✉️  Costruzione email…")
    html = build_email(updates)
    print("📤 Invio email…")
    send_email(html)
