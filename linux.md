# Debian + meshtasticd + Autobot Setup

This guide installs **meshtasticd** on Debian, verifies a USB-connected LoRa/Meshtastic radio, installs the Python **Autobot** responder, and runs both components as persistent `systemd` services.

The goal is that:

- `meshtasticd` starts automatically at boot.
- `autobot` starts automatically after `meshtasticd`.
- Closing SSH does **not** stop either service.
- There is no Meshpoint login/JWT timeout involved.
- If either service crashes, `systemd` restarts it.
- You can restart both services together with one command.

## Autobot Rules

Autobot sends **direct messages back to the sender**.

### Spanish Inquisition

Exact message, case-insensitive:

```text
spanish inquisition
```

Reply:

```text
*Nobody expects the Spanish Inquisition!*
```

### Test / Ping

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

### Public-channel telemetry warning

If an incoming message contains either of these phrases, case-insensitively:

```text
End of Day Report:
```

or:

```text
in Upper Newport Bay
```

Autobot sends the sender this DM:

```text
no telemetry on Public please
```

The telemetry-warning rule is checked first.

> This guide assumes Debian 12 (bookworm) or Debian 13 (trixie).

---

# 1. Log in with SSH

From your computer:

```bash
ssh YOUR_USERNAME@YOUR_LINUX_IP
```

Example:

```bash
ssh tim@192.168.1.50
```

Check the Linux version:

```bash
cat /etc/os-release
uname -m
```

You should identify whether the machine is:

- Debian 13 / `trixie`
- Debian 12 / `bookworm`

Also note the CPU architecture, such as:

```text
x86_64
```

or:

```text
aarch64
```

---

# 2. Find the LoRa / Meshtastic Device Over USB

Before installing anything, connect the USB radio/device.

## 2.1 See what changed when the device was plugged in

Run:

```bash
sudo dmesg -w
```

Now unplug and reconnect the USB device.

Look for entries mentioning things such as:

- USB
- CH341 / CH340
- CP210x
- CDC ACM
- FTDI
- ttyACM
- ttyUSB
- MeshStick / Meshstick
- Meshtastic

Press `Ctrl+C` when finished.

---

## 2.2 List USB devices

Run:

```bash
lsusb
```

For additional detail:

```bash
lsusb -v 2>/dev/null | less
```

A supported USB LoRa radio may identify itself by chipset or product name rather than literally saying "Meshtastic".

---

## 2.3 Look for serial-style USB ports

Run:

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

Common examples are:

```text
/dev/ttyACM0
/dev/ttyUSB0
```

Also check persistent names:

```bash
ls -l /dev/serial/by-id/ 2>/dev/null
```

The `/dev/serial/by-id/` path is preferable to `/dev/ttyUSB0` when a stable serial-device name is needed because `ttyUSB0` can become `ttyUSB1` after reconnects or reboots.

---

## 2.4 Show USB/serial device information with udev

Example:

```bash
udevadm info --query=all --name=/dev/ttyUSB0
```

or:

```bash
udevadm info --query=all --name=/dev/ttyACM0
```

Change the device name to match your system.

---

## 2.5 Serial permissions

If you need to access a regular serial Meshtastic device directly from your user account, add yourself to the `dialout` group:

```bash
sudo usermod -aG dialout "$USER"
```

Then log out of SSH and reconnect.

Verify:

```bash
groups
```

You should see:

```text
dialout
```

---

# 3. Important USB Distinction

There are two different USB scenarios.

## A. USB radio supported directly by meshtasticd

A supported USB LoRa radio is controlled directly by `meshtasticd`.

`meshtasticd` becomes the Meshtastic node and owns the radio.

This guide is intended for that configuration.

## B. A normal Meshtastic ESP32/nRF52/etc. node attached by USB

A regular Meshtastic device may appear as:

```text
/dev/ttyACM0
```

or:

```text
/dev/ttyUSB0
```

That device can be controlled by the Meshtastic Python CLI/API over serial.

That is not necessarily the same as a native USB radio supported directly by `meshtasticd`.

---

# 4. Install Required Debian Packages

Run:

