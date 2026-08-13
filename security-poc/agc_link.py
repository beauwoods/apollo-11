"""
agc_link -- minimal peripheral client for the Virtual AGC (yaAGC) emulator.

Speaks yaAGC's 4-byte I/O-channel socket protocol, which is how real
peripherals (DSKY, telemetry, uplink) attach to the emulated computer.

Two channels matter here:

    015   DSKY keyboard   -> raises KEYRUPT   (an astronaut pressing a key)
    0173  uplink          -> writes INLINK, raises UPRUPT
                             (a radio transmission from the ground)

Channel 0173 is yaAGC's model of the S-band up-data link.  See
yaAGC/SocketAPI.c:243-249 -- the value lands in erasable 045 (INLINK)
and sets InterruptRequests[7], exactly as the real hardware did.

Packet format, from yaAGC/agc_utilities.c FormIoPacket():

    Packet[0] = Channel >> 3                                  (bits 7-6 = 00)
    Packet[1] = 0x40 | ((Channel << 3) & 0x38) | ((Value >> 12) & 0x07)
    Packet[2] = 0x80 | ((Value >> 6) & 0x3F)
    Packet[3] = 0xc0 | (Value & 0x3F)
"""

import socket
import time

CH_DSKY_KEY = 0o15
CH_DSKY_OUT = 0o10
CH_UPLINK = 0o173

# DSKY keycodes, verified against yaDSKY2/yaDSKY2.cpp button handlers.
KEY = {
    "0": 16, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "VERB": 0o21,     # 17
    "NOUN": 0o37,     # 31
    "ENTR": 0o34,     # 28
    "RSET": 0o22,     # 18  == ELRCODE, the uplink "ERROR RESET"
    "KEYREL": 0o31,   # 25
    "CLR": 0o36,      # 30
    "PLUS": 0o32,     # 26
    "MINUS": 0o33,    # 27
}

# 5-bit relay codes -> glyph.  Comanche055/PINBALL_GAME_BUTTONS_AND_LIGHTS.agc:378
RELAY_GLYPH = {
    0o00: " ", 0o25: "0", 0o03: "1", 0o31: "2", 0o33: "3",
    0o17: "4", 0o36: "5", 0o34: "6", 0o23: "7", 0o35: "8", 0o37: "9",
}


def encode_uplink_word(char_code):
    """Encode a 5-bit keycode into the AGC's triple-redundancy uplink word.

    UPRUPT accepts a 15-bit word laid out as [char][~char][char], 5 bits
    each, and rejects anything else (Comanche055/KEYRUPT_UPRUPT.agc:75-90).

    This is an error-detecting code for a noisy radio link.  It is not a
    MAC: there is no key, and the layout is public.  Anyone who can
    transmit can produce valid words -- which is the whole finding.
    """
    c = char_code & 0o37
    return (c << 10) | ((~c & 0o37) << 5) | c


def decode_dsky(word):
    """Decode a channel-010 relay word into (relay_addr, sign_bit, digitA, digitB).

    Layout from the DSPTAB table, PINBALL_GAME_BUTTONS_AND_LIGHTS.agc:362:
        bits 15-12 relay address, bit 11 sign, bits 10-6 digit A, bits 5-1 digit B
    """
    relay = (word >> 11) & 0o17
    sign = (word >> 10) & 1
    a = (word >> 5) & 0o37
    b = word & 0o37
    return relay, sign, a, b


