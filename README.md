# Plagiarism Intelligence System
## AI-Driven Academic Integrity Platform — IBM Watsonx.ai + Granite

---

### Overview

A full-stack web application that analyses student assignment submissions for:
- **Exact / verbatim plagiarism** (n-gram overlap)
- **Paraphrase / mosaic plagiarism** (cosine similarity)
- **AI-generated content** (heuristic + Watsonx.ai Granite analysis)
- **Writing-style shifts** (baseline cosine comparison)

Faculty get a clean, responsive dashboard with risk scores, highlighted suspicious passages, explainable AI summaries, and a decision form to confirm, dismiss, or escalate flags.

---

### Quick Start

#### 1. Clone / download the project

```
cd "Ai assignment checker - AICTE IBM"
```

#### 2. Create a Python virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

#### 3. Install dependencies

```bash
pip install -r requirements.txt
```

#### 4. Configure IBM Watsonx.ai credentials

Copy the example file and fill in your real values:

```bash
cp .env.example .env
```

Edit `.env`:

```
IBM_API_KEY       = <your IBM Cloud API key>
IBM_WATSONX_URL   = https://us-south.ml.cloud.ibm.com
IBM_PROJECT_ID    = <your Watsonx.ai project ID>
GRANITE_MODEL_ID  = ibm/granite-13b-instruct-v2
FLASK_SECRET_KEY  = <a long random string>
```

> **Where to find these values:**
> 1. Log in to [IBM Cloud](https://cloud.ibm.com)
> 2. Go to **Manage → Access (IAM) → API Keys** to create your API key
> 3. Open [IBM Watsonx.ai](https://dataplatform.cloud.ibm.com)
> 4. Create or open a project — the **Project ID** is in the project Settings tab
> 5. The **Watsonx URL** depends on your region (us-south, eu-de, jp-tok, etc.)

#### 5. Run the application

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

### Project Structure

```
.
├── app.py                  ← Flask routes / entry point
├── analyzer.py             ← Plagiarism analysis engine (Watsonx.ai + heuristics)
├── config.py               ← ✏️  ALL tunable settings (thresholds, instructions, etc.)
├── requirements.txt
├── .env.example            ← Template for credentials
│
├── utils/
│   ├── text_extractor.py   ← PDF / DOCX / TXT text extraction
│   ├── similarity.py       ← Local similarity metrics (n-gram, cosine, AI heuristic)
│   └── storage.py          ← JSON-based data persistence
│
├── templates/
│   ├── base.html           ← Shared layout + sidebar
│   ├── dashboard.html      ← Faculty dashboard
│   ├── submit.html         ← Assignment upload form
│   ├── report.html         ← Full plagiarism report + decision form
│   ├── students.html       ← Student management
│   └── error.html
│
├── data/                   ← Auto-created; stores students/submissions/reports JSON
├── uploads/                ← Auto-created; stores uploaded files
└── reports/                ← Auto-created; reserved for exported report files
```

---

### Customising Academic Policies

Open **`config.py`** — this is the single file you edit to change behaviour:

| Section | What to change |
|---------|---------------|
| `RISK_THRESHOLDS` | Percentages for LOW / MODERATE / HIGH / CRITICAL |
| `ANALYSIS_INSTRUCTIONS` | AI prompt — tone, language, domain rules, thresholds |
| `INSTITUTION_NAME` | Your university / college name |
| `INSTITUTION_POLICY` | Policy document reference |
| `SUPPORTED_COURSES` | List of courses shown in dropdowns |
| `MODEL_PARAMS` | Token limits, temperature, decoding method |
| `GRANITE_MODEL_ID` | Switch between Granite model variants |

---

### How the Analysis Pipeline Works

```
1. File Upload  →  Text Extraction (PDF/DOCX/TXT)
        ↓
2. Local Metrics (offline, fast)
   • Exact n-gram overlap vs. other submissions in same course
   • Cosine similarity (TF bag-of-words)
   • AI-likelihood heuristic (sentence uniformity + lexical diversity + phrase detection)
   • Style-shift score vs. student's past submissions
        ↓
3. Watsonx.ai Granite Prompt
   • System prompt + ANALYSIS_INSTRUCTIONS (from config.py)
   • Pre-computed metrics embedded in prompt as evidence
   • Submitted text (up to 6 000 chars)
   • Reference texts (up to 3 peers, 4 000 chars combined)
        ↓
4. JSON Report Assembly
   • AI risk score + level
   • Suspicious passages with type + reason
   • AI-generation assessment
   • Style-shift assessment
   • Faculty recommendations
   • Corrective actions for student
        ↓
5. Stored in data/reports.json  →  Displayed in dashboard
```

---

### Supported File Types

| Format | Notes |
|--------|-------|
| `.pdf`  | Text-based PDFs (scanned PDFs require OCR pre-processing) |
| `.docx` | Standard Word documents |
| `.txt`  | Plain text, UTF-8 / Latin-1 |

---

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/reports` | List all reports (JSON) |
| GET | `/api/report/<id>` | Single report detail (JSON) |

---

### Deploying to IBM Cloud (Code Engine)

1. **Containerise:**

```bash
# Create Procfile
echo "web: python app.py" > Procfile
```

2. **Push to IBM Cloud Code Engine:**

```bash
ibmcloud login
ibmcloud ce project select --name plagiarism-checker
ibmcloud ce app create \
  --name plagiarism-intelligence \
  --image <your-registry>/plagiarism-intelligence:latest \
  --env IBM_API_KEY=<key> \
  --env IBM_PROJECT_ID=<id> \
  --env IBM_WATSONX_URL=https://us-south.ml.cloud.ibm.com \
  --env GRANITE_MODEL_ID=ibm/granite-13b-instruct-v2 \
  --env FLASK_SECRET_KEY=<random>
```

3. **Or deploy to IBM Cloud Foundry:**

```bash
ibmcloud cf push plagiarism-intelligence \
  --no-start
ibmcloud cf set-env plagiarism-intelligence IBM_API_KEY <key>
ibmcloud cf start plagiarism-intelligence
```

---

### Demo / Offline Mode

If `IBM_API_KEY`, `IBM_PROJECT_ID`, or `IBM_WATSONX_URL` are blank in `.env`,
the system runs in **Demo Mode** using local heuristics only. Reports will be
labelled `[DEMO MODE]` in the executive summary. All UI features remain functional.

---

### Privacy & Security Notes

- Never commit `.env` to source control (`.gitignore` is pre-configured)
- Uploaded files are stored locally in `uploads/` — delete or encrypt in production
- Submission text is capped at 50 000 characters in storage
- API keys are loaded exclusively from environment variables

---

### License

MIT — see LICENSE file.
