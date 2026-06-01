from vendor_lookup import load_oui_database, lookup_vendor as local_lookup
import ipaddress
import socket
import subprocess
import re
import concurrent.futures
import time
from zeroconf import Zeroconf, ServiceBrowser

load_oui_database()

def arp_refresh_broadcast():
    """
    Sends a UDP broadcast to wake up ARP entries.
    Works on Python 3.13, no NetBIOS required.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(b"ARP-REFRESH", ("255.255.255.255", 9))
        sock.close()
    except:
        pass

class MDNSListener:
    def __init__(self):
        self.devices = []

    def add_service(self, zc, service_type, name):
        info = zc.get_service_info(service_type, name)
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
    ServiceBrowser(zc, "_services._dns-sd._udp.local.", listener)

    time.sleep(0.4)  # short wait

    zc.close()
    return listener.devices

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
def get_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        return "-"

def lookup_vendor_sync(mac: str) -> str:
    return local_lookup(mac)
def ping_stats(ip: str, duration: int):
    count = max(1, duration)

    try:
        output = subprocess.check_output(
            ["ping", "-n", str(count), ip],
            text=True,
            stderr=subprocess.STDOUT
        )
    except:
        return {"success": False, "min": 0, "max": 0, "avg": 0, "loss": 100}

    loss_match = re.search(r"Lost = \d+ \((\d+)% loss\)", output)
    min_match = re.search(r"Minimum = (\d+)ms", output)
    max_match = re.search(r"Maximum = (\d+)ms", output)
    avg_match = re.search(r"Average = (\d+)ms", output)

    loss = int(loss_match.group(1)) if loss_match else 100
    success = loss < 100

    return {
        "success": success,
        "min": int(min_match.group(1)) if min_match else 0,
        "max": int(max_match.group(1)) if max_match else 0,
        "avg": int(avg_match.group(1)) if avg_match else 0,
        "loss": loss
    }
def port_scan(ip: str, mode: str):
    if mode == "fast":
        ports = [21,22,23,25,53,80,110,139,443,445]
    elif mode == "full":
        ports = list(range(1, 1025))
    else:
        ports = [
            21,22,23,25,53,67,68,69,80,110,123,135,139,143,161,389,
            443,445,500,514,587,631,993,995,1900,3389
        ]

    open_ports = []

    for p in ports:
        try:
            sock = socket.socket()
            sock.settimeout(0.25)
            sock.connect((ip, p))
            open_ports.append({"port": p, "protocol": "tcp"})
            sock.close()
        except:
            pass

    return open_ports

def host_scan(ip: str, mode: str):
    ping_result = ping_stats(ip, 4)

    if not ping_result["success"]:
        return {"ping": ping_result, "open_ports": []}

    ports = port_scan(ip, mode)

    return {
        "ping": ping_result,
        "open_ports": ports
    }

def scan_network():

    arp_refresh_broadcast()
    time.sleep(0.2)
    arp_devices = scrape_arp_table()
    arp_map = {d["ip"]: d["mac"] for d in arp_devices}

 
    mdns_devices = mdns_scan_sync()

    discovered_ips = set(arp_map.keys())
    for d in mdns_devices:
        discovered_ips.add(d["ip"])

    discovered_ips = list(discovered_ips)

    def build_device(ip_str: str):
        mac = arp_map.get(ip_str, "-")
        hostname = get_hostname(ip_str)
        vendor = lookup_vendor_sync(mac) if mac != "-" else "-"
        return {
            "ip": ip_str,
            "mac": mac,
            "hostname": hostname,
            "vendor": vendor
        }

    devices = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for dev in executor.map(build_device, discovered_ips):
            devices.append(dev)

  
    for d in mdns_devices:
        if not any(x["ip"] == d["ip"] for x in devices):
            devices.append(d)

    return devices