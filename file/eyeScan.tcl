# Get output directory from environment variable (set by Python script)
set output_dir $::env(EYE_SCAN_OUTPUT_DIR)
puts "Eye scan output directory: $output_dir"

open_hw_manager
connect_hw_server
open_hw
open_hw_target
set device [lindex [get_hw_devices] 0]
refresh_hw_device $device




refresh_hw_device [lindex [get_hw_devices] 0]
# Set Up Link on first GT
set tx0 [lindex [get_hw_sio_txs] 0]
set rx0 [lindex [get_hw_sio_rxs] 0]
set link0 [create_hw_sio_link $tx0 $rx0]
set_property DESCRIPTION {Link 0} [get_hw_sio_links $link0]
# Set link to use None, and write to hardware
set_property LOOPBACK "None" $link0
commit_hw_sio $link0
# Create, run, display and save scan
set scan0 [create_hw_sio_scan -description {Scan 0} 2d_full_eye [get_hw_sio_rxs -of $link0]]
run_hw_sio_scan [get_hw_sio_scans $scan0]
after 10000
write_hw_sio_scan -force "$output_dir/scan00_X0Y4.csv" [get_hw_sio_scans {SCAN_0}]

refresh_hw_device [lindex [get_hw_devices] 1]
# Set Up Link on first GT
set tx1 [lindex [get_hw_sio_txs] 1]
set rx1 [lindex [get_hw_sio_rxs] 1]
set link1 [create_hw_sio_link $tx1 $rx1]
set_property DESCRIPTION {Link 1} [get_hw_sio_links $link1]
# Set link to use PCS Loopback, and write to hardware
set_property LOOPBACK "None" $link1
commit_hw_sio $link1
# Create, run, display and save scan
set scan1 [create_hw_sio_scan -description {Scan 1} 2d_full_eye [get_hw_sio_rxs -of $link1]]
run_hw_sio_scan [get_hw_sio_scans $scan1]
after 10000
write_hw_sio_scan -force "$output_dir/scan01_X0Y5.csv" [get_hw_sio_scans {SCAN_1}]

# ============================================================
# ZYNQ U+ DEVICE BRING-UP INFORMATION
# ============================================================
puts ""
puts "ZYNQ_INFO_START"

# ---- Part A: PL JTAG device properties (always available via JTAG) ----
# Each property is in its own catch so a failure on one does not block the rest.
set rc_a [catch {
    set zynq_dev [lindex [get_hw_devices] 0]
    refresh_hw_device $zynq_dev

    # Part name — always works
    set zynq_part [get_property PART $zynq_dev]
    puts "ZYNQ_PART: $zynq_part"

    # IDCODE — correct property for UltraScale+ is IDCODE (not REGISTER.IDCODE)
    catch {
        set zynq_idcode [get_property IDCODE $zynq_dev]
        puts "ZYNQ_IDCODE: $zynq_idcode"
    }

    # Config Done — property name varies by family; try the two common names
    catch {
        set _done_found 0
        foreach _dp {REGISTER.CONFIG.DONE CONTROL.DONE STATUS.DONE} {
            if {![catch {set zynq_done [get_property $_dp $zynq_dev]}]} {
                puts "ZYNQ_CONFIG_DONE: $zynq_done"
                set _done_found 1
                break
            }
        }
    }

    # Device DNA — 96-bit unique identifier for board traceability
    catch {
        set zynq_dna [get_property REGISTER.DNA_PORT $zynq_dev]
        puts "ZYNQ_DNA: $zynq_dna"
    }

    # Enumerate all devices in JTAG chain (PS ARM DAP + PL TAP)
    set chain_idx 0
    foreach dev [get_hw_devices] {
        set dev_name [get_property NAME $dev]
        set dev_part [get_property PART $dev]
        puts "ZYNQ_JTAG_DEV_${chain_idx}: ${dev_name} | ${dev_part}"
        incr chain_idx
    }
    puts "ZYNQ_JTAG_DEV_COUNT: $chain_idx"
} err_a]
if {$rc_a != 0} {
    puts "ZYNQ_PART_A_ERROR: $err_a"
}

