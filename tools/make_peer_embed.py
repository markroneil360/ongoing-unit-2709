#!/usr/bin/env python3
"""Wrap data/peer_baseline.json as data/peer_embed.js (window.__TREMORLENS_PEER__).

Loaded via <script> so it is file:// safe (no fetch / iframe-unsafe APIs).
"""
import json, os

ROOT = "/home/user/workspace/tremorlens-r6e8a-restored"
SRC = f"{ROOT}/data/peer_baseline.json"
OUT = f"{ROOT}/data/peer_embed.js"

with open(SRC) as f:
    data = json.load(f)

with open(OUT, "w") as f:
    f.write("/* Auto-generated from data/peer_baseline.json by tools/make_peer_embed.py. */\n")
    f.write("/* External Raspberry Shake HDF network-peer percentile baseline. Do not edit by hand. */\n")
    f.write("window.__TREMORLENS_PEER__ = ")
    json.dump(data, f, separators=(",", ":"))
    f.write(";\n")

print(f"WROTE {OUT} ({os.path.getsize(OUT)} bytes)")
print("keys:", list(data.keys()))
print("peer n:", data.get("peer_daily_mean_pa", {}).get("n"))
