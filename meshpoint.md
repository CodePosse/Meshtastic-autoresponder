# Meshpoint + Autobot Setup

This guide installs and runs **Autobot** alongside an existing Meshpoint installation.

Autobot is intentionally kept separate from Meshpoint. It does not modify Meshpoint source code, radio configuration, keys, or database files.

Meshpoint provides:

```text
LoRa radio / SX1302
        |
        v
meshpoint.service
        |
        +-- REST API: http://127.0.0.1:8080
        |
        +-- WebSocket: ws://127.0.0.1:8080/ws
        |
        v
autobot.service
```

Autobot authenticates to Meshpoint, listens for received Meshtastic text packets, and sends direct-message replies through Meshpoint's messaging API.

---

# 1. Autobot Rules

Autobot sends direct messages back to the sender.

## Spanish Inquisition

Exact message, case-insensitive:

```text
spanish inquisition
```

Reply:

```text
*Nobody expects the Spanish Inquisition!*
```

## Test / Ping

Any of these exact messages, case-insensitive:

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

## Public-channel telemetry warning

If an incoming message contains either phrase, case-insensitively:

```text
End of Day Report:
```

or:

```text
in Upper Newport Bay
```

Autobot sends:

```text
no telemetry on Public please
```

The telemetry-warning rule has priority.

---

# 2. Confirm Meshpoint Is Running

Check:

```bash
meshpoint status
```

Also:

```bash
systemctl status meshpoint --no-pager
```

If needed:

```bash
sudo systemctl restart meshpoint
```

Meshpoint's local dashboard normally listens on port `8080`.

Check:

```bash
sudo ss -ltnp | grep ':8080'
```

---

# 3. Install Python Prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv
```

---

# 4. Create the Autobot Service Account

```bash
sudo useradd \
  --system \
  --create-home \
  --home-dir /opt/autobot \
  --shell /usr/sbin/nologin \
  autobot 2>/dev/null || true
```

Create the directory:

```bash
sudo mkdir -p /opt/autobot
sudo chown autobot:autobot /opt/autobot
```

---

# 5. Create the Python Environment

```bash
sudo -u autobot \
  python3 -m venv \
  /opt/autobot/venv
```

Install dependencies:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/pip install -U \
  requests websockets
```

---

# 6. Create the Meshpoint Credential File

Create:

```bash
sudo nano /etc/autobot.env
```

Enter:

```text
MESHPOINT_USERNAME=admin
MESHPOINT_PASSWORD=YOUR_MESHPOINT_PASSWORD
```

Save:

```text
Ctrl+O
Enter
Ctrl+X
```

Protect the credentials:

```bash
sudo chown root:autobot /etc/autobot.env
sudo chmod 640 /etc/autobot.env
```

---

# 7. Install the Autobot Script

Copy:

```text
meshpoint_autobot.py
```

to:

```text
/opt/autobot/autobot.py
```

If the file is already on the host:

```bash
sudo cp meshpoint_autobot.py /opt/autobot/autobot.py
```

Then:

```bash
sudo chown autobot:autobot /opt/autobot/autobot.py
sudo chmod 750 /opt/autobot/autobot.py
```

---

# 8. Syntax Check

Always syntax-check before restarting the service:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  -m py_compile \
  /opt/autobot/autobot.py
```

No output means the syntax is valid.

---

# 9. Test Autobot Manually

Run:

```bash
sudo -u autobot bash -c '
set -a
source /etc/autobot.env
set +a
exec /opt/autobot/venv/bin/python /opt/autobot/autobot.py
'
```

Expected startup includes:

```text
Meshpoint Autobot starting.
Authenticated to Meshpoint as role=admin
Connecting to Meshpoint WebSocket...
Meshpoint Autobot online.
```

Test each trigger from another Meshtastic node.

Press:

```text
Ctrl+C
```

when manual testing is complete.

---

# 10. Create the systemd Service

Create:

```bash
sudo nano /etc/systemd/system/autobot.service
```

Paste:

```ini
[Unit]
Description=Meshpoint Meshtastic Autobot
After=network-online.target meshpoint.service
Wants=network-online.target meshpoint.service

[Service]
Type=simple

User=autobot
Group=autobot

EnvironmentFile=/etc/autobot.env
WorkingDirectory=/opt/autobot

ExecStart=/opt/autobot/venv/bin/python /opt/autobot/autobot.py

Restart=always
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable Autobot:

```bash
sudo systemctl enable autobot
```

Start it:

```bash
sudo systemctl start autobot
```

Verify:

```bash
systemctl status autobot --no-pager
```

---

# 11. Restart Meshpoint and Autobot Together

Use:

```bash
sudo systemctl restart meshpoint
sleep 10
sudo systemctl restart autobot
```

Or:

```bash
sudo systemctl restart meshpoint && \
sleep 10 && \
sudo systemctl restart autobot
```

The delay gives Meshpoint time to initialize the concentrator, API, and WebSocket before Autobot reconnects.

Autobot also retries automatically if Meshpoint is temporarily unavailable.

---

# 12. Avoid SSH Logout Problems

Do not run Autobot permanently in a normal SSH foreground shell.

Use:

```text
autobot.service
```

instead.

Check:

```bash
systemctl is-enabled meshpoint
systemctl is-enabled autobot
```

and:

```bash
systemctl is-active meshpoint
systemctl is-active autobot
```

Autobot continues running when SSH disconnects.

---

