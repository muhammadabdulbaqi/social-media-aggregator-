# Link Aggregator

A small web app that lets users paste social media links (YouTube, X/Twitter, TikTok) and displays them as embedded widgets on a single feed. Built with Flask, SQLite, and server-rendered templates.

## Project structure

```
social_media/
├── app/
│   ├── __init__.py       # Application factory (create_app)
│   ├── config.py         # Config classes (Development, Production)
│   ├── models/           # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── link.py
│   ├── routes/           # Blueprints and view logic
│   │   ├── __init__.py
│   │   └── main.py
│   ├── services/         # Business logic (embed detection, oEmbed fetch)
│   │   ├── __init__.py
│   │   └── embed.py
│   ├── static/           # Frontend assets
│   │   ├── css/
│   │   └── js/
│   └── templates/        # Jinja2 templates
│       ├── base.html
│       └── index.html
├── instance/             # Instance folder (SQLite DB, local config) – gitignored
├── main.py               # Entry point (run app or `flask --app main run`)
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

1. **Clone and create a virtual environment**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # macOS/Linux
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Environment (optional)**

   Copy `.env.example` to `.env` and set:

   - `SECRET_KEY` – for production
   - `DATABASE_URL` – e.g. `sqlite:///instance/links.db` or a PostgreSQL URL
   - `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET` – only if you add Instagram embeds (Phase 2)

## Run

```bash
python main.py
```

Or:

```bash
flask --app main run --debug
```

Then open http://127.0.0.1:5000 .

## How it works

- **Submit URL** → Backend detects platform (YouTube, X, TikTok) from the URL.
- **Fetch embed** → YouTube: iframe from video ID; X and TikTok: oEmbed API (no API keys).
- **Store** → Link and embed data are saved in SQLite (`instance/links.db` in dev).
- **List** → Home page shows all links in a responsive grid; each is rendered as an iframe or oEmbed HTML.

Instagram can be added later by configuring a Meta app and the oEmbed endpoint (see plan).

## Tech stack

- **Backend:** Flask 3, Flask-SQLAlchemy, `requests`
- **Database:** SQLite (default), optional PostgreSQL via `DATABASE_URL`
- **Frontend:** Jinja2, Tailwind CSS (CDN), minimal custom CSS/JS

## License

MIT (or your choice).
