"""
Report Path Utility Module

This module manages the centralized report directory structure for WIB QC testing.

IMPORTANT: Call init_session() ONCE at the start of WIB_QC_Detail.py.
           All test subprocesses will read from the same session file.

Report Structure:
    /home/dune/Documents/WIB_QC/
    └── {WIB_ID}_{MM_DD_YYYY_HH_MM}/
        ├── Test01_Communication_report.html
        ├── Test02_Calibration_report.html
        ├── ...
        └── Final_Report.pdf
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for importing rp_dict
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Base directory for all WIB QC reports
WIB_QC_BASE_DIR = "/home/dune/Documents/WIB_QC"

# Default WIB ID for testing/debugging
DEFAULT_WIB_ID = "qc_debug"

# Session file to store the report path (shared across subprocesses)
SESSION_FILE = os.path.join(os.path.dirname(__file__), '..', '.current_session.txt')


def init_session(wib_id=None, force_new=False):
    """
    Initialize a test session. Creates the report folder ONCE.
    Saves the path to a session file so all subprocess tests can use it.

    IMPORTANT: If a session already exists (from WIB_QC_Detail.py), this function
    will return the existing session path instead of creating a new one.

    Args:
        wib_id: WIB board ID. If None, reads from rp_dict.wib_info or uses default.
        force_new: If True, always create a new session (used by WIB_QC_Detail.py only)

    Returns:
        Path to the report directory for this session.
    """
    # Check if session already exists (don't overwrite existing session from WIB_QC_Detail.py)
    if not force_new:
        existing_dir, existing_wib_id = _read_session_file()
        if existing_dir and os.path.exists(existing_dir):
            print(f"[path_debug] Using existing session: {existing_dir}")
            return existing_dir

    # Get WIB ID
    if not wib_id:
        try:
            import file.report_dict as rp_dict
            wib_id = rp_dict.wib_info.get('WIB_ID', None)
            if not wib_id or wib_id == '':
                wib_id = None
        except (ImportError, AttributeError):
            pass

    if not wib_id:
        wib_id = DEFAULT_WIB_ID

    # Create folder name with current timestamp
    date_str = datetime.now().strftime("%m_%d_%Y_%H_%M")
    dir_name = f"{wib_id}_{date_str}"
    report_dir = os.path.join(WIB_QC_BASE_DIR, dir_name)

    # Create the directory
    os.makedirs(report_dir, exist_ok=True)

    # Save to session file (so subprocesses can read it)
    session_file_path = os.path.abspath(SESSION_FILE)
    with open(session_file_path, 'w') as f:
        f.write(f"{report_dir}\n{wib_id}\n")

    print(f"\n{'=' * 60}")
    print("TEST SESSION INITIALIZED")
    print(f"{'=' * 60}")
    print(f"  WIB ID: {wib_id}")
    print(f"  Report Directory: {report_dir}")
    print(f"  Session File: {session_file_path}")
    print(f"  (All tests will save reports to this folder)")
    print(f"{'=' * 60}\n")

    return report_dir


def _read_session_file():
    """Read the session file to get the current report directory."""
    session_file_path = os.path.abspath(SESSION_FILE)
    if os.path.exists(session_file_path):
        try:
            with open(session_file_path, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    report_dir = lines[0].strip()
                    wib_id = lines[1].strip()
                    if os.path.exists(report_dir):
                        return report_dir, wib_id
        except Exception as e:
            print(f"[path_debug] Warning: Could not read session file: {e}")
    return None, None


def get_wib_id():
    """Get the current session's WIB ID."""
    # First try session file
    _, wib_id = _read_session_file()
    if wib_id:
        return wib_id

    # Try session_info module
    try:
        from function.session_info import get_session_info
        session_info = get_session_info()
        wib_id = session_info.get('WIB_ID', None)
        if wib_id and wib_id != '' and wib_id != 'standalone_test':
            return wib_id
    except (ImportError, AttributeError):
        pass

    # Try rp_dict.wib_info
    try:
        import file.report_dict as rp_dict
        wib_id = rp_dict.wib_info.get('WIB_ID', None)
        if wib_id and wib_id != '':
            return wib_id
    except (ImportError, AttributeError):
        pass

    return DEFAULT_WIB_ID


