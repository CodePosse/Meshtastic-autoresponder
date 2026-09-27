# Meshtastic Autobot

A small autoresponder for Meshtastic networks with two supported backends:

1. **Debian + meshtasticd**
2. **Meshpoint**

The responder listens for selected text messages and sends a direct message back to the sender.

---

## Current Rules

### Spanish Inquisition

Exact match, case-insensitive:

```text
spanish inquisition
```

Reply:

```text
*Nobody expects the Spanish Inquisition!*
```

### Test / Ping

Exact match on any of:

```text
test
ping
dm test
```

Replies:

```text
I hear you
```

then 10 seconds later:

```text
visit www.SoCalMesh.org
```

### Public-channel telemetry warning

If a message contains either:

```text
End of Day Report:
```

or:

```text
in Upper Newport Bay
```

reply by DM:

```text
no telemetry on Public please
```

The telemetry-warning rule is checked first.

---

# Choose Your Platform

## Debian + meshtasticd

Use:

```text
linux.md
```

Python script:

```text
meshtasticd_autobot.py
```

This version connects directly to the local Meshtastic TCP interface:

```text
127.0.0.1:4403
```

Start here:

[linux.md](linux.md)

---

## Meshpoint

Use:

```text
meshpoint.md
```

Python script:

```text
meshpoint_autobot.py
```

This version connects to Meshpoint's local authenticated API and WebSocket:

```text
http://127.0.0.1:8080
ws://127.0.0.1:8080/ws
```

Start here:

[meshpoint.md](meshpoint.md)

---

# Files

```text
README.md
linux.md
meshpoint.md
meshtasticd_autobot.py
meshpoint_autobot.py
```

---

# Backend Comparison

| Feature | meshtasticd | Meshpoint |
|---|---|---|
| Autobot connection | Meshtastic TCP | REST + WebSocket |
| Default local port | 4403 | 8080 |
| Login required | No | Yes |
| JWT handling | No | Yes, handled by script |
| Recommended service name | `autobot` | `autobot` |
| Persistent via systemd | Yes | Yes |
| Survives SSH logout | Yes | Yes |
| Direct-message replies | Yes | Yes |

---

# Service Layout

## meshtasticd

```text
USB / supported LoRa radio
        |
        v
meshtasticd.service
        |
        | TCP 127.0.0.1:4403
        v
autobot.service
```

## Meshpoint

```text
SX1302 / SX1303 concentrator
        |
        v
meshpoint.service
        |
        | REST + WebSocket :8080
        v
autobot.service
```

---

# Important

Do not run the autoresponder permanently from an interactive SSH shell.

Use the provided `systemd` setup so Autobot:

- starts at boot,
- survives SSH logout,
- restarts after failures,
- reconnects to the backend automatically.

See the platform-specific guide for complete installation and troubleshooting steps.
