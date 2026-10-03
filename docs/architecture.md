# Architecture and cloud computing concept map

## Project files

| Path | Responsibility |
|---|---|
| `README.md` | Quick explanation, setup, architecture, API, deployment, security, and portfolio notes |
| `.gitignore` | Excludes environments, local databases/uploads, build output, and secrets |
| `.env.example` | Root-level pointer/default mode; real backend variables are in `backend/.env.example` |
| `backend/requirements.txt` | Python API and test dependencies |
| `backend/.env.example` | Local/cloud API settings template; copy to ignored `backend/.env` |
| `backend/app/main.py` | REST routes, request validation flow, CORS, upload checks, safe service errors |
| `backend/app/config.py` | Environment-based settings |
| `backend/app/schemas.py` | Validated request/response models |
| `backend/app/auth.py` | Local password hashing, JWT issue/verify, protected-user dependency |
| `backend/app/services/store.py` | SQLite/filesystem or Supabase persistence and storage adapter |
| `backend/app/services/diet_engine.py` | Rule-based generator, optional model call, output checks, fallback |
| `backend/tests/conftest.py` | Makes backend imports work from root or backend working directory |
| `backend/tests/test_api.py` | Isolated API, validation, auth, owner separation, upload, fallback-path checks |
| `frontend/package.json`, `frontend/pnpm-lock.yaml` | Pinned React/Vite dependencies and package scripts/lock |
| `frontend/index.html` | Browser document entry point |
| `frontend/.env.example` | Frontend API URL template; copy to ignored `.env.local` |
| `frontend/src/main.jsx` | React auth, profile, dashboard, plan, and file screens |
| `frontend/src/api.js` | Bearer-token API helper and response/error handling |
| `frontend/src/styles.css` | Responsive visual styling |
| `ai_engine/food_data.json` | Synthetic meal examples for deterministic local generation |
| `cloud/schema.sql` | Supabase tables, constraints, private bucket, and RLS policies |
| `docs/architecture.md` | System design, cloud concept map, and scaling explanation |
| `docs/project-report.md` | Course report draft |
| `docs/test-cases.md` | Test scenarios and honest observed status |
| `docs/proof-plan.md` | Day-by-day forward development and commit plan |
| `docs/screenshots.md` | Evidence capture checklist and filenames |
| `sample_data/`, `screenshots/` | Reserved for synthetic demo inputs and captured proof |

## Logical view

```text
Person
  ↓
React browser ── sign-up/sign-in ──> FastAPI ──> Supabase Auth (cloud mode)
  │                                    │
  │ protected REST                     ├──> token verification
  │                                    ├──> profile / plan records (Postgres)
  │                                    ├──> optional AI provider
  │                                    │        └── error/invalid output → local rules
  │                                    └──> private object storage + file metadata
  └── dashboard, saved plans, profile, image uploads/downloads
```

Local mode substitutes SQLite, a demo JWT issuer, and local files. Database records contain structured profile and meal-plan fields; object storage holds image bytes. A metadata row connects an owner's file ID to a private path.

## Data model and API ownership

- **users/auth users:** unique identity and email. Cloud credentials live in Supabase Auth, not the app table.
- **profiles:** primary key and foreign key `user_id`; one profile per user. Includes name, age, height, weight, activity level, dietary preference, goal, allergy/preference list, and creation timestamp.
- **diet_plans:** UUID `id`; foreign key `user_id`; four meal suggestions, summary, hydration note, education disclaimer, engine source, timestamp. One user has many plans.
- **user_files:** UUID `id`; foreign key `user_id`; safe filename, unique storage path, upload timestamp. The binary is outside Postgres.

Each protected request verifies an identity token. Routes use the verified subject to scope list, lookup, delete, and download operations. The caller never chooses the owner ID. Foreign object lookups return 404 to avoid disclosing existence. Supabase RLS is included as defense in depth; the server-side service role bypasses it, so API ownership checks remain mandatory.

## Concepts: where they appear and current limits

