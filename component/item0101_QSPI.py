# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : June 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Item0101_QSPI: QSPI Flash Load
Boots WIB from SD card, runs WIB_QSPI_Load_v2.sh to flash QSPI,
then cleanly powers off.

Steps:
  1. Power on,
  2. Connect via UART — SD card system, check if login, normally, no login credentials required
  3. wait 30 s
  3. Run: source ./WIB_QSPI_Load_v2.sh
  4. Wait 2 minutes for script, send 'poweroff', wait 1 minute, power off PSU
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
import file.report_dict as rp_dict

# Supported USB-to-Serial adapters (same as Test01)
SUPPORTED_ADAPTERS = [
    {"name": "Silicon Labs CP2105", "vid": 0x10C4, "pid": 0xEA70},
    {"name": "FTDI FT232",          "vid": 0x0403, "pid": 0x6001},
    {"name": "FTDI FT2232",         "vid": 0x0403, "pid": 0x6010},
]

QSPI_SCRIPT     = "source ./WIB_QSPI_Load_v2.sh"
SCRIPT_TIMEOUT_S = 300  # max wait for flash completion keywords (5 min safety)
POWEROFF_WAIT_S = 60    # 1 minute after poweroff before cutting PSU
BOOT_WAIT_S     = 30    # step 1: wait after power-on for SD card boot


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
            choice = input("Options:\n  [R] Retry\n  [S] Skip (abort QSPI load)\n  [E] Exit\nChoice (R/S/E): ").strip().upper()
            if choice == 'R':
                time.sleep(1)
                break
            elif choice == 'S':
                print_warning("Skipping QSPI load.")
                return None, None
            elif choice == 'E':
                print_fail("Aborted by user.")
                psu.safe_power_off()
                psu.close()
                sys.exit(1)


