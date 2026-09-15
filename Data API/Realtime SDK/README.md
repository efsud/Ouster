# Realtime Subscriber SDK Sample

This project is a minimal sample for consuming realtime data from the BCT Realtime Subscriber SDK.

The sample in [main.py](main.py) authenticates with `username` and `password`, connects to a sensor `UDID`, subscribes to frame updates, and prints incoming hyperparameters continuously.

## Prerequisites

- Python `>=3.8,<3.12`
- `uv` installed
- The local SDK wheel file:
	- `bctRealtimeSDK_Subscriber-3.1.0-py3-none-any.whl`
- Valid credentials and a sensor UDID

## Install

Dependencies are already configured in [pyproject.toml](pyproject.toml) to use the local wheel.

```bash
uv sync
```

## Configure

Open [main.py](main.py) and set:

- `username`
- `password`
- `UDID`

Current sample setup:

- `singleton=True`
- `subscriptions=[BCTWSConnection.subscriptionOption.FRAME]`
- `semantic_abs=False`

## Run

```bash
uv run main.py
```

The app keeps a long-running stream open and prints each received hyperparameter.

Stop with:

```bash
Ctrl+C
```

## What The Sample Does

1. Imports `BCTWSConnection` from `realtime_subscriber.Realtime_subscriber_api`.
2. Creates a connection using `UDID`, `username`, and `password`.
3. Subscribes to frame events.
4. Loops forever and calls `stream.get_hyperparameter()`.
5. Prints each message to stdout.

## Notes

- Keep credentials out of source control.
- If you want to process different event types, adjust the `subscriptions` list.
- If your stream drops, re-run the script to reconnect.
