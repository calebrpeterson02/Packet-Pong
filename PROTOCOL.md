# Packet Pong — Wire Protocol

---

## 1. General Rules

### Encoding

- Every message is a **UTF-8 JSON object**.
- Every message has a `"t"` (type) field naming the message.
- Field names are short to keep UDP datagrams small.

### Framing

| Transport | Framing rule                                                                                                                               |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| UDP       | One JSON object per datagram. No delimiter needed — UDP preserves message boundaries.                                                      |
| TCP       | One JSON object per line, terminated by `\n` (newline-delimited JSON). A receiver buffers bytes until it sees `\n`, then parses that line. |

### Sequence numbers (UDP only)

- Every UDP message carries `"seq"`: an integer starting at 0 that increases by 1
  per message sent, per sender.
- Receivers use it to:
  - **Drop stale packets** — if `seq` ≤ the last one processed, ignore it (UDP can reorder).
  - **Measure loss** for the HUD network panel — gaps in `seq` are lost packets.
- `seq` resets to 0 when the sender restarts. A receiver that sees `seq` drop by
  more than 1000 treats it as a restart, not as an old packet.

### Coordinate system

The engine works in a fixed logical field, independent of any screen size:

```
(0,0) ─────────────────── x ──────────────────► (800,0)
  │  Paddle A                              Paddle B
  │  (left, x = 20)                    (right, x = 780)
  y
  │
  ▼
(0,480)                                       (800,480)
```

- Field: **800 × 480** units (matches the Pi touchscreen, so HUDs can draw 1:1).
- All positions are **centers**, as floats rounded to 1 decimal place.
- Paddle height: 80 units. Ball size: 10 units.
- Both HUDs draw the same view: Player A on the left, Player B on the right.

### Timing

| Rate                 | Applies to                                             |
| -------------------- | ------------------------------------------------------ |
| 30 Hz (every ~33 ms) | Joystick input (sockets 1–2), game state (sockets 3–4) |
| 1 Hz                 | HUD network panel refresh (computed locally, not sent) |
| On event             | All TCP messages (sockets 5, 6, 8)                     |

---

## 2. Sockets 1 & 2 — Joystick Input (UDP)

**Direction:** Sense HAT Pi → HMI Pi A engine
**Ports:** Player A → `192.168.5.52:9001`, Player B → `192.168.5.52:9002`

### `input`

```json
{ "t": "input", "p": "A", "seq": 1042, "dir": -1 }
```

| Field | Type               | Meaning                           |
| ----- | ------------------ | --------------------------------- |
| `p`   | `"A"` \| `"B"`     | Which player sent it              |
| `seq` | int                | Sequence number                   |
| `dir` | `-1` \| `0` \| `1` | `-1` = up, `0` = none, `1` = down |

**Rules**

- Sent at 30 Hz **even when `dir` is 0** — this doubles as a heartbeat.
- The engine treats a player as **disconnected** if no `input` arrives for 2 seconds.
- The engine checks that `p` matches the port (A on 9001, B on 9002) and drops mismatches.
- The controller sends the joystick's _current_ direction, not "middle press" events.
  The middle press is not used in v1.

---

## 3. Sockets 3 & 4 — Game State (UDP)

**Direction:** Engine → HUD
**Ports:** Player A HUD → `127.0.0.1:9101`, Player B HUD → `192.168.5.42:9101`

### `state`

```json
{
  "t": "state",
  "seq": 5521,
  "phase": "playing",
  "ball": [403.5, 212.0],
  "pa": 240.0,
  "pb": 198.5,
  "sa": 3,
  "sb": 5,
  "rally": 7,
  "ctrl": { "A": true, "B": true }
}
```

| Field      | Type                 | Meaning                                                 |
| ---------- | -------------------- | ------------------------------------------------------- |
| `seq`      | int                  | Sequence number                                         |
| `phase`    | string               | See phase table below                                   |
| `ball`     | `[x, y]`             | Ball center                                             |
| `pa`, `pb` | float                | Paddle A / B center y                                   |
| `sa`, `sb` | int                  | Score A / B                                             |
| `rally`    | int                  | Hits in the current rally                               |
| `ctrl`     | `{A: bool, B: bool}` | Whether each player's controller is currently connected |

### Phases

| Phase     | Meaning                                    | HUD shows                       |
| --------- | ------------------------------------------ | ------------------------------- |
| `lobby`   | Waiting for both players to press Ready    | Ready button, who is ready      |
| `serve`   | Short pause (1 s) before the ball launches | Countdown / ball centered       |
| `playing` | Ball in motion                             | Normal game                     |
| `paused`  | A player pressed Pause                     | "PAUSED" overlay, Resume button |
| `over`    | Someone reached the winning score          | Winner, Rematch button          |

**Rules**

- The **same `state` message** is sent to both HUDs (one `sendto` per HUD).
- The engine is **authoritative**: HUDs never move the ball or paddles themselves —
  they only draw the latest `state`.
- Sent at 30 Hz in **every** phase (including `lobby` and `paused`), so the HUD's
  packet-loss and connection-status readings stay live.
- A HUD shows "Engine disconnected" if no `state` arrives for 2 seconds.
- Approximate size: ~150 bytes — far below the ~1400-byte safe UDP payload.

---

## 4. Sockets 5 & 6 — Lobby / Control (TCP)

