import ctypes, ctypes.util
import struct, os
import fcntl
import time
import statistics

# ── Pure-Python I2C access to LTC2990/LTC2991 (merged from i2cllc.py) ────────
# Same read/write protocol as linearity_wib_measure.py: write control,
# clear stale data, trigger, poll STATUS, read, decode - with a median over
# N samples. Opens /dev/i2c-X directly via Linux ioctl, no dependency on
# wib_util.so for these two chips.
#
# Register references:
#   LTC2990 datasheet Rev.F  (Analog Devices)
#   LTC2991 datasheet 2991ff (Analog Devices / Linear Technology)

# Sample count for LTC2990/LTC2991 rail reads in get_sensors(); the median
# of this many conversions is used for each rail.
LTC_SAMPLES = 30

# ── Linux i2c-dev constants ───────────────────────────────────────────────
_I2C_RDWR = 0x0707       # ioctl request: combined read/write
_I2C_M_RD = 0x0001       # i2c_msg flag: this segment is a read

# ── ADC scale factors (from datasheets) ──────────────────────────────────
_LTC2990_LSB_SE   = 305.18e-6    # V / LSB  single-ended voltage
_LTC2990_LSB_DIFF =  19.42e-6    # V / LSB  differential voltage (current sense)

_LTC2991_LSB_SE   = 305.18e-6    # V / LSB  single-ended voltage
_LTC2991_LSB_DIFF =  19.075e-6   # V / LSB  differential voltage (current sense)


class _I2CMsg(ctypes.Structure):
    _fields_ = [
        ("addr",  ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("len",   ctypes.c_uint16),
        ("buf",   ctypes.POINTER(ctypes.c_uint8)),
    ]


class _I2CRdwrIoctlData(ctypes.Structure):
    _fields_ = [
        ("msgs",  ctypes.POINTER(_I2CMsg)),
        ("nmsgs", ctypes.c_uint32),
    ]


def _make_i2c_msg(addr, flags, buf):
    return _I2CMsg(
        addr & 0x7F,
        flags,
        len(buf),
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)),
    )


def _i2c_rdwr(bus, msgs):
    fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
    try:
        arr     = (_I2CMsg * len(msgs))(*msgs)
        ioctl_d = _I2CRdwrIoctlData(
            ctypes.cast(arr, ctypes.POINTER(_I2CMsg)), len(msgs)
        )
        fcntl.ioctl(fd, _I2C_RDWR, ioctl_d)
    finally:
        os.close(fd)


def _i2c_write(bus, slave, reg, value):
    """Write one byte to a register: START slave+W reg value STOP."""
    buf = (ctypes.c_uint8 * 2)(reg & 0xFF, value & 0xFF)
    _i2c_rdwr(bus, [_make_i2c_msg(slave, 0, buf)])


def _i2c_read(bus, slave, reg, nbytes=1):
    """
    Read nbytes from a register.
    Transaction: START slave+W reg REPEATED-START slave+R data... STOP
    Returns a list of nbytes integers.
    """
    wbuf = (ctypes.c_uint8 * 1)(reg & 0xFF)
    rbuf = (ctypes.c_uint8 * nbytes)()
    _i2c_rdwr(bus, [
        _make_i2c_msg(slave, 0,        wbuf),
        _make_i2c_msg(slave, _I2C_M_RD, rbuf),
    ])
    return [int(rbuf[i]) for i in range(nbytes)]


# LTC2990 STATUS register (0x00) ready-bit for each measurement
_LTC2990_READY = {
    (False, 1): 0x04,   # V1  single-ended
    (False, 2): 0x08,   # V2  single-ended
    (False, 3): 0x10,   # V3  single-ended
    (False, 4): 0x20,   # V4  single-ended
    (False, 5): 0x40,   # VCC
    (True,  1): 0x04,   # V1-V2 differential
    (True,  3): 0x10,   # V3-V4 differential
}


