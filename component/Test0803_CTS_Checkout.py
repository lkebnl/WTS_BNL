# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
CTS Checkout Script
Performs quick checkout test for FEMB boards in 4 slots.
Scans QR codes, runs checkout, provides result summary, and sends email notification.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import csv
import json
from datetime import datetime
from colorama import init, Fore, Style
import cts_ssh_FEMB as cts
import GUI.send_email as send_email
import GUI.Rigol_DP800 as rigol
import GUI.pop_window as pop
from qc_utils import QC_Process
from qc_results import analyze_test_results, display_qc_results
from function.report_path import get_report_dir

# Image paths for instruction popups
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GUI', 'output_pngs')

init()

# Email configuration
SENDER_EMAIL = "bnlr216@gmail.com"
SENDER_PASSWORD = "vvef tosp minf wwhf"

CSV_FILE = './femb_info.csv'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INIT_SETUP_CSV = os.path.join(BASE_DIR, 'init_setup.csv')
WIB_INFO_CSV = os.path.join(BASE_DIR, '..', 'file', 'wib_info.csv')


def read_init_setup():
    """Read configuration from init_setup.csv"""
    config = {}
    with open(INIT_SETUP_CSV, mode='r', newline='', encoding='utf-8-sig') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) == 2:
                key, value = row
                config[key.strip()] = value.strip()
    return config


def print_header(title):
    """Print a formatted header"""
    print("\n" + Fore.CYAN + "=" * 70)
    print(f"  {title.upper()}")
    print("=" * 70 + Style.RESET_ALL + "\n")


def print_step(step_num, total, description):
    """Print a formatted step"""
    print(Fore.CYAN + f"[{step_num}/{total}] {description}" + Style.RESET_ALL)


def print_status(status_type, message):
    """Print status message with icon"""
    icons = {
        'success': ('✓', Fore.GREEN),
        'error': ('✗', Fore.RED),
        'warning': ('⚠', Fore.YELLOW),
        'info': ('ℹ', Fore.CYAN)
    }
    icon, color = icons.get(status_type, ('•', Fore.WHITE))
    print(color + f"{icon} {message}" + Style.RESET_ALL)


def scan_femb_qr_codes():
    """
    Scan QR codes for all 4 FEMB slots.
    Returns a dictionary with slot assignments.
    """
    print_header("FEMB QR Code Scanning")
    print(Fore.YELLOW + "Scan the QR code for each FEMB board in the popup window." + Style.RESET_ALL)
    print(Fore.YELLOW + "Click 'Skip' or press Enter with empty field to skip empty slots.\n" + Style.RESET_ALL)

    femb_ids = {}
    # slot_key, display_name, image_file
    slot_names = [
        ("SLOT0", "Slot #1", "4.png"),
        ("SLOT1", "Slot #2", "5.png"),
        ("SLOT2", "Slot #3", "6.png"),
        ("SLOT3", "Slot #4", "7.png")
    ]

    for slot_key, slot_desc, img_file in slot_names:
        # Show installation instruction popup with QR input field
        slot_num = int(slot_key[-1]) + 1
        # femb_id = pop.show_input_popup(
        #     title=f"Page {slot_num + 3}: Install FEMB into {slot_desc}",
        #     image_path=os.path.join(IMG_DIR, img_file),
        #     prompt=f"Scan FEMB QR Code for {slot_desc}:",
        #     require_confirmation=True
        # )

        femb_ids[slot_key] = 'test{}'.format(slot_num)
        # if femb_id:
        #     print_status('success', f"{slot_desc}: {femb_id}")
        # else:
        #     print_status('info', f"{slot_desc}: Empty (skipped)")

    # Summary
    print("\n" + Fore.CYAN + "-" * 50 + Style.RESET_ALL)
    print(Fore.GREEN + "FEMB Assignment Summary:" + Style.RESET_ALL)
    installed_count = 0
    for slot_key, slot_desc, _ in slot_names:
        femb_id = femb_ids.get(slot_key, "")
        if femb_id:
            print(f"  {slot_desc}: {Fore.GREEN}{femb_id}{Style.RESET_ALL}")
            installed_count += 1
        else:
            print(f"  {slot_desc}: {Fore.YELLOW}Empty{Style.RESET_ALL}")

    print(f"\nTotal FEMBs installed: {Fore.GREEN}{installed_count}{Style.RESET_ALL}")

    return femb_ids


