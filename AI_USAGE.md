# AI Usage Report

## 1. AI tools used

- **Claude (Anthropic chat assistant):** planning the architecture, drafting code, debugging
  from error output, writing tests and documentation.
- **Google Gemini API (`google-genai` SDK):** used inside the application to convert a
  business question into a SQL query.

## 2. How I used AI during development

- Asked Claude to read the task and break it into steps: data loading, backend, analytics,
  AI integration, UI, tests, documentation.
- Used Claude to generate first drafts of `ai_engine.py`, `main.py`, `index.html` and
  `test_main.py`. I ran each file, pasted back the real output or error, and applied the fixes.
- Verified results independently instead of trusting the model: I computed the expected values
  from the CSV (total revenue 1,439,200; Monitor 473,000; South 411,200; April 240,700 vs
  May 318,500) and wrote tests that assert those numbers.
- Designed the application so the LLM only writes SQL. All numbers come from the database,
  never from the model's own arithmetic.

## 3. Problems encountered and how I debugged them

| # | Problem | How I debugged it | Fix |
|---|---|---|---|
| 1 | `test_gemini.py` hung and I had to interrupt it (`KeyboardInterrupt` inside an SSL read) | Read the traceback; it stopped inside the network call, not in my code | Added a request timeout, listed the models available to my key, and switched to the standard `generate_content` call |
| 2 | `ModuleNotFoundError: No module named 'ai_engine'` | Checked the Explorer panel | The file did not exist in the project folder yet; created it there |
| 3 | Dates stored as `dd-mm-yyyy` | Printed sample dates with a check script | Converted to ISO `YYYY-MM-DD` on load so `strftime` monthly queries work; verified the six monthly totals |
| 4 | Gemini returned 503 UNAVAILABLE and 429 RESOURCE_EXHAUSTED | Added logging of the real error type and message on every failed call | Retries across two models, one LLM call per question (answer text built from the result rows), caching of repeated questions, and a deterministic rule-based fallback |
| 5 | I assumed a Gemini model name was invalid | The API's 404 message showed which model was actually unavailable | Reordered the model list; lesson: read the actual error text before changing code |
| 6 | The "delete all records" request was rejected only because the Gemini call failed | Noticed the rejection came from the failure, not from a safety check | Added an explicit destructive-intent check, a SQL validator and a read-only database connection, with tests for each layer |
| 7 | The top-product query returned only a name, with no supporting figure | Read the generated SQL in the output | Changed the prompt to always select the computed value and return the top 3 rows |

## 4. How wrong or unsafe answers are prevented

- The model must return `supported: false` for questions the data cannot answer.
- Generated SQL must be a single SELECT with no write keywords and no comments.
- The database is opened read-only.
- Destructive requests are rejected before any model call.
- Every answer shows its SQL and supporting rows so a user can check it.

## 5. What I would improve with another day

- Replace keyword checks with a real SQL parser (for example `sqlglot`) and an allow-list of
  tables and columns.
- Add a query timeout and a row limit enforced at the database level.
- Build an evaluation set of questions with known answers to measure LLM accuracy automatically.
- Handle any month or year, follow-up questions and simple charts.
- Add continuous integration (GitHub Actions) to run the tests on every push.