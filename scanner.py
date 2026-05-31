from vendor_lookup import load_oui_database, lookup_vendor as local_lookup

import ipaddress
import socket
import subprocess
import re
from zeroconf import Zeroconf, ServiceBrowser

load_oui_database()


# -----------------------------
# mDNS LISTENER (sync)
# -----------------------------
class MDNSListener:
    def __init__(self):
        self.devices = []

    def add_service(self, zeroconf, service_type, name):
        info = zeroconf.get_service_info(service_type, name)
        if info and info.addresses:
            ip = ".".join(map(str, info.addresses[0]))
            hostname = name.split(".")[0]
            self.devices.append({
                "ip": ip,
                "hostname": hostname,
                "vendor": "mDNS Device",
                "mac": "-"
            })


def mdns_scan_sync():
    zc = Zeroconf()
    listener = MDNSListener()
    browser = ServiceBrowser(zc, "_services._dns-sd._udp.local.", listener)

    # give mDNS time to populate
    import time
    time.sleep(2)

    zc.close()
    return listener.devices


# -----------------------------
# ARP TABLE SCRAPING (sync)
# -----------------------------
def scrape_arp_table():
    try:
        output = subprocess.check_output("arp -a", shell=True, text=True)
    except:
        return []

    devices = []

    for line in output.splitlines():
        match = re.search(
            r"(\d+\.\d+\.\d+\.\d+)\s+([0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}",
            line
        )
        if match:
            ip = match.group(1)
            mac = match.group(0).split()[1] if " " in match.group(0) else match.group(0)

            devices.append({
                "ip": ip,
                "mac": mac.replace("-", ":").upper()
            })

    return devices


# -----------------------------
# PING + HOSTNAME + VENDOR (sync)
# -----------------------------
def ping(ip: str) -> bool:
    result = subprocess.run(
        ["ping", "-n", "1", "-w", "200", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def get_local_subnet():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    return ipaddress.ip_network(local_ip + "/24", strict=False)


def get_mac(ip: str) -> str:
    try:
        output = subprocess.check_output("arp -a", shell=True, text=True)
        for line in output.splitlines():
            if ip in line:
                match = re.search(r"([0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}", line)
                if match:
                    return match.group(0)
    except:
        pass
    return "-"


def get_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        return "-"


def lookup_vendor_sync(mac: str) -> str:
    return local_lookup(mac)


# -----------------------------
# MAIN SCANNER (sync)
# -----------------------------
def scan_network():
    network = get_local_subnet()
    devices = []

    # Step 1: ping sweep
    for ip in network.hosts():
        ip_str = str(ip)
        if ping(ip_str):
            mac = get_mac(ip_str)
            hostname = get_hostname(ip_str)
            vendor = lookup_vendor_sync(mac)

            devices.append({
                "ip": ip_str,
                "mac": mac,
                "hostname": hostname,
                "vendor": vendor
            })

    # Step 2: mDNS discovery
    mdns_devices = mdns_scan_sync()
    for d in mdns_devices:
        if not any(x["ip"] == d["ip"] for x in devices):
            devices.append(d)

    # Step 3: ARP table scraping
    arp_devices = scrape_arp_table()
    for d in arp_devices:
        if not any(x["ip"] == d["ip"] for x in devices):
            vendor = lookup_vendor_sync(d["mac"])
            hostname = get_hostname(d["ip"])

            devices.append({
                "ip": d["ip"],
                "mac": d["mac"],
                "hostname": hostname,
                "vendor": vendor
            })

    return devices