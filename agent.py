"""
Post-Trip Loyalty Voice Agent
=============================
Main runtime for the outbound voice assistant.

Architecture:
- Connects to LiveKit rooms
- Places outbound SIP calls via Vobiz
- Uses OpenAI Whisper for STT, OpenAI/Groq for LLM, and OpenAI/Sarvam/Deepgram/Cartesia for TTS
- Retrieves loyalty data via tools (not hardcoded prompts)
"""

import os
import json
import certifi
import logging
from typing import Annotated, Optional

from dotenv import load_dotenv
from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions, llm
from livekit.plugins import (
    openai,
    cartesia,
    deepgram,
    noise_cancellation,
    silero,
    sarvam,
)

import config
import loyalty_store

# -----------------------------------------------------------------------------
# Environment + logging
# -----------------------------------------------------------------------------

os.environ["SSL_CERT_FILE"] = certifi.where()

load_dotenv(".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("loyalty-agent")


# -----------------------------------------------------------------------------
# Loyalty tools callable by the LLM
# -----------------------------------------------------------------------------

class LoyaltyTools(llm.ToolContext):
    """
    Tool container for retrieval-backed loyalty information.
    """

    def __init__(self, phone_number: Optional[str] = None):
        super().__init__(tools=[])
        self._phone_number = phone_number or "default"
        self._resolved_phone_number = phone_number or "default"

    def _active_phone(self) -> str:
        return self._resolved_phone_number or self._phone_number or "default"

    @llm.function_tool(
        description="Look up a member by spoken name for demo scenarios and switch the conversation to that member."
    )
    async def lookup_member_by_name(
        self,
        name: Annotated[str, "The member's name as spoken by the caller"],
    ) -> str:
        logger.info(f"Tool called: lookup_member_by_name for name {name}")
        result = loyalty_store.lookup_member_by_name(name)

        if not result.get("found"):
            members = ", ".join(result.get("available_members", []))
            return f"I couldn't find that member in the demo data. Available test members are: {members}."

        self._resolved_phone_number = result["phone_number"]
        return (
            f"I found {result['name']}. "
            f"They are currently in {result['current_tier']} tier with {result['points_balance']} points. "
            f"I'll use this account for the rest of the conversation."
        )

    @llm.function_tool(
        description="Get the member's profile including name, tier, points, recent trip, and next review timing."
    )
    async def get_member_profile(
        self,
        request: Annotated[str, "Leave empty"] = "",
    ) -> str:
        phone = self._active_phone()
        logger.info(f"Tool called: get_member_profile for {phone}")
        data = loyalty_store.get_member_profile(phone)

        trip_info = data.get("last_trip", {})
        trip_text = ""
        if trip_info:
            destination = trip_info.get("destination", "a recent destination")
            trip_text = f" Last trip destination: {destination}."

        return (
            f"Member name: {data['name']}. "
            f"Current tier: {data['current_tier']}. "
            f"Points balance: {data['points_balance']}.{trip_text} "
            f"Tier review in {data['days_until_tier_review']} days."
        )

    @llm.function_tool(
        description="Get the member's current points balance and points earned from the most recent trip."
    )
    async def get_points_balance(
        self,
        request: Annotated[str, "Leave empty"] = "",
    ) -> str:
        phone = self._active_phone()
        logger.info(f"Tool called: get_points_balance for {phone}")
        data = loyalty_store.get_points_balance(phone)

        return (
            f"Current balance: {data['points_balance']} points. "
            f"Most recent trip earned {data['last_trip_points']} points from {data['last_trip_destination']}."
        )

    @llm.function_tool(
        description="Get the member's current tier and progress to the next tier."
    )
    async def get_tier_status(
        self,
        request: Annotated[str, "Leave empty"] = "",
    ) -> str:
        phone = self._active_phone()
        logger.info(f"Tool called: get_tier_status for {phone}")
        data = loyalty_store.get_tier_status(phone)

        if data.get("at_highest_tier"):
            return (
                f"Current tier: {data['current_tier']}, which is the highest tier. "
                f"Points balance: {data['points_balance']}. "
                f"Tier review in {data['months_until_tier_review']} months."
            )

        return (
            f"Current tier: {data['current_tier']}. "
            f"Points balance: {data['points_balance']}. "
            f"You need {data['points_to_next_tier']} more points to reach {data['next_tier']}. "
            f"Tier review in {data['months_until_tier_review']} months."
        )

    @llm.function_tool(
        description="Get benefits for a specific tier: Blue, Silver, Gold, or Platinum."
    )
    async def get_tier_benefits(
        self,
        tier_name: Annotated[str, "Tier to look up: Blue, Silver, Gold, or Platinum"],
    ) -> str:
        logger.info(f"Tool called: get_tier_benefits for tier {tier_name}")
        data = loyalty_store.get_tier_benefits(tier_name)

        if "error" in data:
            return "I don't recognize that tier. Valid tiers are Blue, Silver, Gold, and Platinum."

        benefits = data.get("benefits", [])
        if not benefits:
            return f"{data['tier']} tier currently has no listed benefits in the demo data."

        if len(benefits) > 3:
            return f"{data['tier']} tier includes: {', '.join(benefits[:3])}, and more."

        return f"{data['tier']} tier includes: {', '.join(benefits)}."

    @llm.function_tool(
        description="Get downgrade risk, review timing, and the 12-month tier maintenance rule."
    )
    async def get_downgrade_info(
        self,
        request: Annotated[str, "Leave empty"] = "",
    ) -> str:
        phone = self._active_phone()
        logger.info(f"Tool called: get_downgrade_info for {phone}")
        data = loyalty_store.get_downgrade_info(phone)

        if not data.get("can_be_downgraded"):
            return (
                f"You're currently in {data['current_tier']}. "
                "This is the starting tier, so there's no downgrade risk from here. "
                "Keep earning points to move up."
            )

        return (
            f"You're currently in {data['current_tier']}. "
            f"Your tier is reviewed every {data['maintenance_period_months']} months. "
            f"Your next review is in about {data['months_until_review']} months. "
            f"If your activity falls short, you could move down to {data['previous_tier']}. "
            f"{data['advice']}"
        )

    @llm.function_tool(
        description="Explain the tier system, thresholds, and what is required to move up."
    )
    async def get_tier_requirements(
        self,
        request: Annotated[str, "Leave empty"] = "",
    ) -> str:
        logger.info("Tool called: get_tier_requirements")
        data = loyalty_store.get_tier_requirements()

        tier_lines = []
        for tier in data.get("tiers", []):
            if tier.get("next_tier"):
                tier_lines.append(
                    f"{tier['name']} needs {tier['points_to_next']} points to reach {tier['next_tier']}"
                )
            else:
                tier_lines.append(f"{tier['name']} is the highest tier")

        return f"Tier progression works like this: {'; '.join(tier_lines)}. {data['maintenance_rule']}"


# -----------------------------------------------------------------------------
# Provider builders
# -----------------------------------------------------------------------------

def _build_tts(
    config_provider: Optional[str] = None,
    config_voice: Optional[str] = None,
    response_language: Optional[str] = None,
):
    """Configure Text-to-Speech provider."""
    provider = (config_provider or os.getenv("TTS_PROVIDER", config.DEFAULT_TTS_PROVIDER)).lower()

    if response_language and response_language.lower().startswith("hi"):
        provider = "sarvam"

    if provider == "cartesia":
        logger.info("TTS: Cartesia")
        return cartesia.TTS(
            model=os.getenv("CARTESIA_TTS_MODEL", config.CARTESIA_MODEL),
            voice=os.getenv("CARTESIA_TTS_VOICE", config.CARTESIA_VOICE),
        )

    if provider == "sarvam":
        voice = os.getenv("SARVAM_VOICE", config.SARVAM_VOICE)
        language = config.SARVAM_LANGUAGE
        model = os.getenv("SARVAM_TTS_MODEL", config.SARVAM_MODEL)
        logger.info(f"TTS: Sarvam ({voice}, {language})")
        return sarvam.TTS(
            model=model,
            speaker=voice,
            target_language_code=language,
        )

    if provider == "deepgram":
        logger.info("TTS: Deepgram")
        return deepgram.TTS(
            model=os.getenv("DEEPGRAM_TTS_MODEL", config.DEEPGRAM_TTS_MODEL)
        )

    voice = config_voice or os.getenv("OPENAI_TTS_VOICE", config.DEFAULT_TTS_VOICE)
    logger.info(f"TTS: OpenAI ({voice})")
    return openai.TTS(
        model=os.getenv("OPENAI_TTS_MODEL", "tts-1"),
        voice=voice,
    )


def _build_llm(config_provider: Optional[str] = None):
    """Configure LLM provider."""
    provider = (config_provider or os.getenv("LLM_PROVIDER", config.DEFAULT_LLM_PROVIDER)).lower()

    if provider == "groq":
        logger.info("LLM: Groq")
        return openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL", config.GROQ_MODEL),
            temperature=float(os.getenv("GROQ_TEMPERATURE", str(config.GROQ_TEMPERATURE))),
        )

    logger.info("LLM: OpenAI")
    return openai.LLM(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", config.DEFAULT_LLM_MODEL),
    )


