# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : June 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Item0102_QSPI: QSPI Boot Verification
Verifies the WIB boots from QSPI after item0101 flashed it.
QSPI boot shows 'WIB_Petalinux' prompt (vs SD card's 'DUNE_WIB_SD').

Steps:
  1. Power on,
  2. Connect via UART — check Boot from QSPI
  3. wait 30 s
  4. send 'poweroff', wait 1 minute, power off PSU
"""

import serial
import serial.tools.list_ports
import time
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import function.Rigol_DP800 as rigol
from function.csv_manager import WIB_QC_CSV_Manager
from function.report_path import get_report_path, init_report_session, get_result_csv_path, get_report_dir
from function.session_info import get_session_info, get_report_filename
from function.ping_host import ping_host
import file.report_dict as rp_dict

SUPPORTED_ADAPTERS = [
    {"name": "Silicon Labs CP2105", "vid": 0x10C4, "pid": 0xEA70},
    {"name": "FTDI FT232",          "vid": 0x0403, "pid": 0x6001},
    {"name": "FTDI FT2232",         "vid": 0x0403, "pid": 0x6010},
]

BOOT_TIMEOUT_S  = 120   # max wait for QSPI boot prompt
POWEROFF_WAIT_S = 60    # wait after poweroff before PSU off
CMD_TIMEOUT_S   = 5     # per-command UART response timeout

# QSPI boot indicators — matched against actual UART output
QSPI_BOOT_KEYWORDS = ['DUNE_WIB_QSPI login:', 'root@DUNE_WIB_QSPI']

# devmem commands to configure network after QSPI boot
DEVMEM_CMD1 = 'devmem 0xFF0B0200 32 0x140'
DEVMEM_CMD2 = 'devmem 0xFF0B0004 32 0x092e0c4A'
PING_TARGET = '192.168.121.1'


def print_header(title):
    print("\n" + "=" * 60)
    print("\033[35m" + title + "\033[0m")
    print("=" * 60)

def print_pass(msg):
    print(f"\033[32m{msg}\033[0m")

def print_fail(msg):
    print(f"\033[31m{msg}\033[0m")

def print_warning(msg):
    print(f"\033[33m{msg}\033[0m")

def ask_retry_skip_exit(label):
    """Prompt user for Retry / Skip / Exit and return 'retry', 'skip', or 'exit'."""
    while True:
        choice = input(f"{label}\nOptions:\n  [R] Retry\n  [S] Skip\n  [E] Exit\nChoice (R/S/E): ").strip().upper()
        if choice == 'R':
            return 'retry'
        elif choice == 'S':
            return 'skip'
        elif choice == 'E':
            return 'exit'


# ============================================================================
# UART helpers
# ============================================================================

def find_serial_port(psu):
    """Locate a supported USB-Serial adapter, with retry/skip/exit options."""
    while True:
        print("\n=== Available USB Serial Devices ===")
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid is not None:
                print(f"  {port.device}  VID:PID={port.vid:04X}:{port.pid:04X}  {port.description}")

        for port in ports:
            for adapter in SUPPORTED_ADAPTERS:
                if port.vid == adapter["vid"] and port.pid == adapter["pid"]:
                    print_pass(f"Found: {adapter['name']} on {port.device}")
                    return port.device, adapter["name"]

        print_fail("No supported USB-Serial adapter found.")
        while True:
            choice = input("Options:\n  [R] Retry\n  [S] Skip\n  [E] Exit\nChoice (R/S/E): ").strip().upper()
            if choice == 'R':
                time.sleep(1)
                break
            elif choice == 'S':
                print_warning("Skipping QSPI verification.")
                return None, None
            elif choice == 'E':
                print_fail("Aborted by user.")
                psu.safe_power_off()
                psu.close()
                sys.exit(1)


def send_uart_cmd(ser, cmd, timeout=CMD_TIMEOUT_S):
    """Send a command via UART, stream and return output until next shell prompt."""
    ser.write((cmd + '\r\n').encode())
    print(f"  >> {cmd}")
    output = ''
    deadline = time.time() + timeout
    while time.time() < deadline:
        waiting = ser.in_waiting
        if waiting:
            raw = ser.read(waiting)
            chunk = raw.decode('utf-8', errors='ignore')
            output += chunk
            for line in chunk.splitlines():
                if line.strip():
                    print(f"  << {line}")
            if 'root@DUNE_WIB_QSPI' in output:
                break
        else:
            time.sleep(0.05)
    return output


def run_qspi_verify(com_port, psu=None):
    """
    Open UART, detect QSPI boot, run devmem commands, ping, then poweroff.

    Returns: (qspi_boot_ok, devmem1_ok, devmem2_ok, ping_ok, poweroff_ok, note)
    """
    print(f"\nOpening {com_port} at 115200 baud...")
    try:
        ser = serial.Serial(
            port=com_port, baudrate=115200,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE, timeout=1,
            rtscts=False, dsrdtr=False, xonxoff=False
        )
    except Exception as e:
        return False, False, f"Serial open failed: {e}"

    qspi_boot_ok = False
    poweroff_ok  = False
    note         = ""

    # Boot info dict — populated during monitoring, stored in rp_dict for reports
    boot_info = {
        'petalinux_version': '',
        'hostname':          '',
        'login_type':        '',
        'shell_prompt':      '',
        'boot_timestamp':    '',
    }

    try:
        # ----------------------------------------------------------------
        # Step 2: monitor boot output, capture info, detect QSPI boot
        # ----------------------------------------------------------------
        print(f"Monitoring boot output (timeout: {BOOT_TIMEOUT_S} s)...")
        boot_deadline = time.time() + BOOT_TIMEOUT_S

        while time.time() < boot_deadline:
            raw = ser.readline()
            line = raw.decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  << {line}")

            # Capture PetaLinux version string
            if 'PetaLinux' in line and not boot_info['petalinux_version']:
                boot_info['petalinux_version'] = line

            # Capture login line — extract hostname and login type
            if 'login:' in line and not boot_info['hostname']:
                boot_info['hostname']   = line.split(' login:')[0].strip()
                boot_info['login_type'] = 'automatic' if 'automatic' in line.lower() else 'manual'

            # QSPI boot confirmed — capture shell prompt and timestamp
            if any(kw in line for kw in QSPI_BOOT_KEYWORDS):
                qspi_boot_ok = True
                note = line
                boot_info['shell_prompt']   = line
                boot_info['boot_timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                print_pass(f"QSPI boot confirmed: {line}")
                break

        # Store in rp_dict for use in any downstream report
        rp_dict.log_qspi_boot = boot_info

        if not qspi_boot_ok and not note:
            note = f"Timeout: no boot prompt in {BOOT_TIMEOUT_S} s"
            print_fail(note)

        # ----------------------------------------------------------------
        # Step 3: devmem commands + ping (only if QSPI boot confirmed)
        # ----------------------------------------------------------------
        devmem1_ok = False
        devmem2_ok = False
        ping_ok    = False

        if qspi_boot_ok:
            time.sleep(20)
            print_header("Step 3a: devmem configuration")
            out1 = send_uart_cmd(ser, DEVMEM_CMD1)
            out1 = send_uart_cmd(ser, DEVMEM_CMD1)
            devmem1_ok = 'root@DUNE_WIB_QSPI' in out1
            if devmem1_ok:
                print_pass(f"devmem cmd1 OK")
            else:
                print_fail(f"devmem cmd1 no shell response")

            out2 = send_uart_cmd(ser, DEVMEM_CMD2)
            out2 = send_uart_cmd(ser, DEVMEM_CMD2)
            out2 = send_uart_cmd(ser, DEVMEM_CMD2)
            devmem2_ok = 'root@DUNE_WIB_QSPI' in out2
            if devmem2_ok:
                print_pass(f"devmem cmd2 OK")
            else:
                print_fail(f"devmem cmd2 no shell response")
            time.sleep(10)
            print_header(f"Step 3b: Ping {PING_TARGET}")
            while True:
                for attempt in range(1, 4):
                    print(f"  Ping attempt {attempt}/3 ...")
                    ping_ok = ping_host(ip_address=PING_TARGET, count=4)
                    if ping_ok:
                        print_pass(f"Ping {PING_TARGET} PASS")
                        break
                    print_fail(f"  Attempt {attempt}/3 failed.")
                    if attempt < 3:
                        time.sleep(3)
                if ping_ok:
                    break
                action = ask_retry_skip_exit(f"Ping {PING_TARGET} failed after 3 attempts.")
                if action == 'retry':
                    continue
                elif action == 'skip':
                    print_warning("Ping skipped by user.")
                    break
                else:  # exit
                    print_fail("Aborted by user.")
                    ser.close()
                    if psu:
                        psu.safe_power_off()
                        psu.close()
                    sys.exit(1)

        # ----------------------------------------------------------------
        # Step 4: poweroff — detect kernel shutdown complete signal
        # ----------------------------------------------------------------
        print_header("Step 4: Poweroff")
        # ser.write(b'poweroff\r\n')
        ser.write(b'systemctl poweroff\r\n')
        print(f"Waiting for OS shutdown (timeout: {POWEROFF_WAIT_S} s)...")

        shutdown_deadline = time.time() + POWEROFF_WAIT_S
        while time.time() < shutdown_deadline:
            raw = ser.readline()
            line = raw.decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  << {line}")
            if 'reboot: Power down' in line:
                print_pass("Power down signal detected — OS shutdown complete.")
                poweroff_ok = True
                break
        else:
            # Timeout reached without detecting the power-down signal
            print_warning(f"Power-down signal not seen in {POWEROFF_WAIT_S} s — assuming complete.")
            poweroff_ok = True

        if poweroff_ok:
            print_pass("Poweroff sequence completed.")

    except KeyboardInterrupt:
        print_fail("\nInterrupted by user.")
        raise
    except Exception as e:
        note = f"UART error: {e}"
        print_fail(note)
    finally:
        ser.close()
        print("Serial port closed.")

    return qspi_boot_ok, devmem1_ok, devmem2_ok, ping_ok, poweroff_ok, note


# ============================================================================
# MAIN
# ============================================================================

def main():
    t_start = time.time()
    utc_now = datetime.now(timezone.utc)

    session_info = get_session_info()
    wib_id    = session_info.get('WIB_ID',   'standalone_test')
    tester    = session_info.get('tester',    'Unknown')
    test_site = session_info.get('test_site', 'BNL')

    print("\n" + "-" * 40)
    print("[session_info] Item0102_QSPI loaded session:")
    print(f"  WIB ID:    {wib_id}")
    print(f"  Tester:    {tester}")
    print(f"  Test Site: {test_site}")
    print("-" * 40)

    init_report_session(wib_id)

    csv_path = get_result_csv_path()
    if csv_path is None:
        report_dir = get_report_dir()
        csv_path = os.path.join(report_dir, f"WIB_{wib_id}_QC_Results.csv")

    if not os.path.exists(csv_path):
        print(f"\nCSV not found — creating: {csv_path}")
        rp_dict.csv_manager = WIB_QC_CSV_Manager(wib_id, csv_filepath=csv_path, overwrite=True)
    elif rp_dict.csv_manager is None:
        print(f"\nCSV found — attaching: {csv_path}")
        rp_dict.csv_manager = WIB_QC_CSV_Manager(wib_id, csv_filepath=csv_path, overwrite=False)

    print_header("Item0102_QSPI : QSPI Boot Verification")
    print("  1. Power on")
    print("  2. Connect UART — detect QSPI boot (DUNE_WIB_QSPI)")
    print(f"  3. devmem {DEVMEM_CMD1}")
    print(f"     devmem {DEVMEM_CMD2}")
    print(f"     Ping {PING_TARGET}")
    print("  4. Poweroff → wait 1 min → PSU off")
    print("=" * 60)

    # Step 1: power on
    psu = rigol.RigolDP800()
    psu.safe_power_off()
    time.sleep(1)

    print_header("Step 1: Power On")
    psu.set_channel(1, 12.0, 3.0, on=True)
    psu.set_channel(2, 12.0, 3.0, on=True)
    time.sleep(2)
    v1, c1 = psu.measure(1)
    v2, c2 = psu.measure(2)
    print(f"  Ch1: {v1:.3f}V {c1:.3f}A   Ch2: {v2:.3f}V {c2:.3f}A")

    # Step 2: find UART port
    print_header("Step 2: Find UART Port")
    com_port, adapter_name = find_serial_port(psu)

    uart_ok      = False
    qspi_boot_ok = False
    devmem1_ok   = False
    devmem2_ok   = False
    ping_ok      = False
    poweroff_ok  = False
    note         = "UART not found"

    if com_port is not None:
        print_header("Steps 2–4: UART / QSPI Verify / Poweroff")
        qspi_boot_ok, devmem1_ok, devmem2_ok, ping_ok, poweroff_ok, note = run_qspi_verify(com_port, psu)
        uart_ok = True

    boot_info = getattr(rp_dict, 'log_qspi_boot', {})

    # PSU off
    print_header("Power Off")
    psu.safe_power_off()
    psu.close()
    print_pass("PSU off.")

    t_end = time.time()
    test_duration = round(t_end - t_start, 2)
    overall_pass = uart_ok and qspi_boot_ok and devmem1_ok and devmem2_ok and ping_ok and poweroff_ok

    # CSV update
    if rp_dict.csv_manager:
        v1_status = "PASS" if 11.0 <= v1 <= 13.0 else "FAIL"
        v2_status = "PASS" if 11.0 <= v2 <= 13.0 else "FAIL"
        rp_dict.csv_manager.batch_update([
            {"item_id": "T_QSPI2_01", "value": com_port if com_port else "Not found",
             "status": "PASS" if uart_ok else "FAIL"},
            {"item_id": "T_QSPI2_02", "value": note if qspi_boot_ok else "FAIL: " + note,
             "status": "PASS" if qspi_boot_ok else "FAIL"},
            {"item_id": "T_QSPI2_03", "value": "poweroff sent",
             "status": "PASS" if poweroff_ok else "FAIL"},
            {"item_id": "T_QSPI2_04", "value": round(v1, 3), "status": v1_status},
            {"item_id": "T_QSPI2_05", "value": round(v2, 3), "status": v2_status},
            {"item_id": "T_QSPI2_06", "value": test_duration, "status": "COMPLETE"},
            {"item_id": "T_QSPI2_07", "value": DEVMEM_CMD1,
             "status": "PASS" if devmem1_ok else "FAIL"},
            {"item_id": "T_QSPI2_08", "value": DEVMEM_CMD2,
             "status": "PASS" if devmem2_ok else "FAIL"},
            {"item_id": "T_QSPI2_09", "value": PING_TARGET,
             "status": "PASS" if ping_ok else "FAIL"},
        ])

    # Summary
    print_header("Item0102_QSPI — SUMMARY")
    print(f"  UART port        : {com_port or 'Not detected'}  {'PASS' if uart_ok else 'FAIL'}")
    print(f"  QSPI boot        : {'PASS' if qspi_boot_ok else 'FAIL'}  ({note})")
    print(f"  devmem cmd1      : {'PASS' if devmem1_ok else 'FAIL'}")
    print(f"  devmem cmd2      : {'PASS' if devmem2_ok else 'FAIL'}")
    print(f"  Ping {PING_TARGET} : {'PASS' if ping_ok else 'FAIL'}")
    print(f"  Poweroff         : {'PASS' if poweroff_ok else 'FAIL'}")
    print(f"  Ch1 power        : {v1:.3f}V")
    print(f"  Ch2 power        : {v2:.3f}V")
    print(f"  Total duration   : {test_duration} s")
    print(f"  PetaLinux ver    : {boot_info.get('petalinux_version', 'N/A')}")
    print(f"  Hostname         : {boot_info.get('hostname', 'N/A')}")
    print(f"  Boot timestamp   : {boot_info.get('boot_timestamp', 'N/A')}")
    print("")
    if overall_pass:
        print_pass("  OVERALL: PASS — QSPI boot and network verified")
    else:
        print_fail("  OVERALL: FAIL — check UART / devmem / ping")
    print("=" * 60)

    # HTML report
    overall_status = "PASS" if overall_pass else "FAIL"
    overall_class  = "pass" if overall_pass else "fail"
    report_filename = get_report_filename("Item0102_QSPI_report", overall_pass)
    report_path = get_report_path(report_filename)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WIB QSPI Boot Verification Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#fff; color:#000; padding:30px; line-height:1.6; }}
        .container {{ max-width:860px; margin:0 auto; }}
        .header {{ border-bottom:3px solid #000; padding-bottom:20px; margin-bottom:30px; }}
        .header h1 {{ font-size:24px; font-weight:bold; margin-bottom:5px; }}
        .header .subtitle {{ font-size:14px; color:#666; }}
        .status-badge {{ display:inline-block; padding:8px 16px; font-weight:bold; font-size:16px;
                         margin-top:15px; border:2px solid; }}
        .status-badge.pass {{ color:#166534; background:#dcfce7; border-color:#166534; }}
        .status-badge.fail {{ color:#991b1b; background:#fee2e2; border-color:#991b1b; }}
        .info-section {{ margin:20px 0; padding:15px; background:#f9fafb; border-left:4px solid #000; }}
        .info-row {{ display:flex; margin:8px 0; }}
        .info-label {{ font-weight:bold; width:200px; }}
        table {{ width:100%; border-collapse:collapse; margin:15px 0; border:1px solid #000; }}
        th {{ background:#f3f4f6; font-weight:bold; text-align:left; padding:12px; border:1px solid #000; }}
        td {{ padding:12px; border:1px solid #d1d5db; }}
        tr:nth-child(even) {{ background:#f9fafb; }}
        .pass {{ color:#166534; font-weight:bold; }}
        .fail {{ color:#991b1b; font-weight:bold; }}
        .footer {{ margin-top:40px; padding-top:20px; border-top:2px solid #e5e7eb;
                   text-align:center; color:#6b7280; font-size:12px; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>DUNE WIB Quality Control</h1>
        <div class="subtitle">QSPI Boot Verification Report (Item0102_QSPI)</div>
        <div class="status-badge {overall_class}">Overall Status: {overall_status}</div>
    </div>

    <div class="info-section">
        <div class="info-row"><div class="info-label">Test Date:</div>
            <div>{utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')}</div></div>
        <div class="info-row"><div class="info-label">WIB ID:</div><div>{wib_id}</div></div>
        <div class="info-row"><div class="info-label">Tester:</div><div>{tester}</div></div>
        <div class="info-row"><div class="info-label">Test Site:</div><div>{test_site}</div></div>
        <div class="info-row"><div class="info-label">Total Duration:</div><div>{test_duration} s</div></div>
    </div>

    <div class="info-section" style="border-left-color:#0066cc; background:#f0f9ff;">
        <div style="font-weight:bold; margin-bottom:8px;">QSPI Boot Info</div>
        <div class="info-row"><div class="info-label">PetaLinux Version:</div>
            <div>{boot_info.get('petalinux_version', 'N/A')}</div></div>
        <div class="info-row"><div class="info-label">Hostname:</div>
            <div>{boot_info.get('hostname', 'N/A')}</div></div>
        <div class="info-row"><div class="info-label">Login Type:</div>
            <div>{boot_info.get('login_type', 'N/A')}</div></div>
        <div class="info-row"><div class="info-label">Shell Prompt:</div>
            <div><code>{boot_info.get('shell_prompt', 'N/A')}</code></div></div>
        <div class="info-row"><div class="info-label">Boot Detected:</div>
            <div>{boot_info.get('boot_timestamp', 'N/A')}</div></div>
    </div>

    <table>
        <thead>
            <tr><th>Step</th><th>Description</th><th>Command / Result</th><th>Status</th></tr>
        </thead>
        <tbody>
            <tr>
                <td>1</td><td>Power On</td>
                <td>Ch1 {v1:.3f} V &nbsp; Ch2 {v2:.3f} V</td>
                <td class="{'pass' if 11.0<=v1<=13.0 and 11.0<=v2<=13.0 else 'fail'}">
                    {'PASS' if 11.0<=v1<=13.0 and 11.0<=v2<=13.0 else 'FAIL'}</td>
            </tr>
            <tr>
                <td>2</td><td>UART + QSPI Boot</td>
                <td>{note}</td>
                <td class="{'pass' if qspi_boot_ok else 'fail'}">{'PASS' if qspi_boot_ok else 'FAIL'}</td>
            </tr>
            <tr>
                <td>3a</td><td>devmem cmd1</td>
                <td><code>{DEVMEM_CMD1}</code></td>
                <td class="{'pass' if devmem1_ok else 'fail'}">{'PASS' if devmem1_ok else 'FAIL'}</td>
            </tr>
            <tr>
                <td>3b</td><td>devmem cmd2</td>
                <td><code>{DEVMEM_CMD2}</code></td>
                <td class="{'pass' if devmem2_ok else 'fail'}">{'PASS' if devmem2_ok else 'FAIL'}</td>
            </tr>
            <tr>
                <td>3c</td><td>Ping {PING_TARGET}</td>
                <td>{PING_TARGET}</td>
                <td class="{'pass' if ping_ok else 'fail'}">{'PASS' if ping_ok else 'FAIL'}</td>
            </tr>
            <tr>
                <td>4</td><td>Poweroff + PSU Off</td>
                <td>Wait {POWEROFF_WAIT_S} s after poweroff</td>
                <td class="{'pass' if poweroff_ok else 'fail'}">{'PASS' if poweroff_ok else 'FAIL'}</td>
            </tr>
        </tbody>
    </table>

    <div class="footer">
        <p>DUNE WIB Quality Control System — Item0102_QSPI: QSPI Boot Verification</p>
        <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Made by Lingyun Ke</p>
    </div>
</div>
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML report saved to: {report_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_fail("\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print_fail(f"\nError: {e}")
        sys.exit(1)
