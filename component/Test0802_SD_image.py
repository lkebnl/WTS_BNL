#!/usr/bin/env python3
# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
SD Card Flasher & Reporter
Auto-detect 32GB SD card, write image, generate report

Usage:
  python Test0802_SD_image.py           Flash image to SD card and write identity
  python Test0802_SD_image.py --read    Read identity from SD card (no flashing)

Identity info written to SD card (unallocated space after image):
  WIB_ID, Tester, Test_Site, Foam_Box_ID, Flash_Date, Image, Image_Size_Bytes
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
DEFAULT_IMAGE_PATH = "/home/dune/QSFP_Production.img"
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


AUTO_SHRINK_LIMIT_MB = 200  # auto-shrink only if image is within this margin


def shrink_image(image_path):
    """
    Shrink the last ext partition of image_path to minimum size, then truncate
    the file.  Modifies the image in-place.  No confirmation prompt.
    """
    import json as _json
    import tempfile

    orig_size = os.path.getsize(image_path)
    print(f"\n  [Shrink] Original size: {orig_size/1e9:.3f} GB")

    # Attach loop device with partition detection
    r = run_sudo(f"losetup -f --show -P {image_path}")
    loop_dev = r.stdout.strip()
    print(f"  [Shrink] Loop device: {loop_dev}")

    new_image_size = None
    try:
        # Find last partition
        r = run(f"lsblk -ln -o NAME,TYPE {loop_dev}")
        parts = [line.split()[0] for line in r.stdout.splitlines()
                 if len(line.split()) >= 2 and line.split()[1] == 'part']
        if not parts:
            raise RuntimeError("No partitions found in image")
        last_part = f"/dev/{parts[-1]}"

        run_sudo(f"partprobe {loop_dev}", check=False)
        r = run_sudo(f"blkid -s TYPE -o value {last_part}", check=False)
        fs_type = r.stdout.strip()
        if not fs_type.startswith('ext'):
            raise RuntimeError(f"Last partition is '{fs_type}' — only ext2/3/4 supported")
        print(f"  [Shrink] Shrinking {last_part} ({fs_type})...")

        # Shrink filesystem to minimum
        # e2fsck exit code 1 = errors corrected (normal), >=4 = real failure
        r = run_sudo(f"e2fsck -f -y {last_part}", check=False)
        if r.returncode >= 4:
            raise RuntimeError(f"e2fsck failed (exit {r.returncode}): {r.stderr.strip()}")
        run_sudo(f"resize2fs -M {last_part}")

        # Get partition start and new filesystem size
        r = run_sudo(f"sfdisk -J {loop_dev}")
        disk_info = _json.loads(r.stdout)
        sector_size = disk_info['partitiontable'].get('sectorsize', 512)
        all_parts = disk_info['partitiontable']['partitions']
        part_entry = next((p for p in all_parts if p['node'] == last_part), all_parts[-1])
        part_start = part_entry['start']

        r = run_sudo(f"tune2fs -l {last_part}")
        block_count = block_size = 0
        for line in r.stdout.splitlines():
            if line.startswith('Block count:'):
                block_count = int(line.split(':')[1].strip())
            elif line.startswith('Block size:'):
                block_size = int(line.split(':')[1].strip())
        new_part_sectors = (block_count * block_size + sector_size - 1) // sector_size
        new_image_size = (part_start + new_part_sectors) * sector_size

        # Update partition table via temp sfdisk script
        script_lines = []
        for p in all_parts:
            sz = new_part_sectors if p['node'] == last_part else p['size']
            script_lines.append(
                f"{p['node']} : start={p['start']}, size={sz}, type={p.get('type', '83')}"
            )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sfdisk', delete=False) as f:
            f.write('\n'.join(script_lines) + '\n')
            tmpfile = f.name
        run_sudo(f"sfdisk --no-reread {loop_dev} < {tmpfile}", check=False)
        os.unlink(tmpfile)

    finally:
        run_sudo(f"losetup -d {loop_dev}", check=False)

    if new_image_size is None:
        raise RuntimeError("Shrink failed, image not modified")

    run(f"truncate -s {new_image_size} {image_path}")
    final_size = os.path.getsize(image_path)
    print(f"  [Shrink] Done: {orig_size/1e9:.3f} GB → {final_size/1e9:.3f} GB  "
          f"(saved {(orig_size - final_size)/1e6:.1f} MB)")


