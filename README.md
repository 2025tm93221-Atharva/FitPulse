# Fitness Membership Application — V1 Feature Completion

A production-oriented V1 completion release building on scanner-device authentication and staging deployment scaffolding. It closes the original V1 account-recovery, profile, in-app notification, support, and privacy-consent gaps. Physical door hardware integration is still a separate vendor-specific release gate. The backend uses FastAPI, SQLAlchemy 2.x, Pydantic, Alembic, SQLite for local development, and JWT bearer authentication.

## What's included

- Member registration and login with Argon2 password hashing (`argon2-cffi`).
- Short-lived JWT access tokens and authenticated `/users/me` endpoint.
- Role checks for `member`, `staff`, and `admin`.
- Admin-only membership creation and status transitions.
- Membership date validation and overlap checks.
- Member-only, short-lived signed gym QR payload issuance.
- Staff/admin-assisted QR validation plus a dedicated scanner-device API-key endpoint, membership revalidation at scan time, per-device location attribution, and one-time token replay prevention using a unique `qr_jti` database constraint.
- Check-in history scoped to the authenticated member.
- Password recovery using hashed, expiring, single-use tokens delivered by SMTP in staging/production; successful reset revokes existing access-token sessions. New reset requests invalidate earlier outstanding links, and unknown-account responses do not disclose account existence.
- Member profile editing for full name (email remains read-only until email verification is implemented).
- In-app notifications with read/unread filtering, per-item read state, and read-all actions; membership and support events generate notifications.
- Member support tickets with category, status tracking, staff response, and staff/admin resolution endpoints.
- Persisted optional analytics and marketing consent preferences, defaulting to opt-out.
- Alembic migration for the initial schema.
- Health and database readiness endpoints, response security headers, timezone-aware membership dates, and runtime validation of staging/production secrets.
- Dockerfiles and Docker Compose staging stack for PostgreSQL, API, Alembic migrations, and an Nginx-served React frontend.
- Nginx login/scanner rate limits and a staging smoke-test script.
- Pytest suite for authentication, authorization, membership lifecycle, and check-in security.
- React login/registration screens wired to the API, authenticated membership dashboard, real short-lived server-issued QR token rendered as QR code, check-in history, and sign-out. The access token is kept in memory rather than `localStorage`.

## Requirements

- Python 3.11+
- Node.js 22.12+ and npm 10+ (for the pinned Vite 8 frontend toolchain)

## Backend setup

From a terminal:

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env   # Windows: Copy-Item .env.example .env
```

Edit `.env` before deployment. In production, set a unique random `SECRET_KEY` of at least 32 characters, `ENVIRONMENT=production`, a production database URL, and exact allowed frontend origins. Do not commit `.env`.

Apply migrations:

```bash
alembic upgrade head
```

Create the initial administrator (password is prompted without echo):

```bash
python -m app.cli create-admin --email admin@example.com --full-name "Gym Administrator"
# Provision front-desk scanner staff similarly:
python -m app.cli create-staff --email staff@example.com --full-name "Front Desk"
```

If you already have a `fitness.db` created by the original starter, back it up first, then mark its old schema baseline and apply the authentication upgrade:

```bash
alembic stamp 0001_initial
alembic upgrade head
```

Legacy member accounts are preserved but have no usable password hash after migration. Set one manually for each account before login:

```bash
python -m app.cli set-password --email existing.member@example.com
```

Only use `alembic stamp 0001_initial` for a database created by the original starter schema. For a new/empty database, run `alembic upgrade head` directly.

Start the API:

```bash
uvicorn app.main:app --reload
```

- API docs: http://127.0.0.1:8000/docs
- API health: http://127.0.0.1:8000/api/health
- Database readiness: http://127.0.0.1:8000/api/health/ready

The migration must be applied before using the API/CLI. The application intentionally does not call `Base.metadata.create_all()` at startup; schema changes should be versioned and deployed through Alembic.

## Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The default Vite origin (`http://localhost:5173`) is included in development CORS settings. Register and sign in through the frontend; a club administrator must assign an active membership before the member can generate a QR pass. The QR image contains a short-lived signed token issued by the backend. Staff can perform operator-assisted validation; a dedicated scanner key authenticates physical scanner requests. The real access-control hardware still must be integrated and tested before live gym entry.