# ---- Part C: PS register reads via hw_axis ----
# Requires JTAG-to-AXI Master IP in PL bitstream, or ARM DAP hw_axis object.
# Falls back gracefully if not available in IBERT-only bitstream.
set rc_c [catch {
    set axis_list [get_hw_axis]
    if {[llength $axis_list] > 0} {
        set axim [lindex $axis_list 0]
        puts "ZYNQ_PS_AXIS_FOUND: [get_property NAME $axim]"

        # CRL_APB BOOT_MODE_USER (0xFF5E0200) — active boot mode
        catch {
            create_hw_axi_txn boot_rd $axim -type READ -address 0xFF5E0200 -len 1 -size 32
            run_hw_axi_txn [get_hw_axi_txns boot_rd]
            puts "ZYNQ_PS_BOOT_MODE: [get_property DATA [get_hw_axi_txns boot_rd]]"
            delete_hw_axi_txn [get_hw_axi_txns boot_rd]
        }

        # CRL_APB BOOT_MODE_POR (0xFF5E0204) — boot mode sampled at power-on reset
        catch {
            create_hw_axi_txn por_rd $axim -type READ -address 0xFF5E0204 -len 1 -size 32
            run_hw_axi_txn [get_hw_axi_txns por_rd]
            puts "ZYNQ_PS_BOOT_MODE_POR: [get_property DATA [get_hw_axi_txns por_rd]]"
            delete_hw_axi_txn [get_hw_axi_txns por_rd]
        }

        # CSU IDCODE (0xFFCA0040) — PS silicon IDCODE
        catch {
            create_hw_axi_txn csuid_rd $axim -type READ -address 0xFFCA0040 -len 1 -size 32
            run_hw_axi_txn [get_hw_axi_txns csuid_rd]
            puts "ZYNQ_PS_CSU_IDCODE: [get_property DATA [get_hw_axi_txns csuid_rd]]"
            delete_hw_axi_txn [get_hw_axi_txns csuid_rd]
        }

        # CSU VERSION (0xFFCA0044) — silicon revision; bits[27:24] = PS_VERSION
        catch {
            create_hw_axi_txn ver_rd $axim -type READ -address 0xFFCA0044 -len 1 -size 32
            run_hw_axi_txn [get_hw_axi_txns ver_rd]
            puts "ZYNQ_PS_CSU_VERSION: [get_property DATA [get_hw_axi_txns ver_rd]]"
            delete_hw_axi_txn [get_hw_axi_txns ver_rd]
        }

        # CSU STATUS (0xFFCA0010) — boot/init status flags
        catch {
            create_hw_axi_txn csu_st $axim -type READ -address 0xFFCA0010 -len 1 -size 32
            run_hw_axi_txn [get_hw_axi_txns csu_st]
            puts "ZYNQ_PS_CSU_STATUS: [get_property DATA [get_hw_axi_txns csu_st]]"
            delete_hw_axi_txn [get_hw_axi_txns csu_st]
        }
    } else {
        puts "ZYNQ_PS_ACCESS: no hw_axis available (IBERT bitstream has no JTAG-to-AXI Master)"
    }
} err_c]
if {$rc_c != 0} {
    puts "ZYNQ_PS_ERROR: $err_c"
}

# ---- Archive device info to file ----
catch {
    set info_fh [open "$output_dir/zynq_device_info.txt" w]
    puts $info_fh "ZYNQ U+ Device Information"
    puts $info_fh "Timestamp: [clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}]"
    puts $info_fh "--------------------------------------------"
    if {[info exists zynq_part]}   { puts $info_fh "Part:         $zynq_part" }
    if {[info exists zynq_idcode]} { puts $info_fh "IDCODE:       $zynq_idcode" }
    if {[info exists zynq_done]}   { puts $info_fh "Config Done:  $zynq_done" }
    if {[info exists zynq_dna]}    { puts $info_fh "DNA:          $zynq_dna" }
    close $info_fh
}

puts "ZYNQ_INFO_END"