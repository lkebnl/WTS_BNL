#!/usr/bin/env python3
# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Test00_copy_image.py
────────────────────
Search for a ~32 GB SD card in Ubuntu and copy it to a local image file.
Usage:
    python Test00_copy_image.py
"""

# ──────────────────────────────────────────────────────────────
# Parameters  (edit here)
# ──────────────────────────────────────────────────────────────
OUTPUT_DIR       = "/home/dune/Documents"   # directory to save the image
IMAGE_NAME       = "local_wib_image"        # output filename (no extension)
TARGET_SIZE_GB   = 32                        # expected SD card size in GB
SIZE_TOLERANCE_GB = 4                        # ± tolerance for size detection
BLOCK_SIZE       = "4M"                      # dd block size
# ──────────────────────────────────────────────────────────────

import subprocess
import os
import sys
import json
import csv
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

WIB_INFO_PATH = os.path.join(os.path.dirname(__file__), '..', 'file', 'wib_info.csv')


def _read_wib_info(key):
    try:
        with open(WIB_INFO_PATH, mode='r', newline='', encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) == 2 and row[0].strip() == key:
                    return row[1].strip()
    except Exception:
        pass
    return None


def get_sudo_password():
    pwd = _read_wib_info('SUDO_PASSWORD')
    if not pwd:
        raise RuntimeError("SUDO_PASSWORD not found in file/wib_info.csv")
    return pwd


def run_sudo(cmd, check=True):
    pwd = get_sudo_password()
    full_cmd = f"echo '{pwd}' | sudo -S {cmd}"
    return subprocess.run(full_cmd, shell=True, capture_output=True, text=True, check=check)


def get_block_devices():
    result = subprocess.run(
        "lsblk -J -b -o NAME,SIZE,TYPE,MOUNTPOINT,HOTPLUG",
        shell=True, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def find_sd_card():
    """Auto-detect ~32 GB SD card, auto-unmount mounted partitions."""
    data = get_block_devices()
    candidates = []

    for dev in data.get("blockdevices", []):
        name     = dev["name"]
        size_bytes = int(dev.get("size") or 0)
        size_gb  = size_bytes / (1024 ** 3)
        dev_type = dev.get("type", "")

        if dev_type != "disk":
            continue
        if abs(size_gb - TARGET_SIZE_GB) > SIZE_TOLERANCE_GB:
            continue
        if not (name.startswith("mmcblk") or name.startswith("sd")):
            continue

        # Auto-unmount mounted partitions
        for part in dev.get("children", []):
            if part.get("mountpoint"):
                print(f"  [Auto-unmount] {part['mountpoint']} ...")
                run_sudo(f"umount {part['mountpoint']}", check=False)

        # Confirm unmounted
        fresh = json.loads(subprocess.run(
            "lsblk -J -b -o NAME,MOUNTPOINT",
            shell=True, capture_output=True, text=True
        ).stdout)
        still_mounted = any(
            p.get("mountpoint")
            for d in fresh.get("blockdevices", []) if d["name"] == name
            for p in d.get("children", [])
        )
        if still_mounted:
            print(f"  [Skip] /dev/{name} — could not unmount, handle manually")
            continue

        candidates.append({
            "name":    name,
            "device":  f"/dev/{name}",
            "size_gb": round(size_gb, 1),
            "size_bytes": size_bytes,
        })

    return candidates


def copy_to_image(device, size_bytes, image_path):
    """Copy SD card to image file using dd, with live progress display."""
    size_mb = size_bytes / (1024 * 1024)
    print(f"\n  Source : {device}")
    print(f"  Output : {image_path}")
    print(f"  Size   : {size_mb:.0f} MB  ({size_bytes} bytes)")
    print("  (This may take several minutes...)\n")

    stop_flag = threading.Event()
    start_time = time.time()

    def show_progress():
        spinner = ['|', '/', '-', '\\']
        spin_idx = 0
        while not stop_flag.is_set():
            elapsed = time.time() - start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            # Estimate read speed ~80 MB/s for mmcblk, ~50 MB/s for USB reader
            est_speed = 60
            est_pct = min(100, (elapsed * est_speed / size_mb) * 100)
            bar_fill = int(est_pct // 5)
            bar = '=' * bar_fill + ' ' * (20 - bar_fill)
            print(f"\r  {spinner[spin_idx]} Elapsed: {mins:02d}:{secs:02d}  "
                  f"[{bar}] ~{est_pct:.0f}%   ", end='', flush=True)
            spin_idx = (spin_idx + 1) % 4
            time.sleep(0.5)

    progress_thread = threading.Thread(target=show_progress)
    progress_thread.start()

    pwd = get_sudo_password()
    cmd = (f"echo '{pwd}' | sudo -S "
           f"dd if={device} of={image_path} bs={BLOCK_SIZE} conv=sync,noerror status=progress")
    try:
        result = subprocess.run(cmd, shell=True, text=True, stderr=subprocess.PIPE)
    finally:
        stop_flag.set()
        progress_thread.join()

    total_time = time.time() - start_time
    mins = int(total_time // 60)
    secs = int(total_time % 60)
    print()  # newline after progress bar

    if result.returncode != 0:
        print(f"\n  ✗ Copy FAILED (dd exit code: {result.returncode})")
        if result.stderr.strip():
            print(f"    {result.stderr.strip()}")
        raise RuntimeError(f"dd failed with code {result.returncode}")

    # Sync to flush buffers
    run_sudo("sync")

    actual_size = os.path.getsize(image_path)
    speed = (actual_size / (1024 * 1024)) / total_time if total_time > 0 else 0

    print(f"\n  ✓ Image copy completed!")
    print(f"  Time          : {mins:02d}:{secs:02d}")
    print(f"  Average speed : {speed:.1f} MB/s")
    print(f"  Image size    : {actual_size / (1024**3):.2f} GB  ({actual_size} bytes)")
    print(f"  Saved to      : {image_path}")


def main():
    print("=" * 60)
    print("  Test00: SD Card → Local Image")
    print("=" * 60)

    # Resolve output path
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"{IMAGE_NAME}_{timestamp}.img"
    image_path = os.path.join(OUTPUT_DIR, image_filename)

    print(f"\n  Output image : {image_path}")
    print(f"\nScanning for ~{TARGET_SIZE_GB} GB SD card...")
    candidates = find_sd_card()

    if not candidates:
        print(f"\n[Error] No ~{TARGET_SIZE_GB} GB SD card found.")
        print("  Check that the card is inserted and recognized by the OS.")
        sys.exit(1)

    if len(candidates) > 1:
        print("\nMultiple candidate devices found:")
        for i, c in enumerate(candidates):
            print(f"  [{i}] {c['device']}  {c['size_gb']} GB")
        choice = int(input("Select device [0/1/...]: "))
        selected = candidates[choice]
    else:
        selected = candidates[0]

    print(f"\n  Selected device : {selected['device']}  ({selected['size_gb']} GB)")

    confirm = input(
        f"\n  Read {selected['device']} → {image_filename} ? [yes/N]: "
    ).strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        sys.exit(0)

    copy_to_image(selected["device"], selected["size_bytes"], image_path)

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
