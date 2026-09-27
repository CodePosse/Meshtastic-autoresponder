#!/usr/bin/env python3

"""
Meshtasticd Autobot for Debian

Connects to a local meshtasticd instance over the Meshtastic TCP interface
(default TCP port 4403), listens for incoming text messages, and sends a
direct-message response back to the sender.

Rules:

1. Exact message (case-insensitive):
       spanish inquisition

   Reply:
       *Nobody expects the Spanish Inquisition!*

2. Exact messages (case-insensitive):
       test
       ping
       dm test

   Reply:
       I hear you
       [wait 10 seconds]
       visit www.SoCalMesh.org

3. Messages containing either phrase (case-insensitive):
       End of Day Report:
       in Upper Newport Bay

   Reply:
       no telemetry on Public please

The telemetry-warning rule is checked first.
"""

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
    """
    Prefer Meshtastic's populated fromId field, which normally looks like:
        !1234abcd

    Fall back to the numeric 'from' field when needed.
    """
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
    """
    Prevent Autobot from replying to text transmitted by its own local node.
    """
    try:
        local_num = interface.myInfo.my_node_num
        source_num = packet.get("from")

        return source_num == local_num

    except Exception:
        return False


def choose_replies(text):
    """
    Return the reply list for an incoming message.

    Priority:
      1. Telemetry/public-channel warning phrases
      2. Spanish Inquisition trigger
      3. Exact test/ping/dm test triggers
    """
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
    """
    Called by the Meshtastic Python library whenever a text packet arrives.

    Keep this callback short: replies are queued for the sender worker rather
    than sleeping inside the receive callback.
    """
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
        log("Ignoring text originating from the local node.")
        return

    replies, rule_name = choose_replies(text)

    if not replies:
        return

    if not source_id:
        log("Trigger matched, but source node ID was unavailable.")
        return

    log(
        f"Rule matched: {rule_name!r} "
        f"from {source_id}"
    )

    # No packet-ID duplicate suppression is used here.
    # Every matching received text event is queued.
    reply_queue.put(
        (
            interface,
            source_id,
            replies,
        )
    )


def on_connection_lost(interface):
    log("Connection to meshtasticd lost.")
    connection_lost.set()


def send_reply(interface, destination, text):
    """
    Send one direct Meshtastic text message with reliable delivery requested.
    """
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

    packet_id = getattr(packet, "id", None)

    if packet_id is None and isinstance(packet, dict):
        packet_id = packet.get("id")

    log(
        f"TX DM -> {destination}: "
        f"{text!r} "
        f"(packet={packet_id})"
    )


def reply_worker():
    """
    Dedicated sender thread.

    This prevents the 10-second delay between the two test replies from
    blocking the Meshtastic receive callback.
    """
    while True:
        interface, destination, replies = reply_queue.get()

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
                        f"Waiting {MULTI_REPLY_DELAY} seconds "
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
    log("Meshtasticd Autobot starting.")

    log(
        f"Spanish trigger: {SPANISH_TRIGGER!r}"
    )

    log(
        "Exact test triggers: "
        + ", ".join(sorted(TEST_TRIGGERS))
    )

    log(
        "Warning phrases: "
        + ", ".join(repr(x) for x in WARNING_PHRASES)
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
            log("Autobot stopped.")

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