```bash
sudo apt update

sudo apt install -y \
  curl \
  ca-certificates \
  gnupg \
  python3 \
  python3-venv \
  python3-pip \
  usbutils
```

---

# 5. Install meshtasticd

Determine the Debian version:

```bash
. /etc/os-release
echo "$VERSION_ID"
```

## Debian 13 / trixie

```bash
echo 'deb http://download.opensuse.org/repositories/network:/Meshtastic:/beta/Debian_13/ /' \
  | sudo tee /etc/apt/sources.list.d/network:Meshtastic:beta.list

curl -fsSL \
  https://download.opensuse.org/repositories/network:Meshtastic:beta/Debian_13/Release.key \
  | gpg --dearmor \
  | sudo tee /etc/apt/trusted.gpg.d/network_Meshtastic_beta.gpg \
  >/dev/null

sudo apt update
sudo apt install -y meshtasticd
```

## Debian 12 / bookworm

```bash
echo 'deb http://download.opensuse.org/repositories/network:/Meshtastic:/beta/Debian_12/ /' \
  | sudo tee /etc/apt/sources.list.d/network:Meshtastic:beta.list

curl -fsSL \
  https://download.opensuse.org/repositories/network:Meshtastic:beta/Debian_12/Release.key \
  | gpg --dearmor \
  | sudo tee /etc/apt/trusted.gpg.d/network_Meshtastic_beta.gpg \
  >/dev/null

sudo apt update
sudo apt install -y meshtasticd
```

---

# 6. Inspect the meshtasticd Installation

Check package/version information:

```bash
apt-cache policy meshtasticd
```

Try:

```bash
meshtasticd --version
```

Inspect configuration directories:

```bash
ls -la /etc/meshtasticd
ls -la /etc/meshtasticd/config.d 2>/dev/null
ls -la /etc/meshtasticd/available.d 2>/dev/null
```

Common locations include:

```text
/etc/meshtasticd/config.yaml
/etc/meshtasticd/config.d/
/etc/meshtasticd/available.d/
/var/lib/meshtasticd/
```

---

# 7. Let meshtasticd Detect the USB Radio

Start the daemon:

```bash
sudo systemctl start meshtasticd
```

Inspect logs:

```bash
sudo journalctl -u meshtasticd -n 100 --no-pager
```

Watch live while reconnecting the USB radio:

```bash
sudo journalctl -u meshtasticd -f
```

For supported USB radios, `meshtasticd` may automatically detect the hardware and select an appropriate configuration.

---

# 8. Enable meshtasticd at Boot

```bash
sudo systemctl enable meshtasticd
sudo systemctl restart meshtasticd
```

Check:

```bash
systemctl status meshtasticd --no-pager
```

Expected:

```text
Active: active (running)
```

---

# 9. Confirm the meshtasticd TCP API

The Meshtastic TCP interface normally listens on port:

```text
4403
```

Check:

```bash
sudo ss -ltnp | grep ':4403'
```

Autobot connects locally to:

```text
127.0.0.1:4403
```

No external firewall opening is required for Autobot because it runs on the same host.

---

# 10. Create the Autobot Service Account

```bash
sudo useradd \
  --system \
  --create-home \
  --home-dir /opt/autobot \
  --shell /usr/sbin/nologin \
  autobot 2>/dev/null || true
```

Create the working directory:

```bash
sudo mkdir -p /opt/autobot
sudo chown autobot:autobot /opt/autobot
```

---

# 11. Create the Python Environment

```bash
sudo -u autobot python3 -m venv /opt/autobot/venv
```

Install the Meshtastic Python package:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/pip install -U \
  "meshtastic[cli]"
```

Verify:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python -c \
  "import meshtastic; from pubsub import pub; print('Meshtastic Python library OK')"
```

---

# 12. Create the Autobot Script

Create:

```bash
sudo nano /opt/autobot/autobot.py
```

Paste this entire file:

