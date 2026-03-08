"""
Loyalty Data Store
==================
Mock loyalty data layer for the post-trip voice agent.

This module provides:
- Tier definitions and thresholds
- Member profile data (mock)
- Retrieval functions exposed as agent tools

Architecture notes:
- Currently uses in-memory dictionaries for prototyping
- Designed to be swapped with real APIs later
- Each function returns structured data the LLM can use naturally
"""

from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger("loyalty-store")

# =============================================================================
# TIER CONFIGURATION
# =============================================================================

TIER_CONFIG = {
    "Blue": {
        "order": 0,
        "min_points": 0,
        "next_tier": "Silver",
        "points_to_next": 10,
        "benefits": [
            "Member-only rates on select hotels",
            "Earn 1 point per dollar spent",
            "Access to member deals and flash sales",
        ],
    },
    "Silver": {
        "order": 1,
        "min_points": 10,
        "next_tier": "Gold",
        "points_to_next": 15,
        "benefits": [
            "All Blue benefits",
            "10% bonus points on bookings",
            "Priority customer support",
            "Free room upgrades when available",
        ],
    },
    "Gold": {
        "order": 2,
        "min_points": 25,
        "next_tier": "Platinum",
        "points_to_next": 20,
        "benefits": [
            "All Silver benefits",
            "25% bonus points on bookings",
            "Complimentary breakfast at select hotels",
            "Late checkout until 2pm",
            "Dedicated Gold support line",
        ],
    },
    "Platinum": {
        "order": 3,
        "min_points": 45,
        "next_tier": None,
        "points_to_next": None,
        "benefits": [
            "All Gold benefits",
            "50% bonus points on bookings",
            "Complimentary suite upgrades when available",
            "Airport lounge access",
            "Dedicated Platinum concierge",
            "No blackout dates on reward bookings",
        ],
    },
}

# Tier maintenance: must maintain for 12 months or face downgrade
TIER_MAINTENANCE_MONTHS = 12


# =============================================================================
# MOCK MEMBER DATABASE
# =============================================================================

# Simulates member profiles. In production, this would be an API call.
# Key = phone number (used for lookup during calls)
MOCK_MEMBERS = {
    "+919876543210": {
        "member_id": "EXP-001",
        "name": "Rahul Sharma",
        "current_tier": "Silver",
        "points_balance": 18,
        "tier_achieved_date": datetime.now() - timedelta(days=200),
        "last_trip": {
            "destination": "Goa",
            "checkout_date": datetime.now() - timedelta(days=3),
            "points_earned": 8,
            "status": "completed",
        },
    },
    "+919123456789": {
        "member_id": "EXP-002",
        "name": "Priya Patel",
        "current_tier": "Gold",
        "points_balance": 32,
        "tier_achieved_date": datetime.now() - timedelta(days=45),
        "last_trip": {
            "destination": "Jaipur",
            "checkout_date": datetime.now() - timedelta(days=1),
            "points_earned": 12,
            "status": "completed",
        },
    },
    "+911234567890": {
        "member_id": "EXP-003",
        "name": "Amit Kumar",
        "current_tier": "Blue",
        "points_balance": 4,
        "tier_achieved_date": datetime.now() - timedelta(days=30),
        "last_trip": {
            "destination": "Mumbai",
            "checkout_date": datetime.now() - timedelta(days=7),
            "points_earned": 4,
            "status": "completed",
        },
    },
    # Default demo member (used when phone number not found)
    "default": {
        "member_id": "EXP-DEMO",
        "name": "Valued Member",
        "current_tier": "Silver",
        "points_balance": 12,
        "tier_achieved_date": datetime.now() - timedelta(days=120),
        "last_trip": {
            "destination": "Delhi",
            "checkout_date": datetime.now() - timedelta(days=2),
            "points_earned": 5,
            "status": "completed",
        },
    },
}


# =============================================================================
# RETRIEVAL FUNCTIONS (These become agent tools)
# =============================================================================


def get_member_profile(phone_number: str) -> dict:
    """
    Retrieve member profile by phone number.
    
    Returns member data including:
    - Name
    - Current tier
    - Points balance
    - Tier achieved date
    - Last trip info
    
    If member not found, returns default demo profile.
    """
    member = MOCK_MEMBERS.get(phone_number, MOCK_MEMBERS["default"])
    tier_config = TIER_CONFIG[member["current_tier"]]
    
    # Calculate days until tier review
    tier_achieved = member["tier_achieved_date"]
    maintenance_deadline = tier_achieved + timedelta(days=TIER_MAINTENANCE_MONTHS * 30)
    days_until_review = (maintenance_deadline - datetime.now()).days
    
    return {
        "member_id": member["member_id"],
        "name": member["name"],
        "current_tier": member["current_tier"],
        "points_balance": member["points_balance"],
        "days_until_tier_review": max(0, days_until_review),
        "last_trip": member.get("last_trip"),
    }


def get_points_balance(phone_number: str) -> dict:
    """
    Get current points balance for a member.
    
    Returns:
    - Current points
    - Points earned from last trip
    """
    member = MOCK_MEMBERS.get(phone_number, MOCK_MEMBERS["default"])
    
    return {
        "points_balance": member["points_balance"],
        "last_trip_points": member.get("last_trip", {}).get("points_earned", 0),
        "last_trip_destination": member.get("last_trip", {}).get("destination", "your recent trip"),
    }


