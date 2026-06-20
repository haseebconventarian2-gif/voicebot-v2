<div align="center">

# Azure Voice Bot v2

FastAPI voice bot using Azure OpenAI speech and chat APIs with ACS WhatsApp Event Grid integration.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white&style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Reference%20Implementation-6366F1?style=for-the-badge)

[Story](#-the-story) · [Features](#-features) · [Setup](#-getting-started) · [Configuration](#-configuration)

</div>

---

## 🎯 Overview

FastAPI voice bot using Azure OpenAI speech and chat APIs with ACS WhatsApp Event Grid integration.

## 📖 The Story

Voicebot v2 explores a more modular route to the same conversational goal. The project combines Azure OpenAI speech and chat APIs with LangChain and FAISS, retaining local retrieval while adding Azure Communication Services event handling.

A customer message can arrive as text or audio. The API normalizes the input, obtains relevant context, generates an answer, and returns text or synthesized media. Event Grid routes extend that loop to ACS-backed WhatsApp workflows.

This iteration is useful as an integration laboratory. Its future direction is to remove duplicate Python and Node responsibilities, formalize event schemas, and add contract tests for every external service boundary.

## ✨ Features

- Text conversation endpoint
- Speech-to-text and text-to-speech
- Conversational AI responses
- WhatsApp and ACS integration

## 🧰 Tech Stack

| Technology | Purpose |
| --- | --- |
| **Python** | Primary programming language |
| **FastAPI** | API and web server |
| **Azure OpenAI** | Chat, transcription, and speech services |
| **LangChain** | RAG orchestration and text processing |
| **FAISS** | Vector similarity search |

## 🚀 Getting Started

```bash
git clone https://github.com/haseebconventarian2-gif/voicebot-v2.git
cd voicebot-v2
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuration

Configure Azure OpenAI deployments and any messaging-channel credentials in `.env`.

> Store credentials in `.env` and never commit secrets.

## ▶️ Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📌 Project Status

This is a learning and reference implementation. Review security, validation, monitoring, and deployment settings before production use.

## 🧩 Detailed Code Reference

**Runtime flow:** `Text/audio -> STT -> retrieval -> LLM -> TTS/text -> channel reply`

### 📁 Repository Map

- `.github/` - supporting package or resources
- `__pycache__/` - supporting package or resources
- `api/` - supporting package or resources
- `app/` - supporting package or resources
- `bank.json` - project file
- `bankislami.html` - project file
- `bankislami_voice_config.json` - project file
- `docs/` - supporting package or resources
- `faiss_index/` - supporting package or resources
- `fastapi_app.py` - project file
- `main.py` - project file
- `package.json` - project file
- `package-lock.json` - project file
- `public/` - supporting package or resources
- `rag_pipeline.py` - project file
- `README.md` - project file
- `requirements.txt` - project file
- `test.wav` - project file
- `vector_database.py` - project file

## 🧪 Validation Checklist

1. Install dependencies in a clean virtual environment.
2. Configure only the environment variables needed by enabled integrations.
3. Start the documented entry point and test its health or root route.
4. Exercise successful and invalid requests.
5. Confirm secrets, private datasets, indexes, and model artifacts are ignored.

## 🔒 Production Checklist

- Use managed secret storage.
- Add authentication, authorization, rate limiting, and request-size limits.
- Add automated tests, structured logs, monitoring, and health checks.
- Pin and audit dependencies.
- Define retention and privacy controls for audio and customer data.

> This README reflects the current codebase. External AI, telephony, and messaging features require their respective accounts, assets, and approvals.




## 🛠 Troubleshooting

<details>
<summary><strong>The application does not start</strong></summary>

Confirm the virtual environment is active, install `requirements.txt`, and check that every required environment variable is defined.
</details>

<details>
<summary><strong>An AI or messaging service cannot be reached</strong></summary>

Verify the endpoint, credentials, deployment names, network access, and external service status. Restart the application after changing `.env`.
</details>

<details>
<summary><strong>A model, index, or artifact is missing</strong></summary>

Run the repository's documented build or training step and confirm that generated files are stored at the paths expected by the code.
</details>
