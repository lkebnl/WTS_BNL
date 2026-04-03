#!/usr/bin/env python3
"""
SD Card Flasher & Reporter
Auto-detect 32GB SD card, write image, generate report
"""

import subprocess
import os
import sys
import json
import csv
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from function.report_path import get_report_dir

# ── Configuration ────────────────────────────────────────
# Default image path (can be overridden by wib_info.csv)
DEFAULT_IMAGE_PATH = "/home/dune/Documents/zynq_sdcard_ceqc.img"
TARGET_SIZE_GB = 32
SIZE_TOLERANCE_GB = 4
WIB_INFO_PATH = os.path.join(os.path.dirname(__file__), '..', 'file', 'wib_info.csv')
# ──────────────────────────────────────────────────────


def _read_wib_info(key):
    """Read a value from wib_info.csv by key"""
    try:
        with open(WIB_INFO_PATH, mode='r', newline='', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) == 2 and row[0].strip() == key:
                    return row[1].strip()
    except Exception as e:
        print(f"  [Warning] Could not read wib_info.csv: {e}")
    return None


def get_sudo_password():
    """Read sudo password from wib_info.csv"""
    pwd = _read_wib_info('SUDO_PASSWORD')
    if pwd is None:
        raise RuntimeError("SUDO_PASSWORD not found in file/wib_info.csv")
    return pwd


def get_image_path():
    """Read SD image path from wib_info.csv, fallback to default"""
    path = _read_wib_info('SD_IMAGE_PATH')
    if path:
        if os.path.exists(path):
            return path
        print(f"  [Warning] SD_IMAGE_PATH in wib_info.csv not found: {path}")
        print(f"  [Warning] Using default: {DEFAULT_IMAGE_PATH}")
    return DEFAULT_IMAGE_PATH


def run(cmd, check=True):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)


def run_sudo(cmd, check=True):
    full_cmd = f"echo '{get_sudo_password()}' | sudo -S {cmd}"
    return subprocess.run(full_cmd, shell=True, capture_output=True, text=True, check=check)


def get_block_devices():
    result = run("lsblk -J -b -o NAME,SIZE,TYPE,MOUNTPOINT,HOTPLUG")
    return json.loads(result.stdout)


def find_sd_card():
    """Auto-detect ~32GB SD card, auto-unmount mounted partitions"""
    data = get_block_devices()
    candidates = []

    for dev in data.get("blockdevices", []):
        name = dev["name"]
        size_bytes = int(dev.get("size") or 0)
        size_gb = size_bytes / (1024 ** 3)
        dev_type = dev.get("type", "")

        if dev_type != "disk":
            continue
        if abs(size_gb - TARGET_SIZE_GB) > SIZE_TOLERANCE_GB:
            continue

        is_mmc = name.startswith("mmcblk")
        is_usb = name.startswith("sd")

        if not (is_mmc or is_usb):
            continue

        # Auto-unmount mounted partitions
        children = dev.get("children", [])
        for part in children:
            mp = part.get("mountpoint")
            if mp:
                print(f"  [Auto-unmount] {mp} ...")
                run_sudo(f"umount {mp}", check=False)

        # Check if still mounted
        result = run("lsblk -J -b -o NAME,MOUNTPOINT")
        fresh = json.loads(result.stdout)
        still_mounted = False
        for d in fresh.get("blockdevices", []):
            if d["name"] == name:
                still_mounted = any(
                    p.get("mountpoint") for p in d.get("children", [])
                )
        if still_mounted:
            print(f"  [Skip] /dev/{name} unmount failed, please handle manually")
            continue

        candidates.append({
            "name": name,
            "device": f"/dev/{name}",
            "size_gb": round(size_gb, 1),
            "is_mmc": is_mmc,
        })

    return candidates


