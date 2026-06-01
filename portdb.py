import json
import os

BASE = os.path.join(os.path.dirname(__file__), "data")

with open(os.path.join(BASE, "tcp.json")) as f:
    TCP = json.load(f)

with open(os.path.join(BASE, "udp.json")) as f:
    UDP = json.load(f)

def lookup_port(port: int, protocol: str):
    port = str(port)
    protocol = protocol.lower()

    db = TCP if protocol == "tcp" else UDP

    if port in db:
        return db[port]

    p = int(port)
    if 49152 <= p <= 65535:
        return db["49152-65535"]

    return "Unassigned / Unknown"