def prepare_device(device, image_path):
    """Check card capacity (auto-shrink if needed), then wipe partition signatures"""
    image_size_bytes = os.path.getsize(image_path)
    result = run(f"lsblk -b -o NAME,SIZE -dn {device}", check=False)
    card_size_bytes = 0
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                card_size_bytes = int(parts[1])
            except ValueError:
                pass

    if card_size_bytes > 0 and card_size_bytes < image_size_bytes:
        shortage_mb = (image_size_bytes - card_size_bytes) / (1024 * 1024)
        if shortage_mb > AUTO_SHRINK_LIMIT_MB:
            raise RuntimeError(
                f"SD card too small! Image: {image_size_bytes/1e9:.3f} GB, "
                f"Card: {card_size_bytes/1e9:.3f} GB "
                f"(short by {shortage_mb:.1f} MB). Use a larger card."
            )
        print(f"\n  [Auto-shrink] Image is {shortage_mb:.1f} MB larger than card — shrinking image...")
        shrink_image(image_path)

    # Wipe partition signatures
    print(f"\n  [Prepare] Wiping partition signatures on {device}...")
    result = run_sudo(f"wipefs -a {device}", check=False)
    if result.returncode != 0:
        err = result.stderr.strip()
        raise RuntimeError(f"wipefs failed (device may be read-only or in use): {err}")
    print(f"  ✓ Device cleared, ready to flash")


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
        if result.stderr:
            print(f"  [dd error] {result.stderr.strip()}")
        raise RuntimeError(f"dd failed with return code: {result.returncode}")

    run_sudo("sync")
    print(f"\n  ✓ Flash completed successfully!")
    print(f"  Total time: {minutes:02d}:{seconds:02d}")
    print(f"  Average speed: {image_size_mb / total_time:.1f} MB/s")


def write_card_identity(device, image_path):
    """
    Write identity info to the unallocated space just after the image.
    Does NOT touch any partition or filesystem.
    Can be read back later with read_card_identity().
    """
    image_size_bytes = os.path.getsize(image_path)
    # Start sector = first 512-byte sector beyond the image
    start_sector = image_size_bytes // 512

    wib_id      = _read_wib_info('WIB_ID')      or 'Unknown'
    tester      = _read_wib_info('tester')      or 'Unknown'
    test_site   = _read_wib_info('test_site')   or 'Unknown'
    foam_box_id = _read_wib_info('Foam_Box_ID') or 'Unknown'
    timestamp   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    identity = (
        f"WIB_ID={wib_id}\n"
        f"Tester={tester}\n"
        f"Test_Site={test_site}\n"
        f"Foam_Box_ID={foam_box_id}\n"
        f"Flash_Date={timestamp}\n"
        f"Image={os.path.basename(image_path)}\n"
        f"Image_Size_Bytes={image_size_bytes}\n"
        f"Made by Lingyun Ke\n"
    )

    # Pad / truncate to exactly 512 bytes
    identity_bytes = identity.encode('utf-8')[:512].ljust(512, b'\x00')

    print(f"\n  [Identity] Writing to sector {start_sector} of {device}...")
    try:
        proc = subprocess.run(
            f"echo '{get_sudo_password()}' | sudo -S dd of={device} bs=512 seek={start_sector} count=1 conv=notrunc",
            input=identity_bytes,
            shell=True,
            capture_output=True
        )
        if proc.returncode == 0:
            print(f"  ✓ Identity written successfully")
            print(f"    WIB_ID        : {wib_id}")
            print(f"    Tester        : {tester}")
            print(f"    Test Site     : {test_site}")
            print(f"    Foam Box ID   : {foam_box_id}")
            print(f"    Flash Date    : {timestamp}")
            print(f"    Image Size    : {image_size_bytes} bytes (sector offset: {start_sector})")
        else:
            print(f"  [Warning] Identity write failed: {proc.stderr.decode()}")
    except Exception as e:
        print(f"  [Warning] Identity write error: {e}")

    return start_sector