def get_sd_info(device_name):
    """Read SD card info, compatible with native mmcblk and USB card reader"""
    info = {"device": f"/dev/{device_name}"}

    if device_name.startswith("mmcblk"):
        base = f"/sys/block/{device_name}/device"
        for field in ["manfid", "oemid", "name", "serial", "date", "cid"]:
            try:
                with open(f"{base}/{field}") as f:
                    info[field] = f.read().strip()
            except Exception:
                info[field] = "N/A"
    else:
        result = run(f"udevadm info --query=all --name=/dev/{device_name}", check=False)
        mapping = {
            "ID_VENDOR":       "vendor",
            "ID_MODEL":        "name",
            "ID_SERIAL_SHORT": "serial",
            "ID_REVISION":     "revision",
        }
        for line in result.stdout.splitlines():
            for key, field in mapping.items():
                if f"E: {key}=" in line:
                    info[field] = line.split("=", 1)[-1].strip()

    # Get capacity
    result = run(f"lsblk -o NAME,SIZE /dev/{device_name}", check=False)
    for line in result.stdout.splitlines():
        if device_name in line:
            info["capacity"] = line.split()[1]
            break

    return info


def flash_image(device, image_path):
    """Flash image to SD card with progress counter"""
    import threading
    import time

    # Get image size for progress estimation
    image_size_bytes = os.path.getsize(image_path)
    image_size_mb = image_size_bytes / (1024 * 1024)

    print(f"\n  Writing {image_path} → {device}")
    print(f"  Image size: {image_size_mb:.1f} MB")
    print("  (This may take several minutes...)\n")

    # Progress display variables
    stop_progress = threading.Event()
    start_time = time.time()

    def show_progress():
        """Display elapsed time counter while dd is running"""
        spinner = ['|', '/', '-', '\\']
        spin_idx = 0
        while not stop_progress.is_set():
            elapsed = time.time() - start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            # Estimate progress (approximate based on typical SD write speed ~20MB/s)
            estimated_speed_mbps = 20
            estimated_progress = min(100, (elapsed * estimated_speed_mbps / image_size_mb) * 100)

            print(f"\r  {spinner[spin_idx]} Writing... Elapsed: {minutes:02d}:{seconds:02d}  "
                  f"[{'=' * int(estimated_progress // 5)}{' ' * (20 - int(estimated_progress // 5))}] "
                  f"~{estimated_progress:.0f}%   ", end='', flush=True)

            spin_idx = (spin_idx + 1) % 4
            time.sleep(0.5)

    # Start progress thread
    progress_thread = threading.Thread(target=show_progress)
    progress_thread.start()

    try:
        cmd = f"dd if={image_path} of={device} bs=4M conv=fsync status=progress"
        result = subprocess.run(
            f"echo '{get_sudo_password()}' | sudo -S {cmd}",
            shell=True, text=True, stderr=subprocess.PIPE
        )
    finally:
        # Stop progress display
        stop_progress.set()
        progress_thread.join()

    # Calculate final time
    total_time = time.time() - start_time
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)

    print()  # New line after progress

    if result.returncode != 0:
        print(f"\n  ✗ Flash FAILED (return code: {result.returncode})")
        raise RuntimeError(f"dd failed with return code: {result.returncode}")

    run_sudo("sync")
    print(f"\n  ✓ Flash completed successfully!")
    print(f"  Total time: {minutes:02d}:{seconds:02d}")
    print(f"  Average speed: {image_size_mb / total_time:.1f} MB/s")


