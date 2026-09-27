#!/usr/bin/env python3

import asyncio
import base64
import json
import os
import time
import urllib.parse

import requests
import websockets


BASE_URL = "http://127.0.0.1:8080"
WS_URL = "ws://127.0.0.1:8080/ws"

USERNAME = os.environ["MESHPOINT_USERNAME"]
PASSWORD = os.environ["MESHPOINT_PASSWORD"]

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
TOKEN_REFRESH_MARGIN = 300


def log(message):
    print(message, flush=True)


def get_jwt_expiration(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        payload = parts[1]
        padding = "=" * (-len(payload) % 4)

        decoded = base64.urlsafe_b64decode(
            payload + padding
        )

        data = json.loads(decoded)
        return data.get("exp")

    except Exception:
        return None


def login():
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        headers={
            "X-Meshpoint-Client": "meshtastic-autoresponder",
        },
        json={
            "username": USERNAME,
            "password": PASSWORD,
        },
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()
    token = data.get("token")

    if not token:
        raise RuntimeError(
            f"Meshpoint login returned no token: {data}"
        )

    log(
        f"Authenticated to Meshpoint "
        f"as role={data.get('role', 'unknown')}"
    )

    return token


def send_dm(token, destination, text):
    return requests.post(
        f"{BASE_URL}/api/messages/send",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "text": text,
            "destination": destination,
            "protocol": "meshtastic",
            "channel": 0,
            "want_ack": True,
        },
        timeout=15,
    )


async def send_reply(token, source_id, text):
    for attempt in range(1, 4):

        log(
            f"Sending DM to {source_id}: "
            f"{text!r} "
            f"(attempt {attempt}/3)..."
        )

        try:
            response = await asyncio.to_thread(
                send_dm,
                token,
                source_id,
                text,
            )

        except Exception as exc:
            log(
                f"DM attempt {attempt} exception: "
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < 3:
                await asyncio.sleep(2)

            continue

        if response.status_code == 401:
            log(
                "Meshpoint token expired; "
                "starting a fresh session."
            )
            return False

        log(
            f"Meshpoint HTTP response: "
            f"{response.status_code} "
            f"{response.text}"
        )

        if not response.ok:
            if attempt < 3:
                await asyncio.sleep(2)
            continue

        try:
            result = response.json()
        except Exception:
            result = {}

        if result.get("success") is False:
            log(
                f"Meshpoint TX failed: "
                f"{result.get('error')}"
            )

            if attempt < 3:
                await asyncio.sleep(2)

            continue

        log(
            f"TX DM -> {source_id}: "
            f"{text!r} "
            f"(packet={result.get('packet_id')})"
        )

        return True

    log(
        f"Unable to send {text!r} "
        f"to {source_id} after 3 attempts."
    )

    return True


async def process_packet(packet, token):
    if packet.get("protocol") != "meshtastic":
        return True

    if packet.get("packet_type") != "text":
        return True

    if not packet.get("decrypted", False):
        return True

    source_id = packet.get("source_id")
    destination_id = packet.get("destination_id")

    payload = packet.get("decoded_payload") or {}
    text = payload.get("text")

    if not isinstance(text, str):
        return True

    text = text.strip()
    normalized = text.casefold()

    log(
        f"RX {source_id} -> {destination_id}: {text!r}"
    )

    replies = TRIGGERS.get(normalized)

    if not replies:
        return True

    if not source_id:
        log(
            "Trigger matched, but packet has no source_id."
        )
        return True

    log(
        f"Trigger matched: {normalized!r} "
        f"from {source_id}"
    )

    for index, reply in enumerate(replies):

        keep_session = await send_reply(
            token,
            source_id,
            reply,
        )

        if not keep_session:
            return False

        if index < len(replies) - 1:
            log(
                f"Waiting {MULTI_REPLY_DELAY} seconds "
                f"before next reply..."
            )

            await asyncio.sleep(
                MULTI_REPLY_DELAY
            )

    return True


async def run_session():
    token = login()

    expiration = get_jwt_expiration(token)

    if expiration:
        refresh_at = (
            expiration - TOKEN_REFRESH_MARGIN
        )

        log(
            f"JWT refresh scheduled in "
            f"{max(int(refresh_at - time.time()), 0)} seconds"
        )

    else:
        refresh_at = time.time() + 1800

        log(
            "Could not read JWT expiration; "
            "using 30-minute refresh."
        )

    encoded_token = urllib.parse.quote(
        token,
        safe="",
    )

    websocket_uri = (
        f"{WS_URL}?token={encoded_token}"
    )

    log(
        "Connecting to Meshpoint WebSocket..."
    )

    async with websockets.connect(
        websocket_uri,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=10,
    ) as websocket:

        log(
            "Meshtastic autoresponder online."
        )

        while True:

            if time.time() >= refresh_at:
                log(
                    "Refreshing Meshpoint authentication..."
                )
                return

            try:
                raw = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=30,
                )

            except asyncio.TimeoutError:
                continue

            try:
                event = json.loads(raw)

            except json.JSONDecodeError:
                continue

            if event.get("type") != "packet":
                continue

            packet = event.get("data") or {}

            keep_session = await process_packet(
                packet,
                token,
            )

            if not keep_session:
                return


async def main():
    log("Meshtastic autoresponder starting.")

    log(
        "Triggers: "
        + ", ".join(repr(x) for x in TRIGGERS)
    )

    while True:

        try:
            await run_session()

            log(
                "Starting fresh Meshpoint session..."
            )

            await asyncio.sleep(1)

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            log(
                f"Connection error: "
                f"{type(exc).__name__}: {exc}"
            )

            log(
                f"Retrying in {RECONNECT_DELAY} seconds..."
            )

            await asyncio.sleep(
                RECONNECT_DELAY
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Bot stopped.")