def get_report_dir(wib_id=None, create=True):
    """
    Get the report directory path for the current session.

    Reads from session file (created by init_session in WIB_QC_Detail.py).
    All test subprocesses will get the SAME path.

    Returns:
        Full path to the report directory.
    """
    # First, try to read from session file (set by WIB_QC_Detail.py)
    report_dir, session_wib_id = _read_session_file()

    if report_dir:
        print(f"[path_debug] Using session path: {report_dir}")
        return report_dir

    # No session file - create new path (standalone test run)
    print(f"[path_debug] No session file found, creating new path")

    if not wib_id:
        wib_id = get_wib_id()

    date_str = datetime.now().strftime("%m_%d_%Y_%H_%M")
    dir_name = f"{wib_id}_{date_str}"
    report_dir = os.path.join(WIB_QC_BASE_DIR, dir_name)

    if create:
        os.makedirs(report_dir, exist_ok=True)

    print(f"[path_debug] Created new path: {report_dir}")
    return report_dir


def get_report_path(filename, subdir=None):
    """
    Get full path for a report file in the current session's folder.

    Args:
        filename: Name of the report file
        subdir: Optional subdirectory (e.g., "Test07_IBERT")

    Returns:
        Full path to the report file.
    """
    report_dir = get_report_dir()

    if subdir:
        subdir_path = os.path.join(report_dir, subdir)
        os.makedirs(subdir_path, exist_ok=True)
        return os.path.join(subdir_path, filename)

    return os.path.join(report_dir, filename)


def get_test_subdir(test_name):
    """
    Get or create a subdirectory for tests that generate multiple files.

    Args:
        test_name: Name of the test (e.g., "Test07_IBERT", "Test0400_FEMB_Slot0_Pulse")

    Returns:
        Full path to the test subdirectory.
    """
    report_dir = get_report_dir()
    subdir = os.path.join(report_dir, test_name)
    os.makedirs(subdir, exist_ok=True)
    return subdir


def set_wib_id(wib_id):
    """Set the WIB ID (call before init_session if needed)."""
    # This is now handled by init_session reading from rp_dict
    pass


def print_report_info():
    """Print current session's report directory information."""
    report_dir, wib_id = _read_session_file()
    print(f"\n{'=' * 60}")
    print("CURRENT SESSION INFO")
    print(f"{'=' * 60}")
    print(f"  WIB ID: {wib_id or get_wib_id()}")
    print(f"  Report Directory: {report_dir or get_report_dir()}")
    print(f"{'=' * 60}\n")


def clear_session():
    """Clear the session file (call at end of testing if needed)."""
    session_file_path = os.path.abspath(SESSION_FILE)
    if os.path.exists(session_file_path):
        os.remove(session_file_path)
        print(f"[path_debug] Session file cleared: {session_file_path}")


# Legacy alias for backward compatibility
def init_report_session(wib_id=None):
    """
    Get the report session path for test components.

    If called from a subprocess (session exists from WIB_QC_Detail.py),
    returns the existing session path. Otherwise creates a new session.

    Note: This NEVER creates a new session if one already exists.
    Use init_session(force_new=True) in WIB_QC_Detail.py to start fresh.
    """
    return init_session(wib_id, force_new=False)


if __name__ == "__main__":
    # Test the module
    print("Testing report_path module...")
    print("=" * 60)

    # Simulate WIB_QC_Detail.py initializing session
    print("\n1. Initialize session (like WIB_QC_Detail.py):")
    init_session(wib_id="TEST_001")

    # Simulate subprocess tests calling get_report_dir
    print("\n2. Subprocess tests call get_report_dir():")
    for i in range(3):
        path = get_report_dir()
        print(f"   Test {i+1}: {path}")

    print("\n3. Get report paths:")
    print(f"   Test01: {get_report_path('Test01_report.html')}")
    print(f"   Test07 subdir: {get_test_subdir('Test07_IBERT')}")

    # Clean up
    print("\n4. Clear session:")
    clear_session()