def generate_report(sd_info, image_path, success, error_msg=None):
    """Generate HTML report (integrated with QC report system)"""
    # Get centralized report directory
    report_dir = get_report_dir()

    # Determine pass/fail suffix
    result_suffix = "_P" if success else "_F"
    report_path = os.path.join(report_dir, f"Test11_SD_Flash_report{result_suffix}.html")

    status_str = "PASS" if success else "FAIL"
    status_color = "#28a745" if success else "#dc3545"
    status_bg = "#d4edda" if success else "#f8d7da"

    # Build HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test11 SD Card Flash Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f9f9f9;
            color: #333;
        }}
        h2 {{
            text-align: center;
            color: #444;
        }}
        .status-banner {{
            text-align: center;
            padding: 15px;
            margin: 20px auto;
            width: 60%;
            border-radius: 8px;
            font-size: 1.2em;
            font-weight: bold;
            background-color: {status_bg};
            color: {status_color};
            border: 2px solid {status_color};
        }}
        table {{
            width: 60%;
            margin: 20px auto;
            border-collapse: collapse;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px 15px;
            text-align: left;
        }}
        th {{
            background-color: #f0f0f0;
            font-weight: bold;
        }}
        tr:nth-child(even) td {{
            background-color: #fafafa;
        }}
        .pass {{ color: #28a745; font-weight: bold; }}
        .fail {{ color: #dc3545; font-weight: bold; }}
    </style>
</head>
<body>
    <h2>Test11: SD Card Flash Report</h2>
    <div class="status-banner">
        Flash Result: {status_str}
    </div>

    <h3 style="text-align: center;">Flash Information</h3>
    <table>
        <tr><th>Item</th><th>Value</th></tr>
        <tr><td>Test Time</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        <tr><td>Image File</td><td>{image_path}</td></tr>
        <tr><td>Flash Result</td><td class="{'pass' if success else 'fail'}">{status_str}</td></tr>
        {'<tr><td>Error Message</td><td class="fail">' + error_msg + '</td></tr>' if error_msg else ''}
    </table>

    <h3 style="text-align: center;">SD Card Information</h3>
    <table>
        <tr><th>Item</th><th>Value</th></tr>
        <tr><td>Device</td><td>{sd_info.get('device', 'N/A')}</td></tr>
        <tr><td>Capacity</td><td>{sd_info.get('capacity', 'N/A')}</td></tr>
        <tr><td>Product Name</td><td>{sd_info.get('name', 'N/A')}</td></tr>
        <tr><td>Serial Number</td><td>{sd_info.get('serial', 'N/A')}</td></tr>
        <tr><td>Vendor</td><td>{sd_info.get('vendor', sd_info.get('manfid', 'N/A'))}</td></tr>
        <tr><td>OEM ID</td><td>{sd_info.get('oemid', 'N/A')}</td></tr>
        <tr><td>Production Date</td><td>{sd_info.get('date', 'N/A')}</td></tr>
        <tr><td>CID</td><td>{sd_info.get('cid', 'N/A')}</td></tr>
    </table>
</body>
</html>"""

    with open(report_path, "w") as f:
        f.write(html_content)

    # Also print text summary to console
    print("\n" + "=" * 55)
    print("         SD Card Flash Report")
    print("=" * 55)
    print(f"  Time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Image:       {image_path}")
    print(f"  Result:      {status_str}")
    if error_msg:
        print(f"  Error:       {error_msg}")
    print("-" * 55)
    print(f"  Device:      {sd_info.get('device', 'N/A')}")
    print(f"  Capacity:    {sd_info.get('capacity', 'N/A')}")
    print(f"  Name:        {sd_info.get('name', 'N/A')}")
    print(f"  Serial:      {sd_info.get('serial', 'N/A')}")
    print("=" * 55)
    print(f"\n  HTML Report saved: {report_path}")

    return report_path


def main():
    print("=" * 55)
    print("  SD Card Flasher")
    print("=" * 55)

    # Get image path from wib_info.csv (or use default)
    image_path = get_image_path()
    print(f"\n  Image file: {image_path}")

    if not os.path.exists(image_path):
        print(f"[Error] Image file not found: {image_path}")
        print(f"  Please update SD_IMAGE_PATH in file/wib_info.csv")
        sys.exit(1)

    print("\nScanning for SD card...")
    candidates = find_sd_card()

    if not candidates:
        print("[Error] No matching 32GB SD card found")
        sys.exit(1)

    if len(candidates) > 1:
        print("Multiple candidate devices found:")
        for i, c in enumerate(candidates):
            print(f"  [{i}] {c['device']}  {c['size_gb']} GB")
        choice = int(input("Select device [0/1/...]: "))
        selected = candidates[choice]
    else:
        selected = candidates[0]

    print(f"\n  Target device: {selected['device']}  ({selected['size_gb']} GB)")

    confirm = input(f"\n  Confirm write to {selected['device']}? This is irreversible! [yes/N]: ")
    if confirm.strip().lower() != "yes":
        print("  Cancelled.")
        sys.exit(0)

    success = True
    error_msg = None
    try:
        flash_image(selected["device"], image_path)
    except Exception as e:
        success = False
        error_msg = str(e)
        print(f"\n  [Error] {error_msg}")

    print("\nReading SD card info...")
    sd_info = get_sd_info(selected["name"])
    generate_report(sd_info, image_path, success, error_msg)


if __name__ == "__main__":
    main()