| Term | Concrete project mapping | Current implementation status |
|---|---|---|
| Cloud computing | Hosted UI/API/managed services serve users over the internet | Local simulation plus Supabase adapter; deployment needs provider setup |
| SaaS | A user opens the app and uses a finished application | Product shape demonstrated; service not yet publicly hosted |
| PaaS | Managed app host and Supabase abstract server/database operation | Deployment option, not provisioned by source code |
| IaaS | VM/network control for self-managed database/API | Not used; discuss as alternate deployment |
| REST API | FastAPI routes with JSON/multipart and HTTP status codes | Implemented |
| Client/server | React browser calls Python API | Implemented |
| Authentication | Supabase Auth hosted account or local signed demo JWT | Implemented; local is explicitly demo only |
| Authorization | User ownership filters and Supabase RLS | Implemented; test user separation |
| Cloud DB | Supabase Postgres | Adapter and schema implemented; credentials required |
| Object storage | Supabase private bucket | Adapter and bucket policy implemented; credentials required |
| Serverless functions | Could move plan generation or file events into functions | Not deployed |
| API gateway | Could protect/rate-limit the public API edge | Not configured |
| Load balancing | Multiple API replicas behind host ingress | Not configured; hosting platform concern |
| Elasticity/autoscaling | Increase/decrease API workers and DB capacity with demand | Not configured; scale plan below |
| Environment variables/secrets | `.env` locally, encrypted host variables in deployment | Local template provided; configure per host |
| Security | Validation, hashed local passwords, token checks, CORS, private storage, ownership | Baseline demo controls; needs production review |
| Logging/monitoring | Host logs, Supabase logs/metrics | Provider dashboards; no custom exporter/alerts |
| Availability/backups | Managed-service redundancy and backup plans | Provider dependent; verify selected plan's policy |
| CI/CD | `.github/workflows/ci.yml` runs API tests and frontend build on pushes/PRs | CI implemented; cloud deployment remains provider configuration |

## Request and data flow

1. User submits registration/login credentials over HTTPS in cloud, or localhost in demo mode.
2. FastAPI delegates cloud registration/login to Supabase Auth. In local mode it hashes a password with bcrypt and issues a time-limited JWT.
3. React stores the access token in browser local storage and sends it as a bearer token. (For a production web app, prefer secure, HttpOnly cookies and a reviewed CSRF strategy.)
4. FastAPI verifies the token and uses its subject as the owner ID. It validates profile fields through Pydantic.
5. Plan generation uses preferences; an optional server-side API receives a constrained structured prompt. JSON shape and field lengths are checked. Any exception or invalid response selects the local rule engine.
6. Plan is stored under the authenticated subject and returned to the UI.
7. Upload validates allowed image type, signature, and size; bytes go to an owner-specific private path and metadata to a relational table.
8. Dashboard requests retrieve only the caller's records. Download is proxied through the API after ownership lookup.

## Security basics and risks

Use HTTPS and encrypted provider storage in the cloud. Keep service role keys, AI keys, and local JWT secret out of Git. Set exact CORS origins. Apply least privilege, private buckets, database constraints, RLS, upload limits, and rate limiting. Back up records and test restores. Avoid logging passwords, tokens, uploaded content, or sensitive profile details. Add an abuse monitor, malware scan, retention policy, and account deletion workflow before real users. This project is not a clinical product.

## Scale discussion for interviews

- **10 users:** one small API instance and managed DB are sufficient for a course demo. Keep files in object storage, not API disk, for deployment durability.
- **1,000 users:** measure API latency and DB connections; use a managed pooler, cache read-heavy reference data, paginate lists, add request quotas, and horizontally scale stateless API replicas behind a load balancer. Add alerts and backup/restore drills.
- **100,000 users:** add CDN for static assets, autoscaling API/container/serverless workers, API gateway rate limits, queue-based asynchronous generation/uploads, managed DB read replicas/partitioning as measured, cache hot reads, object lifecycle policies, and regional strategy. Protect privacy, quotas, and cost budgets. No specific capacity is guaranteed without load testing.

An API gateway provides an edge for authentication/routing/quotas; a load balancer distributes requests among instances; autoscaling adjusts capacity; queues smooth bursts; managed database/storage isolate persistence from stateless API workers. These are scale design options, not features already active in this repository.
