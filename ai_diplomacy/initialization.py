# ai_diplomacy/initialization.py
import logging
import json

# Forward declaration for type hinting, actual imports in function if complex
if False: # TYPE_CHECKING
    from diplomacy import Game
    # from diplomacy.models.game import GameHistory # GameHistory is from ai_diplomacy
    from .game_history import GameHistory
    from .agent import DiplomacyAgent

from .agent import ALL_POWERS, ALLOWED_RELATIONSHIPS
# from .utils import run_llm_and_log, log_llm_response # LLM specific
# from .prompt_constructor import build_context_prompt # LLM specific

logger = logging.getLogger(__name__)

async def initialize_agent_state_ext(
    agent: 'DiplomacyAgent', 
    game: 'Game', 
    game_history: 'GameHistory', 
    # log_file_path: str # No longer needed for LLM logging
):
    """Initializes agent goals and relationships to defaults. LLM call removed."""
    power_name = agent.power_name
    logger.info(f"[{power_name}] Initializing agent state with default values...")
    current_phase = game.get_current_phase() if game else "UnknownPhase"

    try:
        # Set default initial goals if not already provided during agent construction
        if not agent.goals:
            agent.goals = ["Survive and expand", "Form beneficial alliances", "Secure key territories"]
            agent.add_journal_entry(f"[{current_phase}] Set default initial goals.")
            logger.info(f"[{power_name}] Default goals set: {agent.goals}")

        # Set default initial relationships if not already provided
        # Check if relationships are effectively empty or all Neutral
        set_default_relationships = True
        if agent.relationships:
            for p in ALL_POWERS:
                if p != power_name and agent.relationships.get(p) != "Neutral":
                    set_default_relationships = False
                    break
        
        if set_default_relationships:
            agent.relationships = {p: "Neutral" for p in ALL_POWERS if p != power_name}
            agent.add_journal_entry(f"[{current_phase}] Set default neutral relationships.")
            logger.info(f"[{power_name}] Default neutral relationships set: {agent.relationships}")
        else:
            logger.info(f"[{power_name}] Initial relationships already set, retaining: {agent.relationships}")


    except Exception as e:
        logger.error(f"[{power_name}] Error during simplified agent state initialization: {e}", exc_info=True)
        # Ensure basic defaults even if an error occurs above for some reason
        if not agent.goals:
            agent.goals = ["Survive and expand"]
        if not agent.relationships:
            agent.relationships = {p: "Neutral" for p in ALL_POWERS if p != power_name}

    # Final log of state after initialization attempt
    logger.info(f"[{power_name}] Post-initialization state: Goals={agent.goals}, Relationships={agent.relationships}")
