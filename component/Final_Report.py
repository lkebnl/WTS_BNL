# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Final Report Generator for WIB QC Testing

Generates a comprehensive HTML report and PDF with all test results integrated.
- Summary page with clickable links to each test
- Each test report embedded page by page
"""

import sys
import os
import base64
import re
from datetime import datetime, timezone

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import file.report_dict as rp_dict
from function.report_path import get_report_path, get_report_dir, get_wib_id
from function.session_info import get_session_info

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def print_header(msg):
    print("\033[35m" + "=" * 60 + "\033[0m")
    print("\033[35m" + msg + "\033[0m")
    print("\033[35m" + "=" * 60 + "\033[0m")

def print_pass(msg):
    print("\033[32m" + msg + "\033[0m")

def print_fail(msg):
    print("\033[31m" + msg + "\033[0m")

def print_info(msg):
    print("\033[36m" + msg + "\033[0m")

def image_to_base64(image_path):
    """Convert image file to base64 string for embedding in HTML."""
    if not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Warning: Could not encode image {image_path}: {e}")
        return None

def get_image_mime_type(image_path):
    """Get MIME type based on file extension."""
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml'
    }
    return mime_types.get(ext, 'image/png')

# ============================================================
# TEST REPORT MAPPING
# ============================================================

# Define test items and their report files (base names without _P/_F suffix)
TEST_ITEMS = [
    {
        'id': 'test01',
        'name': 'Test01: Serial/TCP/IP Communication',
        'report_base': 'Test01_Communication_report',  # Will match _P.html or _F.html
        'rp_key': 'item01'
    },
    {
        'id': 'test02',
        'name': 'Test02: Calibration Path Control',
        'report_base': 'Test02_Calibration_report',
        'rp_key': 'item02'
    },
    {
        'id': 'test03_1v',
        'name': 'Test03: Power Rail FEMB 1V',
        'report_base': 'Test03_1V_power_report',
        'rp_key': 'item031'
    },
    {
        'id': 'test03_2v',
        'name': 'Test03: Power Rail FEMB 2V',
        'report_base': 'Test03_2V_power_report',
        'rp_key': 'item032'
    },
    {
        'id': 'test03_3v',
        'name': 'Test03: Power Rail FEMB 3V',
        'report_base': 'Test03_3V_power_report',
        'rp_key': 'item033'
    },
    {
        'id': 'test03_4v',
        'name': 'Test03: Power Rail FEMB 4V',
        'report_base': 'Test03_4V_power_report',
        'rp_key': 'item034'
    },
    {
        'id': 'test04_slot0',
        'name': 'Test04: WIB FEMB Pulse Slot 0',
        'report_base': 'Test0400_FEMB_Slot0_Pulse',  # Directory
        'rp_key': 'item041',
        'is_dir': True
    },
    {
        'id': 'test04_slot1',
        'name': 'Test04: WIB FEMB Pulse Slot 1',
        'report_base': 'Test0401_FEMB_Slot1_Pulse',
        'rp_key': 'item042',
        'is_dir': True
    },
    {
        'id': 'test04_slot2',
        'name': 'Test04: WIB FEMB Pulse Slot 2',
        'report_base': 'Test0402_FEMB_Slot2_Pulse',
        'rp_key': 'item043',
        'is_dir': True
    },
    {
        'id': 'test04_slot3',
        'name': 'Test04: WIB FEMB Pulse Slot 3',
        'report_base': 'Test0403_FEMB_Slot3_Pulse',
        'rp_key': 'item044',
        'is_dir': True
    },
    {
        'id': 'test05',
        'name': 'Test05: I2C Device Search',
        'report_base': 'Test05_I2C_Device_report',
        'rp_key': 'item051'
    },
    {
        'id': 'test052',
        'name': 'Test052: I2C Sensor Information',
        'report_base': 'Test052_I2C_Sensor_Info',
        'rp_key': 'item052'
    },
    {
        'id': 'test06',
        'name': 'Test06: PTB Interface Path',
        'report_base': 'Test06_PTB_Interface',
        'rp_key': 'item06'
    },
    {
        'id': 'test07',
        'name': 'Test07: IBERT',
        'report_base': 'Test07_IBERT_report',  # Uses _P.html or _F.html suffix
        'rp_key': 'item07'
    },
    {
        'id': 'test0802',
        'name': 'Test0802: SD Card Flash',
        'report_base': 'Test0802_SD_Flash_report',  # Uses _P.html or _F.html suffix
        'rp_key': 'item0802'
    },
    {
        'id': 'test0803',
        'name': 'Test0803: CTS FEMB Checkout',
        'report_base': 'Test0803_CTS_Checkout_report',  # Uses _P.html or _F.html suffix
        'rp_key': 'item0803'
    }
]

# ============================================================
# REPORT CONTENT EXTRACTION
# ============================================================

def find_report_html(report_dir, test_item):
    """
    Find the HTML report file for a test item and determine pass/fail status.

    Returns:
        tuple: (html_path, passed)
            - html_path: Full path to the HTML report, or None if not found
            - passed: True if _P suffix, False if _F suffix, None if unknown/not found
    """
    report_base = test_item.get('report_base', '')
    is_dir = test_item.get('is_dir', False)

    if is_dir:
        # For directory-based tests, look for result.html inside
        base_dir = os.path.join(report_dir, report_base)

        # Check for subdirectories (e.g., FEMB0_RT_0pF)
        if os.path.exists(base_dir):
            subdirs = [d for d in os.listdir(base_dir)
                      if os.path.isdir(os.path.join(base_dir, d))]
            if subdirs:
                # Use most recent subdirectory
                subdir = sorted(subdirs)[-1]
                result_html = os.path.join(base_dir, subdir, 'result.html')
                if os.path.exists(result_html):
                    # Directory-based tests: assume pass if result.html exists
                    return result_html, True

            # Check for result.html directly in base_dir
            result_html = os.path.join(base_dir, 'result.html')
            if os.path.exists(result_html):
                return result_html, True

            # Check for WIB_07_IBERT_report.html (Test07)
            ibert_html = os.path.join(base_dir, 'WIB_07_IBERT_report.html')
            if os.path.exists(ibert_html):
                return ibert_html, True

        # Check for legacy incorrectly-named directories
        try:
            for dir_name in os.listdir(report_dir):
                if dir_name.startswith(report_base) and os.path.isdir(os.path.join(report_dir, dir_name)):
                    legacy_dir = os.path.join(report_dir, dir_name)
                    result_html = os.path.join(legacy_dir, 'result.html')
                    if os.path.exists(result_html):
                        return result_html, True
        except FileNotFoundError:
            pass

        return None, None
    else:
        # Direct HTML file - check for _P.html or _F.html suffix
        # First try _P (pass)
        pass_html = os.path.join(report_dir, f"{report_base}_P.html")
        if os.path.exists(pass_html):
            return pass_html, True

        # Then try _F (fail)
        fail_html = os.path.join(report_dir, f"{report_base}_F.html")
        if os.path.exists(fail_html):
            return fail_html, False

        # Legacy: check for file without suffix
        legacy_html = os.path.join(report_dir, f"{report_base}.html")
        if os.path.exists(legacy_html):
            return legacy_html, None  # Unknown status for legacy files

    return None, None

def extract_body_content(html_path):
    """Extract the body content from an HTML file and convert images to base64."""
    if not html_path or not os.path.exists(html_path):
        return None

    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Extract body content
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_content = body_match.group(1)
        else:
            # If no body tag, use the whole content
            body_content = html_content

        # Convert relative image paths to base64
        html_dir = os.path.dirname(html_path)

        def replace_img_src(match):
            img_tag = match.group(0)
            src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
            if src_match:
                src = src_match.group(1)
                # Skip if already base64
                if src.startswith('data:'):
                    return img_tag

                # Resolve relative path
                if not os.path.isabs(src):
                    img_path = os.path.join(html_dir, src)
                else:
                    img_path = src

                if os.path.exists(img_path):
                    img_data = image_to_base64(img_path)
                    if img_data:
                        mime_type = get_image_mime_type(img_path)
                        new_src = f'data:{mime_type};base64,{img_data}'
                        img_tag = img_tag.replace(src_match.group(0), f'src="{new_src}"')
            return img_tag

        body_content = re.sub(r'<img[^>]+>', replace_img_src, body_content, flags=re.IGNORECASE)

        return body_content
    except Exception as e:
        print(f"Warning: Could not extract content from {html_path}: {e}")
        return None

def get_test_status(rp_key):
    """Get test status from rp_dict."""
    status = rp_dict.log_fn_rp.get(rp_key, 'Not Run')
    passed = 'Pass' in status
    return status, passed

# ============================================================
# HTML GENERATION
# ============================================================

def generate_html_content(wib_info, report_dir):
    """Generate comprehensive HTML report with embedded test reports."""

    wib_id = wib_info.get('WIB_ID', 'Unknown')
    foam_box_id = wib_info.get('Foam_Box_ID', '')
    tester = wib_info.get('tester', 'Unknown')
    test_site = wib_info.get('test_site', 'Unknown')
    start_time = wib_info.get('start_time', '')
    test_date = start_time if start_time else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Collect test info - determine pass/fail from filename suffix (_P or _F)
    test_reports = []
    for item in TEST_ITEMS:
        # Find report and determine pass/fail status from filename suffix
        html_path, file_passed = find_report_html(report_dir, item)
        body_content = extract_body_content(html_path) if html_path else None

        # Determine status: use filename suffix if available, otherwise use rp_dict
        if file_passed is not None:
            passed = file_passed
            status = "PASS" if passed else "FAIL"
        else:
            # Fallback to rp_dict status (for legacy reports or missing files)
            status, passed = get_test_status(item['rp_key'])

        test_reports.append({
            'id': item['id'],
            'name': item['name'],
            'status': status,
            'passed': passed,
            'has_report': body_content is not None,
            'content': body_content
        })

    # Count pass/fail - overall PASS only if ALL tests passed
    total_tests = len(test_reports)
    passed_tests = sum(1 for r in test_reports if r['passed'])
    failed_tests = total_tests - passed_tests
    overall_status = "PASS" if failed_tests == 0 else "FAIL"
    status_color = "#28a745" if overall_status == "PASS" else "#dc3545"

    # Start HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WIB QC Final Report - {wib_id}</title>
    <style>
        @page {{
            size: A4 landscape;
            margin: 8mm;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #ffffff;
            color: #000000;
            padding: 10px;
            line-height: 1.3;
            font-size: 9pt;
        }}
        .container {{
            max-width: 100%;
            margin: 0 auto;
        }}

        /* Header */
        .header {{
            text-align: center;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .header h1 {{
            font-size: 16pt;
            font-weight: bold;
            margin-bottom: 3px;
        }}
        .header .subtitle {{
            font-size: 10pt;
            color: #666;
        }}

        /* Status Banner */
        .status-banner {{
            text-align: center;
            padding: 8px;
            margin: 10px 0;
            font-size: 12pt;
            font-weight: bold;
            border: 2px solid {status_color};
            background-color: {'#d4edda' if overall_status == 'PASS' else '#f8d7da'};
            color: {status_color};
        }}

        /* Info Grid */
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin: 15px 0;
            padding: 12px;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
        }}
        .info-item {{
            display: flex;
        }}
        .info-label {{
            font-weight: bold;
            min-width: 110px;
        }}

        /* Summary Table */
        .summary-section {{
            margin: 15px 0;
        }}
        .section-title {{
            font-size: 11pt;
            font-weight: bold;
            padding: 6px 10px;
            background: #343a40;
            color: white;
            margin-bottom: 0;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8pt;
        }}
        .summary-table th {{
            background-color: #495057;
            color: white;
            font-weight: bold;
            text-align: left;
            padding: 5px 8px;
            border: 1px solid #000;
        }}
        .summary-table td {{
            padding: 5px 8px;
            border: 1px solid #dee2e6;
        }}
        .summary-table tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        .summary-table tr:hover {{
            background-color: #e9ecef;
        }}
        .summary-table a {{
            color: #0066cc;
            text-decoration: none;
            font-weight: 500;
        }}
        .summary-table a:hover {{
            text-decoration: underline;
        }}

        /* Status Colors */
        .status-pass {{
            color: #28a745;
            font-weight: bold;
        }}
        .status-fail {{
            color: #dc3545;
            font-weight: bold;
        }}
        .status-na {{
            color: #6c757d;
        }}

        /* Test Report Section */
        .test-report {{
            page-break-before: always;
            margin-top: 10px;
            border: 1px solid #343a40;
        }}
        .test-report-header {{
            background: #343a40;
            color: white;
            padding: 6px 10px;
            font-size: 10pt;
            font-weight: bold;
        }}
        .test-report-header a {{
            color: white;
            text-decoration: none;
        }}
        .back-to-top {{
            float: right;
            font-size: 8pt;
            font-weight: normal;
        }}
        .test-report-content {{
            padding: 10px;
            background: #fff;
        }}
        .test-report-content img {{
            max-width: 100%;
            height: auto;
        }}
        .test-report-content table {{
            font-size: 8pt;
            width: 100%;
        }}
        .no-report {{
            padding: 30px;
            text-align: center;
            color: #999;
            font-style: italic;
        }}

        /* Footer */
        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 2px solid #dee2e6;
            text-align: center;
            font-size: 9pt;
            color: #6c757d;
        }}

        /* Embedded report overrides */
        .test-report-content .container {{
            padding: 0;
        }}
        .test-report-content .header {{
            display: none;
        }}
        .test-report-content .footer {{
            display: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>DUNE WIB Quality Control Report</h1>
            <div class="subtitle">Warm Interface Board - Final Test Report</div>
        </div>

        <!-- Overall Status -->
        <div class="status-banner" id="top">
            OVERALL QC STATUS: {overall_status}
        </div>

        <!-- Board Information -->
        <div class="info-grid">
            <div class="info-item"><span class="info-label">WIB ID:</span> {wib_id}</div>
            <div class="info-item"><span class="info-label">Foam Box ID:</span> {foam_box_id}</div>
            <div class="info-item"><span class="info-label">Test Date:</span> {test_date}</div>
            <div class="info-item"><span class="info-label">Tester:</span> {tester}</div>
            <div class="info-item"><span class="info-label">Test Site:</span> {test_site}</div>
            <div class="info-item"><span class="info-label">Tests Passed:</span> {passed_tests}/{total_tests}</div>
        </div>

        <!-- Test Summary Table with Clickable Links -->
        <div class="summary-section">
            <div class="section-title">Test Results Summary (Click to Jump to Report)</div>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th style="width: 5%;">#</th>
                        <th style="width: 50%;">Test Item</th>
                        <th style="width: 30%;">Result</th>
                        <th style="width: 15%;">Status</th>
                    </tr>
                </thead>
                <tbody>"""

    # Add summary rows with links
    for idx, report in enumerate(test_reports, 1):
        status_class = "status-pass" if report['passed'] else "status-fail"
        status_text = "PASS" if report['passed'] else "FAIL"
        if 'Not Run' in report['status']:
            status_class = "status-na"
            status_text = "N/A"

        # Create link if report exists
        if report['has_report']:
            name_cell = f'<a href="#{report["id"]}">{report["name"]}</a>'
        else:
            name_cell = f'{report["name"]} <span class="status-na">(No Report)</span>'

        html += f"""
                    <tr>
                        <td>{idx}</td>
                        <td>{name_cell}</td>
                        <td>{report['status']}</td>
                        <td class="{status_class}">{status_text}</td>
                    </tr>"""

    html += """
                </tbody>
            </table>
        </div>"""

    # Add each test report as a separate page
    for report in test_reports:
        if report['has_report'] and report['content']:
            html += f"""

        <!-- {report['name']} -->
        <div class="test-report" id="{report['id']}">
            <div class="test-report-header">
                {report['name']}
                <a href="#top" class="back-to-top">[Back to Summary]</a>
            </div>
            <div class="test-report-content">
                {report['content']}
            </div>
        </div>"""
        else:
            html += f"""

        <!-- {report['name']} -->
        <div class="test-report" id="{report['id']}">
            <div class="test-report-header">
                {report['name']}
                <a href="#top" class="back-to-top">[Back to Summary]</a>
            </div>
            <div class="no-report">
                No report available for this test item.
            </div>
        </div>"""

    # Footer
    html += f"""

        <!-- Footer -->
        <div class="footer">
            <p>DUNE WIB Quality Control System - Final Report</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Report Directory: {report_dir}</p>
            <p>Made by Lingyun Ke</p>
        </div>
    </div>
</body>
</html>"""

    return html

