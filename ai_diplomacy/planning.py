from dotenv import load_dotenv
import logging
import concurrent.futures
from typing import Dict, Optional # Added Optional

# from .clients import load_model_client # Removed
from .game_history import GameHistory
from .agent import DiplomacyAgent
from .human_player_interface import get_human_plan # Added
from .utils import gather_possible_orders # Added, was missing from original import but used

logger = logging.getLogger(__name__)

async def planning_phase(
    game, 
    agents: Dict[str, DiplomacyAgent], 
    game_history: GameHistory, 
    # model_error_stats, # Removed
    log_file_path: Optional[str] = None, # Made optional, might not be needed if no LLM
):
    """
    Lets each power generate a strategic plan using their DiplomacyAgent.
    """
    logger.info(f"Starting planning phase for {game.current_short_phase}...")
    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]
    eliminated_powers = [
        p_name for p_name, p_obj in game.powers.items() if p_obj.is_eliminated()
    ]
    
    logger.info(f"Active powers for planning: {active_powers}")
    if eliminated_powers:
        logger.info(f"Eliminated powers (skipped): {eliminated_powers}")
    else:
        logger.info("No eliminated powers yet.")
    
    # human_player_name and ai_power_agents logic removed. All players are human.
    # ThreadPoolExecutor removed as calls are sequential.

    for power_name in active_powers:
        if power_name not in agents:
            logger.warning(f"Agent for {power_name} not found in planning phase. Skipping.")
            continue

        logger.info(f"Gathering plan for HUMAN player {power_name}...")
        agent = agents.get(power_name)
        
        try:
            # Call get_human_plan sequentially for each power
            plan_result = get_human_plan(game, power_name, game_history)

            if plan_result and plan_result.strip() and plan_result != "No plan submitted.":
                if agent:
                    agent.add_journal_entry(f"Submitted plan for {game.current_short_phase}: {plan_result[:100]}...")
                game_history.add_plan(
                    game.current_short_phase, power_name, plan_result
                )
                logger.info(f"Plan for player {power_name} recorded.")
                logger.debug(f"Added plan for {power_name} to history: {plan_result[:100]}...")
            elif plan_result == "No plan submitted.":
                 game_history.add_plan(game.current_short_phase, power_name, plan_result)
                 logger.info(f"Player {power_name} submitted no plan.")
            else: # Empty string or similar after stripping
                game_history.add_plan(game.current_short_phase, power_name, "No plan submitted.")
                logger.warning(f"Player {power_name} returned an empty plan. Recorded as 'No plan submitted.'")

        except Exception as e_human_plan:
            logger.error(f"Exception during get_human_plan for {power_name}: {e_human_plan}", exc_info=True)
            game_history.add_plan(game.current_short_phase, power_name, "Error retrieving plan.")

    logger.info("Planning phase processing complete.")
    return game_history