```python
#!/usr/bin/env python3

import queue
import threading
import time

from pubsub import pub
from meshtastic.tcp_interface import TCPInterface


MESHTASTIC_HOST = "127.0.0.1"

SPANISH_TRIGGER = "spanish inquisition"
SPANISH_REPLY = "*Nobody expects the Spanish Inquisition!*"

TEST_TRIGGERS = {
    "test",
    "ping",
    "dm test",
}

TEST_REPLIES = [
    "I hear you",
    "visit www.SoCalMesh.org",
]

WARNING_PHRASES = [
    "end of day report:",
    "in upper newport bay",
]

WARNING_REPLY = "no telemetry on Public please"

MULTI_REPLY_DELAY = 10
RECONNECT_DELAY = 5

reply_queue = queue.Queue()
connection_lost = threading.Event()


def log(message):
    print(message, flush=True)


def get_source_id(packet):
    source_id = packet.get("fromId")

    if source_id:
        return source_id

    source_num = packet.get("from")

    if isinstance(source_num, int):
        return f"!{source_num:08x}"

    return None


def get_text(packet):
    decoded = packet.get("decoded") or {}

    text = decoded.get("text")

    if isinstance(text, str):
        return text

    payload = decoded.get("payload")

    if isinstance(payload, bytes):
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            return None

    return None


def is_local_packet(packet, interface):
    try:
        local_num = interface.myInfo.my_node_num
        source_num = packet.get("from")

        return source_num == local_num

    except Exception:
        return False


def choose_replies(text):
    normalized = text.strip().casefold()

    for phrase in WARNING_PHRASES:
        if phrase in normalized:
            return [WARNING_REPLY], "telemetry warning"

    if normalized == SPANISH_TRIGGER:
        return [SPANISH_REPLY], "spanish inquisition"

    if normalized in TEST_TRIGGERS:
        return list(TEST_REPLIES), "test"

    return None, None


def on_receive(packet, interface):
    text = get_text(packet)

    if not isinstance(text, str):
        return

    text = text.strip()

    source_id = get_source_id(packet)
    destination_id = packet.get("toId")

    log(
        f"RX {source_id} -> {destination_id}: {text!r}"
    )

    if is_local_packet(packet, interface):
        log(
            "Ignoring text originating from the local node."
        )
        return

    replies, rule_name = choose_replies(text)

    if not replies:
        return

    if not source_id:
        log(
            "Trigger matched, but source node ID was unavailable."
        )
        return

    log(
        f"Rule matched: {rule_name!r} "
        f"from {source_id}"
    )

    reply_queue.put(
        (
            interface,
            source_id,
            replies,
        )
    )


def on_connection_lost(interface):
    log(
        "Connection to meshtasticd lost."
    )

    connection_lost.set()


def send_reply(interface, destination, text):
    log(
        f"Sending DM to {destination}: "
        f"{text!r}"
    )

    packet = interface.sendText(
        text,
        destinationId=destination,
        wantAck=True,
        channelIndex=0,
    )

    packet_id = getattr(
        packet,
        "id",
        None,
    )

    if (
        packet_id is None
        and isinstance(packet, dict)
    ):
        packet_id = packet.get("id")

    log(
        f"TX DM -> {destination}: "
        f"{text!r} "
        f"(packet={packet_id})"
    )


def reply_worker():
    while True:
        (
            interface,
            destination,
            replies,
        ) = reply_queue.get()

        try:
            for index, reply in enumerate(replies):

                try:
                    send_reply(
                        interface,
                        destination,
                        reply,
                    )

                except Exception as exc:
                    log(
                        f"TX error to {destination}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    break

                if index < len(replies) - 1:
                    log(
                        f"Waiting "
                        f"{MULTI_REPLY_DELAY} seconds "
                        f"before next reply..."
                    )

                    time.sleep(
                        MULTI_REPLY_DELAY
                    )

        finally:
            reply_queue.task_done()


def connect():
    log(
        f"Connecting to meshtasticd at "
        f"{MESHTASTIC_HOST}:4403..."
    )

    interface = TCPInterface(
        MESHTASTIC_HOST
    )

    try:
        node_num = interface.myInfo.my_node_num
        node_id = f"!{node_num:08x}"

        log(
            f"Connected to meshtasticd "
            f"as {node_id}"
        )

    except Exception:
        log(
            "Connected to meshtasticd."
        )

    return interface


def main():
    log(
        "Meshtasticd Autobot starting."
    )

    log(
        f"Spanish trigger: {SPANISH_TRIGGER!r}"
    )

    log(
        "Exact test triggers: "
        + ", ".join(
            sorted(TEST_TRIGGERS)
        )
    )

    log(
        "Warning phrases: "
        + ", ".join(
            repr(x)
            for x in WARNING_PHRASES
        )
    )

    pub.subscribe(
        on_receive,
        "meshtastic.receive.text",
    )

    pub.subscribe(
        on_connection_lost,
        "meshtastic.connection.lost",
    )

    worker = threading.Thread(
        target=reply_worker,
        name="autobot-reply-worker",
        daemon=True,
    )

    worker.start()

    while True:
        interface = None
        connection_lost.clear()

        try:
            interface = connect()

            log(
                "Meshtasticd Autobot online."
            )

            while not connection_lost.wait(
                timeout=5
            ):
                pass

        except KeyboardInterrupt:
            log(
                "Autobot stopped."
            )

            if interface is not None:
                try:
                    interface.close()
                except Exception:
                    pass

            break

        except Exception as exc:
            log(
                f"Connection error: "
                f"{type(exc).__name__}: {exc}"
            )

        finally:
            if interface is not None:
                try:
                    interface.close()
                except Exception:
                    pass

        log(
            f"Reconnecting in "
            f"{RECONNECT_DELAY} seconds..."
        )

        time.sleep(
            RECONNECT_DELAY
        )


if __name__ == "__main__":
    main()
```

