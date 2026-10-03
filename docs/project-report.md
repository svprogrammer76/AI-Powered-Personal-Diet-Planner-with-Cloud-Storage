# Project report — AI-Powered Personal Diet Planner with Cloud Storage

## Abstract

This course project demonstrates a cloud-shaped full-stack application for producing educational meal-plan examples and saving them per account. React, FastAPI, a deterministic recommendation engine, SQLite/local files, and an optional Supabase implementation illustrate web APIs, authentication, relational persistence, and object storage. The report and software use synthetic/demo data and make no clinical claims.

## Introduction and problem statement

Meal inspirations are often spread across notes and devices. A centralized account can make saved examples accessible from multiple devices. The learning challenge is to connect a responsive user interface, identity, API, structured data, and file storage while enforcing owner access.

## Objectives

Implement register/login/logout, user profile management, meal suggestions by preference and general goal, saved history, optional file upload/download, fallback recommendation generation, clear setup/deployment documentation, and automated tests for core ownership behavior.

## Existing and proposed systems

An existing manual approach stores meal notes locally and may not synchronize. The proposed demonstration provides a browser dashboard and API backed locally by SQLite/files or in cloud by Supabase Auth, Postgres, and private object storage. This is a software architecture comparison, not a measured clinical or commercial comparison.

## Cloud concepts and technology stack

The repository implements a React client, FastAPI REST service, Pydantic request validation, local SQLite/file mode, Supabase service adapter/schema, and rule-based examples with optional AI API. Hosted static frontend and backend services represent PaaS; Supabase offers managed identity/data/storage. Serverless execution, gateway, load balancing, autoscaling, and IaaS are extension/design concepts rather than configured resources.

## System architecture and data flow

Browser → FastAPI → verified identity → profile and plan persistence → dashboard. Optional generation calls the server-side model with structured preferences; failure falls back to local rules. Image bytes live in object storage and relational metadata connects each file to its owner. Local mode substitutes a demo token and SQLite/files.

## Database design

Auth user identity is the owner key. `profiles.user_id` has a one-to-one relationship to a user. `diet_plans.user_id` and `user_files.user_id` are one-to-many relationships. Plan rows hold meal strings and notes; file records hold an object path, not file bytes. Foreign keys, accepted-value checks, and owner policies are in `cloud/schema.sql`.

## Cloud storage design

Supabase bucket `user-files` is private and limited to image MIME types and 5 MiB. Paths begin with the authenticated user UUID. The API checks ownership before a download or deletion. Local mode writes the same logical path under ignored `backend/data/uploads`.

## AI recommendation logic

The deterministic engine selects examples from `ai_engine/food_data.json`, based on dietary preference and broad goal. Optional AI generation receives age band/value, activity, preference, goal, and foods to avoid; the prompt asks for five bounded text fields and forbids diagnosis, treatment, and prescribed calories. The API validates the returned shape/length and falls back when the key is absent, request fails, or response is malformed. The menu and allergy filter are simple examples and are not reliable safety mechanisms.

## Authentication, authorization, and API design

Cloud mode uses Supabase Auth; local mode hashes passwords and issues an expiring JWT for demonstration. The API derives owner identity from a verified token. Protected routes cover profile, plan, and file operations. Other users' identifiers are not accepted as ownership claims. Cloud app credentials remain on the server. API paths and common status codes are listed in the README.

## Implementation and testing

The implementation is organized by UI, API/schema, storage adapter, deterministic engine, and SQL setup. Automated tests exercise registration, duplicate registration, login failures, unauthenticated access, profile save, preference-aware plan creation, owner isolation, upload validation, and download behavior. Record actual local test output and deployed smoke-test outcomes before presenting results.

## Cloud deployment

Approach A uses a static host, a Python app host, and Supabase. Approach B maps the system to an AWS, Azure, or GCP managed architecture. Provider selection, service quotas, billing, account setup, and deployment credentials are external prerequisites. Local mode requires no cloud account.

## Security and scalability

Baseline controls include Pydantic validation, password hashing in local demo mode, expiring token, ownership checks, upload MIME/signature/size checks, private object paths, CORS configuration, environment variables, SQL constraints, and Supabase RLS. Hosted deployments need HTTPS, rate limits, secure cookies, monitoring, backup/restore testing, and secret rotation. At larger scale use stateless API replicas, load balancing, pooling, CDN, cache, queues, autoscaling, and managed database scaling after measurement.

## Results, advantages, and limitations

Expected result is a locally executable application and an optional cloud adapter demonstrating account-specific structured records and files. Advantages include modular code, no required paid AI, local portability, and an explicit fallback. Limitations include unverified provider deployment, no active CI/CD/monitoring integration, basic demo auth in local mode, simple food rules, non-clinical content, and no guarantee that an allergy text filter detects all unsafe ingredients.

## Future scope and conclusion

Potential work includes provider-specific deployment automation, secure cookie sessions, rate limiting, audit events, deletion/export tools, image scanning, provider integration tests, observability, accessibility review, and a nutritionist-reviewed dataset if the scope ever becomes a real product. The project demonstrates how cloud identity, API services, relational data, and object storage fit together while distinguishing working code from deployment concepts.

## Disclaimer

The generated outputs are general educational wellness examples only. They are not medical/clinical nutrition advice and must not be used for diagnosis, treatment, or prescribed dietary management. Use synthetic/demo data.
