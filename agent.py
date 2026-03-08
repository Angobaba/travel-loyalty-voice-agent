"""
Post-Trip Loyalty Voice Agent
==============================
Main runtime for the outbound voice assistant.

Architecture:
- Connects to LiveKit rooms
- Places outbound SIP calls via Vobiz
- Uses Deepgram for STT, Groq/OpenAI for LLM, Sarvam for TTS
- Retrieves loyalty data via tools (not hardcoded prompts)
"""

import os
import certifi

# Fix for macOS SSL Certificate errors - MUST be before other imports
os.environ["SSL_CERT_FILE"] = certifi.where()

import logging
import json
from typing import Annotated

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

# Load environment variables
load_dotenv(".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("loyalty-agent")


# =============================================================================
# LOYALTY TOOLS (Callable by the LLM)
# =============================================================================

class LoyaltyTools(llm.FunctionContext):
    """
    Tools that let the LLM retrieve real loyalty data.
    
    The LLM calls these functions during conversation to get member-specific
    information instead of relying on hardcoded values.
    """
    
    def __init__(self, phone_number: str = None):
        super().__init__()
        # Store the phone number for member lookups
        self._phone_number = phone_number or "default"
    
    @llm.ai_callable(
        description="Get the member's profile including name, tier, and recent trip info"
    )
    def get_member_profile(self) -> str:
        """Retrieve member profile data."""
        logger.info(f"Tool called: get_member_profile for {self._phone_number}")
        data = loyalty_store.get_member_profile(self._phone_number)
        
        # Format for natural speech
        trip_info = data.get("last_trip", {})
        trip_text = ""
        if trip_info:
            trip_text = f" Your last trip was to {trip_info.get('destination', 'a recent destination')}."
        
        return (
            f"Member: {data['name']}. "
            f"Current tier: {data['current_tier']}. "
            f"Points balance: {data['points_balance']}.{trip_text} "
            f"Tier review in {data['days_until_review']} days."
        )
    
    @llm.ai_callable(
        description="Get the member's current points balance and recent earnings"
    )
    def get_points_balance(self) -> str:
        """Retrieve points balance."""
        logger.info(f"Tool called: get_points_balance for {self._phone_number}")
        data = loyalty_store.get_points_balance(self._phone_number)
        
        return (
            f"Current balance: {data['points_balance']} points. "
            f"Earned {data['last_trip_points']} points from {data['last_trip_destination']}."
        )
    
    @llm.ai_callable(
        description="Get tier status and progress toward the next tier"
    )
    def get_tier_status(self) -> str:
        """Retrieve tier status and progression info."""
        logger.info(f"Tool called: get_tier_status for {self._phone_number}")
        data = loyalty_store.get_tier_status(self._phone_number)
        
        if data["at_highest_tier"]:
            return (
                f"Current tier: {data['current_tier']} — the highest tier. "
                f"Points balance: {data['points_balance']}. "
                f"Tier review in {data['months_until_review']} months."
            )
        
        return (
            f"Current tier: {data['current_tier']}. "
            f"Points: {data['points_balance']}. "
            f"Need {data['points_to_next_tier']} more points to reach {data['next_tier']}. "
            f"Tier review in {data['months_until_review']} months."
        )
    
    @llm.ai_callable(
        description="Get benefits for a specific tier (Blue, Silver, Gold, or Platinum)"
    )
    def get_tier_benefits(
        self,
        tier_name: Annotated[str, "The tier to look up: Blue, Silver, Gold, or Platinum"]
    ) -> str:
        """Retrieve benefits for a specific tier."""
        logger.info(f"Tool called: get_tier_benefits for tier {tier_name}")
        data = loyalty_store.get_tier_benefits(tier_name)
        
        if "error" in data:
            return f"Sorry, I don't recognize that tier. Valid tiers are: Blue, Silver, Gold, and Platinum."
        
        benefits_list = data["benefits"]
        # Keep it concise for voice
        if len(benefits_list) > 3:
            top_benefits = ", ".join(benefits_list[:3])
            return f"{data['tier']} tier includes: {top_benefits}, and more."
        
        return f"{data['tier']} tier includes: {', '.join(benefits_list)}."
    
    @llm.ai_callable(
        description="Get info about tier maintenance and potential downgrade"
    )
    def get_downgrade_info(self) -> str:
        """Retrieve tier maintenance and downgrade information."""
        logger.info(f"Tool called: get_downgrade_info for {self._phone_number}")
        data = loyalty_store.get_downgrade_info(self._phone_number)
        
        if not data["can_be_downgraded"]:
            return (
                f"You're at {data['current_tier']} tier. "
                "This is the starting tier, so there's no risk of downgrade. "
                "Keep earning to move up!"
            )
        
        return (
            f"You're currently {data['current_tier']}. "
            f"Your tier is reviewed every {data['maintenance_period_months']} months. "
            f"Next review in about {data['months_until_review']} months. "
            f"If activity drops significantly, you could move to {data['previous_tier']}. "
            f"{data['advice']}"
        )
    
    @llm.ai_callable(
        description="Explain how the tier system works and what's needed to move up"
    )
    def get_tier_requirements(self) -> str:
        """Retrieve tier progression requirements."""
        logger.info("Tool called: get_tier_requirements")
        data = loyalty_store.get_tier_requirements()
        
        tiers_summary = []
        for tier in data["tiers"]:
            if tier["next_tier"]:
                tiers_summary.append(
                    f"{tier['name']} needs {tier['points_to_next']} points to reach {tier['next_tier']}"
                )
            else:
                tiers_summary.append(f"{tier['name']} is the highest tier")
        
        return (
            f"Tier progression: {'. '.join(tiers_summary)}. "
            f"{data['maintenance_rule']}"
        )


# =============================================================================
# TTS / LLM BUILDERS
# =============================================================================

def _build_tts(config_provider: str = None, config_voice: str = None):
    """Configure Text-to-Speech provider."""
    provider = (config_provider or os.getenv("TTS_PROVIDER", config.DEFAULT_TTS_PROVIDER)).lower()
    
    # Auto-detect Sarvam voices
    sarvam_voices = ["anushka", "aravind", "amartya", "dhruv"]
    if config_voice and config_voice.lower() in sarvam_voices:
        provider = "sarvam"
    
    if provider == "cartesia":
        logger.info("TTS: Cartesia")
        return cartesia.TTS(
            model=os.getenv("CARTESIA_TTS_MODEL", config.CARTESIA_MODEL),
            voice=os.getenv("CARTESIA_TTS_VOICE", config.CARTESIA_VOICE),
        )
    
    if provider == "sarvam":
        voice = config_voice or os.getenv("SARVAM_VOICE", config.DEFAULT_TTS_VOICE)
        language = os.getenv("SARVAM_LANGUAGE", config.SARVAM_LANGUAGE)
        logger.info(f"TTS: Sarvam ({voice}, {language})")
        return sarvam.TTS(
            model=os.getenv("SARVAM_TTS_MODEL", config.SARVAM_MODEL),
            speaker=voice,
            target_language_code=language,
        )
    
    if provider == "deepgram":
        logger.info("TTS: Deepgram")
        return deepgram.TTS(model=os.getenv("DEEPGRAM_TTS_MODEL", config.DEEPGRAM_TTS_MODEL))
    
    # Default to OpenAI
    voice = config_voice or os.getenv("OPENAI_TTS_VOICE", "alloy")
    logger.info(f"TTS: OpenAI ({voice})")
    return openai.TTS(
        model=os.getenv("OPENAI_TTS_MODEL", "tts-1"),
        voice=voice,
    )


def _build_llm(config_provider: str = None):
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
    return openai.LLM(model=config.DEFAULT_LLM_MODEL)


# =============================================================================
# AGENT DEFINITION
# =============================================================================

class PostTripLoyaltyAgent(Agent):
    """
    Voice agent for post-trip loyalty assistance.
    
    Uses tools to retrieve actual member data instead of hardcoded values.
    """
    
    def __init__(self, fnc_ctx: LoyaltyTools) -> None:
        super().__init__(
            instructions=config.SYSTEM_PROMPT,
            fnc_ctx=fnc_ctx,
        )


# =============================================================================
# ENTRYPOINT
# =============================================================================

async def entrypoint(ctx: agents.JobContext):
    """
    Main entrypoint for the voice agent.
    
    Flow:
    1. Parse job/room metadata for phone number and config
    2. Initialize STT, LLM, TTS
    3. Create agent with loyalty tools bound to this member
    4. Place outbound call if needed
    5. Generate greeting
    """
    logger.info(f"Starting agent for room: {ctx.room.name}")
    
    # Extract configuration from metadata
    phone_number = None
    config_dict = {}
    
    # Try job metadata first
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            config_dict = data
            logger.info(f"Job metadata: phone={phone_number}")
    except Exception as e:
        logger.warning(f"Could not parse job metadata: {e}")
    
    # Room metadata can override
    try:
        if ctx.room.metadata:
            data = json.loads(ctx.room.metadata)
            if data.get("phone_number"):
                phone_number = data.get("phone_number")
            config_dict.update(data)
            logger.info(f"Room metadata applied: phone={phone_number}")
    except Exception as e:
        logger.warning(f"Could not parse room metadata: {e}")
    
    # Create loyalty tools bound to this member's phone number
    loyalty_tools = LoyaltyTools(phone_number=phone_number)
    logger.info(f"Loyalty tools initialized for: {phone_number or 'default member'}")
    
    # Build the agent session
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model=config.STT_MODEL, language=config.STT_LANGUAGE),
        llm=_build_llm(config_dict.get("model_provider")),
        tts=_build_tts(config_dict.get("model_provider"), config_dict.get("voice_id")),
    )
    
    # Start the session with tools enabled
    await session.start(
        room=ctx.room,
        agent=PostTripLoyaltyAgent(fnc_ctx=loyalty_tools),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True,
        ),
    )
    logger.info("Agent session started with loyalty tools")
    
    # Determine if we need to dial out
    should_dial = False
    if phone_number:
        # Check if user is already in the room (dashboard-dispatched)
        user_in_room = any(
            "sip_" in p.identity 
            for p in ctx.room.remote_participants.values()
        )
        should_dial = not user_in_room
        
        if should_dial:
            logger.info("User not in room — initiating dial-out")
        else:
            logger.info("User already in room — skipping dial-out")
    
    # Place outbound call if needed
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
            logger.info("Call answered — generating greeting")
            await session.generate_reply(instructions=config.INITIAL_GREETING)
            
        except Exception as e:
            logger.error(f"Dial-out failed: {e}")
            ctx.shutdown()
    else:
        # Dashboard or test scenario — just greet
        logger.info("Generating fallback greeting")
        await session.generate_reply(instructions=config.FALLBACK_GREETING)


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="loyalty-agent",
        )
    )