**Direction:** Both ways. HUD connects to engine at `192.168.5.52:8000`
(Player A's HUD connects to `127.0.0.1:8000`).
**Framing:** newline-delimited JSON.

### Connection handshake

The first line a HUD sends after connecting must be:

```json
{ "t": "hello", "p": "A", "v": 1 }
```

The engine replies:

```json
{ "t": "welcome", "p": "A" }
```

or, on a bad version, duplicate player, or invalid `p`:

```json
{ "t": "error", "msg": "player A already connected" }
```

and then closes the connection.

### HUD → Engine commands

| Message            | Valid in phase     | Effect                                                                            |
| ------------------ | ------------------ | --------------------------------------------------------------------------------- |
| `{"t": "ready"}`   | `lobby`            | Marks this player ready. When both are ready → `serve`.                           |
| `{"t": "pause"}`   | `serve`, `playing` | → `paused`                                                                        |
| `{"t": "resume"}`  | `paused`           | → `serve`                                                                         |
| `{"t": "rematch"}` | `over`             | Marks this player as wanting a rematch. When both do → `lobby` with scores reset. |

A command sent in the wrong phase gets `{"t": "error", "msg": "..."}` and is otherwise ignored.
The engine does **not** send a separate acknowledgement — the HUD sees the result
in the next `state` packet (e.g. `phase` changes to `paused`).

### Engine → HUD messages

| Message | When                                   | Example                                                                                     |
| ------- | -------------------------------------- | ------------------------------------------------------------------------------------------- |
| `lobby` | Whenever readiness changes             | `{"t": "lobby", "ready": {"A": true, "B": false}}`                                          |
| `board` | On connect, and after every match ends | `{"t": "board", "rows": [{"rally": 23, "match_id": 14, "at": "2026-11-10T11:20:00"}, ...]}` |
| `error` | Bad command                            | `{"t": "error", "msg": "cannot pause in lobby"}`                                            |

- `board.rows` holds at most 10 entries, sorted by `rally` descending.
- If the database is unreachable, the engine sends its last known board (or an empty list).

### Disconnects

- If a HUD's TCP connection drops during `playing`, the engine switches to `paused`.
- HUDs reconnect every 2 seconds until the engine accepts them, then resend `hello`.

---

## 5. Socket 7 — Database Logging (TCP / MySQL)

**Direction:** Engine → Classroom NAS `:3306`, database `packet_pong`.
This socket uses the MySQL protocol through a client library, not a custom format.

| Event                                   | Database action                                                                          |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| Match enters `serve` for the first time | `INSERT` into `matches` (`started_at`, `player_a`, `player_b`) — keep the new `match_id` |
| A point is scored                       | `INSERT` into `points` (`match_id`, `scored_at`, `scorer`, `rally_length`)               |
| Match enters `over`                     | `UPDATE matches` set `ended_at`, `score_a`, `score_b`, `winner`, `longest_rally`         |
| Match ends / engine start               | `SELECT` top 10 by `longest_rally` → send `board` to HUDs                                |

**Rules**

- Database writes must **never block the game loop.** Do them off the 30 Hz loop
  (a separate thread or queue).
- If the NAS is unreachable, keep writes in a queue, retry every 10 seconds, and keep the game running.
- Credentials come from `.env` (`DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`) — never committed.

---

## 6. Socket 8 — LED Events (TCP)

**Direction:** Sense HAT Pi connects to engine at `192.168.5.52:9300`; engine sends events.
**Framing:** newline-delimited JSON.

### Handshake

Controller sends: `{"t": "hello", "p": "B", "v": 1}`
Engine replies: `{"t": "welcome", "p": "B"}` (or `error` + close, as on port 8000).

### Engine → Controller events

Events are already written **from that player's point of view**, so the controller
never has to work out whose goal it was.

| Message                              | LED matrix shows                                 |
| ------------------------------------ | ------------------------------------------------ |
| `{"t": "led", "ev": "goal_for"}`     | Green flash                                      |
| `{"t": "led", "ev": "goal_against"}` | Red flash                                        |
| `{"t": "led", "ev": "win"}`          | `W`                                              |
| `{"t": "led", "ev": "lose"}`         | `L`                                              |
| `{"t": "led", "ev": "paused"}`       | Pause icon / dim                                 |
| `{"t": "led", "ev": "clear"}`        | Blank (sent on `serve` and on return to `lobby`) |

- The controller does not send anything after `hello`.
- It reconnects every 2 seconds if the connection drops.

---

## 7. Constants

These live in one shared config (e.g. `config.py` / `.env`) — never hard-coded in several places.

| Name                                     | Value                  |
| ---------------------------------------- | ---------------------- |
| `PROTOCOL_VERSION`                       | 1                      |
| `FIELD_W`, `FIELD_H`                     | 800, 480               |
| `PADDLE_H`                               | 80                     |
| `BALL_SIZE`                              | 10                     |
| `TICK_HZ`                                | 30                     |
| `TIMEOUT_S` (UDP silence → disconnected) | 2                      |
| `RECONNECT_S` (TCP retry interval)       | 2                      |
| `WIN_SCORE`                              | 11 _(team to confirm)_ |
| `SERVE_DELAY_S`                          | 1                      |

---

## 8. Open Decisions

- [ ] Winning score — 11, or something shorter for the demo (e.g. 5)?
- [ ] `player_a` / `player_b` in `matches` — fixed names ("Table 5", "Table 4"), or entered on the HUD?
- [ ] Should Player B's HUD mirror the field so each player sees their own paddle on the left?
