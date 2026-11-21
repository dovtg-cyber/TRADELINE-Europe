# TRADELINE Free Infrastructure Deployment

## Architecture
- Static frontend: Render static site `tradeline-europe` at `https://tradeline-europe-u7gw.onrender.com`.
- API: Render free Docker Web Service `tradeline-api`.
- Durable accounts: Neon PostgreSQL free tier by setting `DATABASE_URL`; no Render paid disk.
- Email: Resend HTTPS API; no direct SMTP required.
- AI: Google Gemini Developer API free tier; availability and quotas vary by account and model. Missing key produces HTTP 503, not a fake answer.

## Render environment variables
- `DATABASE_URL`: Neon PostgreSQL connection string. Recommended for accounts, sessions and counters.
- `ALLOWED_ORIGINS=https://tradeline-europe-u7gw.onrender.com`
- `GEMINI_API_KEY`: Google AI Studio API key.
- `GEMINI_MODEL`: optional model name; default `gemini-2.5-flash`.
- `RESEND_API_KEY`: Resend secret.
- `EMAIL_FROM`: sender using a verified domain.

Optional SMTP fallback variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`. Free Render web services may block SMTP ports, so Resend is recommended.

## Frontend configuration
`public/config.js` points at `https://tradeline-api.onrender.com`. If Render generates another API URL, replace it before deployment. Never put secrets in this file.

## Deploy
1. Create a Neon database and copy `DATABASE_URL` to Render.
2. Create/verify a Resend sending domain and copy API key/environment values to Render.
3. Create a Gemini API key in Google AI Studio and set `GEMINI_API_KEY` in Render.
4. Deploy Blueprint only without disk or paid instance settings.
5. Open the API `/health` and verify `ok`, `database`, `provider` and `email` fields.
