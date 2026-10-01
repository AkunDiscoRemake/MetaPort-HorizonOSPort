# Isolated RCpc compatibility experiment

This is not a METAPORT release, a substitute launcher, or a physical-phone test.
The baseline remains available separately from the adapted experiment.

## Established evidence

- API 36 run **36897515996** crashed with Berberis `UndefinedInsnThunk` during
  original `libc++.so` locale construction. A later different PID did not prove
  survival.
- Run **36900295491** independently compiled and executed an ordinary ARM64
  instrumentation fixture on that emulator: control returned 7; LSE `ldaddal`
  returned the expected old/new values; RCpc `ldaprb` caused SIGILL. No Horizon
  library was loaded by that fixture. This isolates a translation limitation,
  not physical Infinix capabilities or all possible causes of the original crash.

## Narrow adaptation being tested

Only the hash-pinned system `libc++.so` dependency is eligible:
`9d8e75c1c1abdecb9dcd71602aba2fa28b30c6f6918f20d6721c164fc8196d72`.
At ELF `0x88ac4`, exact word `0x38bfc108` (`ldaprb w8, [x8]`) becomes
`0x08dffd08` (`ldarb w8, [x8]`). The instruction still reads an actual byte and
zero-extends it into W8, with stronger acquire ordering. No condition, permission
check, function, or service is replaced by a constant, NOP or stub. No broad
pattern-based rewriting of executable segments is performed.

Architecture references (Arm A64 documentation mirror, 2026-03 release):
[LDAPRB](https://www.scs.stanford.edu/~zyedidia/arm64/ldaprb.html) and
[LDARB](https://www.scs.stanford.edu/~zyedidia/arm64/ldarb.html).
The documentation distinguishes AcquirePC from Acquire and provides the
encodings. Single-thread instruction tests do not validate all concurrent
behavior, timing or complete binary compatibility.

The adapter refuses a different source hash, opcode, unaligned PC or an address
outside executable file bytes. It records source/adapted hashes, offset and both
words. Original retained APK members remain unchanged; this **added dependency
is modified** and is labeled accordingly. Own test signing is not Meta identity.

The independent fixture additionally tests `ldarb` in the adapted experiment.
Reports are separate:

- `analysis/android-runtime/original-shell-bundled-baseline.json`: original
  dependency baseline;
- `analysis/android-runtime/original-shell-rcpc-baseline.json`: adapted experiment;
- `analysis/android-runtime/original-shell-rcpc-dependency-bundle.json`: explicit
  adaptation provenance.

`original-shell-rcpc.yml` calls the reusable offline workflow through an authorized
push trigger. Manual dispatch returned an integration-permission denial; it was
not necessary to request credentials or change branches. APKs and signing keys
are not published. The experiment does not assert original UI, service, hand,
compositor or hardware readiness even if the first crash is passed.

## First adapted execution: run 36901717864

The original locale load site was passed; the next recorded SIGILL is inside
`__cxa_guard_acquire`, which contains another LDAPRB at ELF `0x48cb0`, word
`0x38bfc008` (`w8, [x0]`). Control, LSE and the independent LDARB fixture passed;
LDAPRB still crashed. The application remained nonfunctional.

The next experiment expands the explicit whitelist to those **two observed
sites**. The second replacement is `0x08dffc08` (LDARB with the same registers).
The C++ initialization guard, branch, mutex and return behavior are retained;
this is not removal of the guard. Both source instruction checks must pass before
any adapted file is written. The new two-site runtime outcome is not established
by the preceding one-site run. Baseline and adapted evidence stay separate.
