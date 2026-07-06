import json
import os
import sys
from datetime import datetime
from pathlib import Path

def get_data_dir():
    if getattr(sys, 'frozen', False):
        base = Path(os.getenv("APPDATA")) / "NetworkSuite"
    else:
        base = Path.cwd() / "data"

    base.mkdir(parents=True, exist_ok=True)
    return base


class HistoryManager:
    def __init__(self, filename="history.json"):
        self.path = get_data_dir() / filename
        self.data = self._load()

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except:
            return {}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=4)

    def _now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def ensure_device(self, ip, mac, hostname, vendor):
        if ip not in self.data:
            self.data[ip] = {
                "mac": mac,
                "hostname": hostname,
                "vendor": vendor,
                "first_seen": self._now(),
                "last_seen": self._now(),
                "events": [
                    {"time": self._now(), "event": "online"}
                ]
            }
            self._save()


    def update_online(self, ip, mac, hostname, vendor):
        dev = self.data[ip]
        dev["last_seen"] = self._now()

        if dev["mac"] != mac:
            dev["events"].append({"time": self._now(), "event": f"MAC changed to {mac}"})
            dev["mac"] = mac

        if dev["hostname"] != hostname:
            dev["events"].append({"time": self._now(), "event": f"Hostname changed to {hostname}"})
            dev["hostname"] = hostname

        if dev["vendor"] != vendor:
            dev["events"].append({"time": self._now(), "event": f"Vendor changed to {vendor}"})
            dev["vendor"] = vendor

        if dev["events"][-1]["event"] != "online":
            dev["events"].append({"time": self._now(), "event": "online"})

        self._save()


    def update_offline(self, ip):
        if ip not in self.data:
            return

        dev = self.data[ip]

        if dev["events"][-1]["event"] != "offline":
            dev["events"].append({"time": self._now(), "event": "offline"})

        self._save()

    def get_history(self, ip):
        return self.data.get(ip, None)
