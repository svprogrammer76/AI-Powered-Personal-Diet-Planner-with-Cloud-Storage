# Screenshot and evidence checklist

Capture only real states from your own run; hide emails, tokens, keys, and personal data. Use synthetic demo account details. Save images under `screenshots/` using the filenames below.

| Filename | Capture | Evidence it provides |
|---|---|---|
| `01-project-structure.png` | Repository tree | Modular folder layout |
| `02-cloud-architecture.png` | Architecture diagram from docs | Component/data flow |
| `03-registration.png` | Registration screen | Account creation UI |
| `04-registration-success.png` | Success state with redacted demo email | Registration works |
| `05-login.png` | Login screen | Authentication UI |
| `06-profile-form.png` | Completed synthetic profile (no real identity) | Profile inputs |
| `07-diet-preference.png` | Preference selection | Vegetarian/vegan/general options |
| `08-generate-plan.png` | Generate action | User flow to plan generation |
| `09-plan-result.png` | Generated plan and disclaimer | Output and wellness boundary |
| `10-plan-saved.png` | Saved plan list | Persistence and history |
| `11-supabase-profile-row.png` | Supabase profile table with synthetic data | Cloud database persistence |
| `12-supabase-storage-bucket.png` | Bucket settings/path with sensitive details hidden | Private object-storage setup |
| `13-image-upload.png` | File library after demo image upload | Upload and metadata |
| `14-dashboard.png` | Dashboard summary | User-specific home view |
| `15-api-response.png` | Redacted `/docs` API response | Backend contract |
| `16-backend-running.png` | Terminal showing Uvicorn startup | Local API process |
| `17-test-results.png` | Actual pytest output | Automated checks run |
| `18-cloud-deployment-dashboard.png` | Selected host status page | Hosting configuration |
| `19-live-application.png` | Deployed application in browser | Public cloud app availability |
| `20-github-commits.png` | Real commit history | Incremental work history |
| `21-github-repository.png` | Repo overview/topics | Public project presentation |
| `22-readme-preview.png` | README top and architecture section | Recruiter-facing documentation |

Before publishing screenshots: crop out browser profiles, account identifiers, API keys, service-role secrets, JWTs, and unneeded records. Never create a screenshot of a cloud database unless the setup actually ran.
