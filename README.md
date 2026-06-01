Network-Suite
A fast, modern Python TUI for scanning your local network, discovering devices, resolving hostnames, identifying vendors, and checking open ports in a clean interface. Currently only supports Windows as of now.
(<Screenshot 2026-06-01 170256-1.png>)
Try it: https://github.com/Argentrhino/network-suite/blob/main/NetworkSuite.exe
Setup is as easy as:
1. Download
2. Run
3. Allow network discovery

Features:

ARP device discovery 
mDNS scanning 
Vendor lookup 
Hostname resolution 
Ping statistics 
Port scanning
Auto‑refresh mode 
Textual‑powered TUI


Commands:
Scan a specific host:
Fast: Scans the 10 most common ports to quickly identify devices.

Normal: Scans a curated set of important ports used by routers, printers, IoT, and Windows systems.

Full: Scans all 1024 well‑known ports for maximum detail.

<IP ADDRESS> /scan -Fast
<IP ADDRESS> /scan -Normal
<IP ADDRESS> /scan -Full
Ping a device
/ping for one ping, /ping -<number of seconds>s allows you to set pinging time, and see stats such as average, max, min.
<IP ADDRESS> /ping
<IP ADDRESS> /ping -10s
Enable auto‑refresh: autorefresh=1
Disable auto‑refresh: autorefresh=0
To quit type: exit OR quit

How it works:
Network Suite runs all network operations such as port scans and ARP discovery inside background async workers. This makes sure that the Textual TUI never blocks user input during operations, even during long scans. The scanner uses ARP_table_parsing together with mDNS_service_resolution to detect devices that don’t respond to ping, and port‑scan modes adjust the number of ports scanned decided by a curated list for a balance of speed and detail when needed. All data files (OUI, TCP, UDP) are loaded through a PyInstaller_safe_path helper which helps the app behave in the same way both in Python and in the packaged EXE.

Credits:
Textual
Zeroconf
MAC vendor DB
Python standard library