class AGC:
    def __init__(self, host="127.0.0.1", port=19697):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.setblocking(False)
        self.buf = b""
        # DSKY state: 11 relay words worth of digits, plus sign flags.
        self.digits = {}          # digit position index -> glyph
        self.signs = {}           # relay addr -> bool
        self.channels = {}        # last seen value per channel

    # -- wire format ----------------------------------------------------

    @staticmethod
    def _pack(channel, value):
        return bytes([
            channel >> 3,
            0x40 | ((channel << 3) & 0x38) | ((value >> 12) & 0x07),
            0x80 | ((value >> 6) & 0x3F),
            0xC0 | (value & 0x3F),
        ])

    @staticmethod
    def _unpack(p):
        if (p[0] & 0xC0) != 0x00 or (p[1] & 0xC0) != 0x40:
            return None
        if (p[2] & 0xC0) != 0x80 or (p[3] & 0xC0) != 0xC0:
            return None
        channel = (p[0] << 3) | ((p[1] & 0x38) >> 3)
        value = ((p[1] & 0x07) << 12) | ((p[2] & 0x3F) << 6) | (p[3] & 0x3F)
        return channel, value

    def send(self, channel, value):
        self.sock.sendall(self._pack(channel, value))

    def pump(self, seconds=0.25):
        """Read and decode whatever the AGC has sent us."""
        end = time.time() + seconds
        while time.time() < end:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.buf += data
            except BlockingIOError:
                time.sleep(0.01)
                continue
            while len(self.buf) >= 4:
                # Resynchronise on a valid 4-byte frame.
                got = self._unpack(self.buf[:4])
                if got is None:
                    self.buf = self.buf[1:]
                    continue
                self.buf = self.buf[4:]
                channel, value = got
                self.channels[channel] = value
                if channel == CH_DSKY_OUT:
                    self._apply_dsky(value)

    def _apply_dsky(self, word):
        relay, sign, a, b = decode_dsky(word)
        if relay == 0 or relay > 11:
            return
        self.signs[relay] = bool(sign)
        # Each relay word carries two digit positions; map per DSPTAB table.
        pos = {
            11: (25, 24), 10: (23, 22), 9: (21, 20), 8: (None, 16),
            7: (15, 14), 6: (13, 12), 5: (11, 10), 4: (7, 6),
            3: (5, 4), 2: (3, 2), 1: (1, 0),
        }.get(relay)
        if not pos:
            return
        hi, lo = pos
        if hi is not None:
            self.digits[hi] = RELAY_GLYPH.get(a, "?")
        self.digits[lo] = RELAY_GLYPH.get(b, "?")

    # -- input paths ----------------------------------------------------

    def keypress(self, name, settle=0.35):
        """Press a key on the physical DSKY (channel 015 -> KEYRUPT)."""
        self.send(CH_DSKY_KEY, KEY[name])
        self.pump(settle)
        self.send(CH_DSKY_KEY, 0)
        self.pump(0.05)

    def uplink(self, name_or_code, settle=0.35):
        """Transmit one character over the radio uplink (-> INLINK, UPRUPT).

        This is the attacker primitive.  No credential, no key, no
        challenge -- just a correctly formatted word.
        """
        code = KEY[name_or_code] if isinstance(name_or_code, str) else name_or_code
        self.send(CH_UPLINK, encode_uplink_word(code))
        self.pump(settle)

    def uplink_raw(self, word, settle=0.35):
        """Transmit an arbitrary 15-bit word, valid or not (for DoS tests)."""
        self.send(CH_UPLINK, word & 0o77777)
        self.pump(settle)

    def uplink_str(self, s, settle=0.35):
        """Uplink a keystroke sequence, e.g. 'VERB 3 5 ENTR'."""
        for tok in s.split():
            self.uplink(tok, settle)

    # -- observation ----------------------------------------------------

    def g(self, i):
        return self.digits.get(i, " ")

    def render(self):
        """Text rendering of the DSKY display."""
        def f(*idx):
            return "".join(self.g(i) for i in idx)

        def sign(plus_relay, minus_relay):
            if self.signs.get(plus_relay):
                return "+"
            if self.signs.get(minus_relay):
                return "-"
            return " "

        return "\n".join([
            "    +----------------------+",
            "    |  PROG           {:2s}   |".format(f(25, 24)),
            "    |  VERB {:2s}   NOUN {:2s}   |".format(f(23, 22), f(21, 20)),
            "    +----------------------+",
            "    |  R1      {}{:5s}      |".format(sign(6, 5), f(16, 15, 14, 13, 12)),
            "    |  R2      {}{:5s}      |".format(sign(4, 3), f(11, 10, 7, 6, 5)),
            "    |  R3      {}{:5s}      |".format(sign(2, 1), f(4, 3, 2, 1, 0)),
            "    +----------------------+",
        ])