def get_tier_status(phone_number: str) -> dict:
    """
    Get tier status and progression info for a member.
    
    Returns:
    - Current tier
    - Points needed for next tier
    - Current points
    - Next tier name (if applicable)
    - Days until tier review
    """
    member = MOCK_MEMBERS.get(phone_number, MOCK_MEMBERS["default"])
    current_tier = member["current_tier"]
    tier_config = TIER_CONFIG[current_tier]
    
    # Calculate points to next tier
    if tier_config["next_tier"]:
        next_tier_config = TIER_CONFIG[tier_config["next_tier"]]
        points_needed = next_tier_config["min_points"] - member["points_balance"]
        points_needed = max(0, points_needed)
    else:
        points_needed = None
    
    # Calculate tier review timeline
    tier_achieved = member["tier_achieved_date"]
    maintenance_deadline = tier_achieved + timedelta(days=TIER_MAINTENANCE_MONTHS * 30)
    days_until_review = (maintenance_deadline - datetime.now()).days
    months_until_review = days_until_review // 30
    
    return {
        "current_tier": current_tier,
        "points_balance": member["points_balance"],
        "next_tier": tier_config["next_tier"],
        "points_to_next_tier": points_needed,
        "months_until_tier_review": max(0, months_until_review),
        "at_highest_tier": tier_config["next_tier"] is None,
    }


def get_tier_benefits(tier_name: str) -> dict:
    """
    Get benefits for a specific tier.
    
    Args:
        tier_name: One of Blue, Silver, Gold, Platinum
        
    Returns:
        List of benefits for that tier
    """
    tier_name = tier_name.capitalize()
    
    if tier_name not in TIER_CONFIG:
        return {
            "error": f"Unknown tier: {tier_name}",
            "valid_tiers": list(TIER_CONFIG.keys()),
        }
    
    return {
        "tier": tier_name,
        "benefits": TIER_CONFIG[tier_name]["benefits"],
    }


def get_tier_requirements() -> dict:
    """
    Get all tier thresholds and requirements.
    
    Returns complete tier progression info.
    """
    return {
        "tiers": [
            {
                "name": name,
                "min_points": config["min_points"],
                "next_tier": config["next_tier"],
                "points_to_next": config["points_to_next"],
            }
            for name, config in TIER_CONFIG.items()
        ],
        "maintenance_rule": f"Tiers must be maintained for {TIER_MAINTENANCE_MONTHS} months. If activity drops, tier may be downgraded.",
    }


def get_downgrade_info(phone_number: str) -> dict:
    """
    Get tier maintenance and potential downgrade info.
    
    Returns:
    - Current tier
    - Previous tier (what they'd drop to)
    - Time remaining to maintain
    - What they need to do to maintain
    """
    member = MOCK_MEMBERS.get(phone_number, MOCK_MEMBERS["default"])
    current_tier = member["current_tier"]
    tier_config = TIER_CONFIG[current_tier]
    
    # Calculate timeline
    tier_achieved = member["tier_achieved_date"]
    maintenance_deadline = tier_achieved + timedelta(days=TIER_MAINTENANCE_MONTHS * 30)
    days_until_review = (maintenance_deadline - datetime.now()).days
    months_until_review = days_until_review // 30
    
    # Find previous tier
    if tier_config["order"] > 0:
        previous_tier = [
            name for name, cfg in TIER_CONFIG.items() 
            if cfg["order"] == tier_config["order"] - 1
        ][0]
    else:
        previous_tier = None
    
    return {
        "current_tier": current_tier,
        "previous_tier": previous_tier,
        "months_until_review": max(0, months_until_review),
        "can_be_downgraded": previous_tier is not None,
        "maintenance_period_months": TIER_MAINTENANCE_MONTHS,
        "advice": "Keep booking to maintain your tier status and earn points towards the next level.",
    }


# =============================================================================
# TOOL DEFINITIONS FOR LIVEKIT AGENT
# =============================================================================

def get_loyalty_tools_schema() -> list:
    """
    Returns tool definitions in the format expected by LiveKit/OpenAI function calling.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_member_profile",
                "description": "Get the member's profile including name, tier, and recent trip info. Use this at the start of the conversation or when you need to know who you're speaking with.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_points_balance",
                "description": "Get the member's current points balance and points earned from their last trip. Use when they ask about points.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_tier_status",
                "description": "Get the member's current tier, points needed for next tier, and tier review timeline. Use when they ask about tier status or progression.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_tier_benefits",
                "description": "Get the benefits for a specific tier (Blue, Silver, Gold, or Platinum). Use when they ask what benefits they have or what a tier includes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tier_name": {
                            "type": "string",
                            "description": "The tier to look up: Blue, Silver, Gold, or Platinum",
                            "enum": ["Blue", "Silver", "Gold", "Platinum"],
                        }
                    },
                    "required": ["tier_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_downgrade_info",
                "description": "Get information about tier maintenance and potential downgrade. Use when they ask about keeping their tier or what happens if they don't book.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_tier_requirements",
                "description": "Get all tier thresholds and progression requirements. Use when they ask how the tier system works or how to move up.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    ]
