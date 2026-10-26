# Packet-Pong

## Project Purpose:
This project is intended for recreational purpose, expanding on the traditional pong experience to provide a multiplayer atmosphere. This project is built for two players connected through a personal screen and joystick. Although this project does not revolutionize any particular real-world problem, it builds on the entertainment aspect of a classic game. This design connects players across a local network, providing a unique twist to the classic experience.

## Project Scope:
### HMI Pi Role (Services hosted, UI role, data processing): 
  * HMI PI (A): Runs the game engine; determines ball physics; handles score
  * HMI PI (B): Runs game state for player B
### Sense HAT Pi Role (Sensors/actuators polled, daemons hosted): 
  * Sense HAT Pi (A): Player A paddle input
  * Senes HAT Pi (B): Player B paddle input
### Remote Storage / Infrastructure Role (NAS Database, MQTT Broker, or SFTP/SCP Server): 
  * High score stored in NAS Database
### Out-of-Scope Boundaries (List 1–2 features your team is intentionally excluding to ensure completion by Week 15): 
  * Gesture manipulation of paddle using imu; playing against a cpu
## System Overview

Packet Pong is a two-player networked Pong game. Each player has an HMI Pi
(touchscreen) and a Sense HAT Pi (joystick + LED matrix). The game engine runs in
Docker on HMI Pi A and controls the ball, paddles, and score.

| Node | Table | Software | Role |
|---|---|---|---|
| HMI Pi A | 5 | `game_engine.py` (Docker), `hud.py` | Game engine + Player A's screen |
| HMI Pi B | 4 | `hud.py` | Player B's screen |
| Sense HAT Pi A | 5 | `controller.py` | Player A's joystick + LED matrix |
| Sense HAT Pi B | 4 | `controller.py` | Player B's joystick + LED matrix |
| Classroom NAS | — | MySQL (`packet_pong`) | Stores match and point records |

## Socket Allocation

| # | Transport | Server (Node : Port) | Client | Purpose |
|---|---|---|---|---|
| 1 | UDP | HMI Pi A : 9001 | Sense HAT Pi A | Player A joystick input (30 Hz) |
| 2 | UDP | HMI Pi A : 9002 | Sense HAT Pi B | Player B joystick input (30 Hz) |
| 3 | UDP | HMI Pi A HUD : 127.0.0.1:9101 | Game engine | Game state to Player A's screen (30 Hz) |
| 4 | UDP | HMI Pi B HUD : 9101 | Game engine | Game state to Player B's screen (30 Hz) |
| 5 | TCP | Game engine : 8000 | HMI Pi A HUD | Lobby/control (Ready, Pause, Rematch) |
| 6 | TCP | Game engine : 8000 | HMI Pi B HUD | Lobby/control (Ready, Pause, Rematch) |
| 7 | TCP | NAS : 3306 | Game engine | Match and point logging to MySQL |
| 8 | TCP | Game engine : 9300 | Sense HAT Pi A & B | LED events (goal, win, lose, paused) |

No WebSockets are used. All custom ports are in the unprivileged range (1025–65

**Why UDP vs. TCP:** Sockets 1–4 send small, constant updates where speed matte
and a lost packet is replaced by the next one 33 ms later, so they use UDP.
Sockets 5–8 carry messages that must arrive (commands, saved scores, LED events
so they use TCP for reliable delivery.

## Functional Requirements

1. **Sockets:** 8 raw TCP/UDP sockets as listed above. UDP for fast game data,
   TCP for data that must arrive.
2. **Distributed software:** The engine runs on HMI Pi A; each HMI Pi runs the
   game screen; each Sense HAT Pi runs the controller.
3. **Physical input:** The joystick is read 30 times per second. Paddles move on
   both screens in under 100 ms. The LED matrix flashes green/red on goals and
   shows W/L at match end.
4. **Touchscreen UI:** Full-screen Pygame GUI redrawn 30 times per second from
   each player's side, with Ready/Pause/Rematch buttons and a network panel
   (packets/sec, packet loss %, connection status) updated every second.
5. **Remote logging:** The engine writes to the `packet_pong` MySQL database on
   the classroom NAS. A `matches` row is created per game and a `points` row pe
   point. Both screens show a top-10 longest-rally board. The game keeps running
   if the database is unreachable.
6. **Docker:** The engine runs in the `packet-pong-engine` container on HMI Pi A,
   built from a Dockerfile, started with `docker compose up -d`, using host
   networking, and restarting automatically after a crash or reboot.

## Database Schema

- **matches:** match_id, started_at, ended_at, player_a, player_b, score_a,
  score_b, winner, longest_rally
- **points:** point_id, match_id, scored_at, scorer (A/B), rally_length
