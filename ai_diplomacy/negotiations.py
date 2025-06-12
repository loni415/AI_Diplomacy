from dotenv import load_dotenv
import logging
import asyncio
from typing import Dict, TYPE_CHECKING

from diplomacy.engine.message import Message, GLOBAL

from .agent import DiplomacyAgent
# from .clients import load_model_client # Removed
from .utils import gather_possible_orders # load_prompt removed as prompts are gone
from .human_player_interface import send_human_messages

if TYPE_CHECKING:
    from .game_history import GameHistory
    from diplomacy import Game

logger = logging.getLogger("negotiations")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


async def conduct_negotiations(
    game: 'Game',
    agents: Dict[str, DiplomacyAgent],
    game_history: 'GameHistory',
    # model_error_stats: Dict[str, Dict[str, int]], # Removed
    log_file_path: Optional[str] = None, # Made optional, might not be needed if no LLM
    max_rounds: int = 3,
):
    """
    Conducts a round-robin conversation among all non-eliminated powers.
    Each power can send up to 'max_rounds' messages, choosing between private
    and global messages each turn. Uses asyncio for concurrent message generation.
    """
    logger.info("Starting negotiation phase.")

    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]
    eliminated_powers = [
        p_name for p_name, p_obj in game.powers.items() if p_obj.is_eliminated()
    ]
    
    logger.info(f"Active powers for negotiations: {active_powers}")
    if eliminated_powers:
        logger.info(f"Eliminated powers (skipped): {eliminated_powers}")
    else:
        logger.info("No eliminated powers yet.")

    # We do up to 'max_rounds' single-message turns for each power
    for round_index in range(max_rounds):
        logger.info(f"Negotiation Round {round_index + 1}/{max_rounds}")
        
        # Prepare tasks for asyncio.gather
        tasks = []
        power_names_for_tasks = []

        for power_name in active_powers:
            if power_name not in agents:
                logger.warning(f"Agent for {power_name} not found in negotiations. Skipping.")
                continue
            if power_name not in agents:
                logger.warning(f"Agent for {power_name} not found in negotiations. Skipping.")
                continue

            # human_player_name removed, all players are human and interact sequentially.
            logger.info(f"Prompting HUMAN player {power_name} for messages...")
            agent = agents.get(power_name)

            try:
                # Call send_human_messages directly and sequentially.
                human_messages = send_human_messages(game, power_name, game_history, active_powers)

                # Process messages immediately
                if human_messages:
                    for message_dict in human_messages:
                        if not isinstance(message_dict, dict) or "content" not in message_dict or "recipient" not in message_dict:
                            logger.warning(f"Invalid message format received from {power_name}: {message_dict}. Skipping.")
                            continue
                        
                        recipient = message_dict.get("recipient", GLOBAL)
                        content = message_dict.get("content", "")

                        # Fallback logic for invalid recipient to GLOBAL is removed.
                        # send_human_messages should now ensure recipient is valid or GLOBAL.
                        # The check for message_type != "private" and recipient != GLOBAL can remain as a warning if a non-private message has a specific recipient.
                        if message_dict.get("message_type") != "private" and recipient != GLOBAL:
                             if recipient != GLOBAL :
                                 logger.warning(f"Message to specific power {recipient} from {power_name} was not marked 'private' (should be 'global' if recipient is GLOBAL, or 'private' otherwise). Assuming private for specific recipient based on context.")
                                 # No change to recipient, assume it was intended as private.
                                 # If it was meant to be GLOBAL, send_human_messages should have set recipient to "GLOBAL".

                        diplo_message = Message(
                            phase=game.current_short_phase,
                            sender=power_name,
                            recipient=recipient,
                            message=content,
                            time_sent=None,
                        )
                        game.add_message(diplo_message)
                        game_history.add_message(
                            game.current_short_phase,
                            power_name,
                            recipient,
                            content,
                        )

                        if agent:
                            journal_recipient = f"to {recipient}" if recipient != GLOBAL else "globally"
                            agent.add_journal_entry(f"Sent message {journal_recipient} in {game.current_short_phase}: {content[:100]}...")
                        logger.info(f"[{power_name} -> {recipient}] {content[:100]}...")
                else:
                    logger.debug(f"No messages sent by {power_name} in round {round_index + 1}.")

            except Exception as e_human_msg:
                logger.error(f"Error during send_human_messages for {power_name}: {e_human_msg}", exc_info=True)
                # Optionally, add a journal entry or some other indicator of error for this power.

        # asyncio.gather and related logic for tasks/results removed as calls are now sequential.
        logger.info(f"Finished message round {round_index + 1} for all human players.")

    logger.info("Negotiation phase complete.")
    return game_history
