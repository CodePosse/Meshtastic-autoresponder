#!/usr/bin/env python3

"""
Meshtasticd Autobot for Debian

Connects to a local meshtasticd instance over the Meshtastic TCP interface
(default TCP port 4403), listens for incoming text messages, and sends a
direct-message response back to the sender.

Triggers:
    spanish inquisition
        -> *Nobody expects the Spanish Inquisition!*

    dm test
        -> I hear you
        -> wait 10 seconds
        -> visit www.SoCalMesh.org
"""

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


def on_receive(packet, interface):
    """
    Called by the Meshtastic Python library whenever a text packet arrives.
    Keep this callback short: queue replies for the worker thread rather than
    sleeping inside the receive callback.
    """
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
        log("Trigger matched, but source node ID was unavailable.")
        return

    # Prevent the local daemon/node from responding to its own transmitted
    # text if such a packet is ever reflected back to the client.
    try:
        local_num = interface.myInfo.my_node_num
        source_num = packet.get("from")

        if source_num == local_num:
            log("Ignoring text originating from the local node.")
            return

    except Exception:
        pass

    log(
        f"Trigger matched: {normalized!r} "
        f"from {source_id}"
    )

    # No packet-ID duplicate suppression is used here.
    # Every matching received text event is queued.
    reply_queue.put(
        (
            interface,
            source_id,
            list(replies),
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

    This prevents the 10-second multi-message delay from blocking the
    Meshtastic receive callback.
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
        "Triggers: "
        + ", ".join(repr(x) for x in TRIGGERS)
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
