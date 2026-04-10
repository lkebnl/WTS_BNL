# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.

"""
WIB QC Watchdog Process
-----------------------
Run as a background process at the start of WIB_QC_Detail.py.
Monitors /tmp/wib_qc_heartbeat.json.
If the heartbeat is not refreshed within the timeout, sends an alert email
to the tester and continues monitoring.
Exits cleanly when status is set to 'DONE'.
"""

import json
import os
import sys
import time
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

HEARTBEAT_PATH = "/tmp/wib_qc_heartbeat.json"
CHECK_INTERVAL = 30   # seconds between heartbeat checks


def read_heartbeat():
    if not os.path.exists(HEARTBEAT_PATH):
        return None
    try:
        with open(HEARTBEAT_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def send_alert(data, elapsed_minutes):
    """Send a stuck-process alert email to the tester."""
    tester_email   = data.get('tester_email', '')
    sender_email   = data.get('sender_email', '')
    sender_password = data.get('sender_password', '')
    wib_id         = data.get('wib_id', 'Unknown')
    test_name      = data.get('test_name', 'Unknown')
    timeout        = data.get('timeout_minutes', 7)

    if not tester_email or not sender_email:
        print("[Watchdog] No email configured — skipping alert.")
        return

    subject = f"[WIB QC ALERT] Process may be stuck — WIB {wib_id}"
    body = f"""\
WIB QC Watchdog Alert
=====================
WIB ID       : {wib_id}
Current Test : {test_name}
Elapsed      : {elapsed_minutes:.1f} minutes (timeout: {timeout} min)
Time         : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

The QC test process has not responded for more than {timeout} minutes.
It may be stuck or crashed. Please check the test station.

---
This is an automated message from the WIB QC Watchdog.
Made by Lingyun Ke
"""
    try:
        msg = MIMEMultipart()
        msg['From']    = sender_email
        msg['To']      = tester_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [tester_email], msg.as_string())

        print(f"[Watchdog] Alert email sent to {tester_email} ({datetime.now().strftime('%H:%M:%S')})")
    except Exception as e:
        print(f"[Watchdog] Failed to send alert email: {e}")


def main():
    print(f"[Watchdog] Started — monitoring {HEARTBEAT_PATH}")
    alert_sent_for = None   # track which test we already alerted on

    while True:
        time.sleep(CHECK_INTERVAL)

        data = read_heartbeat()
        if data is None:
            continue

        if data.get('status') == 'DONE':
            print("[Watchdog] Status DONE — exiting without sending email.")
            break

        try:
            last_update = datetime.fromisoformat(data['last_update'])
        except (KeyError, ValueError):
            continue

        elapsed_minutes = (datetime.now() - last_update).total_seconds() / 60
        timeout         = data.get('timeout_minutes', 7)
        test_name       = data.get('test_name', 'Unknown')

        if elapsed_minutes > timeout:
            # Only alert once per test item (avoid spam)
            if alert_sent_for != test_name:
                print(f"[Watchdog] TIMEOUT on '{test_name}' ({elapsed_minutes:.1f} min > {timeout} min) — sending alert")
                send_alert(data, elapsed_minutes)
                alert_sent_for = test_name
        else:
            # Reset alert tracker when heartbeat refreshes
            if alert_sent_for is not None and alert_sent_for != test_name:
                alert_sent_for = None


if __name__ == '__main__':
    main()