# ============================================================
# PDF GENERATION
# ============================================================

def generate_pdf(html_path, pdf_path):
    """Generate PDF from HTML using weasyprint."""
    try:
        from weasyprint import HTML
        print_info(f"  Generating PDF from HTML...")
        HTML(filename=html_path).write_pdf(pdf_path)
        print_pass(f"  ✓ PDF saved: {pdf_path}")
        return True
    except ImportError:
        print_fail("  ✗ weasyprint not installed. Install with: pip install weasyprint")
        return False
    except Exception as e:
        print_fail(f"  ✗ PDF generation failed: {e}")
        return False

# ============================================================
# MAIN FUNCTION
# ============================================================

def generate_final_report():
    """Generate the final comprehensive report."""
    print_header("Generating Final QC Report")

    # Get session info (shared across subprocesses via JSON file)
    session_info = get_session_info()

    # Build wib_info from session_info (primary) with rp_dict fallback
    wib_info = {
        'WIB_ID': session_info.get('WIB_ID') or rp_dict.wib_info.get('WIB_ID', get_wib_id()),
        'Foam_Box_ID': session_info.get('Foam_Box_ID', ''),
        'tester': session_info.get('tester') or rp_dict.wib_info.get('tester', 'Unknown'),
        'test_site': session_info.get('test_site') or rp_dict.wib_info.get('test_site', 'Unknown'),
        'start_time': session_info.get('start_time', ''),
        'date': datetime.now(timezone.utc)
    }

    # Get report directory
    report_dir = get_report_dir()
    print_info(f"  Report Directory: {report_dir}")

    # List available reports and their pass/fail status
    print_info("  Scanning for test reports...")
    for item in TEST_ITEMS:
        html_path, file_passed = find_report_html(report_dir, item)
        if html_path:
            if file_passed is True:
                print_pass(f"    ✓ {item['name']} [PASS]")
            elif file_passed is False:
                print_fail(f"    ✗ {item['name']} [FAIL]")
            else:
                print_info(f"    ? {item['name']} [unknown status]")
        else:
            print_info(f"    - {item['name']} (not found)")

    # Generate HTML
    print_info("  Generating integrated HTML report...")
    html_content = generate_html_content(wib_info, report_dir)

    # Save HTML
    html_path = get_report_path("Final_Report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print_pass(f"  ✓ HTML saved: {html_path}")

    # Generate PDF
    pdf_path = get_report_path("Final_Report.pdf")
    pdf_success = generate_pdf(html_path, pdf_path)

    # Summary
    print_header("Final Report Generated")
    print_info(f"  WIB ID:       {wib_info['WIB_ID']}")
    print_info(f"  Foam Box ID:  {wib_info.get('Foam_Box_ID', 'N/A')}")
    print_info(f"  Tester:       {wib_info['tester']}")
    print_info(f"  Test Site:    {wib_info['test_site']}")
    print_info(f"\n  HTML Report: {html_path}")
    if pdf_success:
        print_info(f"  PDF Report: {pdf_path}")

    return html_path, pdf_path if pdf_success else None

# ============================================================
# LEGACY SUPPORT
# ============================================================

def fin_rep(item=1, status=True):
    """Legacy function to update test status."""
    status_map = {
        1: ('item01', 'Serial_TCP/IP_Communication'),
        2: ('item02', 'Calibration Path Control'),
        31: ('item031', 'Power Rail 1V'),
        32: ('item032', 'Power Rail 2V'),
        33: ('item033', 'Power Rail 3V'),
        34: ('item034', 'Power Rail 4V'),
        41: ('item041', 'WIB FEMB Pulse Slot 0'),
        42: ('item042', 'WIB FEMB Pulse Slot 1'),
        43: ('item043', 'WIB FEMB Pulse Slot 2'),
        44: ('item044', 'WIB FEMB Pulse Slot 3'),
        51: ('item051', 'I2C Device Search'),
        52: ('item052', 'I2C Sensor Info'),
        6: ('item06', 'PTB Interface'),
        7: ('item07', 'IBERT'),
        802: ('item0802', 'SD Card Flash'),
        803: ('item0803', 'CTS FEMB Checkout')
    }

    if item in status_map:
        key, name = status_map[item]
        status_text = "Pass QC" if status else "QC Failed"
        rp_dict.log_fn_rp[key] = f'Item_{item:02d} {name} {status_text}'

# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Set default test statuses (for testing)
    for item in [1, 2, 31, 32, 33, 34, 41, 42, 43, 44, 51, 52, 6, 7]:
        fin_rep(item=item, status=True)

    # Generate final report
    html_path, pdf_path = generate_final_report()

    print(f"\nReport generation complete.")
    print(f"HTML: {html_path}")
    if pdf_path:
        print(f"PDF: {pdf_path}")