## Run automated tests

From `backend/`, with the venv active:

```bash
pytest -q
```

Tests use an isolated in-memory SQLite database, and do not require a running server or a developer database file. The current local run passes **53 backend tests** (including V1 acceptance paths). `TEST_PLAN.md` lists the test cases and expected outcomes. GitHub Actions runs the suite against Python 3.11, 3.12, and 3.13.

## Phase 2: trusted scanner devices

Apply all migrations with `alembic upgrade head`, then register a scanner device:

```bash
python -m app.cli create-scanner --name "Front Door Reader" --location-name "Downtown Club"
```

The command prints the scanner key once. Store it in the scanner's protected configuration; never commit or log it. The API stores only a SHA-256 digest of the high-entropy secret.

Trusted device endpoint:

```http
POST /api/scanner/check-ins/validate
X-Scanner-Key: fscan_<key-id>.<secret>
Content-Type: application/json

{"qr_token":"<short-lived-token-from-member-pass>"}
```

The scanner location is read from the registered device record; request JSON cannot override it. A scanner key can be rotated or disabled:

```bash
python -m app.cli rotate-scanner-key --scanner-id 1
python -m app.cli deactivate-scanner --scanner-id 1
```

The API key authenticates the device to this API. It does not by itself authenticate a physical door controller or protect a plaintext network connection, so external devices must use HTTPS and the real controller integration must be validated before live entry.

## API endpoints

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/register` | Public | Create a member account |
| `POST` | `/api/auth/login` | Public | Exchange credentials for a bearer token |
| `POST` | `/api/auth/password-reset/request` | Public | Request a generic account-recovery response; email delivery is environment-configured |
| `POST` | `/api/auth/password-reset/confirm` | Public | Consume reset token, change password, revoke existing sessions |
| `GET` | `/api/users/me` | Authenticated | Read the current user profile |
| `PATCH` | `/api/users/me` | Authenticated | Edit the member full name |
| `GET/PATCH` | `/api/privacy/preferences` | Authenticated | Read/update optional analytics and marketing consent |
| `GET/PATCH/POST` | `/api/notifications/...` | Authenticated | Read notifications and mark one/all as read |
| `POST` | `/api/support/tickets` | Authenticated | Create support request |
| `GET` | `/api/support/tickets/me` | Authenticated | View own support tickets |
| `GET/PATCH` | `/api/support/tickets/...` | Staff/admin | List and resolve support tickets |
| `GET` | `/api/memberships/me` | Authenticated | List the current member's memberships |
| `GET` | `/api/memberships/{id}` | Owner/admin | Read one membership |
| `POST` | `/api/memberships` | Admin | Create a membership |
| `PATCH` | `/api/memberships/{id}/status` | Admin | Apply an allowed membership status transition |
| `POST` | `/api/check-ins/qr-token` | Member | Issue a short-lived gym pass token |
| `POST` | `/api/check-ins/validate` | Staff/admin | Operator-assisted validation and check-in |
| `POST` | `/api/scanner/check-ins/validate` | Scanner API key | Device-authenticated check-in at its registered location |
| `GET` | `/api/scanner/check-ins/whoami` | Scanner API key | Verify scanner key/device configuration |
| `GET` | `/api/check-ins/me` | Authenticated | Read the current member's check-in history |
| `GET` | `/api/health` | Public | Liveness check |
| `GET` | `/api/health/ready` | Public | Database readiness check |

Use the `Authorize` button in `/docs` and paste the `access_token`; Swagger UI adds the `Bearer` scheme to the request header.

## Membership rules implemented

- Self-registration always creates a normal `member`; clients cannot set their own role.
- Only `admin` can issue memberships or change membership status.
- Allowed transitions: `pending -> active/cancelled`, `active -> frozen/cancelled/expired`, and `frozen -> active/cancelled/expired`. `cancelled` and `expired` are terminal in this phase.
- Creating or activating an active membership requires that its start/expiry dates cover today's server date and that it does not overlap another pending, active, or frozen membership.
- QR tokens expire quickly and are signed on the server. The scanner re-checks membership status and date eligibility at scan time.
- A QR token can be redeemed once. A database uniqueness constraint protects against concurrent replay attempts.

## Tests covered

- Health/readiness behavior.
- Registration normalization, duplicate emails, password policy, password non-disclosure, login success/failure, and protected routes.
- Role-based membership creation and status changes, date validation, overlapping dates, resource ownership, and terminal state transitions.
- QR pass issuance, expired/frozen membership denial, staff-only scanner access, malformed/expired token denial, successful check-in, replay rejection, and member-specific history.

## Start the staging stack

This stack is for **local/staging acceptance testing only**. It publishes HTTP on the configured port (default `8080`); put a TLS-enabled ingress/load balancer in front of any remotely accessible staging environment. Do not expose the raw API or database ports to the internet.

At the repository root:

```bash
cp .env.staging.example .env.staging
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48)); print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(36))"
```

Replace the placeholder values in `.env.staging` with newly generated values. Preserve URL-safe characters in `POSTGRES_PASSWORD` because it is incorporated into the Compose database URL. Set `CORS_ORIGINS` to the exact browser origin used by the staging frontend.

```bash
docker compose --env-file .env.staging -f compose.staging.yml config
docker compose --env-file .env.staging -f compose.staging.yml up --build -d
docker compose --env-file .env.staging -f compose.staging.yml ps
python scripts-staging-smoke.py http://localhost:8080
```

Open `http://localhost:8080` for the frontend and `http://localhost:8080/docs` for API docs through Nginx. Follow logs with:

