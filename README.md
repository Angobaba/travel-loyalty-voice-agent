# OTA/Travel Post-Trip Loyalty Voice AI Agent 📞

**Disclaimer:** This project is a concept prototype built for exploration purposes only.  
It does not use Expedia systems, APIs, data, or member information.  
All loyalty values shown in demos are mocked.

A demo-focused outbound voice assistant built with **LiveKit**, **Vobiz SIP trunking**, **OpenAI Whisper STT**, **OpenAI / Groq LLM**, and **OpenAI TTS with Sarvam Hindi fallback**.

This project is currently configured as a **post-trip loyalty assistant** that can:
- place outbound calls
- greet travelers after a trip
- answer mock loyalty questions using a structured demo loyalty store
- identify demo members by phone number or spoken name
- use English by default and support Hindi-oriented fallback scenarios
- run as a controlled prototype for a broader **Loyalty Coach** vision

---

## What this project is

This is **not a production loyalty backend integration**.

It is currently a **voice runtime prototype** that demonstrates:

- outbound calling with LiveKit + SIP
- post-trip loyalty assistant behavior
- mock loyalty lookups through a structured loyalty data store
- bilingual direction (English default, Hindi fallback path)
- a foundation for future loyalty tools such as:
  - points lookup
  - tier status lookup
  - post-trip reward explanation
  - next-tier coaching
  - member lookup by spoken name

At the moment, the most stable use case is a **controlled demo** using mock loyalty values.

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
- English-first by default
- can support Hindi fallback flows
- avoid unnecessary escalation

Typical demo questions:
- “What are my points?”
- “What is my tier status?”
- “How far am I from the next tier?”
- “What are the Silver benefits?”
- “I’m Ankit, check my account”
- “Hindi mein baat karo”

---

## Current Tech Stack

- **Telephony / RTC:** LiveKit
- **SIP Provider:** Vobiz
- **Speech-to-Text (STT):** OpenAI Whisper
- **LLM:** OpenAI by default, optional Groq fallback
- **Text-to-Speech (TTS):** OpenAI by default, Sarvam for Hindi fallback
- **Runtime:** Python

---

## How loyalty data works

This project now uses a **mock loyalty data store** instead of hardcoded answers in prompts.

That means:
- `config.py` defines persona, prompts, and provider defaults
- `agent.py` wires the voice runtime, tools, STT, LLM, and TTS
- `loyalty_store.py` provides dynamic mock member data

The assistant does **not** invent points or tier values if the tools are working correctly.  
Instead, it retrieves:
- member profile
- points balance
- tier status
- tier benefits
- downgrade / maintenance information
- tier requirements
- member lookup by spoken name for demo scenarios

---

## Current Limitations

This prototype is still evolving.

### What works
- LiveKit worker startup
- outbound room/job dispatch
- SIP trunk setup and outbound calling
- initial greeting
- OpenAI Whisper STT
- OpenAI TTS for English-first flows
- Sarvam Hindi fallback path
- tool-based mock loyalty lookup
- member identification by phone number
- demo member lookup by spoken name

### What is not fully implemented yet
- real Expedia loyalty backend integration
- real points lookup from production systems
- real trip/reward metadata injection
- fully dynamic in-call language routing for every scenario
- production-grade observability and analytics
- production auth / identity resolution
- production-safe transfer and escalation orchestration

### Important note
If you ask questions like:
- “How many points do I have?”
- “What is my tier status?”
- “Who am I on this account?”

the assistant answers using:
1. mock values from `loyalty_store.py`, and
2. phone-number or spoken-name matching in demo mode

It is **not** reading any real loyalty system.

---

## Project Structure

```text
.
├── agent.py               # Main voice agent runtime
├── config.py              # Persona, prompts, model config, telephony config
├── loyalty_store.py       # Mock loyalty data store and lookup functions
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