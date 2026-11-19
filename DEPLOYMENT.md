# TRADELINE deployment (free-tier audit)

## Architecture

- **Static frontend:** existing Render Static Site `tradeline-europe`, URL `https://tradeline-europe-u7gw.onrender.com`.
- **API:** `tradeline-api`, a Docker web service on Render.
- **Free database candidate:** Neon PostgreSQL (`DATABASE_URL`) is preferred for durable account and session data. No card is required for its free tier, according to its current documentation, but limits and regional availability can change.
- **Email:** Resend HTTPS API (`RESEND_API_KEY`) is preferred. SMTP variables are fallback only and direct SMTP may not work on a free Render web service.
- **AI:** Anthropic is configurable through `ANTHROPIC_API_KEY`. Missing keys are handled with a 503 response, never by claiming that an answer came from the model.

## Secrets — enter only in provider dashboards

### Render environment variables

- `ANTHROPIC_API_KEY`: Anthropic API key. Anthropic API use is paid usage unless a provider credit explicitly says otherwise.
- `CLAUDE_MODEL`: optional model name.
- `DATABASE_URL`: Neon PostgreSQL connection string, e.g. `postgresql://...?...sslmode=require`. It is recommended before production account use.
- `RESEND_API_KEY`: Resend API key.
- `EMAIL_FROM`: verified sender, e.g. `TRADELINE <no-reply@your-verified-domain.example>`.
- `ALLOWED_ORIGINS`: keep `https://tradeline-europe-u7gw.onrender.com`.

Optional SMTP fallback:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`

## Neon PostgreSQL

Create a Neon project without adding a payment method. Copy the PostgreSQL connection string into Render as `DATABASE_URL`. Neon may scale compute to zero and connection latency can appear as a cold start.

The repository also contains `schema.sql` for the larger Legal Intelligence database, but `server.py` currently uses SQLite for chat/account counters unless `DATABASE_URL` is implemented in the deployment branch. Do not treat temporary SQLite as durable production storage.

## Resend

Create a Resend account, verify the domain DNS SPF/DKIM records, generate an API key, and add `RESEND_API_KEY` and `EMAIL_FROM` to Render. The free plan can change; verify current limits in Resend before production launch. No card is needed only if you remain on the free tier.

## Deploy

1. Merge this branch only after review.
2. In Render, create/update the static service and Docker API service from `render.yaml`.
3. Do not enable a Render disk or paid instance type.
4. Set secrets in Render, never in Git.
5. Deploy `tradeline-api` and open `/health`.
6. Set `public/config.js` and `config.js` `chatApi` to the real API URL if chat is enabled.
7. Redeploy the static site.

## Smoke tests

- `GET /health` must return HTTP 200.
- CORS must return the exact allowed static origin.
- Registration must return 201 and trigger email only when email credentials are configured.
- Verification must reject expired or incorrect codes.
- Login must require verification and the correct password.
- Password reset must require a valid code and invalidate old sessions.
- Missing Anthropic key must return 503 with `not_configured`, not a fake answer.

## Free-tier limitations

- Render free web services spin down after inactivity and cold starts are possible.
- Render free web services do not provide a persistent disk for the API.
- Direct SMTP ports are blocked on free Render web services; use HTTPS email APIs.
- Anthropic API calls generally require billing/credit and are not guaranteed free.
- SQLite is ephemeral unless moved to durable external storage; Neon is the zero-card database option for initial production use.
