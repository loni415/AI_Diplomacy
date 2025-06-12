from typing import List
from diplomacy import Game
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import gather_possible_orders

def get_human_orders(game: Game, power_name: str, game_history: GameHistory) -> List[str]:
    """
    Gets orders for the human player.
    """
    print(f"Current Phase: {game.phase}, Year: {game.year}")
    print("\nUnit Positions:")
    for p_name, units in game.get_units().items():
        print(f"  {p_name}: {units}")
    print("\nSupply Center Ownership:")
    for p_name, centers in game.get_centers().items():
        print(f"  {p_name}: {centers}")

    possible_orders_by_unit = gather_possible_orders(game, power_name)
    chosen_orders = []

    print(f"\n--- {power_name}'s Turn ---")

    units_with_orders = [loc for loc in game.get_orderable_locations(power_name) if possible_orders_by_unit.get(loc)]

    for unit_loc in units_with_orders:
        unit_type = game.get_unit_type_by_location(unit_loc)
        if not unit_type:
            print(f"Warning: Could not determine type for unit at {unit_loc}. Skipping order for this unit.")
            continue # Skip to the next unit_loc
        unit_display = f"{unit_type} {unit_loc}"
        possible_orders = possible_orders_by_unit[unit_loc]

        if not possible_orders:
            print(f"\nNo possible orders for {unit_display}. Defaulting to HOLD if possible.")
            # Try to find a HOLD order
            # Ensure unit_type[0] is safe if unit_type could be empty (though checked above)
            hold_order = f"{unit_type[0]} {unit_loc} H"
            if hold_order in game.get_all_possible_orders().get(unit_loc, []): # Added .get for safety
                 chosen_orders.append(hold_order)
                 print(f"Selected: {hold_order}")
            else:
                print(f"Could not find a valid HOLD order for {unit_display}.")
            continue

        print(f"\nOrders for {unit_display}:")
        for i, order in enumerate(possible_orders):
            print(f"  {i + 1}. {order}")

        while True:
            try:
                choice_str = input(f"Enter the number for your chosen order for {unit_display} (or press Enter to skip): ")
                if not choice_str: # User pressed enter
                    print(f"Skipping orders for {unit_display}.")
                    # Attempt to default to HOLD if possible
                    hold_order = f"{unit_type[0]} {unit_loc} H"
                    if hold_order in possible_orders:
                        chosen_orders.append(hold_order)
                        print(f"Defaulting to: {hold_order}")
                    elif hold_order in game.get_all_possible_orders()[unit_loc]: # Check if hold is generally possible
                        chosen_orders.append(hold_order)
                        print(f"Defaulting to: {hold_order}")
                    else:
                        print(f"No HOLD order available for {unit_display}. This unit may not receive an order.")
                    break
                choice = int(choice_str)
                if 1 <= choice <= len(possible_orders):
                    chosen_orders.append(possible_orders[choice - 1])
                    break
                else:
                    print(f"Invalid choice. Please enter a number between 1 and {len(possible_orders)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    print("\n--- Order Summary ---")
    if chosen_orders:
        for order in chosen_orders:
            print(order)
    else:
        print("No orders were chosen.")
    print("--------------------")

    return chosen_orders


from typing import Dict # Added for send_human_messages

def send_human_messages(game: Game, power_name: str, game_history: GameHistory, active_powers: List[str]) -> List[Dict[str, str]]:
    """
    Allows the human player to send messages during the negotiation phase.
    """
    print(f"\n--- {power_name}'s Message Phase ---")
    print(f"Current Phase: {game.phase}, Year: {game.year}")

    # Display recent messages for context
    recent_messages = game_history.get_messages_this_round(power_name, game.current_short_phase)
    if recent_messages:
        print("\nRecent Messages:")
        for msg in recent_messages:
            # Assuming msg is a dictionary or an object with attributes
            msg_phase = msg.get('phase', game.current_short_phase) # Get phase if available
            if isinstance(msg, dict):
                sender = msg.get('sender', 'Unknown')
                recipient = msg.get('recipient', 'Unknown')
                content = msg.get('content', '')
            else: # Assuming it's a Message object or similar
                sender = msg.sender
                recipient = msg.recipient
                content = msg.message if hasattr(msg, 'message') else msg.content
                if hasattr(msg, 'phase') and msg.phase: # For Message objects
                    msg_phase = msg.phase


            if recipient == power_name:
                print(f"  ({msg_phase}) From {sender}: {content}")
            elif sender == power_name:
                print(f"  ({msg_phase}) To {recipient}: {content}")
            else: # Global messages or messages between other powers shown to all
                print(f"  ({msg_phase}) ({sender} to {recipient}): {content}")
    else:
        print("\nNo new messages this round.")

    outgoing_messages = []
    other_active_powers = [p for p in active_powers if p != power_name]

    while True:
        send_choice = input("\nSend a message? (yes/no, default no): ").strip().lower()
        if send_choice not in ["y", "yes"]:
            break

        # Prompt for recipient
        print("\nWho do you want to send a message to?")
        print("  0. GLOBAL (all powers)")
        for i, p_target in enumerate(other_active_powers):
            print(f"  {i + 1}. {p_target}")

        chosen_recipient = None
        while chosen_recipient is None: # Loop until a valid recipient is chosen or user aborts message
            try:
                choice_str = input("Enter the number for your recipient (or type 'cancel' to abort this message): ").strip()
                if choice_str.lower() == 'cancel':
                    print("Message cancelled.")
                    break # Breaks from recipient choice loop, will go to next "Send a message?"

                recipient_choice_num = int(choice_str)

                if recipient_choice_num == 0:
                    chosen_recipient = "GLOBAL"
                elif 1 <= recipient_choice_num <= len(other_active_powers):
                    # Validate this chosen power is still active and valid in the main game object
                    # (active_powers should be current, but an extra check is safer)
                    potential_recipient = other_active_powers[recipient_choice_num - 1]
                    if potential_recipient in game.powers and not game.powers[potential_recipient].is_eliminated():
                        chosen_recipient = potential_recipient
                    else:
                        print(f"Error: '{potential_recipient}' is no longer an active power. Please choose from the updated list if it changes.")
                        # Potentially re-list active powers here if dynamic changes are frequent
                        # For now, just re-prompt for recipient.
                        other_active_powers = [p for p in active_powers if p != power_name and not game.powers[p].is_eliminated()]
                        print("\nWho do you want to send a message to?")
                        print("  0. GLOBAL (all powers)")
                        for i, p_target in enumerate(other_active_powers):
                            print(f"  {i + 1}. {p_target}")
                        # chosen_recipient remains None, loop continues
                else:
                    print(f"Invalid choice. Please enter a number between 0 and {len(other_active_powers)}.")
            except ValueError:
                print("Invalid input. Please enter a number or 'cancel'.")

        if chosen_recipient is None: # If user cancelled recipient selection
            continue # Go to the next iteration of "Send a message? (yes/no)"

        # Prompt for message content
        message_content = input(f"Enter your message to {chosen_recipient}: ").strip()
        if not message_content:
            print("Empty message. Skipping.")
            continue

        message_dict = {
            'sender': power_name,
            'recipient': chosen_recipient,
            'content': message_content,
            'message_type': 'private' if chosen_recipient != 'GLOBAL' else 'global'
        }
        outgoing_messages.append(message_dict)
        print(f"Message to {chosen_recipient} queued: '{message_content}'")

    print(f"--- End of {power_name}'s Message Phase ---")
    return outgoing_messages


def get_human_plan(game: Game, power_name: str, game_history: GameHistory) -> str:
    """
    Allows the human player to enter their strategic plan for the current phase.
    """
    print(f"\n--- {power_name}'s Planning Phase ---")
    print(f"Current Phase: {game.phase}, Year: {game.year}")

    # Display current unit positions and supply centers
    print("\nUnit Positions:")
    for p_name, units in game.get_units().items():
        print(f"  {p_name}: {units}")
    print("\nSupply Center Ownership:")
    for p_name, centers in game.get_centers().items():
        print(f"  {p_name}: {centers}")

    # Display existing plans for context (if any for this power this phase)
    # Note: game_history structure for plans might need specific adaptation here
    # For now, let's assume a simple way to get current plans or show last plan.
    current_phase_name = game.current_short_phase
    existing_plan = game_history.get_strategic_plan(power_name, current_phase_name)
    if existing_plan:
        print(f"\nYour existing plan for {current_phase_name}:")
        print(existing_plan)
    else:
        # Show plan from previous phase if current is not available
        # This requires a method in GameHistory to get previous phase's plan
        # previous_plan = game_history.get_strategic_plan(power_name, game.get_previous_phase(current_phase_name)) # Fictional method
        # if previous_plan:
        #    print("\nYour plan from the previous phase:")
        #    print(previous_plan)
        # else:
        print("\nNo existing plan recorded for you this phase.")

    print("\nEnter your strategic plan for the upcoming year/phases.")
    print("Describe your general intentions, goals, and approach towards other powers.")
    print("Type your plan and press Enter. To finish, type '/done' on a new line and press Enter.")

    plan_lines = []
    while True:
        line = input("> ")
        if line.strip().lower() == "/done":
            break
        plan_lines.append(line)

    plan_str = "\n".join(plan_lines)

    if not plan_str.strip():
        print("No plan entered. A default 'No plan submitted.' will be recorded.")
        return "No plan submitted."

    print("\n--- Your Plan Summary ---")
    print(plan_str)
    print("-------------------------")

    return plan_str