# -----------------------------------------------------------------------------
# Agent definition
# -----------------------------------------------------------------------------

class PostTripLoyaltyAgent(Agent):
    """
    Voice agent for post-trip loyalty assistance.
    """

    def __init__(self, fnc_ctx: LoyaltyTools) -> None:
        super().__init__(
            instructions=config.SYSTEM_PROMPT,
            tools=list(fnc_ctx.function_tools.values()),
        )


# -----------------------------------------------------------------------------
# Metadata helpers
# -----------------------------------------------------------------------------

def _safe_parse_json(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        logger.warning(f"Could not parse metadata JSON: {e}")
        return {}


def _find_existing_sip_participant(room) -> bool:
    return any("sip_" in p.identity for p in room.remote_participants.values())


# -----------------------------------------------------------------------------
# Main entrypoint
# -----------------------------------------------------------------------------

async def entrypoint(ctx: agents.JobContext):
    logger.info(f"Starting agent for room: {ctx.room.name}")

    job_metadata = _safe_parse_json(getattr(ctx.job, "metadata", None))
    room_metadata = _safe_parse_json(getattr(ctx.room, "metadata", None))

    config_dict = {}
    config_dict.update(job_metadata)
    config_dict.update(room_metadata)

    phone_number = room_metadata.get("phone_number") or job_metadata.get("phone_number")
    logger.info(f"Resolved phone number: {phone_number or 'not provided'}")

    loyalty_tools = LoyaltyTools(phone_number=phone_number)
    logger.info(f"Loyalty tools initialized for {phone_number or 'default member'}")

    logger.info("STT: OpenAI Whisper")
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=openai.STT(
            model=config.STT_MODEL,
            language=config.STT_LANGUAGE,
        ),
        llm=_build_llm(config_dict.get("model_provider")),
        tts=_build_tts(
            config_provider=None,
            config_voice=config_dict.get("voice_id"),
            response_language=config.DEFAULT_RESPONSE_LANGUAGE,
        ),
    )

    await session.start(
        room=ctx.room,
        agent=PostTripLoyaltyAgent(fnc_ctx=loyalty_tools),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True,
        ),
    )
    logger.info("Agent session started with loyalty tools")

    should_dial = False
    if phone_number:
        user_already_in_room = _find_existing_sip_participant(ctx.room)
        should_dial = not user_already_in_room

        if should_dial:
            logger.info("User not in room — initiating dial-out")
        else:
            logger.info("User already present in room — skipping dial-out")

    if should_dial:
        logger.info(f"Dialing {phone_number}...")
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
            logger.info("Call answered — generating initial greeting")
            await session.generate_reply(instructions=config.INITIAL_GREETING)

        except Exception as e:
            logger.error(f"Dial-out failed: {e}")
            ctx.shutdown()
    else:
        logger.info("Generating fallback greeting")
        await session.generate_reply(instructions=config.FALLBACK_GREETING)


# -----------------------------------------------------------------------------
# CLI entrypoint
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="loyalty-agent",
        )
    )