Save with:

```text
Ctrl+O
Enter
Ctrl+X
```

Set ownership and permissions:

```bash
sudo chown autobot:autobot /opt/autobot/autobot.py
sudo chmod 750 /opt/autobot/autobot.py
```

---

# 13. Syntax Check Before Running

Always syntax-check the file before restarting the service:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  -m py_compile \
  /opt/autobot/autobot.py
```

No output means the Python syntax is valid.

---

# 14. Test Autobot Manually

Verify `meshtasticd`:

```bash
systemctl status meshtasticd --no-pager
```

Then run:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  /opt/autobot/autobot.py
```

Expected startup:

```text
Meshtasticd Autobot starting.
Connecting to meshtasticd at 127.0.0.1:4403...
Connected to meshtasticd ...
Meshtasticd Autobot online.
```

Test each rule from another Meshtastic node.

### Test 1

Send:

```text
spanish inquisition
```

Expected DM:

```text
*Nobody expects the Spanish Inquisition!*
```

### Test 2

Send:

```text
ping
```

Expected:

```text
I hear you
```

then about 10 seconds later:

```text
visit www.SoCalMesh.org
```

The same behavior applies to:

```text
test
```

and:

```text
dm test
```

### Test 3

Send a message containing:

```text
End of Day Report:
```

Expected DM:

```text
no telemetry on Public please
```

### Test 4

Send a message containing:

```text
in Upper Newport Bay
```

Expected DM:

```text
no telemetry on Public please
```

Press `Ctrl+C` after manual testing.

---

# 15. Create the systemd Service

Create:

```bash
sudo nano /etc/systemd/system/autobot.service
```

Paste:

```ini
[Unit]
Description=Meshtasticd Autobot
After=network-online.target meshtasticd.service
Wants=network-online.target
Requires=meshtasticd.service

[Service]
Type=simple
User=autobot
Group=autobot

WorkingDirectory=/opt/autobot

ExecStart=/opt/autobot/venv/bin/python /opt/autobot/autobot.py

Restart=always
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Save, then reload:

```bash
sudo systemctl daemon-reload
```

Enable at boot:

```bash
sudo systemctl enable autobot
```

Start it:

```bash
sudo systemctl start autobot
```

Check:

```bash
systemctl status autobot --no-pager
```

Expected:

```text
Active: active (running)
```

---

# 16. Avoid SSH Logout / Timeout Problems

Do not permanently run Autobot as:

```bash
python3 autobot.py
```

inside a normal SSH shell.

Instead use the `systemd` service.

Once enabled, Autobot continues running when:

- SSH disconnects
- your laptop sleeps
- your terminal closes
- you log out
- the server reboots

Check boot persistence:

```bash
systemctl is-enabled meshtasticd
systemctl is-enabled autobot
```

Expected:

```text
enabled
enabled
```

Check runtime state:

```bash
systemctl is-active meshtasticd
systemctl is-active autobot
```

Expected:

```text
active
active
```

---

# 17. No Meshpoint/JWT Timeout

This version does not use the Meshpoint REST API or a Meshpoint JWT.

Autobot talks directly to:

```text
meshtasticd
    |
    +-- TCP 127.0.0.1:4403
```

There is therefore no hourly Meshpoint login token to expire.

The Python reconnect loop and `systemd` restart policy handle ordinary process and connection failures.

---

# 18. Optional SSH Keepalive

This is only for keeping your interactive SSH terminal connected.

On your client computer:

```bash
nano ~/.ssh/config
```

Add:

```text
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 5
```

This has no effect on Autobot once Autobot is running through `systemd`.

---

# 19. Restart meshtasticd and Autobot Together

Use:

```bash
sudo systemctl restart meshtasticd
sleep 5
sudo systemctl restart autobot
```

Or:

```bash
sudo systemctl restart meshtasticd && \
sleep 5 && \
sudo systemctl restart autobot
```

The delay gives `meshtasticd` time to initialize the radio and TCP API before Autobot connects.

---

# 20. Verify Both Services

```bash
systemctl status meshtasticd --no-pager
systemctl status autobot --no-pager
```

Or:

```bash
systemctl is-active meshtasticd autobot
```

Expected:

```text
active
active
```

Confirm port `4403`:

```bash
sudo ss -ltnp | grep ':4403'
```

---

# 21. Logging

## Watch Autobot

```bash
sudo journalctl -u autobot -f
```

## Watch meshtasticd

```bash
sudo journalctl -u meshtasticd -f
```

## Watch both together

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  -f
```

---

# 22. Recent Logs

Autobot:

```bash
sudo journalctl \
  -u autobot \
  -n 100 \
  --no-pager
```

meshtasticd:

```bash
sudo journalctl \
  -u meshtasticd \
  -n 100 \
  --no-pager
```

Both from the last five minutes:

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  --since "5 minutes ago" \
  --no-pager
```

---

# 23. Filtered Autobot / Meshtastic Logs

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  -f \
  | grep --line-buffered -Ei \
  'RX |TX |rule matched|trigger|text|ack|send|error|fail|usb|radio|reconnect'
```

---

# 24. Check Restart Counts

```bash
systemctl show meshtasticd -p NRestarts
systemctl show autobot -p NRestarts
```

Rapidly increasing restart counts indicate a crash loop.

---

# 25. Test meshtasticd with the Meshtastic CLI

Because `"meshtastic[cli]"` was installed in the Autobot virtual environment, use:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --info
```

List nodes:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --nodes
```

Send a test broadcast:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --sendtext "Linux meshtasticd test"
```

---

# 26. Configure the Region

For the United States:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --set lora.region US
```

Confirm:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --info
```

Use the correct legal region if operating outside the United States.

---

# 27. Verify Long_Fast

Inspect:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --info
```

Do not overwrite an existing channel configuration unless you know exactly what channel settings the mesh uses.

Autobot listens to text packets delivered by `meshtasticd` and sends its direct replies on channel index `0`.

---

# 28. Reboot Test

Once everything works:

```bash
sudo reboot
```

Reconnect over SSH.

Check:

```bash
systemctl is-active meshtasticd
systemctl is-active autobot
```

Expected:

```text
active
active
```

Check startup logs:

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  --since boot \
  --no-pager
```

---

# 29. Quick Health Check

Use this block whenever something seems wrong:

```bash
echo "=== MESHTASTICD ==="
systemctl is-active meshtasticd
systemctl show meshtasticd -p NRestarts

echo
echo "=== AUTOBOT ==="
systemctl is-active autobot
systemctl show autobot -p NRestarts

echo
echo "=== TCP 4403 ==="
sudo ss -ltnp | grep ':4403' || true

echo
echo "=== USB ==="
lsusb

echo
echo "=== SERIAL DEVICES ==="
ls -l /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id/* \
  2>/dev/null || true

echo
echo "=== RECENT LOGS ==="
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  --since "5 minutes ago" \
  --no-pager
```

---

# 30. Common Problems

## Autobot says connection refused

```bash
systemctl status meshtasticd --no-pager
sudo ss -ltnp | grep ':4403'
```

Then:

```bash
sudo systemctl restart meshtasticd
sleep 5
sudo systemctl restart autobot
```

---

## Autobot crashes immediately

Check:

```bash
sudo journalctl -u autobot -n 100 --no-pager
```

Syntax test:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  -m py_compile \
  /opt/autobot/autobot.py
```

Dependency test:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  -c "import meshtastic; from pubsub import pub; print('OK')"
```

---

## meshtasticd does not see the USB radio

Check:

```bash
lsusb
sudo dmesg | tail -100
sudo journalctl -u meshtasticd -n 150 --no-pager
```

Reconnect the USB device while watching:

```bash
sudo journalctl -u meshtasticd -f
```

Also inspect:

```bash
ls -la /etc/meshtasticd/available.d/
```

---

## `/dev/ttyUSB0` changes after reboot

Use:

```bash
ls -l /dev/serial/by-id/
```

instead of relying on `/dev/ttyUSB0`.

---

## Permission denied on a serial device

For your login account:

```bash
sudo usermod -aG dialout "$USER"
```

Then log out and reconnect.

For `meshtasticd`, inspect its service account and udev permissions rather than changing the daemon to run as root:

```bash
systemctl cat meshtasticd
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

---

# 31. Expected Autobot Logs

## Spanish Inquisition

```text
RX !1234abcd -> !xxxxxxxx: 'spanish inquisition'
Rule matched: 'spanish inquisition' from !1234abcd
Sending DM to !1234abcd: '*Nobody expects the Spanish Inquisition!*'
TX DM -> !1234abcd: '*Nobody expects the Spanish Inquisition!*'
```

## Ping / Test / DM Test

```text
RX !1234abcd -> !xxxxxxxx: 'ping'
Rule matched: 'test' from !1234abcd
Sending DM to !1234abcd: 'I hear you'
TX DM -> !1234abcd: 'I hear you'
Waiting 10 seconds before next reply...
Sending DM to !1234abcd: 'visit www.SoCalMesh.org'
TX DM -> !1234abcd: 'visit www.SoCalMesh.org'
```

## Telemetry Warning

```text
RX !1234abcd -> !xxxxxxxx: 'End of Day Report: ...'
Rule matched: 'telemetry warning' from !1234abcd
Sending DM to !1234abcd: 'no telemetry on Public please'
TX DM -> !1234abcd: 'no telemetry on Public please'
```

---

# 32. File Locations

Autobot:

```text
/opt/autobot/autobot.py
/opt/autobot/venv/
/etc/systemd/system/autobot.service
```

meshtasticd:

```text
/etc/meshtasticd/config.yaml
/etc/meshtasticd/config.d/
/etc/meshtasticd/available.d/
/var/lib/meshtasticd/
```

---

# 33. Everyday Commands

Restart both:

```bash
sudo systemctl restart meshtasticd
sleep 5
sudo systemctl restart autobot
```

Status:

```bash
systemctl status meshtasticd autobot --no-pager
```

Logs:

```bash
sudo journalctl -u meshtasticd -u autobot -f
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

Re-enable:

```bash
sudo systemctl enable --now autobot
```

---

# 34. Why This Survives Logout

The final architecture is:

```text
USB LoRa radio
      |
      v
meshtasticd.service
      |
      | TCP 127.0.0.1:4403
      v
autobot.service
      |
      v
Meshtastic DM replies
```

Neither service is attached to your SSH shell.

`systemd` owns the processes.

Therefore:

```text
SSH logout != service shutdown
```

A reboot automatically starts both services again when they are enabled.

---

# References

Official Meshtastic documentation:

- MeshtasticD installation:
  https://meshtastic.org/docs/meshtasticd/installation/

- Debian meshtasticd installation:
  https://meshtastic.org/docs/meshtasticd/installation/debian/

- Meshtastic Python CLI:
  https://meshtastic.org/docs/software/python/cli/installation/

- Meshtastic documentation:
  https://meshtastic.org/docs/
