# FIFA WC 2026 Predictor

A team prediction game for the 2026 FIFA World Cup. Each person gets a signed personal link to cast predictions. A live leaderboard tracks points. No login required — identity is enforced server-side via HMAC-signed URLs.

## Features

- Predict match winners (not scores)
- Voting closes automatically at kickoff (server-enforced)
- Points: base × stage multiplier + streak bonus + upset bonus + perfect round bonus
- Tamper-resistant: signed URLs, all scoring server-side, DB-level uniqueness constraints
- Auto-settles results via football-data.org API (or manual admin override)
- Swap-ready frontend: replace `frontend/` with a React app, API contract stays the same

## Scoring

| Category | Points |
|----------|--------|
| Correct prediction (Group) | 1 |
| Correct prediction (R16) | 2 |
| Correct prediction (QF) | 3 |
| Correct prediction (SF) | 4 |
| Correct prediction (Final) | 5 |
| Streak bonus (every 3 in a row) | +1 |
| Upset bonus (underdog win) | +1 |
| Perfect matchday (all correct) | +2 |

## Setup

### 1. Install dependencies

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   SECRET_KEY   — generate with: python -c "import secrets; print(secrets.token_hex(32))"
#   ADMIN_KEY    — another random string, keep private
#   BASE_URL     — http://localhost:8000 for local, your domain in prod
#   FOOTBALLDATA_API_KEY — register free at https://www.football-data.org/client/register
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Seed fixtures

```bash
python -m scripts.sync_fixtures
```

### 5. Edit participants and generate links

Open `scripts/generate_links.py`, update the `PARTICIPANTS` list with your team's names, then run:

```bash
python -m scripts.generate_links
```

Copy each person's link and send it to them privately (Slack DM, WhatsApp, etc.).

### 6. Start the server

```bash
uvicorn app.main:app --reload
```

The vote page is at `http://localhost:8000/?user=NAME&sig=SIG` (use the generated links).  
The leaderboard is at `http://localhost:8000/leaderboard.html`.

## Deploying to Fly.io (free)

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly launch   # follow prompts, choose a region close to you

# Create a persistent volume for the SQLite database
fly volumes create fifa_data --size 1

# Set secrets (never commit these)
fly secrets set \
  SECRET_KEY="your_secret" \
  ADMIN_KEY="your_admin_key" \
  BASE_URL="https://your-app.fly.dev" \
  FOOTBALLDATA_API_KEY="your_key"

fly deploy

# Custom domain
fly certs add yourdomain.com
# Then set an A record at your DNS provider pointing to the Fly IP shown by:
fly certs show yourdomain.com
```

After deploying, run the seed + generate-links scripts with `fly ssh console`:

```bash
fly ssh console
cd /app
python -m scripts.sync_fixtures
python -m scripts.generate_links
```

## Settling results manually (fallback)

If auto-settle isn't working, you can settle a match manually:

```bash
curl -X POST https://your-app/admin/settle \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"match_id": 5, "result": "team_a"}'
```

To list match IDs:

```bash
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app/admin/matches
```

## Replacing the frontend with React

```bash
# 1. Archive the plain HTML frontend
mv frontend frontend-html

# 2. Scaffold a Vite/React app
npm create vite@latest frontend -- --template react

# 3. In your React app, set the API base URL:
#    VITE_API_BASE=https://your-app.fly.dev

# The /api/* endpoints are identical — no backend changes needed.
```

## Forking for your own tournament

1. Register for a free football-data.org key
2. Update `data/rankings.json` with current FIFA rankings
3. Edit `PARTICIPANTS` in `scripts/generate_links.py`
4. Optionally adjust `STAGE_MULTIPLIER` in `app/scoring.py`
5. Deploy and share links

## API Reference

All endpoints require `?user=NAME&sig=HMAC` except admin routes.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/matches` | All matches + your vote + status |
| `POST` | `/api/vote` | Submit a prediction |
| `GET` | `/api/leaderboard` | Ranked scores for all players |
| `GET` | `/api/me` | Your per-match score breakdown |
| `POST` | `/admin/settle` | Manually settle a match result |
| `GET` | `/admin/matches` | List all matches with IDs |