def _ltc2990_data_reg(channel):
    # ch1->0x06  ch2->0x08  ch3->0x0A  ch4->0x0C  ch5(VCC)->0x0E
    return 0x06 + (channel - 1) * 2


def _ltc2990_decode(raw16, diff, channel):
    raw15 = raw16 & 0x7FFF
    code  = (raw15 - 0x8000) if (raw15 & 0x4000) else raw15
    if diff:
        return code * _LTC2990_LSB_DIFF
    if channel == 5:                            # VCC has a 2.5 V offset
        return 2.5 + (raw16 & 0x3FFF) * _LTC2990_LSB_SE
    return code * _LTC2990_LSB_SE


def ltc2990_read_voltage(slave, diff=False, channel=1, bus=1,
                          n=3, timeout=0.25, poll_interval=0.001):
    """
    Read one LTC2990 voltage channel directly via /dev/i2c-{bus}.

    diff    : False -> single-ended (channel 1-4; channel 5 = VCC)
              True  -> differential (channel 1 = V1-V2, channel 3 = V3-V4)
    n       : number of samples; function returns the median
    """
    if diff:
        if channel not in (1, 3):
            raise ValueError(f"LTC2990 diff mode: channel must be 1 or 3, got {channel}")
        control = 0x5E
    else:
        if channel not in (1, 2, 3, 4, 5):
            raise ValueError(f"LTC2990 single-ended: channel must be 1-5, got {channel}")
        control = 0x5F

    data_reg   = _ltc2990_data_reg(channel)
    ready_mask = _LTC2990_READY[(diff, channel)]
    samples    = []

    for _ in range(n):
        # 1. Configure measurement mode
        _i2c_write(bus, slave, 0x01, control)

        # 2. Wait until any previous single-shot round has finished.
        #    A TRIGGER written during BUSY is silently ignored, which would
        #    make the next poll time out.
        deadline = time.monotonic() + timeout
        while _i2c_read(bus, slave, 0x00, 1)[0] & 0x01:      # bit0 = BUSY
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"LTC2990 stuck busy: bus={bus} slave=0x{slave:02X}"
                )
            time.sleep(poll_interval)

        # 3. Read and discard target register to clear the stale DATA_VALID bit
        _i2c_read(bus, slave, data_reg, 2)
        # 4. Trigger one new conversion (chip is idle now, trigger accepted)
        _i2c_write(bus, slave, 0x02, 0xFF)

        # 5. Poll STATUS register until the target channel is ready
        deadline = time.monotonic() + timeout
        status   = 0
        while time.monotonic() < deadline:
            status = _i2c_read(bus, slave, 0x00, 1)[0]
            if status & ready_mask:
                break
            time.sleep(poll_interval)
        else:
            ctrl_now = _i2c_read(bus, slave, 0x01, 1)[0]
            extra = ""
            if ctrl_now != control:
                extra = (
                    f" - CONTROL overwritten 0x{control:02X}->0x{ctrl_now:02X}: "
                    "ANOTHER PROCESS is accessing this chip "
                    "(stop wib_server / sensor monitors on the WIB)"
                )
            raise TimeoutError(
                f"LTC2990 timeout: bus={bus} slave=0x{slave:02X} "
                f"diff={diff} ch={channel} status=0x{status:02X}{extra}"
            )

        # 6. Read the 16-bit data word
        msb, lsb = _i2c_read(bus, slave, data_reg, 2)
        raw16 = (msb << 8) | lsb
        if not (raw16 & 0x8000):
            raise RuntimeError(
                f"LTC2990 DATA_VALID not set after ready bit: "
                f"bus={bus} slave=0x{slave:02X} ch={channel} raw=0x{raw16:04X}"
            )
        samples.append(_ltc2990_decode(raw16, diff, channel))

    return statistics.median(samples)


