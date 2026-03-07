# OTA/Travel Post-Trip Loyalty Voice Agent 📞

Disclaimer: This project is a concept prototype built for exploration purposes only. 
It does not use Expedia systems, APIs, data, or member information. 
All loyalty values shown in demos are mocked.

A demo-focused outbound voice assistant built with **LiveKit**, **Vobiz SIP trunking**, **Deepgram STT**, **Groq LLM**, and **Sarvam TTS**.

This project is currently configured as a **post-trip loyalty assistant** that can:
- place outbound calls
- greet travelers after a trip
- answer simple post-trip loyalty questions
- switch to Hindi for demo scenarios
- run as a controlled prototype for a broader **Loyalty Coach** vision

---

## What this project is

This is **not yet a production loyalty backend integration**.

It is currently a **voice runtime prototype** that demonstrates:

- outbound calling with LiveKit + SIP
- post-trip loyalty assistant behavior
- bilingual experience direction (English + Hindi)
- a foundation for future loyalty tools such as:
  - points lookup
  - tier status lookup
  - post-trip reward explanation
  - next-tier coaching

At the moment, the most stable use case is a **scripted demo** using mock loyalty values.

---

## Current Demo Persona

The assistant is configured as:

**OTA/Travel Post-Trip Loyalty Assistant**

Behavior goals:
- concise
- factual
- loyalty-grounded
- read-only first
- helpful and calm
- switch to Hindi if asked
- avoid unnecessary escalation

Typical demo questions:
- “Hindi mein baat karo”
- “Mere points kitne hain?”
- “Mera tier status kya hai?”
- “Next tier ke liye aur kitna chahiye?”

---

## Current Tech Stack

- **Telephony / RTC:** LiveKit
- **SIP Provider:** Vobiz
- **Speech-to-Text (STT):** Deepgram
- **LLM:** Groq (`llama-3.3-70b-versatile`)
- **Text-to-Speech (TTS):** Sarvam (`bulbul:v2`)
- **Runtime:** Python

---

## Current Limitations

This prototype is still evolving. Right now:

### What works
- LiveKit worker startup
- outbound room/job dispatch
- SIP trunk creation
- outbound calling
- initial greeting
- Sarvam Hindi-capable voice output
- controlled conversational demo flows

### What is not fully implemented yet
- real Expedia loyalty backend integration
- real points lookup
- real tier lookup
- real trip/reward metadata injection
- reliable free-form Hindi switching in every scenario
- production-grade turn detection and conversation observability

### Important note
If you ask questions like:
- “How many points do I have?”
- “What is my tier status?”

the assistant can only answer correctly if:
1. you have added real loyalty tools, or
2. you are using demo/mock values in the prompt.

---

## Project Structure

```text
.
├── agent.py               # Main voice agent runtime
├── config.py              # Persona, prompts, model config, telephony config
├── make_call.py           # Dispatches outbound call jobs
├── create_trunk.py        # Creates LiveKit outbound SIP trunk
├── list_trunks.py         # Lists available LiveKit SIP trunks
├── setup_trunk.py         # Helper script for SIP trunk setup
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── dashboard/             # Optional dashboard / UI pieces

A production-ready voice agent capable of making outbound calls using **LiveKit**, **Deepgram**, and **Groq (Llama 3.3)**.  
Designed for reliability, speed, and ease of deployment.

## 🚀 Features
- **Ultra-Fast LLM**: Uses **Groq** running `llama-3.3-70b-versatile` for near-instant responses.
- **High-Quality Audio**: Uses **Deepgram** for both Speech-to-Text (STT) and Text-to-Speech (TTS).
- **SIP Trunking**: Integrated with **Vobiz** for PSTN connectivity.
- **Robust Configuration**: Centralized `config.py` for easy customization of prompts, models, and voices.

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+ (Recommended: 3.10.13)
- A [LiveKit Cloud](https://cloud.livekit.io/) account
- A [Deepgram](https://deepgram.com/) API Key
- A [Groq](https://groq.com/) API Key
- A SIP Provider (e.g., Vobiz)

### 2. Clone & Install
```bash
# Clone the repository
git clone <your-repo-url>
cd LiveKit-Vobiz-Outbound-main

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment
Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
nano .env  # Or open in your editor
```
**Required Variables:**
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_SECRET`
- `DEEPGRAM_API_KEY`
- `GROQ_API_KEY`
- `VOBIZ_SIP_*` variables (for outbound calls)

---

## 🏃‍♂️ Usage

### 1. Start the Agent
This runs the agent process which listens for room connections.
```bash
python agent.py start
```

### 2. Make an Outbound Call
In a **new terminal window** (ensure `venv` is active), run:
```bash
python make_call.py --to +91XXXXXXXXXX
```
*Note: The number must include the country code (e.g., +1 or +91).*

---

## 🔧 Troubleshooting Guide

### ❌ Error: `model_decommissioned` (Groq/Llama)
**Cause:** The configured LLM model is no longer supported by Groq.  
**Fix:**
1. Open `config.py`.
2. Update `GROQ_MODEL` to a supported model (e.g., `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`).
3. **Restart `agent.py`** to apply changes.

### ❌ Error: `404 Not Found` (SIP Trunk)
**Cause:** The `SIP_TRUNK_ID` in `.env` is incorrect or doesn't exist in your LiveKit project.  
**Fix:**
1. Run `python list_trunks.py` to see available trunks.
2. If none exist, run `python create_trunk.py` to create one.
3. Update `.env` with the correct ID.

### ❌ Error: `Address already in use` (Port 8081)
**Cause:** Another instance of `agent.py` is already running.  
**Fix:**
1. Find the process: `lsof -i :8081`
2. Kill it: `kill -9 <PID>` or `pkill -f "python agent.py"`

### ❌ Error: `No module named 'certifi'` or other imports
**Cause:** Dependencies are missing.  
**Fix:**
1. Ensure your virtual environment is active (`source venv/bin/activate`).
2. Run `pip install -r requirements.txt`.

### ❌ Call Connects but No Audio
**Cause:** TTS (Text-to-Speech) failure or WebSocket issues.  
**Fix:**
1. Check terminal logs for `APIStatusError`.
2. If using OpenAI TTS, ensure you have OpenAI credits.
3. Recommended: Switch to Deepgram TTS (set `TTS_PROVIDER=deepgram` in `.env`).

---