```bash
docker compose --env-file .env.staging -f compose.staging.yml logs -f api scheduler frontend migrate
```

Stop without deleting the database volume:

```bash
docker compose --env-file .env.staging -f compose.staging.yml down
```

`docker compose down -v` deletes the local Postgres volume and should be used only when intentionally wiping test data.

For a deployed environment, run the smoke tests against the HTTPS origin, review the configured TLS certificate and access logs, and run the functional scanner tests against a real trusted scanner in a controlled test area.

## Remaining production integration work

This phase supplies deployment scaffolding and a device-authenticated API, but is not a certified physical access-control system. Before real entry is enabled:

1. Connect the endpoint to the actual scanner/door controller and provision each device through a protected channel.
2. Put TLS in front of the staging/public service; keep database and direct API ports private. Manage secrets in a secret manager and rotate scanner keys after suspected exposure.
3. Complete MFA/admin hardening, centralized audit logs, alerting, and incident-response procedures.
4. Test PostgreSQL backup and restore, migration rollback/recovery, and fail-closed behavior during API/database outages.
5. Run the configured browser end-to-end acceptance workflow, load tests, and a security review on the deployment target. Direct frontend dependency versions are pinned, but this environment could not fetch npm dependencies to perform the production build; generate and commit `frontend/package-lock.json` in a network-enabled environment before production release.
6. Connect membership payments and reconciliation before exposing purchase/renewal flows.
7. Review applicable privacy, retention, and regulatory requirements before collecting sensitive fitness data.

## Database configuration

SQLite is the default for local development (`sqlite:///./fitness.db`). PostgreSQL can be configured using a SQLAlchemy URL and the appropriate PostgreSQL driver. For example, install `psycopg[binary]` and set `DATABASE_URL=postgresql+psycopg://...`; never put credentials in source control.



## Product V2: Self-Service and Class Reservations

