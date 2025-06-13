# AI Diplomacy: Human-Powered Strategic Gameplay
Created by Alex Duffy @Alx-Ai & Tyler Marques @Tylermarques

## Overview

This project provides a console-based interface for playing the classic game of Diplomacy. It is built upon the original [Diplomacy](https://github.com/diplomacy/diplomacy) Python library. All powers are controlled by human players, who input their orders, messages, and strategic plans through a command-line interface. The game orchestrates player turns, processes phases, and records game history, allowing for a pure human-driven strategic experience.

## Key Features

- **Console-Based Gameplay**: All interactions (orders, messages, plans) are managed through a command-line interface.
- **Sequential Player Turns**: Players for each power make their decisions one by one when prompted.
- **Structured Game Phases**: Supports distinct phases for negotiation, planning, and order submission.
- **Game State Display**: Shows relevant game information (unit positions, supply centers, phase results) to inform player decisions.
- **History Tracking**: Records orders, messages, and plans in `GameHistory` for review.
- **Agent State Management**: Each power has an associated `DiplomacyAgent` object that holds user-defined goals, relationships, and a private journal/diary for note-taking.
- **Save and Load Game**: Game progress can be saved to JSON and potentially reloaded (though reload logic for human-in-the-loop state is not explicitly detailed here).

## Architecture for Human-Played Game

The following diagram illustrates the information flow for a game played by humans:

```mermaid
graph TB

    %% Define all nodes first
    %% Nodes for Game State Information
    GS[Game State<br/>(Unit Positions)<br/>(Supply Centers)<br/>(Power Status)]
    GH[Game History<br/>(Past Orders)<br/>(Past Messages)<br/>(Phase Results)<br/>(Player Plans)]
    PHASE_SUMMARY[Phase Summary<br/>(Successful Moves)<br/>(Failed Moves)<br/>(Board Changes)]

    %% Nodes for Agent State
    AGENT_GOALS[User-Defined Goals]
    AGENT_REL[User-Defined Relationships]
    AGENT_JOURNAL[Private Journal (Manual User Notes)]
    AGENT_DIARY[Private Diary (Manual User Notes)]

    %% Nodes for Human Player Interface
    HPI[Human Input Module (`human_player_interface.py`)<br/>(Displays Game Info)<br/>(Prompts for Decisions)]

    %% Nodes for User Decision Inputs
    USER_ORDERS[User Enters Orders]
    USER_MESSAGES[User Sends Messages]
    USER_PLANS[User Defines Plans]

    %% Nodes for Context for Human Player
    POSSIBLE_ORDERS_CTX[Possible Order Context (Displayed to User)]

    %% Nodes for Core Game Engine
    GAME_ENGINE[Game Engine (Processes Orders, Updates State)]
    UTILS_GATHER_ORDERS[utils.gather_possible_orders]
    game_messages[Game Messages Log]

    %% Group nodes into subgraphs
    subgraph "Game State Information"
        GS
        GH
        PHASE_SUMMARY
    end

    subgraph "Agent State (DiplomacyAgent)"
        AGENT_GOALS
        AGENT_REL
        AGENT_JOURNAL
        AGENT_DIARY
    end

    subgraph "Human Player Interface (`human_player_interface.py`)"
        HPI
    end

    subgraph "User Decision Inputs"
        USER_ORDERS
        USER_MESSAGES
        USER_PLANS
    end

    subgraph "Context for Human Player"
        POSSIBLE_ORDERS_CTX
    end

    %% Links remain outside subgraphs if they connect different entities
    %% Information Flow
    GS --> HPI
    GH --> HPI
    PHASE_SUMMARY --> HPI

    GS --> UTILS_GATHER_ORDERS
    UTILS_GATHER_ORDERS --> POSSIBLE_ORDERS_CTX
    POSSIBLE_ORDERS_CTX --> HPI

    HPI --> USER_ORDERS
    HPI --> USER_MESSAGES
    HPI --> USER_PLANS

    USER_ORDERS -->|Set by lm_game.py| GAME_ENGINE
    USER_MESSAGES -->|Added by negotiations.py| GH
    USER_MESSAGES -->|Added by negotiations.py| game_messages
    USER_PLANS -->|Added by planning.py| GH

    GAME_ENGINE --> GS
    GAME_ENGINE --> GH
    GAME_ENGINE --> PHASE_SUMMARY

    %% Styling
    classDef gameState fill:#e74c3c,stroke:#333,stroke-width:2px,color:#fff
    classDef agentState fill:#3498db,stroke:#333,stroke-width:2px,color:#fff
    classDef humanInterface fill:#2ecc71,stroke:#333,stroke-width:2px,color:#fff
    classDef userInputs fill:#f39c12,stroke:#333,stroke-width:2px,color:#fff
    classDef contextDisplay fill:#9b59b6,stroke:#333,stroke-width:2px,color:#fff
    classDef gameEngine fill:#7f8c8d,stroke:#333,stroke-width:2px,color:#fff

    class GS,GH,PHASE_SUMMARY gameState
    class AGENT_GOALS,AGENT_REL,AGENT_JOURNAL,AGENT_DIARY agentState
    class HPI humanInterface
    class USER_ORDERS,USER_MESSAGES,USER_PLANS userInputs
    class POSSIBLE_ORDERS_CTX contextDisplay
    class GAME_ENGINE,game_messages,UTILS_GATHER_ORDERS gameEngine
```

### Core Components Explained

1.  **`lm_game.py`**: The main script for running the game. It initializes the game state, manages player agents, and iterates through game phases (negotiation, planning, orders, processing). It calls upon other modules to handle specific parts of the game flow.

2.  **`ai_diplomacy/agent.py`**: Defines the `DiplomacyAgent` class. In this human-driven version, the agent primarily serves as a state container for each power, holding:
    *   `goals`: A list of strategic goals defined by the human player.
    *   `relationships`: A dictionary mapping other powers to relationship statuses (e.g., "Neutral", "Ally", "Enemy"), managed by the human player.
    *   `private_journal` & `private_diary`: Lists for players to take notes or log significant events manually.

3.  **`ai_diplomacy/human_player_interface.py`**: This module is crucial for human gameplay. It contains functions responsible for:
    *   `get_human_orders()`: Displays the current game state and possible orders, then prompts the active human player to enter their unit orders via the console.
    *   `send_human_messages()`: Allows the active human player to compose and send messages (private or global) to other players during negotiation rounds. It displays recent messages for context.
    *   `get_human_plan()`: Prompts the active human player to enter their strategic plans for the upcoming game phases.

4.  **`ai_diplomacy/game_history.py`**: Manages the historical record of the game. It stores:
    *   Messages exchanged between powers.
    *   Orders submitted by each power in each phase.
    *   Strategic plans laid out by players.
    *   Phase results and summaries. This information is used to display context to players.

5.  **`ai_diplomacy/utils.py`**: Contains utility functions supporting the game, such as:
    *   `gather_possible_orders()`: Determines all valid orders for a given power's units, which is then displayed to the human player.

6.  **`ai_diplomacy/negotiations.py`**: Handles the negotiation phase.
    *   `conduct_negotiations()`: Iterates through active players, calling `send_human_messages` from the human interface for each player to input their diplomatic messages.

7.  **`ai_diplomacy/planning.py`**: Handles the strategic planning phase.
    *   `planning_phase()`: Iterates through active players, calling `get_human_plan` from the human interface for each player to input their strategic plans.

### Running the Game

To run a game:
```bash
# Basic game stopping after 1901, with 2 negotiation rounds per movement phase
python lm_game.py --max_year 1901 --num_negotiation_rounds 2

# Enable the strategic planning phase
python lm_game.py --max_year 1905 --planning_phase --num_negotiation_rounds 3

# Output to a specific game file
python lm_game.py --output results/my_console_game.json
```
The `--models` argument is no longer used as all players are human.

### Environment Setup

Ensure you have Python 3.7+ installed. The primary dependency is the `diplomacy` library.
```bash
pip install diplomacy
```
No API keys are needed as LLM functionality has been removed.

### Game Output

Game progress and details are saved to the `results/` directory, typically in a timestamped subfolder. Key outputs include:
- **`lmvsgame.json`**: The complete game data in JSON format, including all orders, messages, phase results, and player-defined agent states (goals, relationships). This file can be used for review or potentially with compatible visualization tools.
- **`overview.jsonl`**: Contains a summary of the game arguments.
- **`game_manifesto.txt`**: If the planning phase is enabled, players' strategic plans are appended here.
- **`general_game.log`**: Detailed logs of game execution, including player inputs and phase transitions.

### Post-Game Analysis Tools

While LLM-specific analysis tools have been removed, the generated `lmvsgame.json` can still be useful:
- **Manual Review**: The JSON file provides a comprehensive record for analyzing game flow and player decisions.
- **`analyze_game_results.py`**: This script can aggregate win/loss statistics if multiple games are played and saved in the expected format (though its original purpose was for model vs. model games).

#### Animation and Visualization

The original Diplomacy library's visualization tools can still be used:
```bash
# Start the animation server (if using the ai_animation component from the broader project)
cd ai_animation
npm install
npm run dev

# Open http://localhost:5173 in your browser
# Load a game JSON file (e.g., lmvsgame.json) to see animated playback.
```
Alternatively, the standard web interface from the original `diplomacy` library can be used to visualize games (see "Web interface" section below).

---

<p align="center">
  <img width="500" src="docs/images/map_overview.png" alt="Diplomacy Map Overview">
</p>

## Original Diplomacy Library Documentation

The underlying game logic and base functionalities are provided by the [Diplomacy](https://github.com/diplomacy/diplomacy) library.
The complete documentation for the original library is available at [diplomacy.readthedocs.io](https://diplomacy.readthedocs.io/).

## Getting Started (with the base Diplomacy library)

### Installation

The latest version of the package can be installed with:
```python3
pip install diplomacy
```
The package is compatible with Python 3.5, 3.6, and 3.7 (though this project targets 3.7+).

### Running a simple game (base library example)

The following script plays a game locally by submitting random valid orders until the game is completed.
```python3
import random
from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format

# Creating a game
game = Game()
while not game.is_game_done:
    possible_orders = game.get_all_possible_orders()
    for power_name, power in game.powers.items():
        power_orders = [random.choice(possible_orders[loc]) for loc in game.get_orderable_locations(power_name)
                        if possible_orders[loc]]
        game.set_orders(power_name, power_orders)
    game.process()
to_saved_game_format(game, output_path='game.json')
```

## Web interface (from base Diplomacy library)

It is also possible to install a web interface in React to play against bots and/or other humans and to visualize games. This interface is part of the original `diplomacy` library.

The web interface can be installed with:
```bash
# Install NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash
# Activate NVM (may require sourcing .bashrc or similar)
# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
# [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Clone the original diplomacy repo if you haven't
# git clone https://github.com/diplomacy/diplomacy.git
# cd diplomacy/

# Install package locally (if not already done for this project's setup)
# pip install -r requirements_dev.txt # From original repo

# Build node modules
cd diplomacy/web # Navigate to the web directory of the original library
npm install .
npm install . --only=dev

# In a terminal window or tab - Launch React server
npm start

# In another terminal window or tab - Launch diplomacy server
python -m diplomacy.server.run
```
The web interface will be accessible at http://localhost:3000.

![](docs/images/web_interface.png)

### Visualizing a game

It is possible to visualize a game by using the "Load a game from disk" menu on the top-right corner of the web interface. This can load the `lmvsgame.json` files produced by this project.

![](docs/images/visualize_game.png)


## Network Game (from base Diplomacy library)

It is possible to join a game remotely over a network using websockets. The script below plays a game over a network.
Note: The server must be started with `python -m diplomacy.server.run` for the script to work.
```python3
import asyncio
import random
from diplomacy.client.connection import connect
from diplomacy.utils import exceptions

POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

async def create_game(game_id, hostname='localhost', port=8432):
    connection = await connect(hostname, port)
    channel = await connection.authenticate('random_user', 'password')
    await channel.create_game(game_id=game_id, rules={'REAL_TIME', 'NO_DEADLINE', 'POWER_CHOICE'})

async def play(game_id, power_name, hostname='localhost', port=8432):
    connection = await connect(hostname, port)
    channel = await connection.authenticate('user_' + power_name, 'password')
    while not (await channel.list_games(game_id=game_id)):
        await asyncio.sleep(1.)
    game = await channel.join_game(game_id=game_id, power_name=power_name)
    while not game.is_game_done:
        current_phase = game.get_current_phase()
        if game.get_orderable_locations(power_name):
            possible_orders = game.get_all_possible_orders()
            orders = [random.choice(possible_orders[loc]) for loc in game.get_orderable_locations(power_name)
                      if possible_orders[loc]]
            print('[%s/%s] - Submitted: %s' % (power_name, game.get_current_phase(), orders))
            await game.set_orders(power_name=power_name, orders=orders, wait=False)
        while current_phase == game.get_current_phase():
            await asyncio.sleep(0.1)

async def launch(game_id):
    await create_game(game_id)
    await asyncio.gather(*[play(game_id, power_name) for power_name in POWERS])

if __name__ == '__main__':
    # Note: This network example may need to be run from within the original diplomacy library context
    # if it relies on specific server configurations not replicated in this AI-focused project.
    # For this project, focus on running `lm_game.py`.
    # asyncio.run(launch(game_id=str(random.randint(1, 1000))))
    print("Refer to the original diplomacy library for running network games.")
```

## License

This project is licensed under the APGLv3 License - see the [LICENSE](LICENSE) file for details
