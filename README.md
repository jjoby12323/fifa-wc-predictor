# FIFA WC 2026 Predictor

A team prediction game for the 2026 FIFA World Cup. Each person gets a signed personal link to cast predictions. A live leaderboard tracks points. No login required — identity is enforced server-side via HMAC-signed URLs.

## Features

- Predict the winner — or a Draw in the group stage (not scores); change or remove your pick any time before kickoff
- Voting opens 48h before a matchday and closes automatically at kickoff (server-enforced)
- Points: base × stage multiplier + streak bonus + perfect-matchday bonus + participation bonus
- Predictions paginated by day — you land on what's live (open voting + the latest results)
- Tamper-resistant: signed URLs, all scoring server-side, DB-level uniqueness constraints
- Auto-settles results via football-data.org API (or manual admin override)
- Auto-refreshes fixtures every 6h — fills in knockout teams and schedule changes (no manual re-sync once seeded)
- Knockout bracket + live group standings on a dedicated page
- Optional Slack bot: polls-open reminders, vote nudges, match results, daily leaderboard
- Chat widget on every page for smack talk, with a new-message popup
- Click any name on the leaderboard to view their prediction history
- Admin engagement page (`/admin.html`) — key-gated view of who's voting and chatting (never reveals individual picks)
- Swap-ready frontend: replace `frontend/` with a React app, API contract stays the same

## Scoring

Base points scale by stage (48-team format includes a Round of 32):

| Category | Points |
|----------|--------|
| Correct prediction (Group) | 1 |
| Correct prediction (Round of 32) | 2 |
| Correct prediction (Round of 16) | 3 |
| Correct prediction (Quarter-Final) | 4 |
| Correct prediction (Semi-Final) | 5 |
| Correct prediction (Final) | 6 |
| Streak bonus (every 3 correct in a row) | +1 |
| Perfect matchday (all correct, 2+ matches) | +2 |
| Participation (every 3 matches voted on) | +1 |

In the **group stage** you can also predict a **Draw** — worth the same as a correct winner pick. Knockout matches are always decided (extra time / penalties), so there's no draw option there.

## Setup

### 1. Install dependencies

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create `backend/.env` with the following variables:

```
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=

# Separate key for /admin/* endpoints — keep private
ADMIN_KEY=

# http://localhost:8000 for local, your domain in prod
BASE_URL=http://localhost:8000

# sqlite+aiosqlite:///./fifa.db for local
# sqlite+aiosqlite:////data/fifa.db for Fly.io
DATABASE_URL=sqlite+aiosqlite:///./fifa.db

# Register free at https://www.football-data.org/client/register
FOOTBALLDATA_API_KEY=

# * for local dev, your domain in prod
ALLOWED_ORIGINS=*

# Slack Incoming Webhook for reminders + leaderboard posts (optional — leave blank to disable)
SLACK_WEBHOOK_URL=

# Optional Slack tuning (defaults shown):
# SLACK_REMINDER_HOURS_BEFORE=3       # hours before a matchday's first kickoff to nudge non-voters
# SLACK_LEADERBOARD_HOUR_IST=9        # daily standings post — hour of day in SLACK_LEADERBOARD_TZ
# SLACK_LEADERBOARD_TZ=Asia/Kolkata   # timezone for the daily post (IANA name)
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Add participants

Create a `participants.txt` file in the project root (it's gitignored — never committed). One full name per line:

```
Jonathan Joby
Saral Hemnani
Akanksha Goel
```

### 5. Sync fixtures and generate links

```bash
# Pull WC2026 schedule from football-data.org (one-time seed)
python -m scripts.sync_fixtures

# Create users and print one signed URL per person
python -m scripts.generate_links
```

Copy each person's link and send it to them privately (Slack DM, WhatsApp, etc.).

`sync_fixtures` is a **one-time seed** — once the server is running it re-syncs fixtures
itself every 6 hours (filling knockout teams and schedule changes), and settles results
every 10 minutes. No recurring manual runs are needed during the tournament.

### 6. Start the server

```bash
uvicorn app.main:app --reload
```

Vote page: `http://localhost:8000/?user=NAME&sig=SIG` (use the generated links)  
Leaderboard: `http://localhost:8000/leaderboard.html`

## Resetting

```bash
# Wipe votes, scores, and match results (keeps users and fixtures)
python -m scripts.reset

# Wipe everything — re-run sync_fixtures and generate_links after
python -m scripts.reset --all
```

