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
which **rsyncs** the checked-out code into `DEPLOY_DIR` (no git needed on the
VPS) and then, over SSH:

```bash
uv sync --frozen --no-dev
sudo systemctl restart yerzhanbot
```

The rsync excludes `.env`, `.venv`, and runtime dirs, so they're preserved on
the server across deploys. `DEPLOY_DIR` only needs to exist and contain `.env`.

### One-time VPS setup

1. Install [uv](https://docs.astral.sh/uv/) and `ffmpeg`:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   sudo apt-get update && sudo apt-get install -y ffmpeg
   ```
2. Create the deploy dir and its `.env` (the workflow rsyncs the code in):
   ```bash
   sudo mkdir -p /opt/yerzhanbot_stable && sudo chown "$USER" /opt/yerzhanbot_stable
   # create /opt/yerzhanbot_stable/.env from example.env (real tokens; DB_HOST=localhost)
   ```
3. Trigger one deploy (push to `prod` or "Run workflow") to populate the dir,
   then install deps and the service:
   ```bash
   cd /opt/yerzhanbot_stable
   uv sync --frozen --no-dev
   sudo cp deploy/yerzhanbot.service /etc/systemd/system/   # check User/paths
   sudo systemctl daemon-reload
   sudo systemctl enable --now yerzhanbot
   ```
4. Allow the deploy user to restart the service without a password — add a
   sudoers drop-in (`sudo visudo -f /etc/sudoers.d/yerzhanbot`):
   ```
   <deploy_user> ALL=(root) NOPASSWD: /usr/bin/systemctl restart yerzhanbot, /usr/bin/systemctl status yerzhanbot
   ```

> Running this **alongside** the existing bot? Give it its own service name
> (e.g. `yerzhanbot-stable.service`) and a separate `TEST_BOT_TOKEN` in `.env`
> so the two don't fight over Telegram long-polling.

### Required GitHub Actions secrets

| Secret | Purpose |
| --- | --- |
| `VPS_HOST` | VPS hostname/IP |
| `VPS_USER` | SSH user (the deploy user) |
| `VPS_SSH_KEY` | Private key for that user |
| `VPS_PORT` | SSH port (optional, defaults to 22) |
| `DEPLOY_DIR` | Deploy dir on the VPS (e.g. `/opt/yerzhanbot_stable`) |

### Logs & rollback

```bash
journalctl -u yerzhanbot -f          # live logs (also written to src/logs/bot.log)
# rollback: check out the previous commit locally and re-push to prod,
# or rsync an older checkout into DEPLOY_DIR and restart the service.
```
