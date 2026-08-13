"""P27 driver: write arbitrary erasable memory over the uplink.

Comanche055/UPDATE_PROGRAM.agc, verb 72 ("scatter update").  The
ground sends a component count, then (ECADR, value) pairs, then a
V33 PROCEED to commit.

The security-relevant part is UPEND72's store loop (line 459):

    CAE  UPBUFF +1   # PICK UP NEXT ECADR OF REG TO BE UPDATED
    TS   EBANK       # SET EBANK          <-- straight from the radio
    MASK LOW8        # ISOLATE RELATIVE ADDRESS
    INDEX A
    LXCH 1400        # UPDATE THE REGISTER BY CONTENTS OF L

There is no allow-list and no range check on the destination.
"""

DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7"]

# FLAGWRD5 = STATE +5.  Bit 15 is DSKYFLAG, defined in
# ERASABLE_ASSIGNMENTS.agc:858 as "DISPLAYS SENT TO [DSKY] / NO DISPLAYS TO DSKY".
#
# KEYRUPT1 passes through KEYCOM, which sets this flag on every keypress:
#
#     KEYCOM  TS   RUPTREG4
#             CS   FLAGWRD5
#             MASK BIT15          <-- set DSKYFLAG
#             ADS  FLAGWRD5
#
# UPRUPT jumps straight to ACCEPTUP and skips KEYCOM, so an uplinked
# keystroke never sets it.  On a cold computer (erasable all zero) the flag
# is clear, uplinked commands execute normally, and nothing reaches the
# display -- which looks exactly like the uplink not working.
#
# In flight this would rarely matter: the crew used the DSKY constantly, so
# DSKYFLAG was effectively always set.  It matters here because a cold start
# is the honest baseline for a demo.
FLAGWRD5 = 0o0101
DSKYFLAG = 0o40000


def octal_keys(value, width=5):
    """Render a value as octal DSKY keystrokes."""
    s = format(value & 0o77777, "0{}o".format(width))
    return [DIGITS[int(c)] for c in s]


def verb(agc, n, settle=0.35):
    agc.uplink("VERB", settle)
    for d in format(n, "02d"):
        agc.uplink(d, settle)
    agc.uplink("ENTR", settle)


def noun(agc, n, settle=0.35):
    agc.uplink("NOUN", settle)
    for d in format(n, "02d"):
        agc.uplink(d, settle)
    agc.uplink("ENTR", settle)


def load(agc, value, settle=0.35):
    """Key a 5-digit octal value into a flashing load request."""
    for k in octal_keys(value):
        agc.uplink(k, settle)
    agc.uplink("ENTR", settle)


def v72_write(agc, pairs, settle=0.35, log=print):
    """Write (ecadr, value) pairs to erasable memory via P27 verb 72.

    II = 1 + 2*len(pairs), must be odd and in [3, 19].
    """
    ii = 1 + 2 * len(pairs)
    assert 3 <= ii <= 0o23 and ii % 2 == 1, f"bad component count {ii}"

    log(f"  uplink V72E                (start P27 scatter update)")
    verb(agc, 72, settle)

    log(f"  uplink {ii:05o}E              (component count II={ii})")
    load(agc, ii, settle)

    for ecadr, value in pairs:
        log(f"  uplink {ecadr:05o}E              (destination ECADR)")
        load(agc, ecadr, settle)
        log(f"  uplink {value:05o}E              (value)")
        load(agc, value, settle)

    log(f"  uplink V33E                (PROCEED -- commit the write)")
    verb(agc, 33, settle)


def enable_display(agc, settle=0.35, log=print):
    """Turn the crew's display on, from the ground.

    Sets DSKYFLAG by writing FLAGWRD5 through the same V72 primitive.  Safe
    to write wholesale only because this runs against cold erasable, where
    the other FLAGWRD5 bits are already zero; against a warm computer this
    would clobber them.
    """
    log("  uplink V72 write FLAGWRD5  (set DSKYFLAG -- enable the DSKY)")
    v72_write(agc, [(FLAGWRD5, DSKYFLAG)], settle, log=lambda s: None)