## Deploying to Fly.io (free)

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly launch --no-deploy

# Create a persistent volume for SQLite
fly volumes create fifa_data --size 1 --region sin

# Set secrets
fly secrets set \
  SECRET_KEY="..." \
  ADMIN_KEY="..." \
  BASE_URL="https://your-app.fly.dev" \
  FOOTBALLDATA_API_KEY="..."

fly deploy

# Custom domain
fly certs add yourdomain.com
# Point an A record to the IP shown by: fly certs show yourdomain.com
```

After deploying, set up via SSH:

```bash
# Upload your participants.txt first
fly sftp shell
put participants.txt /app/participants.txt
exit

fly ssh console
cd /app
alembic upgrade head
python -m scripts.sync_fixtures
python -m scripts.generate_links
```

## Slack notifications (optional)

Posts reminders and leaderboard updates to a Slack channel via an **Incoming Webhook** (outbound only — no bot user or scopes needed).

**Setup:**
1. In Slack: *Apps → Incoming Webhooks → Add to Slack*, pick your channel, copy the webhook URL.
2. Set it as a secret:
   - Local: add `SLACK_WEBHOOK_URL=...` to `backend/.env`
   - Fly.io: `fly secrets set SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."`
3. Restart the app and verify: `curl -X POST https://your-app/admin/slack-test -H "X-Admin-Key: YOUR_ADMIN_KEY"`

When `SLACK_WEBHOOK_URL` is unset, all Slack code is a no-op — the app runs identically.

**What it posts** (all idempotent; the bot won't replay a backlog when first enabled):
- **Polls open** — when a matchday's voting window opens (48h before its first kickoff)
- **Vote reminder** — `SLACK_REMINDER_HOURS_BEFORE` hours before kickoff, listing who hasn't picked
- **Match results** — as each match auto-settles (flags upsets)
- **Daily leaderboard** — every day at `SLACK_LEADERBOARD_HOUR_IST`

Requires running `alembic upgrade head` (adds the `sent_notifications` table) — see below.

## Settling results manually (fallback)

```bash
# List match IDs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app/admin/matches

# Settle a match
curl -X POST https://your-app/admin/settle \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"match_id": 5, "result": "team_a"}'

# Reset scores (keeps fixtures)
curl -X POST https://your-app/admin/reset-scores -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

## Replacing the frontend with React

```bash
mv frontend frontend-html
npm create vite@latest frontend -- --template react
# Set VITE_API_BASE=https://your-app.fly.dev in your React app
# The /api/* endpoints are identical — no backend changes needed.
```

## Forking for your own tournament

1. Register for a free football-data.org API key
2. Update `backend/data/rankings.json` with current FIFA rankings
3. Create your `participants.txt`
4. Optionally adjust `STAGE_MULTIPLIER` in `backend/app/scoring.py`
5. Deploy and share links

## API Reference

All endpoints require `?user=NAME&sig=HMAC` except `/api/chat` (read), `/api/standings`, `/api/bracket`, and admin routes.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/whoami` | Your display name (validates your link) |
| `GET` | `/api/matches` | Votable matches + your vote + status |
| `GET` | `/api/matches/{id}` | One match's detail + all participants' picks (hidden until kickoff) |
| `POST` | `/api/vote` | Submit or change a prediction (before kickoff) |
| `DELETE` | `/api/vote?match_id=N` | Remove your prediction (before kickoff) |
| `GET` | `/api/leaderboard` | Ranked scores for all players |
| `GET` | `/api/me` | Your per-match score breakdown |
| `GET` | `/api/users/{username}/history` | Any player's prediction history |
| `GET` | `/api/standings` | Live group standings via football-data.org (no auth) |
| `GET` | `/api/bracket` | Knockout-stage matches for the bracket (no auth) |
| `GET` | `/api/chat` | Last 50 chat messages (no auth) |
| `POST` | `/api/chat` | Post a chat message |
| `POST` | `/admin/settle` | Manually settle a match result |
| `GET` | `/admin/matches` | List all matches with IDs |
| `GET` | `/admin/participation` | Engagement overview — who's voting/chatting (no picks revealed); backs `/admin.html` |
| `POST` | `/admin/reset-scores` | Wipe votes, scores, results |
| `POST` | `/admin/reset-all` | Wipe everything |
| `POST` | `/admin/slack-test` | Send a test message to the Slack webhook |
| `POST` | `/admin/announce` | Post a free-form message to Slack as the bot (used by `/admin.html`) |
