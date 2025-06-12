import argparse
import logging
import time
import dotenv
import os
import json
import asyncio
from collections import defaultdict
import concurrent.futures

# Suppress Gemini/PaLM gRPC warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"  # ERROR level only
os.environ["GRPC_VERBOSITY"] = "ERROR"  # Additional gRPC verbosity control
os.environ["ABSL_MIN_LOG_LEVEL"] = "2"  # Suppress abseil warnings
# Disable gRPC forking warnings
os.environ["GRPC_POLL_STRATEGY"] = "poll"  # Use 'poll' for macOS compatibility

from diplomacy import Game
from diplomacy.engine.message import GLOBAL, Message
from diplomacy.utils.export import to_saved_game_format

# from ai_diplomacy.clients import load_model_client # Removed
from ai_diplomacy.utils import (
    get_valid_orders, # Will be reviewed later - might be removed if no AI players
    gather_possible_orders,
    # assign_models_to_powers, # Removed
)
from ai_diplomacy.human_player_interface import get_human_orders
from ai_diplomacy.negotiations import conduct_negotiations
from ai_diplomacy.planning import planning_phase
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.agent import DiplomacyAgent
import ai_diplomacy.narrative
from ai_diplomacy.initialization import initialize_agent_state_ext

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
# Silence noisy dependencies
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("root").setLevel(logging.WARNING) # Assuming root handles AFC


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters."
    )
    parser.add_argument(
        "--max_year",
        type=int,
        default=1901,
        help="Maximum year to simulate. The game will stop once this year is reached.",
    )
    parser.add_argument(
        "--num_negotiation_rounds",
        type=int,
        default=0,
        help="Number of negotiation rounds per phase.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output filename for the final JSON result. If not provided, a timestamped name will be generated.",
    )
    # parser.add_argument( # Removed --models argument
    #     "--models",
    #     type=str,
    #     default="",
    #     help=(
    #         "Comma-separated list of model names to assign to powers in order. "
    #         "The order is: AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY."
    #     ),
    # )
    parser.add_argument(
        "--planning_phase", 
        action="store_true",
        help="Enable the planning phase for each power to set strategic directives.",
    )
    return parser.parse_args()


