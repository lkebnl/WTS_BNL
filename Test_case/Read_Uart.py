# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : June 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Read_Uart.py — Interactive UART terminal for WIB
Finds the USB-Serial adapter, handles WIB login, then enters
live interactive mode: type commands, see WIB OS responses.

Supported systems (auto-detected from boot output):
  WIB_Petalinux  — QSPI/normal boot, login root / password root
  DUNE_WIB_SD    — SD card boot, automatic login (no credentials)
  DUNE_WIB_QSPI  — QSPI verification boot, automatic login

Usage:
  python Read_Uart.py
  python Read_Uart.py --port /dev/ttyUSB0
  python Read_Uart.py --baud 115200

Exit interactive mode: Ctrl+C, or type 'exit' / 'logout' / 'poweroff'
"""

import serial
import serial.tools.list_ports
import select
import termios
import tty
import time
import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import function.Rigol_DP800 as rigol

# ============================================================================
# Configuration
# ============================================================================

BAUD_RATE       = 115200
LOGIN_TIMEOUT_S = 120   # max seconds to wait for a shell prompt after power-on
BOOT_WAIT_S     = 2    # seconds between PSU on and opening UART

SUPPORTED_ADAPTERS = [
    {"name": "Silicon Labs CP2105", "vid": 0x10C4, "pid": 0xEA70},
    {"name": "FTDI FT232",          "vid": 0x0403, "pid": 0x6001},
    {"name": "FTDI FT2232",         "vid": 0x0403, "pid": 0x6010},
]

# Each entry: (keyword_in_line, username, password)
# password=None means automatic login — no credentials sent
LOGIN_PROFILES = [
    ("WIB_Petalinux login:",  "root", "root"),   # normal WIB PetaLinux (QSPI/NAND)
    ("DUNE_WIB_SD login:",    None,   None),      # SD card system — auto-login
    ("DUNE_WIB_QSPI login:",  None,   None),      # QSPI verification system — auto-login
]

# Shell prompt patterns — any of these means we have a live shell
SHELL_PROMPTS = [
    "root@WIB_Petalinux",
    "root@DUNE_WIB_SD",
    "root@DUNE_WIB_QSPI",
]


# ============================================================================
# Colour helpers
# ============================================================================

def cyan(s):    return f"\033[36m{s}\033[0m"
def green(s):   return f"\033[32m{s}\033[0m"
def red(s):     return f"\033[31m{s}\033[0m"
def yellow(s):  return f"\033[33m{s}\033[0m"
def magenta(s): return f"\033[35m{s}\033[0m"


# ============================================================================
# Port detection
# ============================================================================

def find_serial_port(preferred_port=None):
    """
    Return (port_device, adapter_name).
    If preferred_port is given, use it directly without scanning.
    """
    if preferred_port:
        print(cyan(f"Using specified port: {preferred_port}"))
        return preferred_port, "user-specified"

    print("\n" + "=" * 50)
    print(magenta("Scanning for USB-Serial adapters..."))
    ports = serial.tools.list_ports.comports()

    for port in ports:
        if port.vid is not None:
            print(f"  {port.device}  VID:PID={port.vid:04X}:{port.pid:04X}  {port.description}")

    for port in ports:
        for adapter in SUPPORTED_ADAPTERS:
            if port.vid == adapter["vid"] and port.pid == adapter["pid"]:
                print(green(f"Found: {adapter['name']} on {port.device}"))
                return port.device, adapter["name"]

    # Not found — let user choose manually
    print(red("No supported adapter found."))
    print("\nAvailable ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device}  {port.description}")

    while True:
        choice = input("\nEnter port number to use, full path (e.g. /dev/ttyUSB0), or [Q] to quit: ").strip()
        if choice.upper() == 'Q':
            sys.exit(0)
        if choice.isdigit() and int(choice) < len(ports):
            p = ports[int(choice)]
            return p.device, p.description
        if choice.startswith('/dev/') or choice.upper().startswith('COM'):
            return choice, "manual"
        print(yellow("Invalid input, try again."))


# ============================================================================
# Login handler
# ============================================================================

def wait_for_shell(ser):
    """
    Read boot output, handle login prompts, and return (shell_ready, system_name).
    References item0101_QSPI login detection logic.
    """
    print(cyan(f"\nWaiting for WIB boot and shell prompt (up to {LOGIN_TIMEOUT_S} s)..."))
    print(cyan("Boot output:"))

    deadline = time.time() + LOGIN_TIMEOUT_S
    system_name   = "unknown"
    pending_login = None   # (username, password) to send when Password: appears

    while time.time() < deadline:
        raw  = ser.readline()
        line = raw.decode('utf-8', errors='ignore').strip()
        if line:
            print(f"  << {line}")

        # Shell prompt — we're in
        if any(prompt in line for prompt in SHELL_PROMPTS):
            system_name = line.split(':')[0].replace('root@', '')
            print(green(f"\nShell ready on system: {system_name}"))
            return True, system_name

        # Login prompt — match profile
        for keyword, username, password in LOGIN_PROFILES:
            if keyword in line:
                if username is None:
                    # auto-login — just note it
                    system_name = keyword.split(' login:')[0].strip()
                    print(yellow(f"  >> (auto-login detected for {system_name} — waiting for shell)"))
                else:
                    # manual login — send username
                    system_name = keyword.split(' login:')[0].strip()
                    print(yellow(f"  >> sending username: {username}"))
                    ser.write((username + '\r\n').encode())
                    pending_login = (username, password)
                break

        # Password prompt — send password if we have one pending
        if 'Password:' in line and pending_login and pending_login[1]:
            print(yellow(f"  >> sending password"))
            ser.write((pending_login[1] + '\r\n').encode())

    return False, system_name


# ============================================================================
# Interactive terminal  (PuTTY-style: raw mode + select)
# ============================================================================

def interactive_session(ser, system_name):
    """
    Raw-mode terminal using select.select() — works like PuTTY/minicom.
    - Local terminal put in raw mode: every keystroke forwarded immediately,
      no line buffering, no local echo (the WIB echoes it back).
    - select.select() watches stdin and serial in one loop — no threads,
      no race conditions.
    - Ctrl+] exits the session.
    """
    print("\n" + "=" * 50)
    print(green(f"Interactive session — system: {system_name}"))
    print(yellow("  Press Ctrl+] to exit."))
    print("=" * 50 + "\n")

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)   # each keystroke sent immediately, no local buffering

        while True:
            readable, _, _ = select.select([sys.stdin, ser], [], [], 0.1)

            # keyboard → serial
            if sys.stdin in readable:
                ch = sys.stdin.read(1)
                if ch == '\x1d':        # Ctrl+] — exit
                    break
                if ch == '\r':          # Enter → CR+LF
                    ser.write(b'\r\n')
                else:
                    ser.write(ch.encode('utf-8', errors='replace'))

            # serial → screen (raw bytes, preserves colour/control sequences)
            if ser in readable:
                data = ser.read(ser.in_waiting or 1)
                if data:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

    except Exception:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    print(green("\nSession ended."))


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="WIB UART interactive terminal")
    parser.add_argument('--port', default=None, help="Serial port (e.g. /dev/ttyUSB0)")
    parser.add_argument('--baud', type=int, default=BAUD_RATE, help=f"Baud rate (default: {BAUD_RATE})")
    args = parser.parse_args()

    print("\n" + "=" * 50)
    print(magenta("  DUNE WIB UART Terminal"))
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # Power on WIB
    print(cyan("\nPowering on WIB (12V / 3A on Ch1 + Ch2)..."))
    psu = rigol.RigolDP800()
    psu.safe_power_off()
    time.sleep(1)
    psu.set_channel(1, 12.0, 3.0, on=True)
    psu.set_channel(2, 12.0, 3.0, on=True)
    v1, c1 = psu.measure(1)
    v2, c2 = psu.measure(2)
    print(green(f"  Ch1: {v1:.3f}V {c1:.3f}A   Ch2: {v2:.3f}V {c2:.3f}A"))
    print(cyan(f"Waiting {BOOT_WAIT_S} s before opening UART..."))
    time.sleep(BOOT_WAIT_S)

    # Find port
    port_device, adapter_name = find_serial_port(args.port)

    # Open serial
    print(cyan(f"\nOpening {port_device} at {args.baud} baud..."))
    try:
        ser = serial.Serial(
            port=port_device, baudrate=args.baud,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE, timeout=1,
            rtscts=False, dsrdtr=False, xonxoff=False
        )
    except Exception as e:
        print(red(f"Failed to open port: {e}"))
        sys.exit(1)

    print(green(f"Port open: {port_device}  adapter: {adapter_name}"))

    try:
        # Wait for boot and handle login
        shell_ready, system_name = wait_for_shell(ser)

        if not shell_ready:
            print(red(f"\nTimeout — no shell prompt received in {LOGIN_TIMEOUT_S} s."))
            print(yellow("  Tip: make sure the WIB is powered on and the cable is connected."))
            sys.exit(1)

        # Enter interactive mode
        interactive_session(ser, system_name)

    finally:
        ser.close()
        print(cyan(f"Port {port_device} closed."))
        psu.safe_power_off()
        psu.close()
        print(green("PSU off."))


if __name__ == "__main__":
    main()
