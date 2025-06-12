from dotenv import load_dotenv
import logging
import os
from typing import Dict, List, Tuple, Set, Optional
from diplomacy import Game
import csv
from typing import TYPE_CHECKING

# Avoid circular import for type hinting
if TYPE_CHECKING:
    # from .clients import BaseModelClient # Removed
    pass
    # If DiplomacyAgent is used for type hinting for an 'agent' parameter:
    # from .agent import DiplomacyAgent 

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO) # Default, can be overridden by parent logger
# logging.basicConfig(level=logging.INFO) #basicConfig should ideally be called once at application entry point

load_dotenv()


# Removed assign_models_to_powers function

def gather_possible_orders(game: Game, power_name: str) -> Dict[str, List[str]]:
    """
    Returns a dictionary mapping each orderable location to the list of valid orders.
    """
    orderable_locs = game.get_orderable_locations(power_name)
    all_possible = game.get_all_possible_orders()

    result = {}
    for loc in orderable_locs:
        result[loc] = all_possible.get(loc, [])
    return result


async def get_valid_orders(
    game: Game,
    client, # This was BaseModelClient, now unused if only human players or AI is passive
    board_state, # Unused if AI is passive
    power_name: str,
    possible_orders: Dict[str, List[str]], # Still useful for fallback or simple AI
    game_history, # Unused if AI is passive
    model_error_stats: Optional[Dict[str, Dict[str, int]]] = None, # Unused
    agent_goals: Optional[List[str]] = None, # Unused if AI is passive
    agent_relationships: Optional[Dict[str, str]] = None, # Unused if AI is passive
    agent_private_diary_str: Optional[str]] = None, # Unused if AI is passive
    log_file_path: Optional[str] = None, # Unused
    phase: Optional[str] = None, # Unused if AI is passive
) -> List[str]:
    """
    Generates and validates orders.
    If a 'client' (LLM) is not provided or AI is passive, this function
    will return empty orders or simple fallback (e.g. all HOLDs).
    """
    logger.info(f"[{power_name}] In get_valid_orders. Client type: {type(client)}")
    if client is None: # No client passed, assume non-LLM player or passive AI
        logger.warning(f"[{power_name}] No client provided to get_valid_orders. AI player will be passive / submit no orders.")
        # Fallback: submit HOLD orders for all orderable units
        # hold_orders = []
        # for loc in possible_orders.keys():
        #     unit_type = game.get_unit_type_by_location(loc) # Requires game object
        #     if unit_type:
        #          hold_order = f"{unit_type[0]} {loc} H"
        #          # Basic validation that HOLD is possible for this unit
        #          if hold_order in game.get_all_possible_orders().get(loc, []):
        #              hold_orders.append(hold_order)
        # logger.info(f"[{power_name}] Submitting default HOLD orders: {hold_orders}")
        # return hold_orders
        return [] # Return empty orders, making the AI passive

    # --- Original LLM-based logic below, now effectively dead code if client is always None ---
    # --- This part should be removed if get_valid_orders is purely for non-LLM players ---
    # --- or refactored if AI players are to be supported without the old client structure ---

    # Fallback if client logic was expected but not executed
    logger.warning(f"[{power_name}] Fallback: client was provided but logic not fully implemented for non-LLM or new AI structure. Returning empty orders.")
    return []


def normalize_and_compare_orders(
    issued_orders: Dict[str, List[str]],
    accepted_orders_dict: Dict[str, List[str]],
    game: Game,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """
    Normalizes and compares issued orders against accepted orders from the game engine.
    Uses the map's built-in normalization methods to ensure consistent formatting.

    Args:
        issued_orders: Dictionary of orders issued by power {power_name: [orders]}
        accepted_orders_dict: Dictionary of orders accepted by the engine,
                              typically from game.get_state()["orders"].
        game: The current Game object containing the map.

    Returns:
        Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]: (orders_not_accepted, orders_not_issued)
            - orders_not_accepted: Orders issued but not accepted by engine (normalized).
            - orders_not_issued: Orders accepted by engine but not issued (normalized).
    """
    game_map = game.map

    def normalize_order(order: str) -> str:
        # Inner function to normalize a single order string using the game map.
        if not order:
            return order

        try:
            # Use map's normalization methods directly
            normalized = game_map.norm(order)
            # Further split and normalize parts for complex orders if necessary
            # (This part might need refinement depending on how complex orders are handled
            #  and represented after initial normalization by game_map.norm)

            # Example (simplified, game_map.norm often handles this):
            # Split support orders
            # parts = normalized.split(" S ")
            # normalized_parts = []
            # for part in parts:
            #     move_parts = part.split(" - ")
            #     move_parts = [game_map.norm(p.strip()) for p in move_parts]
            #     move_parts = [game_map.aliases.get(p, p) for p in move_parts]
            #     normalized_parts.append(" - ".join(move_parts))
            # return " S ".join(normalized_parts)

            return normalized  # Return the directly normalized string for now
        except Exception as e:
            logger.warning(f"Could not normalize order '{order}': {e}")
            return order  # Return original if normalization fails

    orders_not_accepted = {}
    orders_not_issued = {}

    all_powers = set(issued_orders.keys()) | set(accepted_orders_dict.keys())

    for pwr in all_powers:
        # Normalize issued orders for the power, handling potential absence
        issued_set = set()
        if pwr in issued_orders:
            try:
                issued_set = {normalize_order(o) for o in issued_orders.get(pwr, []) if o}
            except Exception as e:
                logger.error(f"Error normalizing issued orders for {pwr}: {e}")

        # Normalize accepted orders for the power, handling potential absence
        accepted_set = set()
        if pwr in accepted_orders_dict:
            try:
                accepted_set = {normalize_order(o) for o in accepted_orders_dict.get(pwr, []) if o}
            except Exception as e:
                logger.error(f"Error normalizing accepted orders for {pwr}: {e}")

        # Compare the sets
        missing_from_engine = issued_set - accepted_set
        missing_from_issued = accepted_set - issued_set

        if missing_from_engine:
            orders_not_accepted[pwr] = missing_from_engine
        if missing_from_issued:
            orders_not_issued[pwr] = missing_from_issued

    return orders_not_accepted, orders_not_issued


# Removed load_prompt function
# Removed log_llm_response function
# Removed run_llm_and_log function