# 🤖 AI Coding Digest

Newsletter giornaliera automatica che monitora le novità di **OpenAI**, **Anthropic** e **Google AI / Gemini** filtrando i contenuti rilevanti per sviluppatori.

Gira gratis su **GitHub Actions** e invia una mail HTML via **Gmail**.

-----

## Funzionalità

|Feature     |Dettaglio                                                          |
|------------|-------------------------------------------------------------------|
|⏰ Scheduling|Ogni giorno alle **20:00 ora italiana** (18:00 UTC, ora legale)    |
|🔍 Fonti     |OpenAI News, Anthropic News, Google AI Blog, Google Developers Blog|
|🎯 Filtro    |~35 keyword orientate a coding, API, SDK, agenti, tool use, release|
|📧 Email     |HTML stilizzata con gradient header e link diretti agli articoli   |
|🆓 Costo     |Completamente gratuito (GitHub Actions free tier + Gmail)          |

-----

## Struttura del repository

```
ai-coding-digest/
├── .github/
│   └── workflows/
│       └── digest.yml        ← workflow GitHub Actions
├── digest.py                 ← script principale
├── requirements.txt          ← dipendenze Python
└── README.md
```

-----

## Setup rapido

### 1. Crea il repository su GitHub

```bash
git init ai-coding-digest
cd ai-coding-digest
# copia i file qui dentro
git add .
git commit -m "feat: initial setup"
git remote add origin https://github.com/TUO_USERNAME/ai-coding-digest.git
git push -u origin main
```

### 2. Configura Gmail — Password per app

> Necessaria se hai la **verifica in due passaggi** attiva (obbligatoria con account personale).

1. Vai su [myaccount.google.com/security](https://myaccount.google.com/security)
1. Assicurati che la **verifica in due passaggi** sia **attiva**
1. Cerca **“Password per le app”** nella barra di ricerca dell’account Google
1. Crea una nuova password → scegli nome `AI Digest` → copia la password a 16 caratteri

### 3. Aggiungi i Secrets su GitHub

Nel tuo repository: **Settings → Secrets and variables → Actions → New repository secret**

|Nome secret     |Valore                                          |
|----------------|------------------------------------------------|
|`EMAIL_FROM`    |Il tuo indirizzo Gmail (es. `tuo@gmail.com`)    |
|`EMAIL_TO`      |Destinatario (può essere lo stesso mittente)    |
|`EMAIL_PASSWORD`|La password per app a 16 caratteri (senza spazi)|

### 4. Testa manualmente

Vai su **Actions → AI Coding Digest → Run workflow** per eseguire subito senza aspettare le 20:00.

-----

## Ora legale vs solare

GitHub Actions usa sempre **UTC**. Il workflow è configurato per le **18:00 UTC**:

|Periodo         |Fuso italiano|Offset|Cron UTC      |
|----------------|-------------|------|--------------|
|Primavera/Estate|CEST (UTC+2) |−2h   |`0 18 * * *` ✅|
|Autunno/Inverno |CET (UTC+1)  |−1h   |`0 19 * * *`  |

Per l’inverno cambia la riga nel `digest.yml`:

```yaml
- cron: "0 19 * * *"
```

-----

## Personalizzazione

### Aggiungere feed RSS

Nel file `digest.py`, aggiungi URL alla struttura `RSS_FEEDS`:

```python
RSS_FEEDS = {
    "OpenAI": [
        "https://openai.com/news/rss.xml",
    ],
    # Aggiungi un'azienda nuova:
    "Mistral": [
        "https://mistral.ai/news/rss.xml",
    ],
}
```

### Modificare le keyword

Aggiungi termini all’array `KEYWORDS` in `digest.py`. Il match è case-insensitive e usa la ricerca per sottostringa (es. `"fine-tun"` cattura sia `fine-tuning` sia `fine-tuned`).

### Modificare la finestra temporale

```python
LOOKBACK_DAYS = 2  # aumenta a 7 per la newsletter settimanale
```

-----

## Troubleshooting

|Problema                 |Soluzione                                                                          |
|-------------------------|-----------------------------------------------------------------------------------|
|Email non arriva         |Controlla spam. Verifica che `EMAIL_PASSWORD` non abbia spazi                      |
|`SMTPAuthenticationError`|La password per app è scaduta o errata → ricreane una                              |
|Nessun articolo trovato  |I feed RSS possono cambiare URL. Testa manualmente con `python digest.py` in locale|
|Workflow non parte       |Verifica che il file sia in `.github/workflows/` e la sintassi YAML sia corretta   |

-----

## Limitazioni note

- I feed RSS ufficiali non coprono sempre i changelog tecnici e le release note. Per coprire anche quelli bisognerebbe fare scraping delle pagine docs (fuori scope di questo progetto).
- GitHub Actions può ritardare l’esecuzione schedulata di **±30 minuti** nei momenti di picco.
- Gmail limita l’invio a ~500 mail/giorno (ampiamente sufficiente per uso personale).