def read_card_identity(device, start_sector):
    """Read back identity info from SD card unallocated space."""
    print(f"\n  [Identity] Reading from sector {start_sector} of {device}...")
    try:
        proc = subprocess.run(
            f"echo '{get_sudo_password()}' | sudo -S dd if={device} bs=512 skip={start_sector} count=1",
            shell=True,
            capture_output=True
        )
        data = proc.stdout.rstrip(b'\x00').decode('utf-8', errors='ignore')
        print("  Identity on card:")
        for line in data.splitlines():
            if line.strip():
                print(f"    {line}")
        return data
    except Exception as e:
        print(f"  [Warning] Identity read error: {e}")
        return None


def generate_report(sd_info, image_path, success, error_msg=None):
    """Generate HTML report (integrated with QC report system)"""
    # Get centralized report directory
    report_dir = get_report_dir()

    # Determine pass/fail suffix
    result_suffix = "_P" if success else "_F"
    report_path = os.path.join(report_dir, f"Test0802_SD_Flash_report{result_suffix}.html")

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
    <div style="text-align:center; margin-top:30px; color:#999; font-size:0.85em;">
        <p>Made by Lingyun Ke</p>
    </div>
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

    # Save results to shared test08 combined data file
    import json as _json
    _data_path = os.path.join(report_dir, 'test08_combined_data.json')
    _test08 = {}
    if os.path.exists(_data_path):
        try:
            with open(_data_path) as _f:
                _test08 = _json.load(_f)
        except Exception:
            pass
    _test08['test0802'] = {
        'status': 'PASS' if success else 'FAIL',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'image_path': str(image_path),
        'sd_device': sd_info.get('device', 'N/A'),
        'sd_capacity': sd_info.get('capacity', 'N/A'),
        'sd_name': sd_info.get('name', 'N/A'),
        'sd_serial': sd_info.get('serial', 'N/A'),
        'sd_vendor': sd_info.get('vendor', sd_info.get('manfid', 'N/A')),
        'error_msg': error_msg or ''
    }
    try:
        with open(_data_path, 'w') as _f:
            _json.dump(_test08, _f, indent=2)
    except Exception as _e:
        print(f"  [Warning] Could not save test08 combined data: {_e}")

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
    start_sector = None
    try:
        prepare_device(selected["device"], image_path)
        flash_image(selected["device"], image_path)
        start_sector = write_card_identity(selected["device"], image_path)
        read_card_identity(selected["device"], start_sector)
    except Exception as e:
        success = False
        error_msg = str(e)
        print(f"\n  [Error] {error_msg}")

    print("\nReading SD card info...")
    sd_info = get_sd_info(selected["name"])
    generate_report(sd_info, image_path, success, error_msg)


def read_mode():
    """Read identity from SD card without flashing."""
    print("=" * 55)
    print("  SD Card Identity Reader")
    print("=" * 55)

    candidates = find_sd_card()
    if not candidates:
        print("[Error] No SD card found")
        sys.exit(1)

    if len(candidates) > 1:
        print("Multiple candidate devices found:")
        for i, c in enumerate(candidates):
            print(f"  [{i}] {c['device']}  {c['size_gb']} GB")
        choice = int(input("Select device [0/1/...]: "))
        device = candidates[choice]["device"]
    else:
        device = candidates[0]["device"]
        print(f"  Device: {device}")

    image_path = get_image_path()
    image_size_bytes = os.path.getsize(image_path)
    start_sector = image_size_bytes // 512
    read_card_identity(device, start_sector)


def shrink_mode():
    """--shrink: manually shrink image with confirmation prompt"""
    image_path = get_image_path()
    if not os.path.exists(image_path):
        print(f"[Error] Image not found: {image_path}")
        sys.exit(1)

    orig_size = os.path.getsize(image_path)
    print("=" * 55)
    print("  SD Image Shrinker")
    print("=" * 55)
    print(f"\n  Image : {image_path}")
    print(f"  Size  : {orig_size / (1024**3):.3f} GB ({orig_size} bytes)")
    print("\n  [!] This modifies the image file in-place.")
    confirm = input("  Proceed? [yes/N]: ")
    if confirm.strip().lower() != "yes":
        print("  Cancelled.")
        sys.exit(0)

    shrink_image(image_path)


if __name__ == "__main__":
    if "--read" in sys.argv:
        read_mode()
    else:
        main()