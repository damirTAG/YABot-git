# Yerzhan

## Telegram Media Bot

#### Link - https://t.me/yerzhanakh_bot

---

## Stack

- **Python 3.13**, dependencies managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`).
- **Lint/format:** Ruff. **Type check:** ty (advisory).
- **Runtime:** runs natively under a systemd unit, talking to a native Postgres on the same host.
- **CI/CD:** GitHub Actions — lint/type on PRs; pushes to `prod` deploy to the VPS over SSH (git pull + `uv sync` + service restart).

## Local development

```bash
uv sync                       # create .venv from the lockfile (incl. dev tools)
cp example.env .env           # fill in tokens; DB_HOST=localhost
uv run ruff check src         # lint
uv run ruff format src        # format
uv run ty check src           # type report (advisory)
PYTHONPATH=src uv run python src/app.py   # run the bot
```

Modules import top-level (`from config import ...`), so `src/` must be on
`PYTHONPATH` — hence the `PYTHONPATH=src` prefix (the systemd unit sets this).
Schema is created on startup by the idempotent `DB_actions().init_db()`
(`CREATE TABLE IF NOT EXISTS`), so pointing at an existing DB is safe — no
migrations, no data loss.

## Deployment (VPS)

Pushes to the `prod` branch trigger [`.github/workflows/deploy.yaml`](.github/workflows/deploy.yaml),
which SSHes to the VPS and, in `DEPLOY_DIR`:

```bash
git fetch --all --prune
git reset --hard origin/prod
uv sync --frozen --no-dev
sudo systemctl restart yerzhanbot
```

### One-time VPS setup

1. Install [uv](https://docs.astral.sh/uv/) and `ffmpeg`:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   sudo apt-get update && sudo apt-get install -y ffmpeg
   ```
2. Clone the repo into the deploy dir and check out `prod`:
   ```bash
   git clone https://github.com/damirtag/YABot-git.git /opt/yerzhanbot
   cd /opt/yerzhanbot && git checkout prod
   ```
3. Create `/opt/yerzhanbot/.env` from `example.env` (real tokens; `DB_HOST=localhost`).
4. Install deps: `uv sync --frozen --no-dev`.
5. Install the service (adjust `User`/paths in the unit first):
   ```bash
   sudo cp deploy/yerzhanbot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now yerzhanbot
   ```
6. Allow the deploy user to restart the service without a password — add a
   sudoers drop-in (`sudo visudo -f /etc/sudoers.d/yerzhanbot`):
   ```
   <deploy_user> ALL=(root) NOPASSWD: /usr/bin/systemctl restart yerzhanbot, /usr/bin/systemctl status yerzhanbot
   ```

### Required GitHub Actions secrets

| Secret | Purpose |
| --- | --- |
| `VPS_HOST` | VPS hostname/IP |
| `VPS_USER` | SSH user (the deploy user) |
| `VPS_SSH_KEY` | Private key for that user |
| `VPS_PORT` | SSH port (optional, defaults to 22) |
| `DEPLOY_DIR` | Repo dir on the VPS (e.g. `/opt/yerzhanbot`) |

The VPS git checkout must be able to `git fetch origin` (public HTTPS, or a
deploy key for a private repo).

### Logs & rollback

```bash
journalctl -u yerzhanbot -f          # live logs (also written to src/logs/bot.log)
cd /opt/yerzhanbot && git reset --hard <old-sha> && uv sync --frozen --no-dev && sudo systemctl restart yerzhanbot
```
