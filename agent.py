import os
import certifi

# Fix for macOS SSL Certificate errors - MUST be before other imports
os.environ["SSL_CERT_FILE"] = certifi.where()

import logging
import json

from dotenv import load_dotenv
from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    openai,
    cartesia,
    deepgram,
    noise_cancellation,
    silero,
    sarvam,
)

# Load environment variables
load_dotenv(".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

import config


def _build_tts(config_provider: str = None, config_voice: str = None):
    """Configure the Text-to-Speech provider based on env vars or dynamic config."""
    provider = (config_provider or os.getenv("TTS_PROVIDER", config.DEFAULT_TTS_PROVIDER)).lower()

    if config_voice in ["anushka", "aravind", "amartya", "dhruv"]:
        provider = "sarvam"

    if provider == "cartesia":
        logger.info("Using Cartesia TTS")
        model = os.getenv("CARTESIA_TTS_MODEL", config.CARTESIA_MODEL)
        voice = os.getenv("CARTESIA_TTS_VOICE", config.CARTESIA_VOICE)
        return cartesia.TTS(model=model, voice=voice)

    if provider == "sarvam":
        voice = config_voice or os.getenv("SARVAM_VOICE", "anushka")
        language = os.getenv("SARVAM_LANGUAGE", config.SARVAM_LANGUAGE)
        model = os.getenv("SARVAM_TTS_MODEL", config.SARVAM_MODEL)
        logger.info(f"Using Sarvam TTS (Voice: {voice}, Language: {language})")
        return sarvam.TTS(model=model, speaker=voice, target_language_code=language)

    if provider == "deepgram":
        logger.info("Using Deepgram TTS")
        model = os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en")
        return deepgram.TTS(model=model)

    logger.info(f"Using OpenAI TTS (Voice: {config_voice})")
    model = os.getenv("OPENAI_TTS_MODEL", "tts-1")
    voice = config_voice or os.getenv("OPENAI_TTS_VOICE", config.DEFAULT_TTS_VOICE)
    return openai.TTS(model=model, voice=voice)


def _build_llm(config_provider: str = None):
    """Configure the LLM provider based on config or env vars."""
    provider = (config_provider or os.getenv("LLM_PROVIDER", config.DEFAULT_LLM_PROVIDER)).lower()

    if provider == "groq":
        logger.info("Using Groq LLM")
        return openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL", config.GROQ_MODEL),
            temperature=float(os.getenv("GROQ_TEMPERATURE", str(config.GROQ_TEMPERATURE))),
        )

    logger.info("Using OpenAI LLM")
    return openai.LLM(model=config.DEFAULT_LLM_MODEL)


class OutboundAssistant(Agent):
    """
    An AI agent tailored for outbound post-trip loyalty calls.
    """

    def __init__(self, tools: list) -> None:
        super().__init__(
            instructions=config.SYSTEM_PROMPT,
            tools=tools,
        )


async def entrypoint(ctx: agents.JobContext):
    """
    Main entrypoint for the agent.

    For outbound calls:
    1. Checks for 'phone_number' in metadata.
    2. Connects to the room.
    3. Initiates the SIP call to the phone number.
    4. Waits for answer before speaking.
    """
    logger.info(f"Connecting to room: {ctx.room.name}")

    phone_number = None
    config_dict = {}

    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            config_dict = data
    except Exception:
        pass

    try:
        if ctx.room.metadata:
            data = json.loads(ctx.room.metadata)
            if data.get("phone_number"):
                phone_number = data.get("phone_number")
            config_dict.update(data)
    except Exception:
        logger.warning("No valid JSON metadata found in Room.")

    logger.info("Starting agent session with configured STT, LLM, and TTS")

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model=config.STT_MODEL, language=config.STT_LANGUAGE),
        llm=_build_llm(config_dict.get("model_provider")),
        tts=_build_tts(config_dict.get("model_provider"), config_dict.get("voice_id")),
    )

    await session.start(
        room=ctx.room,
        # Tools disabled for now to prevent unwanted transfer behavior during conversation testing
        agent=OutboundAssistant(tools=[]),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True,
        ),
    )

    logger.info("Agent session started successfully")

    should_dial = False
    if phone_number:
        user_already_here = False
        for p in ctx.room.remote_participants.values():
            if f"sip_{phone_number}" in p.identity or "sip_" in p.identity:
                user_already_here = True
                break

        if not user_already_here:
            should_dial = True
            logger.info("User not in room. Agent will initiate dial-out.")
        else:
            logger.info("User already in room (Dashboard dispatched). Only generating greeting.")

    if should_dial:
        logger.info(f"Initiating outbound SIP call to {phone_number}...")
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=config.SIP_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}",
                    wait_until_answered=True,
                )
            )
            logger.info("Call answered! Agent is now listening.")
            logger.info("Generating initial greeting")

            await session.generate_reply(
                instructions=config.INITIAL_GREETING
            )

        except Exception as e:
            logger.error(f"Failed to place outbound call: {e}")
            ctx.shutdown()
    else:
        logger.info("Generating fallback greeting")
        await session.generate_reply(instructions=config.fallback_greeting)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )