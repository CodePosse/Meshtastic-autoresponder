# Debian + meshtasticd + Autobot Setup

This guide installs **meshtasticd** on Debian, verifies a USB-connected LoRa/Meshtastic radio, installs the Python **Autobot** responder, and runs both components as persistent `systemd` services.

The goal is that:

- `meshtasticd` starts automatically at boot.
- `autobot` starts automatically after `meshtasticd`.
- Closing SSH does **not** stop either service.
- There is no Meshpoint login/JWT timeout involved.
- If either service crashes, `systemd` restarts it.
- You can restart both services together with one command.

Autobot responds to these exact phrases, case-insensitively:

| Incoming phrase | Direct-message response |
|---|---|
| `spanish inquisition` | `*Nobody expects the Spanish Inquisition!*` |
| `dm test` | `I hear you`, then 10 seconds later `visit www.SoCalMesh.org` |

> This guide assumes Debian 12 (bookworm) or Debian 13 (trixie). The current official Meshtastic documentation lists both as supported.

---

## 1. Log in with SSH

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

You can also use persistent device names:

```bash
ls -l /dev/serial/by-id/ 2>/dev/null
```

The `/dev/serial/by-id/` path is preferable to `/dev/ttyUSB0` when a program needs a stable serial-device name, because `ttyUSB0` may become `ttyUSB1` after reconnecting devices.

---

## 2.4 Show USB/serial device information with udev

For example:

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

Then log out of SSH and reconnect for the new group membership to apply.

Verify:

```bash
groups
```

You should see:

```text
dialout
```

> `meshtasticd` packages install their own service account and udev support. The `dialout` step is primarily useful for direct CLI/serial testing.

---

# 3. Important USB Distinction

There are two different USB scenarios.

## A. USB radio supported directly by meshtasticd

Examples include supported USB LoRa hardware such as MeshStick-style radios.

`meshtasticd` itself becomes the Meshtastic node and controls the LoRa radio.

This guide is designed for that configuration.

Current Debian builds of `meshtasticd` support USB radios.

## B. Meshtastic ESP32/nRF52 node attached by USB

A normal Meshtastic device may appear as:

```text
/dev/ttyACM0
```

or:

```text
/dev/ttyUSB0
```

That can be controlled directly by the Meshtastic Python CLI/API.

That is not necessarily the same thing as using the USB device as the native LoRa radio for `meshtasticd`.

If your device is a normal flashed Meshtastic node rather than a `meshtasticd`-supported USB radio, use the Python serial interface instead of assuming `meshtasticd` should consume it.

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

The official Meshtastic Debian packages are provided through the OpenSUSE Build Service.

This guide uses the **beta** repository rather than alpha/daily builds.

First determine your Debian version:

```bash
. /etc/os-release
echo "$VERSION_ID"
```

---

## 5.1 Debian 13 / trixie

Use these commands on Debian 13:

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

---

## 5.2 Debian 12 / bookworm

Use these commands on Debian 12:

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

Check the installed version:

```bash
meshtasticd --version
```

If that option is not supported by the installed build, use:

```bash
apt-cache policy meshtasticd
```

Check the package-created configuration directories:

```bash
ls -la /etc/meshtasticd
ls -la /etc/meshtasticd/config.d 2>/dev/null
ls -la /etc/meshtasticd/available.d 2>/dev/null
```

Typical locations are:

```text
/etc/meshtasticd/config.yaml
/etc/meshtasticd/config.d/
/etc/meshtasticd/available.d/
/var/lib/meshtasticd/
```

---

# 7. Let meshtasticd Detect the USB Radio

Start `meshtasticd`:

```bash
sudo systemctl start meshtasticd
```

Then inspect its log:

```bash
sudo journalctl -u meshtasticd -n 100 --no-pager
```

For a supported USB radio, recent `meshtasticd` builds may automatically detect the device.

For example, a supported CH341-based USB LoRa radio may produce log lines similar to:

```text
autoconf: Looking for CH341 device...
autoconf: Found CH341 device ...
autoconf: Setting hardwareModel ...
autoconf: Using lora-usb-....yaml as config file
```

The exact hardware and configuration filename will vary.

Watch live while reconnecting the radio:

```bash
sudo journalctl -u meshtasticd -f
```

---

# 8. Enable meshtasticd at Boot

Run:

```bash
sudo systemctl enable meshtasticd
```

Then restart it:

```bash
sudo systemctl restart meshtasticd
```

Check:

```bash
systemctl status meshtasticd --no-pager
```

You want:

```text
Active: active (running)
```

---

# 9. Confirm meshtasticd TCP API Port

The Meshtastic TCP interface normally listens on port:

```text
4403
```

Check it:

```bash
sudo ss -ltnp | grep ':4403'
```

You should see a listener associated with `meshtasticd`.

Autobot connects locally to:

```text
127.0.0.1:4403
```

No external firewall opening is required for Autobot because it runs on the same Linux host.

---

# 10. Install the Meshtastic Python Environment for Autobot

Create a dedicated service account:

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

Create the Python virtual environment:

```bash
sudo -u autobot python3 -m venv /opt/autobot/venv
```

Install Meshtastic:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/pip install -U \
  "meshtastic[cli]"
```

Verify:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python -c \
  "import meshtastic; print('Meshtastic Python library OK')"
```

---

# 11. Create the Autobot Script

Create:

```bash
sudo nano /opt/autobot/autobot.py
```

Paste the entire script below.

```python
#!/usr/bin/env python3

import queue
import threading
import time

from pubsub import pub
from meshtastic.tcp_interface import TCPInterface


MESHTASTIC_HOST = "127.0.0.1"

TRIGGERS = {
    "spanish inquisition": [
        "*Nobody expects the Spanish Inquisition!*",
    ],
    "dm test": [
        "I hear you",
        "visit www.SoCalMesh.org",
    ],
}

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


def on_receive(packet, interface):
    text = get_text(packet)

    if not isinstance(text, str):
        return

    text = text.strip()
    normalized = text.casefold()

    source_id = get_source_id(packet)
    destination_id = packet.get("toId")

    log(
        f"RX {source_id} -> {destination_id}: {text!r}"
    )

    replies = TRIGGERS.get(normalized)

    if not replies:
        return

    if not source_id:
        log(
            "Trigger matched, but source node ID "
            "was unavailable."
        )
        return

    try:
        local_num = interface.myInfo.my_node_num
        source_num = packet.get("from")

        if source_num == local_num:
            log(
                "Ignoring text originating "
                "from the local node."
            )
            return

    except Exception:
        pass

    log(
        f"Trigger matched: {normalized!r} "
        f"from {source_id}"
    )

    reply_queue.put(
        (
            interface,
            source_id,
            list(replies),
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
        "Triggers: "
        + ", ".join(
            repr(x)
            for x in TRIGGERS
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

Save:

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

# 12. Syntax Check Before Running It

Always perform this check before installing/restarting the service:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  -m py_compile \
  /opt/autobot/autobot.py
```

If it produces no output, the Python syntax is valid.

---

# 13. Test the Script Manually

First make sure `meshtasticd` is running:

```bash
systemctl status meshtasticd --no-pager
```

Then run Autobot:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/python \
  /opt/autobot/autobot.py
```

Expected startup output:

```text
Meshtasticd Autobot starting.
Connecting to meshtasticd at 127.0.0.1:4403...
Connected to meshtasticd ...
Meshtasticd Autobot online.
```

From another Meshtastic node, send:

```text
spanish inquisition
```

Expected direct reply:

```text
*Nobody expects the Spanish Inquisition!*
```

Then send:

```text
dm test
```

Expected replies:

```text
I hear you
```

followed about 10 seconds later by:

```text
visit www.SoCalMesh.org
```

Press:

```text
Ctrl+C
```

to stop the manual test.

---

# 14. Run Autobot Permanently with systemd

Create the service:

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

Save:

```text
Ctrl+O
Enter
Ctrl+X
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable Autobot at boot:

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

You want:

```text
Active: active (running)
```

---

# 15. Avoid SSH Logout / Timeout Problems

## The important rule

Do **not** rely on this:

```bash
python3 autobot.py
```

from a normal SSH window for permanent operation.

A foreground process attached to an SSH session can terminate when the SSH connection closes.

Instead, always run Autobot through:

```text
systemd
```

Once the service is enabled and running, you may:

- close the SSH window,
- disconnect your laptop,
- log out,
- reconnect later,

and Autobot will continue running.

Verify boot persistence:

```bash
systemctl is-enabled meshtasticd
systemctl is-enabled autobot
```

Both should report:

```text
enabled
```

Verify current runtime state:

```bash
systemctl is-active meshtasticd
systemctl is-active autobot
```

Both should report:

```text
active
```

---

# 16. No Meshpoint/JWT Login Timeout

This Linux version does not use the Meshpoint REST login or WebSocket JWT token.

Autobot connects directly to:

```text
meshtasticd -> TCP 127.0.0.1:4403
```

Therefore there is no hourly Meshpoint authentication token for Autobot to renew.

The remaining failure modes are normal service/network/process failures, which are handled by:

```ini
Restart=always
RestartSec=5
```

and the reconnect loop in the Python script.

---

# 17. Optional SSH Keepalive

SSH keepalive is **not required for Autobot** once systemd is running it.

If you want your interactive SSH session itself to remain connected longer, edit your local SSH config:

```bash
nano ~/.ssh/config
```

Example:

```text
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 5
```

This only affects your SSH client session.

It does not control `meshtasticd` or Autobot.

---

# 18. Restart meshtasticd and Autobot Together

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

The small delay gives `meshtasticd` time to initialize its radio and TCP API before Autobot reconnects.

Autobot also has its own reconnect loop, so a temporarily unavailable port should not permanently stop it.

---

# 19. Verify Both Services After Restart

Run:

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

Check TCP port 4403:

```bash
sudo ss -ltnp | grep ':4403'
```

---

# 20. Logging

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

# 21. Show Recent Logs

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

Both for the last five minutes:

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  --since "5 minutes ago" \
  --no-pager
```

---

# 22. Useful Filtered Log View

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  -f \
  | grep --line-buffered -Ei \
  'RX |TX |trigger|text|ack|send|error|fail|usb|radio|reconnect'
```

---

# 23. Check Service Restart Counts

```bash
systemctl show meshtasticd -p NRestarts
systemctl show autobot -p NRestarts
```

A rapidly increasing restart count usually indicates a crash loop.

---

# 24. Test meshtasticd with the Meshtastic CLI

Because `"meshtastic[cli]"` was installed into Autobot's virtual environment, you can use its CLI without installing another system-wide copy.

Node information:

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

# 25. Configure Region

Meshtastic radios must have the correct legal radio region configured.

For the United States:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --set lora.region US
```

Then confirm:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --info
```

Use the appropriate region instead of `US` if the node is operated elsewhere.

---

# 26. Verify Long_Fast

Inspect current configuration:

```bash
sudo -u autobot \
  /opt/autobot/venv/bin/meshtastic \
  --host 127.0.0.1 \
  --info
```

Do not overwrite an existing channel configuration unless you know what channel settings the mesh uses.

The Autobot script simply listens to text messages that `meshtasticd` receives and sends replies using channel index `0`.

---

# 27. Reboot Test

Once everything works, perform a real persistence test:

```bash
sudo reboot
```

Reconnect over SSH after the machine comes back.

Run:

```bash
systemctl is-active meshtasticd
systemctl is-active autobot
```

Expected:

```text
active
active
```

Then:

```bash
sudo journalctl \
  -u meshtasticd \
  -u autobot \
  --since boot \
  --no-pager
```

You should see `meshtasticd` start followed by Autobot connecting to TCP port `4403`.

---

# 28. Quick Health Check

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

# 29. Common Problems

## Autobot says connection refused

Check:

```bash
systemctl status meshtasticd --no-pager
sudo ss -ltnp | grep ':4403'
```

Restart both:

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

Reconnect the USB device while running:

```bash
sudo journalctl -u meshtasticd -f
```

Also inspect:

```bash
ls -la /etc/meshtasticd/available.d/
```

for a configuration matching the hardware.

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

For `meshtasticd` itself, inspect the installed service account and udev permissions rather than blindly running the daemon as root:

```bash
systemctl cat meshtasticd
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

---

# 30. File Locations

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

# 31. Everyday Commands

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

Stop Autobot only:

```bash
sudo systemctl stop autobot
```

Start Autobot only:

```bash
sudo systemctl start autobot
```

Disable Autobot:

```bash
sudo systemctl disable --now autobot
```

Re-enable it:

```bash
sudo systemctl enable --now autobot
```

---

# 32. Why This Survives Logout

The final setup is:

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

Neither program is tied to your SSH shell.

`systemd` owns the processes.

Therefore:

```text
SSH logout != service shutdown
```

and a reboot automatically starts the services again when they are enabled.

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

The Debian package documentation currently lists Debian 12 and Debian 13 as supported and lists USB radio support for Debian.