def run_qspi_load(com_port, psu):
    """
    Open UART, wait for SD-card shell prompt (no credentials needed),
    run the QSPI load script, then send poweroff.

    Returns: (script_ok, poweroff_ok, note)
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

    script_ok   = False
    poweroff_ok = False
    note        = ""

    try:
        # ----------------------------------------------------------------
        # Steps 3a/3b: monitor boot output and detect shell prompt.
        # The prompt may arrive during boot — check for it at every line
        # so we don't miss it.  If a login/password prompt appears,
        # send Enter (SD card system normally auto-logs in as root).
        # Timeout = BOOT_WAIT_S + 90 s.
        # ----------------------------------------------------------------
        shell_deadline = time.time() + BOOT_WAIT_S + 90
        shell_ready = False
        print(f"Waiting for SD card boot and shell prompt (up to {BOOT_WAIT_S + 90} s)...")

        while time.time() < shell_deadline:
            raw = ser.readline()
            line = raw.decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  << {line}")

            # Specific prompt produced by the SD card PetaLinux system
            if 'root@DUNE_WIB_SD' in line:
                shell_ready = True
                break

            # Auto-login line — system handles it, no input required
            if 'automatic login' in line.lower():
                print("  >> (auto-login detected — waiting for shell)")

            # Fallback: manual login/password prompts (not expected normally)
            elif 'login:' in line.lower() and 'automatic' not in line.lower():
                print("  >> (login prompt — sending Enter)")
                ser.write(b'\n')
            elif 'password:' in line.lower():
                print("  >> (password prompt — sending Enter)")
                ser.write(b'\n')

        if not shell_ready:
            return False, False, "Timeout waiting for shell prompt"

        print_pass("Shell prompt obtained.")

        # ----------------------------------------------------------------
        # Step 3: run QSPI load script, detect completion by keywords
        # ----------------------------------------------------------------
        print(f"\nSending: {QSPI_SCRIPT}")
        ser.write((QSPI_SCRIPT + '\n').encode())

        completion_keywords = [
            'All partitions programmed successfully',
            'Safe to reboot',
            'Signalling successful completion',
        ]

        print(f"Waiting for QSPI flash completion (timeout: {SCRIPT_TIMEOUT_S} s)...")
        script_deadline = time.time() + SCRIPT_TIMEOUT_S
        while time.time() < script_deadline:
            raw = ser.readline()
            line = raw.decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  << {line}")
            if any(kw in line for kw in completion_keywords):
                script_ok = True
                note = line
                print_pass(f"QSPI flash complete: {line}")
                break

        if not script_ok:
            return False, False, f"Timeout: no completion keyword in {SCRIPT_TIMEOUT_S} s"

        # Board reboots after flashing — wait for shell prompt to return
        print("Waiting for board reboot and shell to return...")
        reboot_deadline = time.time() + 120
        while time.time() < reboot_deadline:
            raw = ser.readline()
            line = raw.decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  << {line}")
            if 'root@DUNE_WIB_SD' in line:
                print_pass("Board back up after reboot.")
                break

        # ----------------------------------------------------------------
        # Step 4: send poweroff, wait 60 s, then PSU off
        # ----------------------------------------------------------------
        print("\nSending: poweroff")
        # ser.write(b'poweroff\n')
        ser.write(b'systemctl poweroff\r\n')
        print(f"Waiting {POWEROFF_WAIT_S} s for OS shutdown...")

        shutdown_deadline = time.time() + POWEROFF_WAIT_S
        while time.time() < shutdown_deadline:
            raw = ser.readline()
            line = raw.decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  << {line}")

        poweroff_ok = True
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

    return script_ok, poweroff_ok, note


# ============================================================================
# MAIN
# ============================================================================

def main():
    t_start = time.time()
    utc_now = datetime.now(timezone.utc)

    # --- Session info ---
    session_info = get_session_info()
    wib_id    = session_info.get('WIB_ID',      'standalone_test')
    tester    = session_info.get('tester',       'Unknown')
    test_site = session_info.get('test_site',    'BNL')

    print("\n" + "-" * 40)
    print("[session_info] Item0101_QSPI loaded session:")
    print(f"  WIB ID:    {wib_id}")
    print(f"  Tester:    {tester}")
    print(f"  Test Site: {test_site}")
    print("-" * 40)

    init_report_session(wib_id)

    # --- CSV ---
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

    print_header("Item0101_QSPI : QSPI Flash Load")
    print("  1. Power on")
    print("  2. Connect via UART (check login — normally no credentials required)")
    print(f"  3. Wait {BOOT_WAIT_S} s, then run: {QSPI_SCRIPT}")
    print("  4. Wait 2 min → poweroff → wait 1 min → PSU off")
    print("=" * 60)

    # --- PSU ---
    psu = rigol.RigolDP800()
    psu.safe_power_off()
    time.sleep(1)

    # Step 1: power on
    print_header("Step 1: Power On")
    psu.set_channel(1, 12.0, 3.0, on=True)
    psu.set_channel(2, 12.0, 3.0, on=True)
    v1, c1 = psu.measure(1)
    v2, c2 = psu.measure(2)
    print(f"  Ch1: {v1:.3f}V {c1:.3f}A   Ch2: {v2:.3f}V {c2:.3f}A")

    # Step 2: find UART port immediately after power-on
    print_header("Step 2: Find UART Port")
    com_port, adapter_name = find_serial_port(psu)

    uart_ok     = False
    script_ok   = False
    poweroff_ok = False
    note        = "UART not found"

    if com_port is not None:
        print_header("Steps 2–4: UART / QSPI Load / Poweroff")
        script_ok, poweroff_ok, note = run_qspi_load(com_port, psu)
        uart_ok = True

    # PSU off (regardless of outcome)
    print_header("Power Off")
    psu.safe_power_off()
    psu.close()
    print_pass("PSU off.")

    t_end = time.time()
    test_duration = round(t_end - t_start, 2)
    overall_pass = uart_ok and script_ok and poweroff_ok

    # --- CSV update ---
    if rp_dict.csv_manager:
        v1_status = "PASS" if 11.0 <= v1 <= 13.0 else "FAIL"
        v2_status = "PASS" if 11.0 <= v2 <= 13.0 else "FAIL"
        rp_dict.csv_manager.batch_update([
            {"item_id": "T_QSPI_01", "value": com_port if com_port else "Not found",
             "status": "PASS" if uart_ok else "FAIL"},
            {"item_id": "T_QSPI_02", "value": QSPI_SCRIPT,
             "status": "PASS" if script_ok else "FAIL"},
            {"item_id": "T_QSPI_03", "value": "poweroff sent",
             "status": "PASS" if poweroff_ok else "FAIL"},
            {"item_id": "T_QSPI_04", "value": round(v1, 3), "status": v1_status},
            {"item_id": "T_QSPI_05", "value": round(v2, 3), "status": v2_status},
            {"item_id": "T_QSPI_06", "value": test_duration, "status": "COMPLETE"},
        ])

    # --- Summary ---
    print_header("Item0101_QSPI — SUMMARY")
    print(f"  UART port        : {com_port or 'Not detected'}  {'PASS' if uart_ok else 'FAIL'}")
    print(f"  QSPI script      : {'PASS' if script_ok else 'FAIL'}  ({note})")
    print(f"  Poweroff         : {'PASS' if poweroff_ok else 'FAIL'}")
    print(f"  Ch1 power        : {v1:.3f}V")
    print(f"  Ch2 power        : {v2:.3f}V")
    print(f"  Total duration   : {test_duration} s")
    print("")
    if overall_pass:
        print_pass("  OVERALL: PASS — QSPI flash completed successfully")
    else:
        print_fail("  OVERALL: FAIL — check UART connection and SD card")
    print("=" * 60)

    # --- HTML report ---
    overall_status = "PASS" if overall_pass else "FAIL"
    overall_class  = "pass" if overall_pass else "fail"
    report_filename = get_report_filename("Item0101_QSPI_report", overall_pass)
    report_path = get_report_path(report_filename)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WIB QSPI Flash Load Report</title>
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
        .info-label {{ font-weight:bold; width:180px; }}
        table {{ width:100%; border-collapse:collapse; margin:15px 0; border:1px solid #000; }}
        th {{ background:#f3f4f6; font-weight:bold; text-align:left; padding:12px;
              border:1px solid #000; }}
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
        <div class="subtitle">QSPI Flash Load Report (Item0101_QSPI)</div>
        <div class="status-badge {overall_class}">Overall Status: {overall_status}</div>
    </div>

    <div class="info-section">
        <div class="info-row"><div class="info-label">Test Date:</div>
            <div>{utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')}</div></div>
        <div class="info-row"><div class="info-label">WIB ID:</div><div>{wib_id}</div></div>
        <div class="info-row"><div class="info-label">Tester:</div><div>{tester}</div></div>
        <div class="info-row"><div class="info-label">Test Site:</div><div>{test_site}</div></div>
        <div class="info-row"><div class="info-label">Total Duration:</div>
            <div>{test_duration} s</div></div>
    </div>

    <table>
        <thead>
            <tr><th>Step</th><th>Description</th><th>Result</th><th>Status</th></tr>
        </thead>
        <tbody>
            <tr>
                <td>1</td><td>Power On + SD Boot ({BOOT_WAIT_S} s)</td>
                <td>Ch1 {v1:.3f} V &nbsp; Ch2 {v2:.3f} V</td>
                <td class="{'pass' if 11.0<=v1<=13.0 and 11.0<=v2<=13.0 else 'fail'}">
                    {'PASS' if 11.0<=v1<=13.0 and 11.0<=v2<=13.0 else 'FAIL'}</td>
            </tr>
            <tr>
                <td>2</td><td>UART Connection ({com_port or 'N/A'})</td>
                <td>{adapter_name or 'Not detected'}</td>
                <td class="{'pass' if uart_ok else 'fail'}">{'PASS' if uart_ok else 'FAIL'}</td>
            </tr>
            <tr>
                <td>3</td><td>QSPI Load Script</td>
                <td><code>{QSPI_SCRIPT}</code></td>
                <td class="{'pass' if script_ok else 'fail'}">{'PASS' if script_ok else 'FAIL'}</td>
            </tr>
            <tr>
                <td>4</td><td>Poweroff + PSU Off</td>
                <td>Wait {POWEROFF_WAIT_S} s after poweroff</td>
                <td class="{'pass' if poweroff_ok else 'fail'}">{'PASS' if poweroff_ok else 'FAIL'}</td>
            </tr>
        </tbody>
    </table>

    <div class="footer">
        <p>DUNE WIB Quality Control System — Item0101_QSPI: QSPI Flash Load</p>
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