# 13. Meshpoint Authentication Timeout

Meshpoint uses authenticated API and WebSocket access.

Autobot logs in automatically with the credentials stored in:

```text
/etc/autobot.env
```

The script reads the JWT expiration and reconnects with a fresh login before expiration.

If Meshpoint returns:

```text
401 Unauthorized
```

during a send, Autobot drops the current session, logs in again, and reconnects.

There is no need to modify Meshpoint's session-lifetime configuration for this bot.

---

# 14. Logs

Watch Autobot:

```bash
sudo journalctl -u autobot -f
```

Watch Meshpoint:

```bash
sudo journalctl -u meshpoint -f
```

Watch both:

```bash
sudo journalctl \
  -u meshpoint \
  -u autobot \
  -f
```

---

# 15. Recent Logs

Autobot:

```bash
sudo journalctl \
  -u autobot \
  -n 100 \
  --no-pager
```

Meshpoint:

```bash
sudo journalctl \
  -u meshpoint \
  -n 100 \
  --no-pager
```

Both from the last five minutes:

```bash
sudo journalctl \
  -u meshpoint \
  -u autobot \
  --since "5 minutes ago" \
  --no-pager
```

---

# 16. Filtered Troubleshooting Log

```bash
sudo journalctl \
  -u meshpoint \
  -u autobot \
  -f \
  | grep --line-buffered -Ei \
  'RX |TX |rule matched|trigger|text|ack|pki|send|error|fail|reconnect'
```

---

# 17. Restart Counts

```bash
systemctl show meshpoint -p NRestarts
systemctl show autobot -p NRestarts
```

Rapidly increasing values indicate a crash loop.

---

# 18. Common Problems

## Autobot crashes with a Python SyntaxError

Run:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  -m py_compile \
  /opt/autobot/autobot.py
```

Then:

```bash
sudo journalctl -u autobot -n 100 --no-pager
```

---

## Autobot cannot log in

Check:

```bash
sudo ls -l /etc/autobot.env
```

Verify that it contains:

```text
MESHPOINT_USERNAME=...
MESHPOINT_PASSWORD=...
```

Do not paste the real password into public logs or issue reports.

---

## Autobot receives the trigger but the node gets no reply

Watch both services:

```bash
sudo journalctl \
  -u meshpoint \
  -u autobot \
  -f
```

Look for:

```text
RX ...
Rule matched ...
Sending DM ...
Meshpoint HTTP response: 200 ...
TX DM ...
```

If Autobot logs `TX DM` but the receiving node gets nothing, the problem is downstream of the trigger logic in Meshpoint's radio/unicast path.

---

## Meshpoint is not listening on port 8080

Check:

```bash
systemctl status meshpoint --no-pager
sudo ss -ltnp | grep ':8080'
```

Restart:

```bash
sudo systemctl restart meshpoint
```

---

# 19. Expected Logs

## Spanish Inquisition

```text
RX 1234abcd -> ...: 'spanish inquisition'
Rule matched: 'spanish inquisition' from 1234abcd
Sending DM to 1234abcd: '*Nobody expects the Spanish Inquisition!*'
TX DM -> 1234abcd: '*Nobody expects the Spanish Inquisition!*'
```

## Ping / Test / DM Test

```text
RX 1234abcd -> ...: 'ping'
Rule matched: 'test' from 1234abcd
Sending DM to 1234abcd: 'I hear you'
TX DM -> 1234abcd: 'I hear you'
Waiting 10 seconds before next reply...
Sending DM to 1234abcd: 'visit www.SoCalMesh.org'
TX DM -> 1234abcd: 'visit www.SoCalMesh.org'
```

## Telemetry Warning

```text
RX 1234abcd -> ...: 'End of Day Report: ...'
Rule matched: 'telemetry warning' from 1234abcd
Sending DM to 1234abcd: 'no telemetry on Public please'
TX DM -> 1234abcd: 'no telemetry on Public please'
```

---

# 20. Everyday Commands

Restart both:

```bash
sudo systemctl restart meshpoint
sleep 10
sudo systemctl restart autobot
```

Status:

```bash
systemctl status meshpoint autobot --no-pager
```

Logs:

```bash
sudo journalctl -u meshpoint -u autobot -f
```

Stop Autobot:

```bash
sudo systemctl stop autobot
```

Start Autobot:

```bash
sudo systemctl start autobot
```

Disable Autobot:

```bash
sudo systemctl disable --now autobot
```

Enable Autobot:

```bash
sudo systemctl enable --now autobot
```

---

# 21. File Locations

```text
/opt/autobot/autobot.py
/opt/autobot/venv/
/etc/autobot.env
/etc/systemd/system/autobot.service
```

Meshpoint remains installed in its own existing location, normally:

```text
/opt/meshpoint
```

Autobot does not require changes inside that directory.

---

# 22. Meshpoint Installation Reference

If Meshpoint is not installed yet, the upstream project currently documents:

```bash
sudo apt update && sudo apt install -y git
sudo git clone https://github.com/KMX415/meshpoint.git /opt/meshpoint
cd /opt/meshpoint
sudo bash scripts/install.sh
sudo meshpoint setup
```

After setup:

```bash
meshpoint status
```

The dashboard is normally available at:

```text
http://YOUR_PI_IP:8080
```

For current Meshpoint installation, hardware, configuration, and upgrade instructions, follow the upstream project documentation:

```text
https://github.com/KMX415/meshpoint
```
