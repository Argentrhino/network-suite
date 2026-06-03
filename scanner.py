from vendor_lookup import load_oui_database, lookup_vendor as local_lookup
import socket
import subprocess
import re
import concurrent.futures
import time
import platform
from zeroconf import Zeroconf, ServiceBrowser

load_oui_database()

OS = platform.system().lower()
IS_WINDOWS = OS == "windows"
IS_MAC = OS == "darwin"
IS_LINUX = OS == "linux"

def arp_refresh_broadcast():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(b"ARP-REFRESH", ("255.255.255.255", 9))
        sock.close()
    except:
        pass

def ping_sweep():
    if not IS_WINDOWS:
        return
    base = "192.168.1."
    for i in range(1, 255):
        ip = f"{base}{i}"
        subprocess.Popen(
            ["ping", "-n", "1", "-w", "200", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

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
    time.sleep(0.4)
    zc.close()
    return listener.devices

def scrape_arp_table():
    try:
        output = subprocess.check_output("arp -a", shell=True, text=True)
    except:
        return []

    devices = []

    for line in output.splitlines():
        if IS_WINDOWS:
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[0]
                mac = parts[1]
            else:
                continue
        else:
            if "(" in line and ")" in line and " at " in line:
                ip = line.split("(")[1].split(")")[0]
                mac = line.split(" at ")[1].split(" ")[0]
            else:
                continue

        if re.match(r"^[0-9a-fA-F:-]{17}$", mac):
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

    if IS_WINDOWS:
        cmd = ["ping", "-n", str(count), ip]
    else:
        cmd = ["ping", "-c", str(count), ip]

    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except:
        return {"success": False, "min": 0, "max": 0, "avg": 0, "loss": 100}

    if IS_WINDOWS:
        loss_match = re.search(r"Lost = \d+ \((\d+)% loss\)", output)
        min_match = re.search(r"Minimum = (\d+)ms", output)
        max_match = re.search(r"Maximum = (\d+)ms", output)
        avg_match = re.search(r"Average = (\d+)ms", output)
    else:
        loss_match = re.search(r"(\d+)% packet loss", output)
        rtt_match = re.search(r"min/avg/max/[^\s=]+ = ([\d\.]+)/([\d\.]+)/([\d\.]+)/", output)
        min_match = max_match = avg_match = None
        if rtt_match:
            min_match = rtt_match.group(1)
            avg_match = rtt_match.group(2)
            max_match = rtt_match.group(3)

    loss = int(loss_match.group(1)) if loss_match else 100
    success = loss < 100

    return {
        "success": success,
        "min": int(float(min_match)) if min_match else 0,
        "max": int(float(max_match)) if max_match else 0,
        "avg": int(float(avg_match)) if avg_match else 0,
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
    return {"ping": ping_result, "open_ports": ports}

def scan_network():
    ping_sweep()
    time.sleep(0.5)

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
