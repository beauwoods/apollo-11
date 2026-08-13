# Apollo Guidance Computer — uplink security proof-of-concept

Working demonstrations of three security findings in the Apollo 11 Command
Module flight software (Comanche055), executed against the
[Virtual AGC](https://github.com/virtualagc/virtualagc) emulator.

This is historical security research. The Apollo Guidance Computer has not
flown since 1972, the source is public domain, and nothing here applies to
any system in operation. The point is what 1969 flight software assumed
about its command link, and what that assumption looks like under a modern
threat model.

## Background

The AGC had exactly two inputs that originated outside the spacecraft, per
the interrupt vector table in `Comanche055/INTERRUPT_LEAD_INS.agc`:
`UPRUPT` (the S-band up-data link) and `VHFREAD` (VHF ranging). Everything
else is timers, the crew's keyboard, or output.

`UPRUPT` validates an incoming word with a single check — a triple
redundancy code requiring the 15-bit word to be `[char][~char][char]`, five
bits each (`KEYRUPT_UPRUPT.agc:75-90`). That is an error-detecting code for
a noisy radio link. It is not a MAC: there is no key, and the layout is
published. A word that passes falls through to `ACCEPTUP` — the same label
the physical keyboard handler reaches, sharing the same register, which the
source notes explicitly:

```
ACCEPTUP    CAF   CHRPRIO      # (NOTE: RUPTREG4 = KEYTEMP1)
```

The emulator models this faithfully. `yaAGC/SocketAPI.c:243-249` accepts a
value on synthetic channel `0173`, writes it to `INLINK` (erasable 045), and
raises interrupt 7 — exactly as the hardware did.

## Setup

```sh
./setup.sh          # clone + build yaYUL and yaAGC, assemble the rope
./run_agc.sh &      # start the emulated CMC on port 19697
python3 t1_inject.py
```

`setup.sh` writes everything into `./build/`, which is gitignored.
`run_all.sh` runs every demo, each against a freshly booted computer.

Two things matter for reproducibility, both learned the hard way:

* **`--no-resume` is not optional.** By default yaAGC snapshots erasable
  memory to a `core` file every 10 seconds and restores from it on the next
  start. Without `--no-resume`, each run silently inherits the previous run's
  memory — the first version of these demos showed a "before" state still
  holding values written minutes earlier, which would have made every
  before/after comparison worthless.
* **The AGC needs about ten seconds** to finish its fresh start before it will
  accept input. Uplink words sent during boot are simply lost, which looks
  identical to the exploit failing. `BOOT_SETTLE` in each script covers this.

## Findings

### 1. The uplink is indistinguishable from the keyboard — `t1_inject.py`

The same keystroke sequence is run twice: once as an astronaut pressing keys
(channel `015` → KEYRUPT), once as an unauthenticated radio transmission
(channel `0173` → UPRUPT). Both drive V35E, the lamp test.

```
=== via UPLINK (channel 0173, UPRUPT) -- no authentication ===
  after VERB : PROG=88 VERB=   NOUN=88
  after 3    : PROG=88 VERB=3  NOUN=88
  after 5    : PROG=88 VERB=35 NOUN=88
  after ENTR : PROG=88 VERB=88 NOUN=88
    +----------------------+
    |  PROG           88   |
    |  VERB 88   NOUN 88   |
    +----------------------+
    |  R1      -88888      |
    |  R2       88888      |
    |  R3      +88888      |
    +----------------------+
```

### 2. Arbitrary erasable write → popping a 1202 — `t2_1202.py`

P27 verb 72 ("scatter update") takes an address and a value from the uplink
and stores one to the other. The destination is unvalidated
(`UPDATE_PROGRAM.agc:459-476`) — the uplinked ECADR goes straight into the
`EBANK` register and is used as the store index.

We write `01202` into `FAILREG` (ECADR `0375`) from the ground, then read it
back with **V05N09E** — the same keystrokes the crew used on 20 July 1969.
The executive is never loaded and no core sets are exhausted. The alarm is
pure fabrication.

```
=== 3. uplink a V72 scatter update targeting FAILREG ===
  uplink V72E                (start P27 scatter update)
  uplink 00003E              (component count II=3)
  uplink 00375E              (destination ECADR)
  uplink 01202E              (value)
  uplink V33E                (PROCEED -- commit the write)

=== 4. read alarm registers AFTER (V05N09E) ===
    |  VERB 05   NOUN 09   |
    |  R1       01202      |
```

### 3. The lockout is a DoS vector and unlocks itself — `t4_lockout.py`

A malformed word trips `TMFAIL2`, setting UPLOCKFL and blocking the uplink.
But the unlock is an unauthenticated uplinked ERROR RESET (`ELRCODE`, octal
22), tested at `UPOK` *before* the lock check, so it is honoured even while
locked. The lockout stops radio noise, not an adversary — and an attacker
who wants to deny Mission Control its uplink can hold the computer in the
locked state with garbage.

The keyboard is unaffected throughout, which is what proves the block is
specific to the uplink path.

```
1. uplink VERB 1 6      VERB field = 16
2. uplink malformed word 77777 (fails triple-redundancy -> TMFAIL2)
3. uplink VERB 2 1      VERB field = 16   <- unchanged; uplink locked out
4. KEYBOARD VERB 2 1    VERB field = 21   <- keyboard still works
5. uplink ERROR RESET   (unauthenticated, clears the lock)
6. uplink VERB 3 5      VERB field = 35   <- attacker unlocked themselves
```

### Popping calc, 1969 — `t3_calc.py`

The DSKY cannot draw a calculator. Its entire renderable alphabet is blank
plus the ten digits, fixed in relay hardware
(`PINBALL_GAME_BUTTONS_AND_LIGHTS.agc:378`) — the AGC emits 5-bit codes to a
decoder and never addresses segments. A whole class of display-spoofing
attack is structurally impossible, by accident rather than design.

So instead of drawing one, we make the guidance computer *be* one. Three
signed 5-digit registers, every value delivered by unauthenticated radio:

```
    +----------------------+
    |  PROG           00   |
    |  VERB 05   NOUN 09   |
    +----------------------+
    |  R1       00002      |
    |  R2       00002      |
    |  R3       00004      |
    +----------------------+
```

## Known issue: cold-start reliability

The exploits themselves are demonstrated and real — the V72 write, the
fabricated 1202, the calculator, and the lockout behaviour were all observed
directly. But the demo scripts are **not yet reliable from a cold boot**.

Runs against a warm computer succeed consistently. Runs that start from a
genuinely cold fresh start (`--no-resume`, empty erasable) sometimes produce
a completely blank display, as if the uplink characters were never received —
including the very first `V37E 00E`. `t1_inject.py`, which drives the keyboard
before the uplink, does not show this; the failures so far are all in scripts
whose first action is an uplink.

The working hypothesis is a sequencing problem in the harness rather than a
property of the flight software: uplink words are being sent before the AGC's
fresh start has finished bringing up the display system, and are silently
dropped. `BOOT_SETTLE` was raised to 10s for this reason and did not fully fix
it. This is under investigation and the scripts should not be treated as
push-button reproducible until it is resolved.

Stated plainly so nobody mistakes a green run for a verified one: **a blank
display means the harness failed to deliver, not that the exploit was blocked.**

## What this does and does not show

It shows the *software* accepted unauthenticated commands and had no
destination validation on uplinked memory writes. Those are properties of
the code, and they are demonstrated here directly.

It does **not** show the real system was exploitable. The emulator has no RF
model. An actual attack needed a transmitter able to close the link against
Deep Space Network antennas, and the crew's UP TELEMETRY switch in ACCEPT.
Those were the real defences, and they were physical rather than
cryptographic.

P27 is also mode-gated: `TESTXACT` plus a `MODREG` check restrict updates to
P00 on the LM and P00/P02/fresh start on the CSM, so this cannot run during
powered descent. The demos enter P00 first. That gate is a deliberate and
effective control and deserves to be noted alongside the finding.

## Not attempted

Arbitrary code execution. The precondition holds — `LST2` (ECADR `1410`) is
18 words of *erasable* memory holding the 2CADRs of up to nine pending
WAITLIST tasks, i.e. function pointers in RAM, reachable by the same V72
write — and the AGC executes from erasable, which is what made the Apollo 14
erasable-memory patch possible. Chaining that into a working control-flow
hijack was not built or verified here, and should not be assumed to work
until it is.

## Files

| File | Purpose |
|---|---|
| `agc_link.py` | yaAGC socket client, uplink word encoder, DSKY decoder |
| `p27.py` | P27 verb 72 driver (arbitrary erasable write) |
| `t1_inject.py` | Finding 1 — keyboard vs uplink |
| `t2_1202.py` | Finding 2 — arbitrary write, fabricated 1202 |
| `t3_calc.py` | Calculator display |
| `t4_lockout.py` | Finding 3 — lockout DoS and self-unlock |
| `setup.sh` / `run_agc.sh` | Build and run the emulator |