# LTC2991 STATUS_LOW (0x00) ready bit for each channel (1-indexed)
_LTC2991_READY = {
    1: 0x01, 2: 0x02, 3: 0x04, 4: 0x08,
    5: 0x10, 6: 0x20, 7: 0x40, 8: 0x80,
}


def _ltc2991_data_reg(channel):
    # ch1->0x0A  ch2->0x0C  ch3->0x0E  ch4->0x10
    # ch5->0x12  ch6->0x14  ch7->0x16  ch8->0x18
    return 0x0A + (channel - 1) * 2


def _ltc2991_decode(raw16, diff):
    raw15 = raw16 & 0x7FFF
    code  = (raw15 - 0x8000) if (raw15 & 0x4000) else raw15
    return code * (_LTC2991_LSB_DIFF if diff else _LTC2991_LSB_SE)


def ltc2991_read_voltage(bus, slave, diff=False, channel=1,
                          n=5, timeout=0.5, poll_interval=0.002):
    """
    Read one LTC2991 voltage channel directly via /dev/i2c-{bus}.

    diff    : False -> single-ended (channel 1-8)
              True  -> differential pair (channel must be 1, 3, 5, or 7)
    n       : number of samples; function returns the median
    """
    if channel < 1 or channel > 8:
        raise ValueError(f"LTC2991 channel must be 1-8, got {channel}")
    if diff and channel not in (1, 3, 5, 7):
        raise ValueError(
            f"LTC2991 diff mode: channel must be 1, 3, 5, or 7 (pair start), got {channel}"
        )

    # Control register values for mode registers 0x06 and 0x07
    ctrl = 0x11 if diff else 0x00

    # In differential mode the EVEN register of the pair holds the
    # differential result (V_odd - V_even); the ODD register holds the
    # single-ended voltage of the odd pin. The caller still addresses the
    # pair by its odd start channel (1/3/5/7).
    read_ch    = channel + 1 if diff else channel
    data_reg   = _ltc2991_data_reg(read_ch)
    ready_mask = _LTC2991_READY[read_ch]
    samples    = []

    # Enable ONLY the pair containing the target channel (Tint off).
    # Enable bits: bit4=V1V2  bit5=V3V4  bit6=V5V6  bit7=V7V8  bit3=Tint
    enable = 0x10 << ((channel - 1) // 2)

    for _ in range(n):
        # 1. Set measurement mode for all pairs
        _i2c_write(bus, slave, 0x06, ctrl)
        _i2c_write(bus, slave, 0x07, ctrl)
        # 2. Enable target pair only (triggers acquisition)
        _i2c_write(bus, slave, 0x01, enable)
        # 3. Flush stale DATA_VALID for this data register
        _i2c_read(bus, slave, data_reg, 2)
        # 4. Re-write enable to re-arm acquisition
        _i2c_write(bus, slave, 0x01, enable)

        # 5. Poll STATUS_LOW (0x00) until target channel ready. If the
        #    re-arm write above landed while the previous acquisition round
        #    was still in progress it may have been ignored - re-arm once
        #    more after a grace period so the call self-heals instead of
        #    timing out.
        deadline = time.monotonic() + timeout
        rearm_at = time.monotonic() + 0.05
        status   = 0
        while time.monotonic() < deadline:
            status = _i2c_read(bus, slave, 0x00, 1)[0]
            if status & ready_mask:
                break
            if time.monotonic() >= rearm_at:
                _i2c_write(bus, slave, 0x01, enable)
                rearm_at = float("inf")
            time.sleep(poll_interval)
        else:
            m06 = _i2c_read(bus, slave, 0x06, 1)[0]
            m07 = _i2c_read(bus, slave, 0x07, 1)[0]
            extra = ""
            if m06 != ctrl or m07 != ctrl:
                extra = (
                    f" - MODE regs overwritten (0x06=0x{m06:02X} 0x07=0x{m07:02X}, "
                    f"expected 0x{ctrl:02X}): ANOTHER PROCESS is accessing this "
                    "chip (stop wib_server / sensor monitors on the WIB)"
                )
            raise TimeoutError(
                f"LTC2991 timeout: bus={bus} slave=0x{slave:02X} "
                f"diff={diff} ch={channel} status=0x{status:02X}{extra}"
            )

        # 6. Read 16-bit data word
        msb, lsb = _i2c_read(bus, slave, data_reg, 2)
        raw16 = (msb << 8) | lsb
        if not (raw16 & 0x8000):
            raise RuntimeError(
                f"LTC2991 DATA_VALID not set after ready bit: "
                f"bus={bus} slave=0x{slave:02X} ch={channel} raw=0x{raw16:04X}"
            )
        samples.append(_ltc2991_decode(raw16, diff))

    return statistics.median(samples)


class LLC():
    def __init__(self):
        super().__init__()
        self.script_path = "./scripts/"
        self.wib_path = os.getcwd() + "/build/wib_util.so"
        self.wib = ctypes.CDLL(self.wib_path)

        # define C functions' argument types and return types
        self.wib.peek.argtypes = [ctypes.c_size_t]
        self.wib.peek.restype = ctypes.c_uint32

        self.wib.poke.argtypes = [ctypes.c_size_t, ctypes.c_uint32]
        self.wib.poke.restype = None

        self.wib.wib_peek.argtypes = [ctypes.c_size_t]
        self.wib.wib_peek.restype = ctypes.c_uint32

        self.wib.wib_poke.argtypes = [ctypes.c_size_t, ctypes.c_uint32]
        self.wib.wib_poke.restype = None

        self.wib.cdpeek.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
        self.wib.cdpeek.restype = ctypes.c_uint8

        self.wib.cdpoke.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
        self.wib.cdpoke.restype = None

        self.wib.bufread.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_size_t]
        self.wib.bufread.restype = None

        self.wib.i2cread.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
        self.wib.i2cread.restype = ctypes.c_uint8

        self.wib.i2cwrite.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
        self.wib.i2cwrite.restype = None

        self.wib.read_ltc2990.argtypes = [ctypes.c_uint8, ctypes.c_bool, ctypes.c_uint8]
        self.wib.read_ltc2990.restype = ctypes.c_double

        self.wib.read_ltc2991.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_bool, ctypes.c_uint8]
        self.wib.read_ltc2991.restype = ctypes.c_double

        self.wib.read_ad7414.argtypes = [ctypes.c_uint8]
        self.wib.read_ad7414.restype = ctypes.c_double

        self.wib.read_ina226_c.argtypes = [ctypes.c_uint8]
        self.wib.read_ina226_c.restype = ctypes.c_double

        self.wib.read_ina226_v.argtypes = [ctypes.c_uint8]
        self.wib.read_ina226_v.restype = ctypes.c_double

        self.wib.read_ltc2499.argtypes = [ctypes.c_uint8]
        self.wib.read_ltc2499.restype = ctypes.c_double

        self.wib.all_femb_bias_ctrl.argtypes = [ctypes.c_uint8]
        self.wib.all_femb_bias_ctrl.restype = ctypes.c_bool

        self.wib.femb_power_en_ctrl.argtypes = [ctypes.c_int, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
                                                ctypes.c_uint8, ctypes.c_uint8]
        self.wib.femb_power_en_ctrl.restype = ctypes.c_bool

        self.wib.femb_power_reg_ctrl.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_double]
        self.wib.femb_power_reg_ctrl.restype = ctypes.c_bool

        self.wib.femb_power_config.argtypes = [ctypes.c_uint8, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                               ctypes.c_double, ctypes.c_double, ctypes.c_double]
        self.wib.femb_power_config.restype = ctypes.c_bool

        self.wib.script_cmd.argtypes = [ctypes.POINTER(ctypes.c_char)]
        self.wib.script_cmd.restype = ctypes.c_bool

    #        self.wib.script.argtypes =  [ctypes.POINTER(ctypes.c_char), ctypes.c_bool  ]
    #        self.wib.script.restype = ctypes.c_bool

    def script_cmd(self, cmd):
        return self.wib.script_cmd(cmd)

    def script_rd(self, script, cmds=[]):
        fdir = self.script_path
        fn = fdir + script
        with open(fn, 'r') as f:
            cmdline = f.readline()
            while len(cmdline) > 0:
                if ("i2c" in cmdline) or ("delay" in cmdline) or ("mem" in cmdline):
                    cmds.append(cmdline)
                elif ("run" in cmdline):
                    x = cmdline[0:-1].split(" ")
                    if (len(x[1]) > 0) and (len(x) >= 2):
                        self.script_rd(script=x[1], cmds=cmds)
                    else:
                        print("Error - file(%s) has an invalid RUN command: %s" % (fn, cmdline))
                        exit()
                cmdline = f.readline()
            return cmds

    def script_exe(self, script):
        cmds = self.script_rd(script=script, cmds=[])
        for cmd in cmds:
            cmd = bytes(cmd, 'utf-8')
            self.script_cmd(cmd)

    def peek(self, regaddr):
        val = self.wib.peek(regaddr)
        return val

    def poke(self, regaddr, regval):
        self.wib.poke(regaddr, regval)
        return None

    def wib_peek(self, regaddr):
        val = self.wib.wib_peek(regaddr)
        return val

    def wib_poke(self, regaddr, regval):
        self.wib.wib_poke(regaddr, regval)
        return None

    #    def poke_chk(self, regaddr, regval):
    #        self.poke(regaddr, regval)
    #        val = self.peek(regaddr)
    #        if val == regval:
    #            return val
    #        else:
    #            print ("Error: WIB reg addr 0x%x readback value (0x%x) is different from write value (0x%x)"%(regaddr, regval, val))
    #            return None

    def cdpeek(self, femb_id, chip_addr, reg_page, reg_addr):
        val = self.wib.cdpeek(femb_id, chip_addr, reg_page, reg_addr)
        return val

    def cdpoke(self, femb_id, chip_addr, reg_page, reg_addr, data):
        self.wib.cdpoke(femb_id, chip_addr, reg_page, reg_addr, data)

    #    def cdpoke_chk(self, femb_id, chip_addr, reg_page, reg_addr, data):
    #        for i in range(10):
    #            self.wib.cdpoke(femb_id, chip_addr, reg_page, reg_addr, data)
    #            val = self.wib.cdpeek(femb_id, chip_addr, reg_page, reg_addr)
    #            if val == data:
    #                return val
    #            else:
    #                print ("Warning: FEMB%d_chipI2C0x%x_page0x%x_addr0x%x readback(0x%x) is different from write value (0x%x)"%(femb_id, chip_addr, reg_page, reg_addr, regval, val))
    #                print ("Try again...")
    #                if i > 5:
    #                    print ("Error: Failed to configurate FEMB, please check hardware connection...")
    #                    exit()

    def fastcmd(self, cmd):
        fast_dict = {'reset': 1, 'act': 2, 'sync': 4, 'edge': 8, 'idle': 16, 'edge_act': 32}
        self.wib.poke(0xA0030000, fast_dict[cmd])  # fast command

    #    def fastcmd_act(self, femb_id, act_cmd="idle"):
    #        if act_cmd == "idle":
    #            wrdata = 0
    #        elif act_cmd == "larasic_pls":
    #            wrdata = 0x01
    #        elif act_cmd == "save_timestamp":
    #            wrdata = 0x02
    #        elif act_cmd == "save_status":
    #            wrdata = 0x03
    #        elif act_cmd == "clr_saves":
    #            wrdata = 0x04
    #        elif act_cmd == "rst_adcs":
    #            wrdata = 0x05
    #        elif act_cmd == "rst_larasics":
    #            wrdata = 0x06
    #        elif act_cmd == "rst_larasic_spi":
    #            wrdata = 0x07
    #        elif act_cmd == "prm_larasics":
    #            wrdata = 0x08
    #        elif act_cmd == "relay_i2c_sda":
    #            wrdata = 0x09
    #        else:
    #            wrdata = 0
    #
    #        self.cdpoke_chk(femb_id, chip_addr=3, reg_page=0, reg_addr=0x20, wrdata=wrdata)
    #        self.cdpoke_chk(femb_id, chip_addr=2, reg_page=0, reg_addr=0x20, wrdata=wrdata)
    #        self.fastcmd(cmd='act')
    #        #return to "idle" in case other FEMB runs FC
    #        self.cdpoke_chk(femb_id, chip_addr=3, reg_page=0, reg_addr=0x20, wrdata=0)
    #        self.cdpoke_chk(femb_id, chip_addr=2, reg_page=0, reg_addr=0x20, wrdata=0)

    def spybuf(self, fembs=[0, 1, 2, 3]):
        buf0 = True if 0 in fembs or 1 in fembs else False
        buf1 = True if 2 in fembs or 3 in fembs else False

        DAQ_SPY_SIZE = 0x00100000
        buf = (ctypes.c_char * DAQ_SPY_SIZE)()
        # allocate memory in python
        buf0_bytes = bytearray(DAQ_SPY_SIZE)
        buf1_bytes = bytearray(DAQ_SPY_SIZE)

        if buf0:
            self.wib.bufread(buf, 0)  # read buf0
            byte_ptr0 = (ctypes.c_char * DAQ_SPY_SIZE).from_buffer(buf0_bytes)
            if not ctypes.memmove(byte_ptr0, buf, DAQ_SPY_SIZE):
                print('memmove failed')
                exit()

        if buf1:
            self.wib.bufread(buf, 1)  # read buf1
            byte_ptr1 = (ctypes.c_char * DAQ_SPY_SIZE).from_buffer(buf1_bytes)
            if not ctypes.memmove(byte_ptr1, buf, DAQ_SPY_SIZE):
                print('memmove failed')
                exit()
        return buf0_bytes, buf1_bytes

    def get_sensors(self):
        # Sense resistor values from bench calibration (src/llctest.pdf),
        # not the PCB nominal/placeholder values. See LINEARITY_CALIBRATION.md.
        r357 = 0.00481    # P0.9V,  LTC2990 0x4E CH1
        r350 = 0.002982   # P3.3V,  LTC2990 0x4C CH3
        r351 = 0.00185    # P1.2V,  LTC2990 0x4C CH1
        r413 = 0.002325   # P0.85V, LTC2991 0x48 CH1-2
        r416 = 0.001879   # P5V,    LTC2991 0x48 CH3-4
        r352 = 0.0013     # P2.5V,  LTC2991 0x48 CH5-6
        r353 = 0.000973   # P1.8V,  LTC2991 0x48 CH7-8
        power_meas = {}

        # LTC2990: diff result lives in the ODD (lower) register of the pair
        # (channel=1 -> V1-V2, channel=3 -> V3-V4). Bus voltage is read
        # single-ended on the EVEN (load-side) pin of the same pair.
        power_meas["P0.9V_V"] = ltc2990_read_voltage(0x4E, diff=False, channel=2, bus=1, n=LTC_SAMPLES)
        power_meas["P0.9V_I"] = ltc2990_read_voltage(0x4E, diff=True, channel=1, bus=1, n=LTC_SAMPLES) / r357
        power_meas["VCCPSPLL_Z_1P2V_V"] = ltc2990_read_voltage(0x4E, diff=False, channel=3, bus=1, n=LTC_SAMPLES)
        power_meas["PS_DDR4_vtt_V"] = ltc2990_read_voltage(0x4E, diff=False, channel=4, bus=1, n=LTC_SAMPLES)

        power_meas["P1.2V_V"] = ltc2990_read_voltage(0x4C, diff=False, channel=2, bus=1, n=LTC_SAMPLES)
        power_meas["P1.2V_I"] = ltc2990_read_voltage(0x4C, diff=True, channel=1, bus=1, n=LTC_SAMPLES) / r351
        power_meas["P3.3V_V"] = ltc2990_read_voltage(0x4C, diff=False, channel=4, bus=1, n=LTC_SAMPLES)
        power_meas["P3.3V_I"] = ltc2990_read_voltage(0x4C, diff=True, channel=3, bus=1, n=LTC_SAMPLES) / r350

        # LTC2991: diff result is the OPPOSITE convention - it lives in the
        # EVEN register (V_odd - V_even); the pair is still addressed by its
        # odd start channel (1/3/5/7). Bus voltage is read single-ended on
        # the even (load-side) pin. WIB LTC2991 0x48 is on i2c bus 1
        # (bus 0 is not a valid i2c-dev bus).
        bus = 1
        power_meas["P0.85V_V"] = ltc2991_read_voltage(bus, 0x48, diff=False, channel=2, n=LTC_SAMPLES)
        power_meas["P0.85V_I"] = ltc2991_read_voltage(bus, 0x48, diff=True, channel=1, n=LTC_SAMPLES) / r413
        power_meas["P5V_V"] = ltc2991_read_voltage(bus, 0x48, diff=False, channel=4, n=LTC_SAMPLES)
        power_meas["P5V_I"] = ltc2991_read_voltage(bus, 0x48, diff=True, channel=3, n=LTC_SAMPLES) / r416
        power_meas["P2.5V_V"] = ltc2991_read_voltage(bus, 0x48, diff=False, channel=6, n=LTC_SAMPLES)
        power_meas["P2.5V_I"] = ltc2991_read_voltage(bus, 0x48, diff=True, channel=5, n=LTC_SAMPLES) / r352
        power_meas["P1.8V_V"] = ltc2991_read_voltage(bus, 0x48, diff=False, channel=8, n=LTC_SAMPLES)
        power_meas["P1.8V_I"] = ltc2991_read_voltage(bus, 0x48, diff=True, channel=7, n=LTC_SAMPLES) / r353

        vcco_psddr_504_c = self.wib.read_ina226_c(0x46)
        vcco_psddr_504_v = self.wib.read_ina226_v(0x46)
        power_meas["VCCO_PSDDR_504_V"] = vcco_psddr_504_v
        power_meas["VCCO_PSDDR_504_I"] = vcco_psddr_504_c

        ad7414_4d = self.wib.read_ad7414(0x4d)
        power_meas["Temp_U42_0x4d"] = ad7414_4d

        if False:
            ad7414_49 = self.wib.read_ad7414(0x49)
            ad7414_4a = self.wib.read_ad7414(0x4a)
            power_meas["Temp_U47_0x49"] = ad7414_49
            power_meas["Temp_U64_0x4a"] = ad7414_4a

        ltc2499_15s = []
        for i in range(0, 7, 1):
            t = self.wib.read_ltc2499(i)
            ltc2499_15s.append(t)
        power_meas["LTC4644_BRD0_temp"] = ltc2499_15s[0]
        power_meas["LTC4644_BRD1_temp"] = ltc2499_15s[1]
        power_meas["LTC4644_BRD2_temp"] = ltc2499_15s[2]
        power_meas["LTC4644_BRD3_temp"] = ltc2499_15s[3]
        power_meas["LTC4644_WIB1_temp"] = ltc2499_15s[4]
        power_meas["LTC4644_WIB2_temp"] = ltc2499_15s[5]
        power_meas["LTC4644_WIB3_temp"] = ltc2499_15s[6]

        # FEMB power monitoring on bus 2. Same diff-register convention as
        # the WIB LTC2991 0x48 above: diff current on the odd pair-start
        # channel, single-ended bus voltage on the even (load-side) channel.
        bus = 2
        R_DCDC_STD = 0.1   # DC2DC0/1/3 shunt
        R_DCDC2    = 0.01  # DC2DC2 shunt (different value)
        R_BIAS     = 0.1   # FEMB bias shunt

        # LTC2991 0x4E: FEMB0-3 bias, one differential pair per FEMB
        # (ch1-2=FEMB0, ch3-4=FEMB1, ch5-6=FEMB2, ch7-8=FEMB3).
        _bias_ch = {"FEMB0": 1, "FEMB1": 3, "FEMB2": 5, "FEMB3": 7}
        # Dedicated per-FEMB LTC2991 for DC-DC monitoring.
        _dcdc_slave = {"FEMB0": 0x48, "FEMB1": 0x49, "FEMB2": 0x4A, "FEMB3": 0x4B}

        for femb in ("FEMB0", "FEMB1", "FEMB2", "FEMB3"):
            bias_ch = _bias_ch[femb]
            power_meas[f"{femb}_BIAS_V"] = ltc2991_read_voltage(bus, 0x4E, diff=False, channel=bias_ch + 1, n=LTC_SAMPLES)
            power_meas[f"{femb}_BIAS_I"] = ltc2991_read_voltage(bus, 0x4E, diff=True, channel=bias_ch, n=LTC_SAMPLES) / R_BIAS

            slave = _dcdc_slave[femb]
            power_meas[f"{femb}_DC2DC0_V"] = ltc2991_read_voltage(bus, slave, diff=False, channel=2, n=LTC_SAMPLES)
            power_meas[f"{femb}_DC2DC0_I"] = ltc2991_read_voltage(bus, slave, diff=True, channel=1, n=LTC_SAMPLES) / R_DCDC_STD
            power_meas[f"{femb}_DC2DC1_V"] = ltc2991_read_voltage(bus, slave, diff=False, channel=4, n=LTC_SAMPLES)
            power_meas[f"{femb}_DC2DC1_I"] = ltc2991_read_voltage(bus, slave, diff=True, channel=3, n=LTC_SAMPLES) / R_DCDC_STD
            power_meas[f"{femb}_DC2DC2_V"] = ltc2991_read_voltage(bus, slave, diff=False, channel=6, n=LTC_SAMPLES)
            power_meas[f"{femb}_DC2DC2_I"] = ltc2991_read_voltage(bus, slave, diff=True, channel=5, n=LTC_SAMPLES) / R_DCDC2
            power_meas[f"{femb}_DC2DC3_V"] = ltc2991_read_voltage(bus, slave, diff=False, channel=8, n=LTC_SAMPLES)
            power_meas[f"{femb}_DC2DC3_I"] = ltc2991_read_voltage(bus, slave, diff=True, channel=7, n=LTC_SAMPLES) / R_DCDC_STD

        #        for key in power_meas:
        #            print (key, ":", power_meas[key])
        return power_meas

    def femb_power_config(self, femb_id=0, vfe=3.0, vcd=3.0, vadc=3.5):
        self.wib.femb_power_config(femb_id, vfe, vcd, vadc, 0, 0, 0)

    def all_femb_bias_ctrl(self, enable=0):
        self.wib.all_femb_bias_ctrl(enable)

    def femb_power_en_ctrl(self, femb_id=0, vfe_en=1, vcd_en=1, vadc_en=1, bias_en=1):
        self.wib.femb_power_en_ctrl(femb_id, vfe_en, vcd_en, vadc_en, 0, bias_en)

#    def femb_power_set(self, femb_id=0, on=1, vfe=3.0, vcd=3.0, vadc=3.5, allon=1):
#        self.femb_power_config(femb_id, vfe, vcd, vadc)
#        self.all_femb_bias_ctrl(enable=allon)
#        self.femb_power_en_ctrl(femb_id, vfe_en=on, vcd_en=on, vadc_en=on, bias_en=on)
