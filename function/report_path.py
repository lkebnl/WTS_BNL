"""
Report Path Utility Module

This module manages the centralized report directory structure for WIB QC testing.

Report Structure:
    /home/dune/Documents/WIB_QC/
    └── {WIB_ID}_{MM_DD_YYYY}/
        ├── Test01_Communication_report.html
        ├── Test02_Calibration_report.html
        ├── Test03_1V_power_report.html
        ├── ...
        └── Test07_IBERT/
            ├── WIB_07_IBERT_report.html
            ├── eye_scan_X0Y4.png
            └── ...

Usage:
    from function.report_path import get_report_dir, get_report_path

    # Get report directory for current WIB
    report_dir = get_report_dir()  # Uses default WIB_ID "qc_debug"

    # Get report directory with specific WIB_ID
    report_dir = get_report_dir(wib_id="WIB_001")

    # Get full path for a specific report file
    report_path = get_report_path("Test01_Communication_report.html")
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

# Global variable to store current session's WIB_ID
_current_wib_id = None
_current_report_dir = None


def set_wib_id(wib_id):
    """
    Set the WIB ID for the current test session.
    This should be called at the start of testing.

    Args:
        wib_id: The WIB board identifier
    """
    global _current_wib_id, _current_report_dir
    _current_wib_id = wib_id
    _current_report_dir = None  # Reset so it gets regenerated


def get_wib_id():
    """
    Get the current WIB ID.
    Checks in order:
    1. _current_wib_id (set via set_wib_id())
    2. rp_dict.wib_info['WIB_ID'] (set via GUI)
    3. DEFAULT_WIB_ID ("qc_debug")
    """
    global _current_wib_id

    # First check if explicitly set
    if _current_wib_id:
        return _current_wib_id

    # Then check rp_dict.wib_info (from GUI input)
    try:
        import file.report_dict as rp_dict
        wib_id = rp_dict.wib_info.get('WIB_ID', None)
        if wib_id and wib_id != '':
            return wib_id
    except (ImportError, AttributeError):
        pass

    # Default fallback
    return DEFAULT_WIB_ID


def get_date_string():
    """
    Get current date and time in MM_DD_YYYY_HH_MM format.
    Includes hours and minutes to distinguish multiple test sessions per day.
    """
    return datetime.now().strftime("%m_%d_%Y_%H_%M")


def get_report_dir(wib_id=None, create=True):
    """
    Get the report directory path for a WIB board.
    Creates the directory if it doesn't exist.

    Args:
        wib_id: Optional WIB ID. If None, uses current session WIB_ID or default.
        create: If True, creates the directory if it doesn't exist.

    Returns:
        Full path to the report directory.

    Example:
        /home/dune/Documents/WIB_QC/qc_debug_02_24_2026/
    """
    global _current_report_dir

    # Use provided wib_id, or current session, or default
    if wib_id is None:
        wib_id = get_wib_id()

    # Get date string
    date_str = get_date_string()

    # Build directory name: WIB_ID_MM_DD_YYYY
    dir_name = f"{wib_id}_{date_str}"

    # Full path
    report_dir = os.path.join(WIB_QC_BASE_DIR, dir_name)

    # Create directory if needed
    if create:
        os.makedirs(report_dir, exist_ok=True)

    # Cache for session
    if wib_id == get_wib_id():
        _current_report_dir = report_dir

    return report_dir


def get_report_path(filename, wib_id=None, subdir=None):
    """
    Get full path for a report file.

    Args:
        filename: Name of the report file
        wib_id: Optional WIB ID
        subdir: Optional subdirectory within the report dir (e.g., "Test07_IBERT")

    Returns:
        Full path to the report file.

    Example:
        get_report_path("Test01_Communication_report.html")
        -> /home/dune/Documents/WIB_QC/qc_debug_02_24_2026/Test01_Communication_report.html

        get_report_path("eye_scan_X0Y4.png", subdir="Test07_IBERT")
        -> /home/dune/Documents/WIB_QC/qc_debug_02_24_2026/Test07_IBERT/eye_scan_X0Y4.png
    """
    report_dir = get_report_dir(wib_id=wib_id)

    if subdir:
        subdir_path = os.path.join(report_dir, subdir)
        os.makedirs(subdir_path, exist_ok=True)
        return os.path.join(subdir_path, filename)

    return os.path.join(report_dir, filename)


def get_test_subdir(test_name, wib_id=None):
    """
    Get or create a subdirectory for tests that generate multiple files.

    Args:
        test_name: Name of the test (e.g., "Test07_IBERT", "Test0400_FEMB_Pulse")
        wib_id: Optional WIB ID

    Returns:
        Full path to the test subdirectory.
    """
    report_dir = get_report_dir(wib_id=wib_id)
    subdir = os.path.join(report_dir, test_name)
    os.makedirs(subdir, exist_ok=True)
    return subdir


def print_report_info():
    """Print current report directory information."""
    print(f"\n{'=' * 60}")
    print("REPORT DIRECTORY INFORMATION")
    print(f"{'=' * 60}")
    print(f"  WIB ID: {get_wib_id()}")
    print(f"  Date: {get_date_string()}")
    print(f"  Report Directory: {get_report_dir(create=False)}")
    print(f"{'=' * 60}\n")


# Convenience function for test scripts
def init_report_session(wib_id=None):
    """
    Initialize a report session. Call this at the start of testing.

    Args:
        wib_id: WIB board ID. Defaults to "qc_debug" if not provided.

    Returns:
        Path to the report directory.
    """
    if wib_id:
        set_wib_id(wib_id)

    report_dir = get_report_dir()
    print_report_info()

    return report_dir


if __name__ == "__main__":
    # Test the module
    print("Testing report_path module...")

    # Test with default WIB_ID
    print(f"\nDefault WIB_ID: {get_wib_id()}")
    print(f"Date string: {get_date_string()}")
    print(f"Report dir: {get_report_dir(create=False)}")

    # Test with custom WIB_ID
    set_wib_id("WIB_TEST_001")
    print(f"\nCustom WIB_ID: {get_wib_id()}")
    print(f"Report dir: {get_report_dir(create=False)}")

    # Test report paths
    print(f"\nTest01 report: {get_report_path('Test01_Communication_report.html', wib_id='qc_debug')}")
    print(f"IBERT subdir: {get_test_subdir('Test07_IBERT', wib_id='qc_debug')}")
