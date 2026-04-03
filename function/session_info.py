# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Session Info Module - Global Test Metadata Storage

Stores and retrieves test session information across subprocesses.
Uses a JSON file to share data between the main script and test components.

Usage:
    In WIB_QC_Detail.py (main script):
        from function.session_info import init_session_info
        init_session_info(wib_id="WIB001", foam_box_id="FB001", ...)

    In test components:
        from function.session_info import get_session_info
        info = get_session_info()
        wib_id = info['WIB_ID']
"""

import os
import json
from datetime import datetime

# Session file path (JSON format for structured data)
SESSION_FILE = os.path.join(os.path.dirname(__file__), '..', '.session_info.json')

# Default values when running standalone (not from WIB_QC_Detail.py)
DEFAULT_SESSION_INFO = {
    'WIB_ID': 'standalone_test',
    'Foam_Box_ID': '',
    'tester': 'Unknown',
    'test_site': 'BNL',
    'start_time': '',
    'report_dir': '',
    'comment': 'Standalone test run'
}


def init_session_info(wib_id=None, foam_box_id=None, tester=None, test_site=None,
                       comment=None, report_dir=None):
    """
    Initialize session info at the start of WIB_QC_Detail.py.

    Call this ONCE at the beginning of the test flow.
    All subprocess tests will read from the saved JSON file.

    Args:
        wib_id: WIB board ID
        foam_box_id: Foam box ID
        tester: Tester name
        test_site: Test site (e.g., 'BNL')
        comment: Optional comment
        report_dir: Report directory path

    Returns:
        dict: The session info dictionary
    """
    session_info = {
        'WIB_ID': wib_id or DEFAULT_SESSION_INFO['WIB_ID'],
        'Foam_Box_ID': foam_box_id or DEFAULT_SESSION_INFO['Foam_Box_ID'],
        'tester': tester or DEFAULT_SESSION_INFO['tester'],
        'test_site': test_site or DEFAULT_SESSION_INFO['test_site'],
        'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'report_dir': report_dir or '',
        'comment': comment or DEFAULT_SESSION_INFO['comment']
    }

    # Save to JSON file
    session_file_path = os.path.abspath(SESSION_FILE)
    try:
        with open(session_file_path, 'w') as f:
            json.dump(session_info, f, indent=2)

        print(f"\n{'=' * 60}")
        print("SESSION INFO INITIALIZED")
        print(f"{'=' * 60}")
        print(f"  WIB ID:       {session_info['WIB_ID']}")
        print(f"  Foam Box ID:  {session_info['Foam_Box_ID']}")
        print(f"  Tester:       {session_info['tester']}")
        print(f"  Test Site:    {session_info['test_site']}")
        print(f"  Start Time:   {session_info['start_time']}")
        print(f"  Report Dir:   {session_info['report_dir']}")
        print(f"  Session File: {session_file_path}")
        print(f"{'=' * 60}\n")

    except Exception as e:
        print(f"Warning: Could not save session info: {e}")

    return session_info


def get_session_info():
    """
    Get the current session info.

    Reads from the JSON file created by init_session_info().
    If no session file exists (standalone run), returns defaults.

    Returns:
        dict: Session info dictionary with keys:
            - WIB_ID
            - Foam_Box_ID
            - tester
            - test_site
            - start_time
            - report_dir
            - comment
    """
    session_file_path = os.path.abspath(SESSION_FILE)

    if os.path.exists(session_file_path):
        try:
            with open(session_file_path, 'r') as f:
                session_info = json.load(f)

            # Validate required keys exist
            for key in DEFAULT_SESSION_INFO:
                if key not in session_info:
                    session_info[key] = DEFAULT_SESSION_INFO[key]

            return session_info

        except Exception as e:
            print(f"[session_info] Warning: Could not read session file: {e}")

    # No session file - return defaults (standalone run)
    print("[session_info] No session file found, using defaults (standalone run)")
    return DEFAULT_SESSION_INFO.copy()


def update_session_info(**kwargs):
    """
    Update specific fields in the session info.

    Args:
        **kwargs: Key-value pairs to update

    Returns:
        dict: Updated session info
    """
    session_info = get_session_info()
    session_info.update(kwargs)

    session_file_path = os.path.abspath(SESSION_FILE)
    try:
        with open(session_file_path, 'w') as f:
            json.dump(session_info, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not update session info: {e}")

    return session_info


def get_wib_id():
    """Get the WIB ID from session info."""
    return get_session_info().get('WIB_ID', DEFAULT_SESSION_INFO['WIB_ID'])


def get_tester():
    """Get the tester name from session info."""
    return get_session_info().get('tester', DEFAULT_SESSION_INFO['tester'])


def get_test_site():
    """Get the test site from session info."""
    return get_session_info().get('test_site', DEFAULT_SESSION_INFO['test_site'])


def get_foam_box_id():
    """Get the Foam Box ID from session info."""
    return get_session_info().get('Foam_Box_ID', DEFAULT_SESSION_INFO['Foam_Box_ID'])


def get_report_dir():
    """Get the report directory from session info."""
    return get_session_info().get('report_dir', '')


def clear_session_info():
    """Clear the session info file."""
    session_file_path = os.path.abspath(SESSION_FILE)
    if os.path.exists(session_file_path):
        os.remove(session_file_path)
        print(f"[session_info] Session file cleared: {session_file_path}")


def is_session_active():
    """Check if a session is currently active."""
    session_file_path = os.path.abspath(SESSION_FILE)
    return os.path.exists(session_file_path)


def get_report_filename(base_name, passed, extension='.html'):
    """
    Generate report filename with pass/fail suffix.

    Args:
        base_name: Base name without extension (e.g., 'Test01_Communication_report')
        passed: True for pass (_P), False for fail (_F)
        extension: File extension (default: '.html')

    Returns:
        Filename with pass/fail suffix (e.g., 'Test01_Communication_report_P.html')

    Example:
        get_report_filename('Test01_Communication_report', True)
        -> 'Test01_Communication_report_P.html'

        get_report_filename('Test01_Communication_report', False)
        -> 'Test01_Communication_report_F.html'
    """
    suffix = '_P' if passed else '_F'
    return f"{base_name}{suffix}{extension}"


def check_report_status(report_dir, base_name):
    """
    Check if a report file exists and determine its pass/fail status from filename.

    Args:
        report_dir: Directory containing reports
        base_name: Base name of the report (e.g., 'Test01_Communication_report')

    Returns:
        tuple: (found, passed, filepath)
            - found: True if report file exists
            - passed: True if _P suffix, False if _F suffix, None if not found
            - filepath: Full path to the report file, or None if not found
    """
    import glob

    # Look for _P or _F suffix
    for suffix, status in [('_P', True), ('_F', False)]:
        pattern = os.path.join(report_dir, f"{base_name}{suffix}.*")
        matches = glob.glob(pattern)
        if matches:
            return True, status, matches[0]

    # Check for file without suffix (legacy)
    pattern = os.path.join(report_dir, f"{base_name}.*")
    matches = glob.glob(pattern)
    if matches:
        # Legacy file without suffix - assume unknown status
        return True, None, matches[0]

    return False, None, None


if __name__ == "__main__":
    # Test the module
    print("Testing session_info module...")
    print("=" * 60)

    # Test initialization
    print("\n1. Initialize session:")
    init_session_info(
        wib_id="TEST_WIB_001",
        foam_box_id="FB_001",
        tester="Test User",
        test_site="BNL",
        report_dir="/home/dune/Documents/WIB_QC/TEST_WIB_001_02_25_2026"
    )

    # Test reading
    print("\n2. Read session info:")
    info = get_session_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    # Test helper functions
    print("\n3. Helper functions:")
    print(f"  get_wib_id(): {get_wib_id()}")
    print(f"  get_tester(): {get_tester()}")
    print(f"  get_test_site(): {get_test_site()}")

    # Test update
    print("\n4. Update session:")
    update_session_info(comment="Updated comment")
    print(f"  Updated comment: {get_session_info()['comment']}")

    # Clean up
    print("\n5. Clear session:")
    clear_session_info()
