# AI-Powered Personal Diet Planner with Cloud Storage

A student cloud-computing project that turns a demo profile into general meal inspiration, saves each plan to a private user account, and stores optional meal images. It runs locally without paid services and can switch to Supabase Auth, Postgres, and private object storage.

> **Wellness disclaimer:** generated plans are educational/general-wellness examples, not medical or clinical nutrition advice. Do not use this project for diagnosis, treatment, or prescribed nutrition. Use synthetic/demo data only.

## Overview and problem statement

People often want a simple place to collect meal ideas and revisit them from different devices. This project demonstrates how a client/server application can create account-specific content and persist structured records and files. It is a course demonstration, not a clinically validated nutrition product.

Objectives: build a responsive web interface; expose a documented REST API; authenticate users; store profiles and plans; support file uploads; demonstrate a pluggable local/cloud architecture; document security, testing, deployment, and scaling.

## Simple and technical explanation

**Simple:** Sign in, enter demo preferences, generate a general meal idea, and save it. An optional image can be uploaded and downloaded later.

**Technical:** React sends JSON and multipart requests to FastAPI. The API checks a bearer token, validates input, generates a structured response, and calls a storage adapter. Local mode persists users/plans in SQLite and files on disk. Supabase mode validates Supabase Auth tokens, writes profile/plan/file metadata to Postgres, and writes bytes to a private Storage bucket. User IDs come from verified credentials, never from client-supplied IDs.

```text
Browser (React)
  ├── Sign up/sign in ──> FastAPI ──> local demo auth or Supabase Auth
  ├── REST requests ────> FastAPI ──> profile/plan database
  │                            └────> rule engine (optional AI API, with fallback)
  └── image upload ────> FastAPI ──> local files or private Supabase Storage
                                  └──> dashboard, saved plans, downloads
```

Cloud database stores structured fields and relationships; object storage holds image bytes. The metadata row links an owner and filename to the object's storage path. Authentication proves identity; authorization checks each requested record against that identity.

## Technology choices

| Track | Architecture | Difficulty/cost | Concepts and expected output |
|---|---|---|---|
| A Beginner | HTML/JS, Flask, SQLite, local files, rules | Low; locally free | API, client/server, persistence; small local demo |
| B Recommended (implemented) | React, FastAPI, local fallback or Supabase Auth/Postgres/Storage, optional AI API | Moderate; local mode free, cloud free tiers and quotas vary | REST, authentication, managed DB/object storage, local/cloud portability; complete app and deployment path |
| C Advanced | React/Next.js, FastAPI, AWS/Azure/GCP managed services, queues/functions | High; free-tier limits and billing vary | API gateway, serverless, monitoring, CDN, autoscaling; production-shaped architecture |

