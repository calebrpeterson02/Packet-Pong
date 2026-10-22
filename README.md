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