Product V2 adds member class discovery and bookings, bounded waitlists with promotion, staff class scheduling/cancellation, class reminders, membership renewal requests, and freeze/resume with expiry reconciliation. The existing dark membership dashboard now includes the Classes & bookings and Plan management panels.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/classes` | Authenticated | Search upcoming classes by time, location, type, and text |
| `POST` | `/api/classes` | Staff/admin | Publish a future class |
| `GET` | `/api/classes/{id}` | Authenticated | Read class details and availability |
| `PATCH` | `/api/classes/{id}` | Staff/admin | Update or cancel class |
| `POST` | `/api/classes/{id}/bookings` | Member | Book a spot or join the waitlist |
| `GET` | `/api/bookings/me` | Authenticated | Read own upcoming bookings; set `upcoming_only=false` for history |
| `POST` | `/api/bookings/{id}/cancel` | Owner/staff/admin | Cancel booking; promote waitlist if a spot is released |
| `POST` | `/api/memberships/{id}/renew` | Owner/staff/admin | Request a renewal for 30/90/180/365 days |
| `GET` | `/api/memberships/renewals/me` | Authenticated | View own renewal requests |
| `GET` | `/api/memberships/renewals?status_filter=pending` | Staff/admin | View renewal review queue |
| `PATCH` | `/api/memberships/renewals/{id}` | Staff/admin | Approve/reject a pending renewal request |
| `POST` | `/api/memberships/renewals/{id}/cancel` | Owner | Cancel own pending renewal request |
| `POST` | `/api/memberships/{id}/freeze` | Owner/staff/admin | Freeze an eligible membership for 1–30 days |
| `POST` | `/api/memberships/{id}/resume` | Owner/staff/admin | Resume early and reconcile expiration date |

**Important commercial boundary:** renewal requests are staff-approved and do not charge a payment method. Connect a payment gateway and reconciliation before presenting renewal as a completed purchase.

### Class reminders and optional browser push

Confirmed bookings schedule 24-hour and 2-hour reminders where the reminder time is still in the future. The scheduler must run periodically to create in-app reminders and attempt Web Push. The staging Compose stack includes a worker that runs every minute; on non-Compose deployments, run `python -m app.tasks` under a process supervisor or scheduler at least once per minute.

To optionally enable browser push, in `backend/` run:

```bash
python -m scripts.generate_vapid_keys
```

Store the generated public/private key and claims email in `.env.staging` or a secret manager as `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_CLAIMS_EMAIL`. Do not commit the private key. If these variables are left blank, the in-app class reminder fallback continues to work. Web Push requires HTTPS in real browsers and outbound network connectivity.

### V2 acceptance

```bash
cd backend
PYTHONPATH=. pytest -q
DATABASE_URL=sqlite:////tmp/fitness-v2-migration.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/fitness-v2-migration.db alembic check
```

See `V2_RELEASE_NOTES.md` and `V2_TEST_PLAN.md` for release scope, expected test behavior, limitations, and staging acceptance. The development environment used for this package could not fetch npm dependencies and does not have Docker, so Vite production compilation, browser acceptance, and container builds must be verified by CI or a network-enabled machine.

## V1 completion and acceptance

Migration `0004_v1_completion` adds reset tokens, in-app notifications, privacy preferences, support tickets, and a `token_version` field used to revoke old access sessions when a password is reset. Apply it with `alembic upgrade head`; do not use `create_all()` for deployment.

For local account recovery, `MAIL_BACKEND=console` logs a reset URL and the API may return `debug_reset_token` only when `ENVIRONMENT=development`. Staging/production rejects console mail delivery and requires configured SMTP. The reset request response deliberately does not reveal whether an account exists.

Run backend automated tests and verify the migration state:

```bash
cd backend
PYTHONPATH=. pytest -q
DATABASE_URL=sqlite:////tmp/fitness-migration.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/fitness-migration.db alembic check
```

Real-browser acceptance coverage was added in `scripts/e2e_acceptance.py`, with test-only admin/staff seeding in `backend/scripts/seed_e2e_accounts.py` and a CI workflow in `.github/workflows/v1-acceptance.yml`. See `scripts/README-E2E.md` to run it locally. The latest V1 baseline had 53 backend tests; Product V2 extends the suite. For the current count and most recent verification details, see `V2_TEST_PLAN.md` and `V2_RELEASE_NOTES.md`. A full npm/Vite production build and Chromium browser run were not executed locally because npm dependency installation timed out in this environment; CI is configured to perform those checks when registry access is available.

**Launch boundary:** Feature-level V1 requirements are implemented, but a production launch still requires successful browser acceptance, environment-specific SMTP verification, HTTPS deployment, backup/restore review, and vendor-specific physical scanner/door-controller acceptance if the app will unlock gym entry.
