# Deploying LitFinder on AWS EC2

**English** | [简体中文](deploy-ec2.zh-CN.md)

This guide puts LitFinder on the public internet at the lowest cost: one small EC2 instance running the existing Docker Compose setup, with [Caddy](https://caddyserver.com) in front for automatic HTTPS. Everything is done in the AWS web console; the AWS CLI isn't needed.

## Architecture

```
Browser / MCP client
      │  HTTPS (443)
      ▼
┌──────── EC2 t4g.small (Ubuntu 24.04, Arm, 2 GB RAM + 2 GB swap) ────────┐
│  Caddy: HTTPS certificates, security headers                             │
│   ├─ /mcp*        → Bearer token check → mcp container :8000             │
│   └─ everything else → web container :5001 (gunicorn + Flask + reranker) │
│  backend/.env and deploy/.env: keys and settings, readable only by you   │
└──────────────────────────────────────────────────────────────────────────┘
Security group: 80/443 open to all, 22 (SSH) open to your IP only.
The app and the MCP server publish no ports; they are reachable only through Caddy.
```

What the production setup adds (`deploy/`):

| Piece | Purpose |
|---|---|
| Usage limits (`backend/usage_limits.py`) | Each costly endpoint has a per-client hourly limit and a site-wide daily limit; over either, the API answers HTTP 429 with `Retry-After` |
| `deploy/Caddyfile` | HTTPS, HTTP→HTTPS redirect, security headers; `/mcp` requires `Authorization: Bearer <MCP_TOKEN>` |
| `deploy/docker-compose.prod.yml` | Adds Caddy, removes the app's published ports, turns on the limits, trusts Caddy's `X-Forwarded-For`, disables cross-origin API calls, rotates logs |
| `deploy/setup-server.sh` | One-time server setup: swap, Docker from Docker's apt repository, firewall, automatic security updates |
| `deploy/deploy.sh` | Checks the config files, then builds and starts everything; also runs any other `docker compose` command with the right files |

## Cost

Approximate on-demand prices in us-west-2 / us-east-1; check the AWS pricing pages for current numbers.

| Item | Per month |
|---|---|
| EC2 t4g.small (2 vCPU, 2 GB), running all the time | ~US$12.3 |
| Public IPv4 address (charged separately since 2024) | ~US$3.6 |
| 20 GB gp3 disk | ~US$1.6 |
| **Server total** | **~US$17.5** |
| API usage, worst case with the default daily limits | OpenAI ≤ ~US$0.35/day plus paper analyses; OpenAlex ≤ ~US$0.9/day, inside its free US$1/day |

Ways to pay less:

- **New-account credits.** New AWS accounts get promotional credits that can cover the first months; see the sign-up page for the current offer.
- **Stop the instance when you don't need it.** A stopped instance costs only the disk and the IP address, about US$5 a month.
- **Lightsail.** Its 2 GB Linux plan is a flat ~US$12 a month including the IP address. The steps below work the same on a Lightsail Ubuntu instance.

### Default usage limits

Set in `backend/.env` as `LIMIT_<NAME>=<per client per hour>,<per UTC day>`; `0` means unlimited.

| Endpoints | Setting | Default | Cost of one request |
|---|---|---|---|
| `/api/search` and the other pipeline searches | `LIMIT_SEARCH` | 20 / hour, 300 / day | ~US$0.0014 |
| `/api/agent-search` | `LIMIT_AGENT` | 10 / hour, 100 / day | ~US$0.003-0.008 |
| `/api/publication/<id>/analyze` | `LIMIT_ANALYZE` | 10 / hour, 50 / day | one `LLM_MODEL` call |
| `/api/publication/<id>` | `LIMIT_DETAILS` | 60 / hour, 1000 / day | ~US$0.0001 |

Counters are kept in memory by the single gunicorn process, so they reset when the container restarts. `GET /api/health_check` reports today's counts.

## 1. Create the AWS account (about 30 minutes)

1. Sign up at [aws.amazon.com](https://aws.amazon.com). You'll need a card and a phone number.
2. **Turn on MFA for the root user** (account menu → Security credentials). A leaked root password without MFA can run up a huge bill.
3. **Create a budget alert:** Billing and Cost Management → Budgets → Create budget → Monthly cost budget, e.g. US$20, with email alerts at 80% and 100%.
4. Pick one region and stay in it, e.g. **us-west-2 (Oregon)**.

## 2. Launch the instance (about 20 minutes)

EC2 → Launch instance:

| Setting | Value |
|---|---|
| Name | `litfinder` |
| AMI | Ubuntu Server 24.04 LTS, **64-bit (Arm)** |
| Instance type | `t4g.small` |
| Key pair | Create one (ED25519), download the `.pem` file to `~/.ssh/` |
| Network settings | Create a security group: SSH from **My IP**; HTTP and HTTPS from anywhere |
| Storage | 20 GB gp3 |

Then give the instance a fixed address: EC2 → Elastic IPs → Allocate Elastic IP address → Actions → Associate with the `litfinder` instance.

On your computer, make the key readable only by you (SSH refuses keys others can read):

```bash
chmod 400 ~/.ssh/litfinder.pem
```

## 3. Choose the address

Caddy needs a host name to get an HTTPS certificate. Either:

- **Free, no setup:** [sslip.io](https://sslip.io). For Elastic IP `3.14.15.92`, use `3-14-15-92.sslip.io`, which already resolves to it. Certificates for sslip.io names share Let's Encrypt's rate limits with everyone else, so issuance can occasionally be delayed.
- **Your own domain** (about US$10 a year, e.g. from Cloudflare Registrar): add an A record such as `litfinder.example.com` pointing to the Elastic IP. It looks better on a resume.

## 4. Set up the server and start LitFinder (about 30 minutes)

Log in:

```bash
ssh -i ~/.ssh/litfinder.pem ubuntu@YOUR_ELASTIC_IP
```

Get the code:

```bash
git clone https://github.com/LynnUoE/om-dissertation-implementation.git litfinder && cd litfinder
```

Run the one-time setup (swap, Docker, firewall, automatic security updates):

```bash
sudo bash deploy/setup-server.sh
```

Log out and back in so your user can run `docker` without `sudo`, then `cd litfinder` again.

Create the app configuration. Use a **separate OpenAI project and API key** for the server, and turn off auto-recharge in OpenAI billing, so a leaked key can spend at most the remaining balance:

```bash
cp backend/.env.example backend/.env && nano backend/.env && chmod 600 backend/.env
```

At minimum set `OPENAI_API_KEY`, `OPENALEX_API_KEY` and `RESEARCHER_EMAIL`. `DEBUG`, `HOST` and `PORT` are overridden by Docker Compose.

Create the deployment configuration (the site address and the MCP token):

```bash
openssl rand -hex 32
```

```bash
cp deploy/.env.example deploy/.env && nano deploy/.env && chmod 600 deploy/.env
```

Build and start. The first build on the instance takes about 10-15 minutes:

```bash
deploy/deploy.sh
```

## 5. Check it

The health check should report `"status": "healthy"` and today's usage:

```bash
curl https://YOUR_ADDRESS/api/health_check
```

- Open `https://YOUR_ADDRESS` in a browser and run a search.
- Without the token, `/mcp` answers 401:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://YOUR_ADDRESS/mcp
```

- Add the remote MCP server to Claude Code on your computer:

```bash
claude mcp add --transport http litfinder-cloud https://YOUR_ADDRESS/mcp --header "Authorization: Bearer YOUR_MCP_TOKEN"
```

## 6. Running it

| Task | How |
|---|---|
| Update to the latest code | `git pull && deploy/deploy.sh` |
| Logs | `deploy/deploy.sh logs -f --tail 100 web` (logs are rotated at 3 × 10 MB per container) |
| Status | `deploy/deploy.sh ps` |
| Restart after a reboot | Automatic: Docker starts at boot and the containers use `restart: unless-stopped` |
| Change the limits | Edit `LIMIT_*` in `backend/.env`, then `deploy/deploy.sh` |
| Pause to save money | EC2 → Instances → Stop; Start it again later (the Elastic IP stays) |
| Watch spending | AWS Budgets emails, the OpenAI usage page, and `usage` in `/api/health_check` |

**Security notes**

- SSH accepts keys only (Ubuntu's default on EC2). If your IP changes, update the security group's SSH rule.
- `backend/.env` and `deploy/.env` are ignored by git; never commit them. Rotate the API keys if you think they leaked.
- The firewall (ufw) allows only SSH, HTTP and HTTPS. Docker-published ports bypass ufw, which is why the production compose file publishes only Caddy's.
- The app has no user accounts. The usage limits cap what anyone can spend, but anyone can use the demo up to them.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| The browser can't connect | The security group doesn't allow 80/443, or the address doesn't resolve to the Elastic IP yet |
| Certificate errors right after the first start | Caddy is still getting the certificate; check `deploy/deploy.sh logs caddy` |
| The build is killed or the instance freezes | Out of memory: check that swap is on with `swapon --show` |
| `web` keeps restarting | Check `deploy/deploy.sh logs web`, usually a missing `OPENAI_API_KEY` in `backend/.env` |
| "The public demo has used today's ..." | The daily limit was reached; it resets at 00:00 UTC, or raise `LIMIT_*` |
