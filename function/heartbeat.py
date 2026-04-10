# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.

import json
import os
from datetime import datetime

HEARTBEAT_PATH = "/tmp/wib_qc_heartbeat.json"


def start_watchdog_session(wib_id, tester_email, sender_email, sender_password):
    """Initialize heartbeat file at the start of a QC session."""
    data = {
        'status':          'running',
        'test_name':       'Initializing',
        'last_update':     datetime.now().isoformat(),
        'timeout_minutes': 7,
        'wib_id':          wib_id,
        'tester_email':    tester_email,
        'sender_email':    sender_email,
        'sender_password': sender_password,
    }
    _write(data)


def update_heartbeat(test_name, timeout_minutes=7):
    """Call before each test to reset the watchdog timer."""
    data = _read()
    data['test_name']       = test_name
    data['last_update']     = datetime.now().isoformat()
    data['timeout_minutes'] = timeout_minutes
    data['status']          = 'running'
    _write(data)


def stop_watchdog():
    """Call when all tests finish. Watchdog will exit without sending email."""
    data = _read()
    data['status'] = 'DONE'
    _write(data)


def _read():
    if os.path.exists(HEARTBEAT_PATH):
        with open(HEARTBEAT_PATH, 'r') as f:
            return json.load(f)
    return {}


def _write(data):
    with open(HEARTBEAT_PATH, 'w') as f:
        json.dump(data, f, indent=2)