async def main():
    args = parse_arguments()
    max_year = args.max_year

    logger.info(
        "Starting a new Diplomacy game, configured for human players."
    )
    start_whole = time.time()

    # Create a fresh Diplomacy game
    game = Game()
    game_history = GameHistory()

    # Ensure game has phase_summaries attribute
    if not hasattr(game, "phase_summaries"):
        game.phase_summaries = {}

    # Determine the result folder based on a timestamp
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    result_folder = f"./results/{timestamp_str}"
    os.makedirs(result_folder, exist_ok=True)

    # ADDED: Setup general file logging
    general_log_file_path = os.path.join(result_folder, "general_game.log")
    file_handler = logging.FileHandler(general_log_file_path, mode='a') # Append mode
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - [%(funcName)s:%(lineno)d] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_formatter)
    # Use the same log_level as basicConfig, or set a different one if needed for the file
    file_handler.setLevel(logging.INFO) 
    logging.getLogger().addHandler(file_handler) # Add handler to the root logger
    
    # It's good practice to define 'logger' after all root logger configurations if it's module-specific.
    # If 'logger = logging.getLogger(__name__)' is defined later, this message will use it.
    # If not, it uses the root logger directly.
    logging.info(f"General game logs will be appended to: {general_log_file_path}")

    # File paths
    manifesto_path = f"{result_folder}/game_manifesto.txt"
    # Use provided output filename or generate one based on the timestamp
    game_file_path = args.output if args.output else f"{result_folder}/lmvsgame.json"
    overview_file_path = f"{result_folder}/overview.jsonl"
    # == Add LLM Response Log Path == # This can be repurposed for general human action logs if needed, or removed.
    # For now, let's assume general_log_file_path covers enough.
    # llm_log_file_path = f"{result_folder}/llm_responses.csv" # Removed specific LLM log path

    # Handle power model mapping - Removed
    # if args.models:
    #     # Expected order: AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY
    #     powers_order = [
    #         "AUSTRIA",
    #         "ENGLAND",
    #         "FRANCE",
    #         "GERMANY",
    #         "ITALY",
    #         "RUSSIA",
    #         "TURKEY",
    #     ]
    #     provided_models = [name.strip() for name in args.models.split(",")]
    #     if len(provided_models) != len(powers_order):
    #         logger.error(
    #             f"Expected {len(powers_order)} models for --power-models but got {len(provided_models)}. Exiting."
    #         )
    #         return
    #     game.power_model_map = dict(zip(powers_order, provided_models))
    # else:
    #     # game.power_model_map = assign_models_to_powers() # Removed
    #     # For a human-only game, or human-primary game, we can just iterate available powers.
    #     # If specific powers need to be designated as human/AI, this will need new config.
    #     # For now, assume all powers will have an agent, and human interaction is gated by human_player_name.
    #     pass


    # == Goal 1: Centralize Agent Instances ==
    agents = {}
    initialization_tasks = []
    logger.info("Initializing Diplomacy Agents for each power...")
    # Iterate through all powers defined in the game (e.g., "AUSTRIA", "ENGLAND", etc.)
    for power_name in game.powers.keys():
        if not game.powers[power_name].is_eliminated(): # Only create for active powers initially
            try:
                # client = load_model_client(model_id) # Client loading removed
                # TODO: Potentially load initial goals/relationships from config later
                agent = DiplomacyAgent(power_name=power_name) # No client passed
                agents[power_name] = agent
                logger.info(f"Preparing initialization task for {power_name}")
                # Pass log path to initialization - initialize_agent_state_ext no longer takes llm_log_file_path
                initialization_tasks.append(initialize_agent_state_ext(agent, game, game_history))
            except Exception as e:
                logger.error(f"Failed to create agent for {power_name}: {e}", exc_info=True)
        else:
             logger.info(f"Skipping agent initialization for eliminated power: {power_name}")
    
    # == Run initializations concurrently ==
    logger.info(f"Running {len(initialization_tasks)} agent initializations concurrently...")
    initialization_results = await asyncio.gather(*initialization_tasks, return_exceptions=True)
    # Check results for errors
    # Note: agents dict might have fewer entries than results if client creation failed
    initialized_powers = list(agents.keys()) # Get powers for which agents were created
    for i, result in enumerate(initialization_results):
         if i < len(initialized_powers): # Ensure index is valid for initialized_powers
             power_name = initialized_powers[i]
             if isinstance(result, Exception):
                 logger.error(f"Failed to initialize agent state for {power_name}: {result}", exc_info=result)
                 # Potentially remove agent if initialization failed? Depends on desired behavior.
             else:
                 logger.info(f"Successfully initialized agent state for {power_name}.")
         else:
             logger.error(f"Initialization result mismatch - unexpected result: {result}")
    # ========================================

    # == Add storage for relationships per phase ==
    all_phase_relationships = {}
    all_phase_relationships_history = {} # Initialize history

    while not game.is_game_done:
        phase_start = time.time()
        current_phase = game.get_current_phase()

        # Ensure the current phase is registered in the history
        game_history.add_phase(current_phase)
        
        # Store the current phase's short name once for consistent use
        current_short_phase = game.current_short_phase
        
        logger.info(
            f"PHASE: {current_phase} (time so far: {phase_start - start_whole:.2f}s)"
        )

        # DEBUG: Print the short phase to confirm
        logger.debug(f"DEBUG: current_short_phase is '{current_short_phase}'")

        # Prevent unbounded simulation based on year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

        # If it's a movement phase (e.g. ends with "M"), conduct negotiations
        if game.current_short_phase.endswith("M"):
            if args.num_negotiation_rounds > 0:
                logger.info(f"Running {args.num_negotiation_rounds} rounds of negotiations...")
                game_history = await conduct_negotiations(
                    game,
                    agents,
                    game_history,
                    # model_error_stats, # Removed
                    max_rounds=args.num_negotiation_rounds,
                    # Pass log path
                    log_file_path=general_log_file_path, # Use general log for now, or None
                )
            else:
                logger.info("Skipping negotiation phase as num_negotiation_rounds=0")

            # === Execute Planning Phase (if enabled) AFTER potential negotiations ===
            if args.planning_phase:
                logger.info("Executing strategic planning phase...")
                await planning_phase(
                    game,
                    agents,
                    game_history,
                    # model_error_stats, # Removed
                    log_file_path=general_log_file_path, # Use general log for now, or None
                )
            # ======================================================================

            # === Generate Negotiation Diary Entries === (This was LLM-driven, remove/comment out)
            # logger.info(f"Generating negotiation diary entries for phase {current_short_phase}...")
            # active_powers_for_neg_diary = [p for p in agents.keys() if not game.powers[p].is_eliminated()]
            # eliminated_powers_for_neg_diary = [p for p in agents.keys() if game.powers[p].is_eliminated()]
            # logger.info(f"Active powers for negotiation diary: {active_powers_for_neg_diary}")
            # if eliminated_powers_for_neg_diary:
            #     logger.info(f"Eliminated powers (skipped): {eliminated_powers_for_neg_diary}")
            # neg_diary_tasks = []
            # human_player_name = "AUSTRIA" # Example, make configurable
            # for power_name, agent in agents.items():
            #     if not game.powers[power_name].is_eliminated() and power_name != human_player_name: # Skip for human
            #         # This method was removed from agent.py
            #         # neg_diary_tasks.append(
            #         #     agent.generate_negotiation_diary_entry(
            #         #         game,
            #         #         game_history,
            #         #         general_log_file_path
            #         #     )
            #         # )
            #         pass # No LLM diary entries
            # if neg_diary_tasks:
            #     await asyncio.gather(*neg_diary_tasks, return_exceptions=True)
            # logger.info(f"Finished generating negotiation diary entries for {current_short_phase}.")
            # ==========================================

        # AI Decision Making: Get orders for each power
        logger.info("Getting orders from agents...")
        
        # Log active and eliminated powers for order generation
        active_powers_for_orders = [p for p in agents.keys() if not game.powers[p].is_eliminated()]
        eliminated_powers_for_orders = [p for p in agents.keys() if game.powers[p].is_eliminated()]
        
        logger.info(f"Active powers for order generation: {active_powers_for_orders}")
        if eliminated_powers_for_orders:
            logger.info(f"Eliminated powers (skipped): {eliminated_powers_for_orders}")
        
        order_tasks = []
        order_power_names = []
        # Calculate board state once before the loop
        board_state = game.get_state()

        for power_name, agent in agents.items():
            if game.powers[power_name].is_eliminated():
                logger.debug(f"Skipping order generation for eliminated power {power_name}.")
                continue

            # ADDED: Diagnostic logging for orderable locations
            logger.info(f"--- Diagnostic Log for {power_name} in phase {current_phase} ---")
            try:
                orderable_locs_from_game = game.get_orderable_locations(power_name)
                logger.info(f"[{power_name}][{current_phase}] game.get_orderable_locations(): {orderable_locs_from_game}")
                actual_units = game.get_units(power_name)
                actual_unit_locs = [unit.split(' ')[1].split('/')[0] for unit in actual_units if ' ' in unit] # Corrected parsing
                logger.info(f"[{power_name}][{current_phase}] Actual unit locations (from game.get_units()): {actual_unit_locs}")
            except Exception as e_diag:
                logger.error(f"[{power_name}][{current_phase}] Error during diagnostic logging: {e_diag}")
            logger.info(f"--- End Diagnostic Log for {power_name} in phase {current_phase} ---")

            # Calculate possible orders for the current power
            possible_orders = gather_possible_orders(game, power_name)
            if not possible_orders:
                logger.debug(f"No orderable locations for {power_name}; submitting empty orders.")
                game.set_orders(power_name, []) # Ensure empty orders if none possible
                continue

            order_power_names.append(power_name)
            
            # Determine if the current power is human or AI
            # For now, let's assume a specific power is human, e.g., "AUSTRIA"
            # This should ideally be configurable.
            # human_player_name variable removed - all players are human
            logger.info(f"Gathering orders for HUMAN player {power_name}...")
            try:
                # Call get_human_orders sequentially - no more asyncio.gather for orders
                orders = get_human_orders(game, power_name, game_history)
                logger.debug(f"Orders for {power_name}: {orders}")
                if orders:
                    game.set_orders(power_name, orders)
                    logger.debug(
                        f"Set orders for {power_name} in {game.current_short_phase}: {orders}"
                    )
                else:
                    logger.debug(f"No orders returned for {power_name}. Setting empty orders.")
                    game.set_orders(power_name, []) # Ensure empty orders if none given
            except Exception as e_human:
                logger.error(f"Error during get_human_orders for {power_name}: {e_human}", exc_info=True)
                game.set_orders(power_name, []) # Set empty orders on error
                logger.warning(f"Setting empty orders for {power_name} due to error in get_human_orders.")

        # The order_tasks and asyncio.gather logic for orders is removed as calls are sequential.
        # Processing of results is now handled directly after the call to get_human_orders.
        logger.info("Finished gathering orders for all human players.")
        # --- End Order Generation ---

        # Process orders
        logger.info(f"Processing orders for {current_phase}...")
        
        # Process with a custom summary callback that captures our custom game_history data
        def phase_summary_callback(system_prompt, user_prompt):
            # This will be called by the game engine's _generate_phase_summary method
            # Get messages for this phase from game_history
            current_phase_obj = None
            for phase in game_history.phases:
                if phase.name == current_short_phase:
                    current_phase_obj = phase
                    break
                
            if not current_phase_obj:
                return f"Phase {current_short_phase} Summary: (No game history data available)"
            
            # 1) Gather the current board state, sorted by # of centers
            power_info = []
            for power_name, power in game.powers.items():
                units_list = list(power.units)
                centers_list = list(power.centers)
                power_info.append(
                    (power_name, len(centers_list), units_list, centers_list)
                )
            # Sort by descending # of centers
            power_info.sort(key=lambda x: x[1], reverse=True)

            # 2) Build text lines for the top "Board State Overview"
            top_lines = ["Current Board State (Ordered by SC Count):"]
            for (p_name, sc_count, units, centers) in power_info:
                top_lines.append(
                    f" • {p_name}: {sc_count} centers (needs 18 to win). "
                    f"Units={units} Centers={centers}"
                )

            # 3) Map orders to "successful", "failed", or "other" outcomes
            success_dict = {}
            fail_dict = {}
            other_dict = {}

            orders_dict = game.order_history.get(current_short_phase, {})
            results_for_phase = game.result_history.get(current_short_phase, {})

            for pwr, pwr_orders in orders_dict.items():
                for order_str in pwr_orders:
                    # Extract the unit from the string
                    tokens = order_str.split()
                    if len(tokens) < 3:
                        # Something malformed
                        other_dict.setdefault(pwr, []).append(order_str)
                        continue
                    unit_name = " ".join(tokens[:2])
                    # We retrieve the order results for that unit
                    results_list = results_for_phase.get(unit_name, [])
                    # Check if the results contain e.g. "dislodged", "bounce", "void"
                    # We consider success if the result list is empty or has no negative results
                    if not results_list or all(res not in ["bounce", "void", "no convoy", "cut", "dislodged", "disrupted"] for res in results_list):
                        success_dict.setdefault(pwr, []).append(order_str)
                    elif any(res in ["bounce", "void", "no convoy", "cut", "dislodged", "disrupted"] for res in results_list):
                        fail_dict.setdefault(pwr, []).append(f"{order_str} - {', '.join(str(r) for r in results_list)}")
                    else:
                        other_dict.setdefault(pwr, []).append(order_str)

            # 4) Build textual lists of successful, failed, and "other" moves
            def format_moves_dict(title, moves_dict):
                lines = [title]
                if not moves_dict:
                    lines.append("  None.")
                    return "\n".join(lines)
                for pwr in sorted(moves_dict.keys()):
                    lines.append(f"  {pwr}:")
                    for mv in moves_dict[pwr]:
                        lines.append(f"    {mv}")
                return "\n".join(lines)

            success_section = format_moves_dict("Successful Moves:", success_dict)
            fail_section = format_moves_dict("Unsuccessful Moves:", fail_dict)
            other_section = format_moves_dict("Other / Unclassified Moves:", other_dict)

            # 5) Combine everything into the final summary text
            summary_parts = []
            summary_parts.append("\n".join(top_lines))
            summary_parts.append("\n" + success_section)
            summary_parts.append("\n" + fail_section)
            
            # Only include "Other" section if it has content
            if other_dict:
                summary_parts.append("\n" + other_section)

            return f"Phase {current_short_phase} Summary:\n\n" + "\n".join(summary_parts)
        
        # Process with our custom callback
        game.process(phase_summary_callback=phase_summary_callback)

        # Log the results
        logger.info(f"Results for {current_phase}:")
        for power_name, power in game.powers.items():
            logger.info(f"{power_name}: {power.centers}")

        # Ensure messages from game_history are added to the game's message system
        # This is required for messages to appear in the Messages tab
        for phase in game_history.phases:
            if phase.name == current_short_phase:
                for msg in phase.messages:
                    try:
                        # Only add if not already present (avoid duplicates)
                        if not any(m.sender == msg.sender and 
                                  m.recipient == msg.recipient and 
                                  m.message == msg.content 
                                  for m in game.messages.values()):
                            game.add_message(Message(
                                phase=current_short_phase,
                                sender=msg.sender,
                                recipient=msg.recipient,
                                message=msg.content,
                                time_sent=int(time.time())
                            ))
                    except Exception as e:
                        logger.warning(f"Could not add message to game: {e}")

        # Add orders to game history
        for power_name in game.order_history[current_short_phase]:
            orders = game.order_history[current_short_phase][power_name]
            results = []
            for order in orders:
                # Example move: "A PAR H" -> unit="A PAR", order_part="H"
                tokens = order.split(" ", 2)
                if len(tokens) < 3:
                    continue
                unit = " ".join(tokens[:2])  # e.g. "A PAR"
                order_part = tokens[2]  # e.g. "H" or "S A MAR"
                results.append(
                    [str(x) for x in game.result_history[current_short_phase][unit]]
                )
            game_history.add_orders(
                current_short_phase,
                power_name,
                game.order_history[current_short_phase][power_name],
            )

        logger.info(f"--- Orders Submitted for {current_phase} ---")
        for power, orders in game.order_history.get(current_short_phase, {}).items():
            order_str = ", ".join(orders) if orders else "(No orders/NOP)"
            logger.info(f"  {power:<8}: {order_str}")
        logger.info("-----------------------------------")

        # == Collect Agent Relationships for this Phase ==
        current_relationships_for_phase = {}
        logger.debug(f"Collecting relationships for phase: {current_short_phase}")
        active_powers_in_phase = set(game.powers.keys()) # Get powers present at end of phase
        for power_name, agent in agents.items():
            # Only collect relationships if the power is still active in the game
            if power_name in active_powers_in_phase and not game.powers[power_name].is_eliminated():
                try:
                    current_relationships_for_phase[power_name] = agent.relationships
                    logger.debug(f"  Collected relationships for {power_name}")
                except Exception as e:
                     logger.error(f"Error getting relationships for {power_name}: {e}")
            # else:
            #    logger.debug(f"  Skipping relationships for inactive/eliminated power {power_name}")
        all_phase_relationships[current_short_phase] = current_relationships_for_phase
        logger.debug(f"Stored relationships for {len(current_relationships_for_phase)} agents in phase {current_short_phase}")
        # ================================================

        # Log phase duration
        phase_end = time.time()
        logger.info(f"Phase {current_phase} took {phase_end - phase_start:.2f}s")

        # --- Generate Phase Result Diary Entries ---
        # This happens after processing but before state updates
        completed_phase_name = current_phase
        logger.info(f"Generating phase result diary entries for completed phase {completed_phase_name}...")
        
        # Log active and eliminated powers for phase result diary
        active_powers_for_phase_diary = [p for p in agents.keys() if not game.powers[p].is_eliminated()]
        eliminated_powers_for_phase_diary = [p for p in agents.keys() if game.powers[p].is_eliminated()]
        
        logger.info(f"Active powers for phase result diary: {active_powers_for_phase_diary}")
        if eliminated_powers_for_phase_diary:
            logger.info(f"Eliminated powers (skipped): {eliminated_powers_for_phase_diary}")
        
        # Get phase summary and all orders for this phase
        phase_summary = game.phase_summaries.get(current_phase, "(Summary not generated)")
        all_orders_this_phase = game.order_history.get(current_short_phase, {})
        
        # Generate diary entries concurrently for all active agents
        phase_result_diary_tasks = []
        for power_name, agent in agents.items():
            if not game.powers[power_name].is_eliminated():
                phase_result_diary_tasks.append(
                    # This method was removed from agent.py
                    # agent.generate_phase_result_diary_entry(
                    #     game,
                    #     game_history,
                    #     phase_summary,
                    #     all_orders_this_phase,
                    #     general_log_file_path
                    # )
                    pass # No LLM diary entries
                )
        
        # if phase_result_diary_tasks: # LLM related, tasks will be empty
            # logger.info(f"Running {len(phase_result_diary_tasks)} phase result diary tasks concurrently...")
            # await asyncio.gather(*phase_result_diary_tasks, return_exceptions=True) # LLM related
            # logger.info(f"Finished generating phase result diary entries.")
        logger.info("Skipping LLM-driven phase result diary entries.")
        # --- End Phase Result Diary Generation (LLM-driven parts removed) ---

        # --- Diary Consolidation Check --- (LLM-driven, all agent methods removed)
        logger.info("Skipping LLM-driven diary consolidation.")
        # --- End Diary Consolidation ---

        # --- Async State Update --- (LLM-driven, all agent methods removed)
        logger.info("Skipping LLM-driven agent state updates.")
        # The all_phase_relationships_history can still be populated directly if desired,
        # as it reads agent.relationships which can be manually updated by humans in future.
        current_phase_name_for_history = completed_phase_name
        all_phase_relationships_history[current_phase_name_for_history] = {}
        for power_name, agent_obj in agents.items():
            if not game.powers[power_name].is_eliminated(): # Only for active powers
                 all_phase_relationships_history[current_phase_name_for_history][power_name] = agent_obj.relationships.copy()
        logger.info(f"Recorded relationships for phase {current_phase_name_for_history} into history.")
        # --- End Async State Update ---

        # Append the strategic directives to the manifesto file
        strategic_directives = game_history.get_strategic_directives()
        if strategic_directives:
            out_str = f"Strategic directives for {current_phase}:\n"
            for power, directive in strategic_directives.items():
                out_str += f"{power}: {directive}\n\n"
            out_str += f"------------------------------------------\n"
            with open(manifesto_path, "a") as f:
                f.write(out_str)

        # Check if we've exceeded the max year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

    # Game is done
    total_time = time.time() - start_whole
    logger.info(f"Game ended after {total_time:.2f}s. Saving results...")

    # Now save the game with our added data
    output_path = game_file_path
    # If the file already exists, append a timestamp to the filename
    if os.path.exists(output_path):
        logger.info("Game file already exists, saving with unique filename.")
        timestamp = int(time.time())
        base, ext = os.path.splitext(output_path)
        output_path = f"{base}_{timestamp}{ext}"

    # Generate the saved game JSON using the standard export function
    saved_game = to_saved_game_format(game)
    
    # Verify phase_summaries are available in game.phase_summaries
    logger.info(f"Game has {len(game.phase_summaries)} phase summaries: {list(game.phase_summaries.keys())}")

    # CRITICAL: Add phase_summaries as a top-level property in the saved game
    # The frontend expects this exact structure
    saved_game['phase_summaries'] = game.phase_summaries
    logger.info(f"Added phase_summaries to saved game with {len(game.phase_summaries)} phases")

    # Also add summaries to individual phases for backward compatibility
    summary_phases_count = 0
    for i, phase in enumerate(saved_game['phases']):
        phase_name = phase['name']
        if phase_name in game.phase_summaries:
            saved_game['phases'][i]['summary'] = game.phase_summaries[phase_name]
            summary_phases_count += 1
            logger.debug(f"Added summary to phase {phase_name} in export")
    logger.info(f"Added summaries to {summary_phases_count}/{len(saved_game['phases'])} phases in the export")

    # == Capture Final Agent States After All Updates ==
    final_agent_states = {}
    if agents: # Ensure agents exist
        for power_name, agent in agents.items():
            # Access attributes directly as they should exist on the agent object
            final_agent_states[power_name] = {
                "relationships": agent.relationships,
                "goals": agent.goals,
                # Optionally add last diary entry or other final state info here
            }
        logger.info(f"Captured final states for {len(final_agent_states)} agents.")
        # Add this dictionary to the main saved_game object
        saved_game['final_agent_states'] = final_agent_states
        logger.info("Added 'final_agent_states' key to the saved game data.")
    else:
        logger.info("No agents found, skipping capture of final agent states.")
        saved_game['final_agent_states'] = {} # Add empty dict for consistency

    # == Add Agent Relationships to Each Phase in the Export (Using History) ==
    relationships_added_to_phases_count = 0
    for i, phase_data in enumerate(saved_game.get('phases', [])):
        phase_name = phase_data.get('name')
        if phase_name in all_phase_relationships_history:
            saved_game['phases'][i]['agent_relationships'] = all_phase_relationships_history[phase_name]
            relationships_added_to_phases_count += 1
            logger.debug(f"Added agent_relationships from history to phase {phase_name} in export")
    logger.info(f"Added agent_relationships from history to {relationships_added_to_phases_count}/{len(saved_game.get('phases', []))} phases in the export")
    # ======================================================================

    # Save the modified game data
    logger.info(f"Saving game to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(saved_game, f, indent=4)

    # Dump overview file (args are still relevant)
    with open(overview_file_path, "w") as overview_file:
        overview_data = {
            "arguments": vars(args),
            # Add any other non-LLM specific overview data if needed
        }
        overview_file.write(json.dumps(overview_data) + "\n")

    logger.info(f"Saved game data, manifesto, and overview in: {result_folder}")
    logger.info("Done.")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
