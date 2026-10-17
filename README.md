# Sarvam AI Stamp Intelligence Agent

A production-style Python project that analyzes **JPG/PNG document images** to:

1. Extract stamps, seals, and signatures.
2. Validate authenticity, placement, and document compliance.
3. Trigger workflow decisions (**APPROVED**, **REJECTED**, **FRAUD_REVIEW**) with JSON report generation and SMTP email notification.

This project includes both:
- **CLI** (`python -m stamp_agent ...`)
- **FastAPI server** (`python -m stamp_agent serve`)

> Live Sarvam API integration is fully configured via documented endpoints and job lifecycle. A mock/injectable client is also included for offline tests and demos.

**Developer:** Rashmi

---

### Features
- Sarvam Doc AI integration using official lifecycle:
  - `POST /doc-ai/v1/job/digitise`
  - `GET /doc-ai/v1/job/{job_id}/status`
  - `GET /doc-ai/v1/job/{job_id}/results`
- OpenCV extraction heuristics for:
  - colored seal/stamp regions (red/blue/green, circular/rectangular)
  - signature-like dark ink strokes
- Validation checks with pass/warn/fail + score for auditability:
  - authenticity (authority/signer/date/ink plausibility)
  - placement (signature lower page, stamp near signature)
  - compliance (required elements)
- Workflow engine mapping checks to verdict + workflow action
- SMTP email notifications (non-fatal: pipeline continues on email failure)
- JSON report writer with full findings/checks/verdict/reasons/confidence
- Mock Sarvam client for deterministic local testing
- End-to-end demo runner

---

### Architecture
```text
              +-----------------------------+
Input JPG/PNG |   CLI / FastAPI Endpoint    |
------------->|  (analyze command / POST)   |
              +--------------+--------------+
                             |
                             v
                   +---------+---------+
                   | Sarvam Doc AI     |
                   | (HTTP or Mock)    |
                   +---------+---------+
                             |
                             v
                  +----------+-----------+
                  | Extraction Engine    |
                  | OpenCV + OCR text    |
                  +----------+-----------+
                             |
                             v
                  +----------+-----------+
                  | Validation Engine    |
                  | pass/warn/fail checks|
                  +----------+-----------+
                             |
                             v
                  +----------+-----------+
                  | Workflow Decision    |
                  | APPROVED/REJECTED/   |
                  | FRAUD_REVIEW         |
                  +----------+-----------+
                             |
             +---------------+----------------+
             |                                |
             v                                v
     JSON report writer               SMTP notifier
```

---

### Project Structure
```text
stamp_intelligence_agent/
├── config/
│   └── config.yaml
├── output/
├── scripts/
│   └── run_demo.py
├── stamp_agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── demo.py
│   ├── extractor.py
│   ├── models.py
│   ├── notifier.py
│   ├── pipeline.py
│   ├── report_writer.py
│   ├── sarvam_client.py
│   ├── validator.py
│   └── workflow.py
├── tests/
│   ├── test_api.py
│   └── test_pipeline.py
├── .env.example
├── pyproject.toml
└── requirements.txt
```

---

### Setup

**Windows (PowerShell / cmd):**
```bash
cd stamp_intelligence_agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux:**
```bash
cd stamp_intelligence_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Optional: edit `config/config.yaml` to tune validation/workflow rules.

---

### Which Sarvam Model/API Is Used
This project calls Sarvam's **Doc AI "digitise" job** (document parsing/OCR), not a chat/LLM model. The full job lifecycle used is:
1. `POST /doc-ai/v1/job/digitise` — submit the document image and start the job
2. `GET /doc-ai/v1/job/{job_id}/status` — poll until the job reaches a terminal state
3. `GET /doc-ai/v1/job/{job_id}/results` — fetch the extracted text/OCR results

This logic lives in `stamp_agent/sarvam_client.py` (`SarvamHttpDocAIClient`). No model name needs to be configured — only the API key, base URL, and language.

---

### Sarvam API Key — Get It and Paste It
1. Log in to your Sarvam dashboard (https://dashboard.sarvam.ai).
2. Open the API key/subscription section.
3. Generate a new key and **copy it immediately** (you may not be able to view it again).
4. Open the `.env` file you created from `.env.example` in the project root.
5. Paste the key as the value of `SARVAM_API_KEY`, e.g.:
   ```
   SARVAM_API_KEY=your_copied_key_here
   SARVAM_USE_MOCK=false
   ```
6. Save the file. Never commit `.env` or share the key — it is read automatically at startup via `python-dotenv`.

If `SARVAM_API_KEY` is missing or `SARVAM_USE_MOCK=true`, the pipeline automatically falls back to the built-in mock client so you can still run and test the project without a live key.

---

### Environment Variables
| Variable | Required | Description |
|---|---|---|
| `SARVAM_API_KEY` | For live API | Sarvam API key used in `api-subscription-key` header |
| `SARVAM_BASE_URL` | No | Default: `https://api.sarvam.ai` |
| `SARVAM_LANGUAGE` | No | OCR language (default `en-IN`) |
| `SARVAM_TIMEOUT_SECONDS` | No | Request timeout |
| `SARVAM_POLL_INTERVAL_SECONDS` | No | Status polling interval |
| `SARVAM_MAX_WAIT_SECONDS` | No | Max polling window |
| `SARVAM_USE_MOCK` | No | `true` to force mock client |
| `SMTP_HOST` | For email | SMTP server host |
| `SMTP_PORT` | For email | SMTP server port |
| `SMTP_USER` | For email | SMTP login user / sender |
| `SMTP_PASSWORD` | For email | SMTP login password |
| `SMTP_USE_TLS` | No | `true` to enable STARTTLS |
| `NOTIFY_EMAIL` | For email | Recipient for notifications |
| `OUTPUT_DIR` | No | Directory where JSON reports are written |

---

### CLI Usage
Analyze one document image:
```bash
python -m stamp_agent analyze /path/to/document.png --config config/config.yaml --out output
```

Force mock mode even if key exists:
```bash
python -m stamp_agent analyze /path/to/document.jpg --mock
```

Run API server:
```bash
python -m stamp_agent serve --host 0.0.0.0 --port 8000
```

Run demo:
```bash
python -m stamp_agent demo --out output
# or
python scripts/run_demo.py
```

---

### FastAPI Endpoints
- `GET /health` → service health check
- `POST /analyze` → multipart upload (`file`) for JPG/PNG image; returns report JSON and report path

---

### Running Tests
```bash
pytest
```

Tests synthesize document images with Pillow and run the full mock pipeline end-to-end.

---

### Verdict → Workflow Action Mapping
| Verdict | Workflow Action |
|---|---|
| `APPROVED` | `AUTO_APPROVE` |
| `REJECTED` | `AUTO_REJECT` |
| `FRAUD_REVIEW` | `QUEUE_FRAUD_REVIEW` |

---

### Notes
- Email failures never crash analysis; they are logged and pipeline continues.
- JSON reports include input filename, timestamp, extraction findings (bboxes/confidence), validation checks, verdict, reasons, and overall confidence.
- The live Sarvam path requires a valid `SARVAM_API_KEY` and network access; without one, the mock client is used.
