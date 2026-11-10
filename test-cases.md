# Test case matrix

Automated API suite result: **9 passed** on the local SQLite/filesystem path. `Pass` means that scenario was exercised by an automated test. `Not run` means it still needs a manual test or an added test before presenting it as verified. Cloud integration requires Supabase project credentials and was not run here.

| ID | Scenario | Input | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| T01 | New registration | Valid synthetic email and 8+ character password | Account created and token returned | 201 and bearer token | Pass |
| T02 | Existing email registration | Reuse the same email | Conflict response, no duplicate account | 409 | Pass |
| T03 | Valid login | Registered email and password | Token returned | 200 | Pass |
| T04 | Invalid login | Wrong password | Generic unauthorized response | 401 | Pass |
| T05 | Unauthorized protected request | No bearer token | Request rejected | 401 | Pass |
| T06 | Profile creation | Valid age, height, weight, preference, goal | Profile saved for owner | 200 and stored profile | Pass |
| T07 | Diet-plan generation | Existing profile | Four meals, notes, disclaimer, persisted plan | 201 and saved plan | Pass |
| T08 | Vegetarian preference | Vegetarian profile | Vegetarian examples selected | Generator path exercised | Pass |
| T09 | Vegan preference | Vegan profile | Vegan examples selected | Vegan dinner includes tofu/lentils in test | Pass |
| T10 | Different goal | Fitness or weight-management selection | Goal-appropriate general note | Not exercised in current suite | Not run |
| T11 | AI API failure | Configure model key and simulate timeout/bad JSON | Rule-based fallback returned without exposing error | External AI path not exercised | Not run |
| T12 | Rule-based fallback | No AI key configured | Local rule engine responds | `source=rule-based` | Pass |
| T13 | Save plan | Generate for authenticated user | Plan saved under owner | Included in generation test | Pass |
| T14 | Retrieve plan | List plans as plan owner | Owner sees saved plan | Owner list returns saved plan | Pass |
| T15 | Upload file | PNG with matching content signature, under 5 MB | Private owner path and metadata returned | 201 | Pass |
| T16 | Retrieve file | Download file as owner | Original bytes returned | Bytes match uploaded payload | Pass |
| T17 | Invalid file | Text file, unsupported type, or fake signature | Upload rejected | Unsupported type returns 415 | Pass |
| T18 | User A vs User B | B requests A's plan/file ID | Not found; no record disclosed | Plan and file requests return 404 | Pass |
| T19 | Logout | Click Log out, then revisit protected view | Local token removed; protected API rejects request | UI clears token; manual relogin flow not exercised | Not run |
| T20 | Database/service failure | Simulated store exception | Safe temporary error without provider details | 503 generic response | Pass |
| T21 | Supabase cloud failure | Invalid credentials/network/table unavailable | Safe error; no secrets returned; user can retry | Requires cloud project and credentials | Not run |

Add actual outputs and date after each manual case. Do not change `Not run` to `Pass` based on expected behavior alone.