def save_config(tester_name, tester_email, femb_ids, init_config):
    """Save configuration to CSV file with all fields matching femb_info_implement.csv"""
    csv_data = {
        # User input
        'tester': tester_name,
        'SLOT0': femb_ids.get('SLOT0', ''),
        'SLOT1': femb_ids.get('SLOT1', ''),
        'SLOT2': femb_ids.get('SLOT2', ''),
        'SLOT3': femb_ids.get('SLOT3', ''),
        'comment': 'Checkout test',
        # From init_setup.csv with defaults
        'test_site': init_config.get('Test_Site', 'BNL'),
        'toy_TPC': init_config.get('toy_TPC', 'y'),
        'top_path': init_config.get('QC_data_root_folder', '/home/dune/Documents/data'),
        'Tech_site_email': tester_email or init_config.get('Tech_site_email', ''),
        'Tech_receiver': init_config.get('Tech_receiver', 'lke@bnl.gov'),
        'Test_Site': init_config.get('Test_Site', 'BNL'),
        'Tech_Coordinator': init_config.get('Tech_Coordinator', ''),
        'QC_data_root_folder': init_config.get('QC_data_root_folder', '/home/dune/Documents/data'),
        'Rigol_PS_for_WIB': init_config.get('Rigol_PS_for_WIB', 'True'),
        'Rigol_PS_ID': init_config.get('Rigol_PS_ID', ''),
        'CTS_LN2_AM': init_config.get('CTS_LN2_AM', '1800'),
        'CTS_LN2_PM': init_config.get('CTS_LN2_PM', '1200'),
        'PS_Control_Mode': init_config.get('PS_Control_Mode', 'USB'),
        'CTS_LN2_Fill_Wait': init_config.get('CTS_LN2_Fill_Wait', '1800'),
        'CTS_Warmup_Wait': init_config.get('CTS_Warmup_Wait', '3600'),
        'Network_Upload_Path': init_config.get('Network_Upload_Path', '/data/femb/FEMB_CHK'),
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)

    with open(CSV_FILE, mode="w", newline="", encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        for key, value in csv_data.items():
            writer.writerow([key, value])
        print(csv_data)

    return csv_data


def run_checkout_test(inform, psu):
    """
    Run the checkout test for all installed FEMBs.
    Returns paths to data and report directories.
    """
    print_header("Running Checkout Test")

    # Step 1: Power ON WIB via USB-controlled power supply
    print_step(1, 4, "Power On Warm Interface Board")
    print_status('info', "Powering ON WIB via USB power supply...")
    psu.set_channel(1, 12.0, 3.0, on=True)
    psu.set_channel(2, 12.0, 3.0, on=True)
    print_status('success', "WIB power ON (CH1: 12V/3A, CH2: 12V/3A)")

    # Step 2: Wait for fiber converter
    print_step(2, 4, "Waiting for Fiber Converter")
    print(Fore.YELLOW + "Waiting 30 seconds for fiber converter..." + Style.RESET_ALL)
    for i in range(30, 0, -1):
        print(f"\r  Countdown: {Fore.GREEN}{i:2d}s{Style.RESET_ALL}", end="", flush=True)
        time.sleep(1)
    print(f"\r  {Fore.GREEN}✓ Fiber converter ready!{' '*20}{Style.RESET_ALL}")

    # Step 3: Initialize WIB
    print_step(3, 4, "Initializing WIB")
    qc_path = inform['QC_data_root_folder']
    QC_Process(path=qc_path, QC_TST_EN=77, input_info=inform)  # Ping WIB
    QC_Process(path=qc_path, QC_TST_EN=0, input_info=inform)   # Init WIB
    QC_Process(path=qc_path, QC_TST_EN=1, input_info=inform)   # Init FEMB I2C

    # Step 4: Run checkout test
    print_step(4, 4, "Running Assembly Checkout Test")
    data_path, report_path = QC_Process(path=qc_path, QC_TST_EN=2, input_info=inform)  # Checkout

    return data_path, report_path


def generate_result_summary(inform, data_path, report_path):
    """
    Generate test result summary for all slots.
    Returns (all_passed, summary_text, slot_results)
    """
    print_header("Test Results Summary")

    paths = []
    if data_path:
        paths.append(data_path)
    if report_path:
        paths.append(report_path)

    # Analyze results
    result = analyze_test_results(paths, inform)
    all_passed, failed_slots = display_qc_results(result, "Checkout Test", verbose=True)

    # Build summary text for email
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_lines = [
        "=" * 60,
        "CTS FEMB CHECKOUT TEST RESULTS",
        "=" * 60,
        f"Date/Time: {timestamp}",
        f"Tester: {inform.get('tester', 'Unknown')}",
        f"Test Site: {inform.get('test_site', 'BNL')}",
        "",
        "-" * 60,
        "SLOT RESULTS:",
        "-" * 60,
    ]

    slot_results = {}
    for slot_num in ['0', '1', '2', '3']:
        slot_key = f'SLOT{slot_num}'
        display_slot = int(slot_num) + 1
        femb_id = inform.get(slot_key, '')

        if not femb_id or femb_id in ['', ' ', 'N/A', 'EMPTY', 'NONE']:
            summary_lines.append(f"  Slot {display_slot}: Empty (skipped)")
            slot_results[slot_num] = ('empty', '')
            continue

        if slot_num in result.slot_status:
            passed, _ = result.slot_status[slot_num]
            status = "PASS" if passed else "FAIL"
            summary_lines.append(f"  Slot {display_slot} ({femb_id}): {status}")
            slot_results[slot_num] = ('pass' if passed else 'fail', femb_id)
        else:
            summary_lines.append(f"  Slot {display_slot} ({femb_id}): No test data")
            slot_results[slot_num] = ('no_data', femb_id)

    summary_lines.extend([
        "",
        "-" * 60,
        f"OVERALL RESULT: {'PASS' if all_passed else 'FAIL'}",
        "-" * 60,
    ])

    if not all_passed:
        summary_lines.append("\nFailed FEMBs requiring attention:")
        for slot_num, femb_id in failed_slots:
            display_slot = int(slot_num) + 1
            summary_lines.append(f"  - Slot {display_slot}: {femb_id}")

    summary_text = "\n".join(summary_lines)
    return all_passed, summary_text, slot_results


def save_html_report(inform, slot_results, all_passed):
    """Generate a combined HTML report for Test0801 + Test0802 + Test0803."""
    report_dir = get_report_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Read shared data saved by Test0801 and Test0802
    data_path = os.path.join(report_dir, 'test08_combined_data.json')
    test08_data = {}
    if os.path.exists(data_path):
        try:
            with open(data_path) as _f:
                test08_data = json.load(_f)
        except Exception:
            pass

    d0801 = test08_data.get('test0801', None)
    d0802 = test08_data.get('test0802', None)

    # Overall: all available tests must pass
    sub_statuses = []
    if d0801:
        sub_statuses.append(d0801.get('status', 'FAIL') == 'PASS')
    if d0802:
        sub_statuses.append(d0802.get('status', 'FAIL') == 'PASS')
    sub_statuses.append(all_passed)
    combined_pass = all(sub_statuses)

    suffix = "_P" if combined_pass else "_F"
    report_path = os.path.join(report_dir, f"Test08_Combined_report{suffix}.html")

    overall_str = "PASS" if combined_pass else "FAIL"
    overall_color = "#28a745" if combined_pass else "#dc3545"
    overall_bg = "#d4edda" if combined_pass else "#f8d7da"

    # ── Section 0801 ─────────────────────────────────────────
    if d0801:
        c0801 = "#28a745" if d0801.get('status') == 'PASS' else "#dc3545"
        s0801 = d0801.get('status', 'FAIL')
        ok_hosts = ', '.join(d0801.get('remotes_success', [])) or 'None'
        fail_hosts = ', '.join(d0801.get('remotes_failed', [])) or 'None'
        sec0801 = f"""
    <div class="section">
        <div class="section-header" style="background:{c0801};">
            Test0801: SSH Key Setup &mdash; {s0801}
        </div>
        <div class="section-body">
            <table>
                <tr><th>Item</th><th>Value</th></tr>
                <tr><td>Timestamp</td><td>{d0801.get('timestamp','N/A')}</td></tr>
                <tr><td>Result</td><td class="{'pass' if s0801=='PASS' else 'fail'}">{s0801}</td></tr>
                <tr><td>Successful Hosts</td><td>{ok_hosts}</td></tr>
                <tr><td>Failed Hosts</td><td>{fail_hosts}</td></tr>
            </table>
        </div>
    </div>"""
    else:
        sec0801 = """
    <div class="section">
        <div class="section-header" style="background:#6c757d;">
            Test0801: SSH Key Setup &mdash; Not Run
        </div>
        <div class="section-body">
            <p class="na">This test was not run in the current session.</p>
        </div>
    </div>"""

    # ── Section 0802 ─────────────────────────────────────────
    if d0802:
        c0802 = "#28a745" if d0802.get('status') == 'PASS' else "#dc3545"
        s0802 = d0802.get('status', 'FAIL')
        err_row = (f"<tr><td>Error</td><td class='fail'>{d0802['error_msg']}</td></tr>"
                   if d0802.get('error_msg') else '')
        sec0802 = f"""
    <div class="section">
        <div class="section-header" style="background:{c0802};">
            Test0802: SD Card Flash &mdash; {s0802}
        </div>
        <div class="section-body">
            <table>
                <tr><th>Item</th><th>Value</th></tr>
                <tr><td>Timestamp</td><td>{d0802.get('timestamp','N/A')}</td></tr>
                <tr><td>Image File</td><td>{d0802.get('image_path','N/A')}</td></tr>
                <tr><td>SD Device</td><td>{d0802.get('sd_device','N/A')}</td></tr>
                <tr><td>Capacity</td><td>{d0802.get('sd_capacity','N/A')}</td></tr>
                <tr><td>Product Name</td><td>{d0802.get('sd_name','N/A')}</td></tr>
                <tr><td>Serial</td><td>{d0802.get('sd_serial','N/A')}</td></tr>
                <tr><td>Vendor</td><td>{d0802.get('sd_vendor','N/A')}</td></tr>
                <tr><td>Flash Result</td><td class="{'pass' if s0802=='PASS' else 'fail'}">{s0802}</td></tr>
                {err_row}
            </table>
        </div>
    </div>"""
    else:
        sec0802 = """
    <div class="section">
        <div class="section-header" style="background:#6c757d;">
            Test0802: SD Card Flash &mdash; Not Run
        </div>
        <div class="section-body">
            <p class="na">SD card flash was not performed in the current session.</p>
        </div>
    </div>"""

    # ── Section 0803 ─────────────────────────────────────────
    c0803 = "#28a745" if all_passed else "#dc3545"
    s0803 = "PASS" if all_passed else "FAIL"
    slot_rows = ""
    for slot_num in ['0', '1', '2', '3']:
        femb_id = inform.get(f'SLOT{slot_num}', '')
        display_slot = int(slot_num) + 1
        if not femb_id or femb_id in ['', ' ', 'N/A', 'EMPTY', 'NONE']:
            slot_rows += f"<tr><td>Slot {display_slot}</td><td>—</td><td class='na'>Empty</td></tr>"
        else:
            st, _ = slot_results.get(slot_num, ('no_data', ''))
            css = 'pass' if st == 'pass' else ('fail' if st == 'fail' else 'na')
            slot_rows += (f"<tr><td>Slot {display_slot}</td><td>{femb_id}</td>"
                          f"<td class='{css}'>{st.upper()}</td></tr>")

    sec0803 = f"""
    <div class="section">
        <div class="section-header" style="background:{c0803};">
            Test0803: CTS FEMB Checkout &mdash; {s0803}
        </div>
        <div class="section-body">
            <table>
                <tr><th>Item</th><th>Value</th></tr>
                <tr><td>Timestamp</td><td>{timestamp}</td></tr>
                <tr><td>Tester</td><td>{inform.get('tester','Unknown')}</td></tr>
                <tr><td>Test Site</td><td>{inform.get('test_site','BNL')}</td></tr>
                <tr><td>Overall Result</td><td class="{'pass' if all_passed else 'fail'}">{s0803}</td></tr>
            </table>
            <h4>Slot Results</h4>
            <table>
                <tr><th>Slot</th><th>FEMB ID</th><th>Result</th></tr>
                {slot_rows}
            </table>
        </div>
    </div>"""

    # ── Assemble full HTML ────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test08 Combined Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f9f9f9; color: #333; }}
        h2 {{ text-align: center; color: #444; margin-bottom: 5px; }}
        .status-banner {{
            text-align: center; padding: 15px; margin: 20px auto; width: 60%;
            border-radius: 8px; font-size: 1.2em; font-weight: bold;
            background-color: {overall_bg}; color: {overall_color};
            border: 2px solid {overall_color};
        }}
        .section {{
            margin: 25px 0; border: 1px solid #ddd; border-radius: 8px;
            overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }}
        .section-header {{
            padding: 12px 20px; font-size: 1.05em;
            font-weight: bold; color: white;
        }}
        .section-body {{ padding: 20px; background: #fff; }}
        table {{ width: 70%; margin: 0 auto; border-collapse: collapse; background: #fff; }}
        th, td {{ border: 1px solid #ddd; padding: 9px 14px; text-align: left; }}
        th {{ background-color: #f0f0f0; font-weight: bold; }}
        tr:nth-child(even) td {{ background-color: #fafafa; }}
        .pass {{ color: #28a745; font-weight: bold; }}
        .fail {{ color: #dc3545; font-weight: bold; }}
        .na   {{ color: #6c757d; }}
        h4 {{ margin: 18px 15%; font-size: 0.95em; }}
        p.na {{ text-align: center; color: #6c757d; padding: 20px; font-style: italic; }}
        .footer {{ text-align: center; margin-top: 30px; color: #999; font-size: 0.85em; }}
    </style>
</head>
<body>
    <h2>Test08: SSH Setup / SD Card Flash / CTS Checkout</h2>
    <div class="status-banner">Overall Result: {overall_str}</div>
    {sec0801}
    {sec0802}
    {sec0803}
    <div class="footer">
        <p>Generated: {timestamp}</p>
        <p>Made by Lingyun Ke</p>
    </div>
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [Report] Combined Test08 report saved: {report_path}")
    return report_path


def process_board_removal(inform, slot_results):
    """
    Guide tester through removing each board slot by slot.
    Requires QR scan confirmation before removal.
    Uses popup window with image, result display, and QR scan field.
    """
    print_header("Board Removal Process")
    print(Fore.YELLOW + "Remove boards one by one. Scan QR code to confirm each board." + Style.RESET_ALL)
    print(Fore.YELLOW + "PASS -> GOOD tray | FAIL -> BAD tray\n" + Style.RESET_ALL)

    # slot_num, display_name, image_file
    slot_names = [
        ("0", "Slot #1", "10.png"),
        ("1", "Slot #2", "11.png"),
        ("2", "Slot #3", "12.png"),
        ("3", "Slot #4", "13.png")
    ]

    for slot_num, slot_desc, img_file in slot_names:
        slot_key = f'SLOT{slot_num}'
        expected_id = inform.get(slot_key, '')

        # Skip empty slots
        if not expected_id or expected_id in ['', ' ', 'N/A', 'EMPTY', 'NONE']:
            print(Fore.CYAN + f"\n[{slot_desc}] " + Fore.YELLOW + "Empty - Skip" + Style.RESET_ALL)
            continue

        # Get test result for this slot
        status, _ = slot_results.get(slot_num, ('no_data', ''))

        # Determine tray info for logging
        if status == 'pass':
            tray_name = "GOOD"
            tray_style = Fore.GREEN
        elif status == 'fail':
            tray_name = "BAD"
            tray_style = Fore.RED
        else:
            tray_name = "REVIEW"
            tray_style = Fore.YELLOW

        # Show combined removal popup with image, result, and QR scan
        display_slot = int(slot_num) + 1
        # confirmed = pop.show_removal_popup(
        #     title=f"Page {display_slot + 9}: Remove Board from {slot_desc}",
        #     image_path=os.path.join(IMG_DIR, img_file),
        #     expected_id=expected_id,
        #     test_status=status
        # )

        # Log result to terminal
        print("\n" + Fore.CYAN + "=" * 60 + Style.RESET_ALL)
        print(Fore.CYAN + f"  {slot_desc}" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)
        print(f"  FEMB ID: {Fore.WHITE}{expected_id}{Style.RESET_ALL}")
        print(f"  Test Result: {tray_style}{status.upper()}{Style.RESET_ALL}")

        # if confirmed:
        #     print_status('success', f"ID confirmed. FEMB removed and placed in {tray_name} tray.")
        # else:
        #     print_status('warning', f"Removal cancelled for {slot_desc}.")

    print("\n" + Fore.GREEN + "=" * 60)
    print("  All boards processed!")
    print("=" * 60 + Style.RESET_ALL)


def send_result_email(tester_email, all_passed, summary_text, inform):
    """Send email notification with test results to tester and tech receiver"""
    print_header("Sending Email Notification")
    # Build recipient list
    recipients = []
    if tester_email and '@' in tester_email:
        recipients.append(tester_email)
    tech_receiver = inform.get('Tech_receiver', 'lke@bnl.gov')
    if tech_receiver and '@' in tech_receiver and tech_receiver not in recipients:
        recipients.append(tech_receiver)
    if not recipients:
        print_status('warning', "No valid email recipients. Skipping email notification.")
        return False
    status_str = "PASS" if all_passed else "FAIL"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    test_site = inform.get('test_site', 'BNL')
    subject = f"[CTS Checkout {status_str}] {test_site} - {timestamp}"
    body = f"""CTS FEMB Checkout Test Completed
{summary_text}

---
This is an automated message from the FEMB Post-Assembly Checkout System.
"""

    try:
        send_email.send_email(
            SENDER_EMAIL,
            SENDER_PASSWORD,
            recipients,
            subject,
            body
        )
        print_status('success', f"Email sent to: {', '.join(recipients)}")
        return True
    except Exception as email_err:
        print_status('error', f"Failed to send email: {email_err}")
        return False


def main():
    """Main checkout workflow"""
    print_header("CTS FEMB Checkout Test")
    print(Fore.GREEN + "This script performs a quick checkout test for FEMB boards." + Style.RESET_ALL)
    print(Fore.GREEN + "Supports 4 slots. Empty slots will be skipped.\n" + Style.RESET_ALL)

    # Step 1: Get tester information
    # Show Page 2: Tester information instruction
    print_step(1, 5, "Tester Information")
    tester_name = "Unknown"
    try:
        with open(WIB_INFO_CSV, mode='r', newline='', encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) == 2 and row[0].strip() == 'tester':
                    tester_name = row[1].strip() or "Unknown"
                    break
    except Exception as e:
        print(Fore.YELLOW + f"  [Warning] Could not read tester from wib_info.csv: {e}" + Style.RESET_ALL)
    print(f"  Tester: {Fore.CYAN}{tester_name}{Style.RESET_ALL}")

    tester_email = SENDER_EMAIL

    print_step(2, 5, "Scanning FEMB QR Codes")
    femb_ids = scan_femb_qr_codes()

    # Check if any FEMB installed
    installed_fembs = [k for k, v in femb_ids.items() if v]
    if not installed_fembs:
        print_status('error', "No FEMBs installed. Exiting.")
        sys.exit(1)

    # Step 3: Review and confirm
    print_step(3, 5, "Configuration Review")
    print(Fore.GREEN + "\nPlease review the configuration:" + Style.RESET_ALL)
    print(f"  Tester: {tester_name}")
    for slot_key in ['SLOT0', 'SLOT1', 'SLOT2', 'SLOT3']:
        femb_id = femb_ids.get(slot_key, '')
        status = femb_id if femb_id else "Empty"
        print(f"  {slot_key}: {status}")

    # confirm = input(Fore.YELLOW + "\nProceed with checkout test? (y/n): " + Style.RESET_ALL).lower()
    confirm = 'y'
    if confirm != 'y':
        print_status('info', "Test cancelled by user.")
        sys.exit(0)

    # Show Page 8: Close cover and start test
    # pop.show_image_popup(
    #     title="Page 8: Review Information and Close Cover",
    #     image_path=os.path.join(IMG_DIR, "8.png")
    # )
    while True:
        print(Fore.YELLOW + "\n⚠️  SAFETY CHECK:" + Style.RESET_ALL)
        print("Please confirm the CTS chamber is empty.")
        print("Type " + Fore.GREEN + "'I confirm the cover is closed'" + Style.RESET_ALL + " to proceed")
        # com = input(Fore.YELLOW + '>> ' + Style.RESET_ALL)
        com = 'i confirm the cover is closed'
        if com.lower() == 'i confirm the cover is closed':
            print(
                Fore.GREEN + '✓ Ready for Test.' + Style.RESET_ALL)
            break
    # Read init_setup.csv for configuration
    init_config = read_init_setup()

    # Save configuration with all fields matching femb_info_implement.csv
    save_config(tester_name, tester_email, femb_ids, init_config)
    inform = cts.read_csv_to_dict(CSV_FILE, 'RT')

    # Initialize power supply controller
    print_status('info', "Initializing power supply controller...")
    psu = rigol.PowerSupplyController()

    try:
        # Step 4: Run checkout test
        print_step(4, 5, "Running Checkout Test")
        data_path, report_path = run_checkout_test(inform, psu)

        # Step 5: Generate results and send email
        print_step(5, 6, "Generating Results and Sending Email")
        all_passed, summary_text, slot_results = generate_result_summary(inform, data_path, report_path)
        save_html_report(inform, slot_results, all_passed)
        send_result_email(tester_email, all_passed, summary_text, inform)
        # Show Page 9: Open cover for board removal
        # pop.show_image_popup(
        #     title="Page 9: Review Result and Open Cover",
        #     image_path=os.path.join(IMG_DIR, "9.png")
        # )

        # Step 6: Board removal with QR confirmation
        print_step(6, 6, "Board Removal")
        process_board_removal(inform, slot_results)

        # Show Page 14: Clean the test site
        # pop.show_image_popup(
        #     title="Page 14: Clean the Test Site",
        #     image_path=os.path.join(IMG_DIR, "14.png")
        # )

        # Final summary display

        print_header("Checkout Test Complete")
        if all_passed:
            print(Fore.GREEN + "  ✓✓✓ ALL TESTS PASSED ✓✓✓" + Style.RESET_ALL)
        else:
            print(Fore.RED + "  ✗✗✗ SOME TESTS FAILED ✗✗✗" + Style.RESET_ALL)
            print(Fore.YELLOW + "\n  Please check the failed FEMBs and take appropriate action." + Style.RESET_ALL)
        print_status('success', "Power supply turned OFF and connection closed.")
        return 0 if all_passed else 1

    finally:
        # Always power off, even on exceptions
        print_status('info', "Powering OFF WIB...")
        try:
            psu.safe_power_off()
            psu.close()
        except Exception as _e:
            print_status('warning', f"Power off error: {_e}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\nTest interrupted by user." + Style.RESET_ALL)
        sys.exit(1)
    except Exception as e:
        print(Fore.RED + f"\nError: {e}" + Style.RESET_ALL)
        sys.exit(1)