This repository implements Option B: Supabase and FastAPI. Local mode is the default. It does not require an AI key. Cloud deployment provider is intentionally a separate choice: see [deployment approaches](#cloud-deployment).

## Architecture and data flow

1. User registers or signs in. Local mode issues a short-lived signed token after password hashing; Supabase mode delegates accounts to Supabase Auth.
2. User saves a profile through `PUT /profile`; the API validates ranges and accepted preference values.
3. `POST /generate-plan` uses the verified user ID to read that profile. The optional AI call receives only structured preferences; timeout, malformed output, missing key, or API failure falls back to local food rules.
4. The response is stored as a user-owned plan and displayed by the dashboard.
5. Image upload validates type, content signature, and 5 MB size; image bytes and metadata are stored separately.
6. Saved-plan and file reads are scoped to the authenticated owner. A missing or foreign ID returns 404.

See [architecture and cloud concept map](docs/architecture.md) for deployment mapping and the data model.

## Features

- Registration, login, logout, protected dashboard, and user-specific data.
- Profile fields: name, age, height, weight, activity, food preference, general goal, optional foods to avoid.
- Breakfast, lunch, snack, dinner, general nutrition note, hydration reminder, and visible educational disclaimer.
- Vegetarian, vegan, or general recommendations; balanced, weight-management demo, or fitness-oriented demo goal.
- Rule-based engine always available; optional server-side AI API with schema checks and deterministic fallback.
- Save/list/read/delete plans, export plans as Markdown, and upload/list/download/delete optional JPEG, PNG, or WebP images.
- SQLite/filesystem local simulation, or Supabase Auth/Postgres/private Storage cloud integration.
- API validation, password hashing in local demo mode, per-user access checks, CORS settings, upload limits, and automated API tests.

## Database and storage

| Entity | Primary key | Important fields and relationship |
|---|---|---|
| Auth user | `auth.users.id` in cloud; `users.id` locally | Email, password hash only in local mode, creation time |
| Profile | `user_id` | One per user; demo profile fields; references Auth user |
| Diet plan | `id` | Meal text, source, notes, timestamp; many plans per user |
| User file metadata | `id` | Owner, filename, storage path, upload time; file bytes live in object storage |

Cloud schema and access policies are in `cloud/schema.sql`. Run it in the Supabase SQL editor before setting `APP_MODE=supabase`. Never expose the service role key in the browser; the API uses it server-side after it validates the caller token.

## REST API

Protected routes require `Authorization: Bearer <token>`.

| Method and path | Purpose | Success / common errors |
|---|---|---|
| `GET /health` | Liveness and mode | 200 |
| `POST /register` | Create account | 201 / 400, 409 |
| `POST /login` | Authenticate | 200 / 401 |
| `GET /profile`, `PUT /profile` | Read/update own profile | 200 / 401, 404, 422 |
| `POST /generate-plan` | Generate and save | 201 / 400, 401 |
| `GET /plans`, `GET /plans/{id}`, `DELETE /plans/{id}` | List/read/delete own plans | 200/204 / 404 |
| `POST /upload`, `GET /files`, `GET /files/{id}/download`, `DELETE /files/{id}` | Manage own image files | 201/200/204 / 401, 404, 413, 415 |

Interactive API documentation is available at `http://localhost:8000/docs` while the backend runs.

## Folder structure

```text
backend/app/         FastAPI routes, settings, schemas, auth, storage adapter, AI service
backend/tests/       API and authorization tests
frontend/src/        React application, API client, responsive styles
ai_engine/           Rule-based food examples (synthetic static data)
cloud/               Supabase Postgres schema, bucket, and RLS setup
docs/                Architecture, report, proof plan, screenshot checklist
sample_data/         Reserved for non-sensitive demo assets
screenshots/         Reserved for captured project evidence
```

## Local development

Requirements: Python 3.11+, Node.js 22+, and npm. The frontend lockfile pins pnpm 11.19.0; `npx` can run that pinned version without a global install. PowerShell commands from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Set a private local JWT secret in `backend/.env` (PowerShell example):

```powershell
$secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content backend\.env) -replace '^JWT_SECRET=.*$', "JWT_SECRET=$secret" | Set-Content backend\.env
```

In terminal 1, from the repository root:

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

In terminal 2, from the repository root:

```powershell
cd frontend
Copy-Item .env.example .env.local
npx pnpm@11.19.0 install --frozen-lockfile
npx pnpm@11.19.0 run dev
```

Open `http://localhost:5173`, register a synthetic demo account, fill in a profile, generate a plan, upload a small image, and check saved plans/files. SQLite and uploads are created under `backend/data/`. Verify logout/login by signing out and back in. All data remains local in this mode.

## Cloud deployment

Two approaches are documented. Free plans change and may sleep, limit resources, or require a payment method; check each provider's current terms before deployment. The application works locally even if a provider is unavailable.

### Approach A — student-friendly managed services (implemented adapter)

Use Supabase for Auth, Postgres, and Storage, a static hosting service for `frontend/`, and a Python-compatible application host for `backend/`. This architecture is provider-flexible. Before deploying, select the frontend/backend host based on current free-tier availability and account access.

1. Create a Supabase project; run `cloud/schema.sql` in SQL Editor. In Auth settings configure the site URL and allowed redirect URLs for the chosen frontend host.
2. Obtain Project URL, anon/public key, and service role key from project settings. Set these only in the backend host environment as `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`; set `APP_MODE=supabase`, a strong `JWT_SECRET`, and the exact frontend origin in `CORS_ORIGINS`. Keep service role credentials server-only.
3. Deploy the backend from repository root with build/install command `pip install -r backend/requirements.txt` and start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `PYTHONPATH=backend` if the host launches from the root, or set its root directory to `backend` and use `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Set `VITE_API_BASE` at frontend build time to the public HTTPS backend URL. Build with `pnpm run build` in `frontend/`; publish `frontend/dist` through the chosen static host.
5. Set backend CORS to the deployed frontend origin, use HTTPS, verify `/health`, test registration/login, profile save, generation, image upload/download, and owner isolation. Inspect host logs and Supabase records/storage.
6. For updates, push code to GitHub and enable host auto-deploy or deploy from the dashboard. Add a build check workflow before describing this as CI/CD.

### Approach B — AWS/Azure/GCP architecture

This is a design path, not configured in this repository. Select one provider before deployment; services and free-tier eligibility differ. A typical mapping is: static frontend on object hosting + CDN; API on container app service or managed container runtime; managed relational database; private object bucket; managed identity/auth provider; secret manager; centralized logs/metrics; optional API gateway and serverless workers. Store DB credentials and AI keys in a secret manager, restrict bucket access, use HTTPS, and configure backups/alerts. For a course demonstration, avoid creating billable resources until you have reviewed quotas and shutdown steps.

**Local vs cloud:** local mode uses a laptop process, SQLite, filesystem uploads, and demo JWTs; cloud mode uses hosted identity, managed Postgres, private object storage, public HTTPS endpoints, platform secrets, and provider logs. Cloud data is centrally reachable from multiple signed-in devices; local data is not automatically synchronized.

## Testing

From the repository root with the Python virtual environment active:

```powershell
python -m pytest backend/tests -v
```

The automated suite covers account duplication/login, unauthorized access, profile-dependent plan generation, vegetarian/vegan/general options, plan isolation, file upload/download isolation, invalid file type, and missing profile behavior. The [test-case matrix](docs/test-cases.md) marks each result as passed or not run. API failures can also be inspected in `/docs`. Use synthetic data only. For a deployed project, repeat the manual smoke cases in the evidence checklist and capture actual results rather than claiming unrun tests passed.

## Cloud computing concepts shown

| Concept | Project location / honest scope |
|---|---|
| Cloud computing, SaaS | Hosted browser-accessible application; demo users consume a web service |
| PaaS | Supabase and selected application host manage runtime/database services |
| IaaS | Not provisioned by this repo; VM-based equivalent is an extension |
| Cloud database vs object storage | Supabase Postgres rows vs private Storage object bytes |
| Authentication/authorization | Supabase Auth or local demo account; owner-scoped API access |
| REST and client/server | React JSON/multipart requests to FastAPI |
| Serverless/API gateway | Not currently deployed; described as scale-out architecture only |
| Scalability/elasticity/load balancing | Not demonstrated by local code; host/provider can add replicas, gateway, and balancing |
| Secrets/security | Environment variables; service role and AI keys backend-only |
| Logging/monitoring/backups | Host and Supabase dashboards plus provider backups; no custom monitoring integration configured |
| Deployment/CI/CD | GitHub Actions runs API tests and frontend production build; cloud deployment remains a provider setup step |

The architecture and interview-ready scaling scenarios are described in [docs/architecture.md](docs/architecture.md).

## Security and limitations

- Local auth is a teaching simulation, not production identity management. Use Supabase Auth in a hosted deployment.
- Cloud backend verifies the Supabase access token and derives user ID server-side. Service-role access bypasses RLS, so the API's ownership filters are critical; test them and never expose the key. Database and Storage RLS policies are also provided as defense in depth.
- Passwords in local mode are hashed; tokens expire. Use HTTPS in deployment, exact CORS origins, host-managed secret settings, private buckets, backups, and rate limiting at the host/API gateway.
- Uploads are restricted to image MIME types, file signatures, extensions, and 5 MB. Production should also scan content, randomize object names, rate-limit, and monitor abuse.
- No medical validation, calorie calculation, diagnosis, or clinician review. Allergy matching is a simple text filter and cannot guarantee safety. Do not use for real dietary decisions.
- AI output may be wrong; the deterministic engine is educational sample data, not a substitute for nutrition expertise.

See [docs/project-report.md](docs/project-report.md), [docs/proof-plan.md](docs/proof-plan.md), and [docs/screenshots.md](docs/screenshots.md) for report, GitHub timeline, and proof checklist.

## Learning outcomes

You can explain client/server design, REST, token authentication, data ownership, structured database vs object storage, fallback behavior, managed cloud services, environment secrets, testing, and the difference between a locally simulated service and an actually deployed service.

## Author

Student project — SHRADDHA VERMA, B.TECH IN COMPUTER SCIENCE AND ENGINEERING
