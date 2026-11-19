# TRADELINE Free Infrastructure Deployment

## Architecture
- Static frontend: Render static site `tradeline-europe` at `https://tradeline-europe-u7gw.onrender.com`.
- API: Render free Docker Web Service `tradeline-api`.
- Durable accounts: Neon PostgreSQL free tier by setting `DATABASE_URL`; no Render paid disk.
- Email: Resend HTTPS API; no direct SMTP required.
- AI: Anthropic API; billing is provider-dependent and may require a card. Missing key produces HTTP 503, not a fake answer.

## No-card providers
- Neon: current free plan is designed for no-card signup, but provider limits can change; verify the dashboard before production.
- Resend: free API signup is without card according to current official pricing, but a verified sending domain is required.
- Render: API is a free web service only if the instance is left at free settings. Do not enable a disk or paid instance in Blueprint/dashboard.

## Render environment variables
- `DATABASE_URL`: Neon PostgreSQL connection string. Recommended for accounts, sessions and counters.
- `ALLOWED_ORIGINS=https://tradeline-europe-u7gw.onrender.com`
- `ANTHROPIC_API_KEY`: Anthropic secret.
- `CLAUDE_MODEL`: optional model name.
- `RESEND_API_KEY`: Resend secret.
- `EMAIL_FROM`: sender using a verified domain.

Optional SMTP fallback variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`. Free Render web services may block SMTP ports, so Resend is recommended.

## Frontend configuration
`public/config.js` points at `https://tradeline-api.onrender.com`. If Render generates another API URL, replace it before deployment. Never put secrets in this file.

## Deploy
1. Create a Neon database and copy `DATABASE_URL` to Render.
2. Create/verify a Resend sending domain and copy API key/environment values to Render.
3. Deploy Blueprint only without disk or paid instance settings.
4. Open `https://tradeline-api.onrender.com/health` and verify `ok`, `database` and `email` fields.
5. Redeploy the static frontend.

## Known limitations
- Free Render web services sleep and cold-start.
- `/tmp` SQLite is only a safe local/test fallback and not durable on Render.
- Neon and Resend free limits can change and impose quotas.
- Anthropic API access is not guaranteed free.
