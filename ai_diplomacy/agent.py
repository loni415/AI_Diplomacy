import logging
import os
from typing import List, Dict, Optional
# import json # No longer needed
# import re # No longer needed
# import json_repair # No longer needed
# import json5  # No longer needed

# # Assuming BaseModelClient is importable from clients.py in the same directory
# from .clients import BaseModelClient, load_model_client # No longer needed
# # Import load_prompt and the new logging wrapper from utils
# from .utils import load_prompt, run_llm_and_log, log_llm_response # No longer needed
# from .prompt_constructor import build_context_prompt # No longer needed

logger = logging.getLogger(__name__)

# == Best Practice: Define constants at module level ==
ALL_POWERS = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})
ALLOWED_RELATIONSHIPS = ["Enemy", "Unfriendly", "Neutral", "Friendly", "Ally"]

# == New: Helper function to load prompt files reliably ==
# def _load_prompt_file(filename: str) -> Optional[str]: # No longer needed
#     """Loads a prompt template from the prompts directory."""
#     try:
#         # Construct path relative to this file's location
#         current_dir = os.path.dirname(os.path.abspath(__file__))
#         prompts_dir = os.path.join(current_dir, 'prompts')
#         filepath = os.path.join(prompts_dir, filename)
#         with open(filepath, 'r', encoding='utf-8') as f:
#             return f.read()
#     except FileNotFoundError:
#         logger.error(f"Prompt file not found: {filepath}")
#         return None
#     except Exception as e:
#         logger.error(f"Error loading prompt file {filepath}: {e}")
#         return None

class DiplomacyAgent:
    """
    Represents a stateful agent playing as a specific power in Diplomacy.
    It holds the agent's goals, relationships, and private journal.
    """
    def __init__(
        self, 
        power_name: str, 
        # client: BaseModelClient, # Removed client
        initial_goals: Optional[List[str]] = None,
        initial_relationships: Optional[Dict[str, str]] = None,
    ):
        """
        Initializes the DiplomacyAgent.

        Args:
            power_name: The name of the power this agent represents (e.g., 'FRANCE').
            # client: An instance of a BaseModelClient subclass for LLM interaction. # Removed
            initial_goals: An optional list of initial strategic goals.
            initial_relationships: An optional dictionary mapping other power names to 
                                     relationship statuses (e.g., 'ALLY', 'ENEMY', 'NEUTRAL').
        """
        if power_name not in ALL_POWERS:
            raise ValueError(f"Invalid power name: {power_name}. Must be one of {ALL_POWERS}")

        self.power_name: str = power_name
        # self.client: BaseModelClient = client # Removed

        self.goals: List[str] = initial_goals if initial_goals is not None else [] 
        if initial_relationships is None:
            self.relationships: Dict[str, str] = {p: "Neutral" for p in ALL_POWERS if p != self.power_name}
        else:
            self.relationships: Dict[str, str] = initial_relationships

        self.private_journal: List[str] = []
        self.private_diary: List[str] = []

        # --- System prompt loading removed ---

        logger.info(f"Initialized DiplomacyAgent for {self.power_name} with goals: {self.goals}")
        self.add_journal_entry(f"Agent initialized. Initial Goals: {self.goals}")

    # _extract_json_from_text and _clean_json_text removed

    def add_journal_entry(self, entry: str):
        """Adds a formatted entry string to the agent's private journal."""
        # Ensure entry is a string
        if not isinstance(entry, str):
            entry = str(entry)
        self.private_journal.append(entry)
        logger.debug(f"[{self.power_name} Journal]: {entry}")

    def add_diary_entry(self, entry: str, phase: str):
        """Adds a formatted entry string to the agent's private diary."""
        if not isinstance(entry, str):
            entry = str(entry) # Ensure it's a string
        formatted_entry = f"[{phase}] {entry}"
        self.private_diary.append(formatted_entry)
        # Keep diary to a manageable size, e.g., last 100 entries
        #self.private_diary = self.private_diary[-100:] # Manual management if needed
        logger.info(f"[{self.power_name}] DIARY ENTRY ADDED for {phase}. Total entries: {len(self.private_diary)}. New entry: {entry[:100]}...")

    def format_private_diary_for_prompt(self, max_entries=40) -> str: # May still be useful for human context
        """Formats the last N private diary entries for inclusion in a prompt or display."""
        logger.info(f"[{self.power_name}] Formatting diary. Total entries: {len(self.private_diary)}")
        if not self.private_diary:
            logger.warning(f"[{self.power_name}] No diary entries found when formatting.")
            return "(No diary entries yet)"
        # Get the most recent entries
        recent_entries = self.private_diary[-max_entries:]
        formatted_diary = "\n".join(recent_entries)
        logger.info(f"[{self.power_name}] Formatted {len(recent_entries)} diary entries. Preview: {formatted_diary[:200]}...")
        return formatted_diary
    
    # Removed: consolidate_year_diary_entries
    # Removed: generate_negotiation_diary_entry
    # Removed: generate_order_diary_entry
    # Removed: generate_phase_result_diary_entry
    # Removed: analyze_phase_and_update_state

    def log_state(self, prefix=""):
        logger.debug(f"[{self.power_name}] {prefix} State: Goals={self.goals}, Relationships={self.relationships}")

    def update_goals(self, new_goals: List[str]):
        """Updates the agent's strategic goals."""
        self.goals = new_goals
        self.add_journal_entry(f"Goals updated: {self.goals}")
        logger.info(f"[{self.power_name}] Goals updated to: {self.goals}")

    def update_relationship(self, other_power: str, status: str):
        """Updates the agent's perceived relationship with another power."""
        other_power_upper = other_power.upper()
        if other_power_upper not in ALL_POWERS:
            logger.warning(f"[{self.power_name}] Attempted to update relationship with invalid power: {other_power}")
            return
        if other_power_upper == self.power_name:
            logger.warning(f"[{self.power_name}] Attempted to set relationship with self.")
            return
        if status not in ALLOWED_RELATIONSHIPS:
            logger.warning(f"[{self.power_name}] Attempted to set invalid relationship status '{status}' for {other_power_upper}.")
            return

        self.relationships[other_power_upper] = status
        self.add_journal_entry(f"Relationship with {other_power_upper} updated to {status}.")
        logger.info(f"[{self.power_name}] Relationship with {other_power_upper} set to {status}.")


    def get_agent_state_summary(self) -> str:
        """Returns a string summary of the agent's current state."""
        summary = f"Agent State for {self.power_name}:\n"
        summary += f"  Goals: {self.goals}\n"
        summary += f"  Relationships: {self.relationships}\n"
        summary += f"  Journal Entries: {len(self.private_journal)}\n"
        summary += f"  Diary Entries: {len(self.private_diary)}"
        return summary

    # Removed: generate_plan (LLM version)