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

## Broader fault window — run 36917029516

After three adapted byte loads, startup still crashed in the locale constructor
at guest block PC `0x81550`. The expanded window exposes `ldapr x8, [x21]` at
`0x8162c`, matching the offset suggested by the host thunk's saved addresses.
This is a **64-bit** acquire, not a byte load. The next explicit experiment adds
only that site, replacing `0xf8bfc2a8` with `0xc8dffea8` (`ldar x8, [x21]`).
The independent fixture adds both 64-bit forms and checks a value with nonzero
upper 32 bits. Width and register changes are rejected by unit tests.

The decoder census found 203 remaining RCpc candidates in this three-site adapted
`libc++.so`. These are static candidates, not 203 proven runtime failures; they
are not automatically patched. The census now stays separate from verified
crash windows, so an optional census error cannot erase the latter. No original
UI has rendered in the recorded run. Four-site runtime validation is pending.

## Inventory-based experiment after run 36918169876

That run confirmed independent 64-bit LDAPR failure and LDAR success, including
upper-word preservation, while the original app progressed to the next repeated
locale initialization load (`0x816f4`) and still crashed. A four-site change is
therefore not enough to cover the known translation limitation.

The next experiment **changes strategy**, from one fault site per run to a fixed,
reviewable inventory of 206 decoded byte/64-bit acquire candidates in this exact
library. `libcxx-rcpc-sites.json` records every source/destination word and address,
the census run and its library hash. The runtime-frontier sites and static-only
candidates are distinguished. This is NOT proof that all 206 execute, nor a new
claim that static disassembly establishes safety or complete compatibility.

The adapter never scans and rewrites arbitrary words automatically at runtime.
It requires the original whole-file hash, checks every explicit word against the
input, rejects other opcodes, destination zero-register, width/register changes,
unmapped/non-executable addresses and duplicates, then emits the adapted copy.
Only byte or 64-bit AcquirePC-to-Acquire lowering is supported. All affected bytes
and hashes remain declared. The original-baseline job stays unmodified; this is
an additional, not-yet-validated translation experiment, not a physical-phone
optimization or release. No permission/entitlement check, C++ guard branch or
service is bypassed. Concurrent behavior and end-to-end UI still need validation.

## Inventory experiment outcome — run 36919477652

The 206-site `libc++.so` experiment installed and executed, but the app still
crashed before original UI rendering. The recorded fault moved to
`libutils.so`, `android::SharedBuffer::attemptEdit() const`, ELF `0xf860`:
`0xb8bfc008` / `ldapr w8, [x0]` (a 32-bit load). The observed process was absent
at the final sample. This is not a working demo and not validation of all adapted
paths. The existing byte/64-bit instruction fixtures do not cover this 32-bit
form; it must be tested separately before extending compatibility to it.

There is no validated release APK or defensible same-day release commitment on
the basis of these reports. UI surface/client recovery remains a separate task
from CPU translation, private-service integration and physical-phone validation.

## Word-load preflight and second library — run 36924213557

The fixture now runs **before** original APK installation/start. Control, LSE,
byte acquire, word acquire and 64-bit acquire must all return their expected
values; missing/failed cases prevent the original launch. Native mode names are
explicit and unknown modes fail, rather than silently selecting the control.
The 32-bit check reads `0x89abcdef` into a prefilled 64-bit register and checks
zero-extension, not merely the low byte.

On API 36 this run passed every prerequisite, while all tested RCpc forms crashed.
The original then passed the adapted `libutils.so` site at `0xf860` and crashed
at `SharedBuffer::release()`, with LDAPR W8 at `0x10058`. There was no surviving
process or original UI. The next library inventory contains 14 explicit sites
(the original observed site plus 13 decoded candidates), pinned to original
`libutils.so` SHA-256
`2d7422e92852d7c62e2528ba6100f5b484dfd33c38d156613c6aaeb89b9f9167`.
No reference counter, branch or return value is replaced. The next experiment's
outcome remains unknown until its runtime evidence is collected.

The optional inventory now prioritizes crash libraries and then examines the
remaining verified small dependencies: at most 64 libraries, 2 MiB/library,
32 MiB aggregate input, 8192 candidates, 16 MiB disassembler output/library,
and a 120-second admission deadline (an admitted parser has its own 45-second
timeout). Hash mismatches, symlinks, invalid names, budget skips and timeouts
are explicit and do not discard the already verified crash windows. Completeness
means the bounded decoder output was scanned, not all code paths were reached.
Nothing from this inventory is automatically patched or treated as a successful
runtime/ABI/service integration.

## Dependency inventory experiment following 36925786582

The original still crashed after the 14-site libutils adaptation, now inside
`libhidlbase.so / getBnConstructorMap()` at ELF `0x4f0f0`. No UI was rendered.
The bounded inventory found additional byte/word/doubleword RCpc candidates in
15 unchanged firmware libraries. `dependency-rcpc-sites.json` pins each original
hash, ELF PC and replacement word; its own digest is pinned in the loader.
Only the already independently exercised width-preserving acquire conversions
are allowed. This is not an automatic patch of arbitrary future census output,
a Binder/HIDL service implementation, or a physical-device optimization.

Run **36939212398** passed the instruction preflight and the adapted HIDL
constructor but still crashed, now in `libnblog.so`, ELF `0x20600`, during the
JSON-value static constructor. Its verified inventory adds 19 explicit sites.
No UI appeared. The census admitted only the first 64 small dependencies;
remaining names were explicitly skipped. The next census prioritizes as-yet
unadapted firmware dependencies and admits up to the existing 128-node closure
limit, retaining the same byte, candidate, output and time limits. This avoids
alphabetic starvation without claiming the larger libraries were scanned.

Run **36940043323** still crashed before UI, at the JSON-value constructor in
`libprocessgroup.so` (guest block ELF `0x50460`). The expanded census completed for
all bounded small libraries; only original APK members `libshell.so`,
`libnetwork.so` and `libovravatar2p.so` exceeded its size limit. The remaining
11 unchanged firmware libraries contribute 120 explicit byte/word/doubleword
candidates to the next fixed policy (597 sites / 29 libraries in total).
Each addition has its own evidence-run provenance. No original APK member is
changed, and neither startup success nor complete instruction coverage is claimed.

## First Java constructor failure after native instruction adaptations

Run **36940917880** recorded no SIGILL in its observed crash. It reached
`ShellApplication.<init>` and failed with `NoClassDefFoundError` for
`horizonos.graphics.Vector4f`; the process still terminated, without original UI.
This does not prove complete CPU compatibility or a completed native startup.

The next separate opt-in experiment extracts `/framework/hzos-framework.jar`
from the hash-pinned system_ext image. It requires a real Vector4f class definition
in that JAR, validates DEX checksums and rejects definitions colliding with APK
classes or boot namespaces. If any requirement fails, packaging fails closed.
It appends original DEX bytes under fresh multidex names; no existing APK DEX or
resources are rewritten. The exact source-image, JAR and DEX hashes are recorded.
The class owner and runtime outcome remain unverified until that run completes.
Adding classes does not register PreferencesManager or provide spatial services.

Run **36942098540** failed during preparation; the original APK was not installed
or launched. The archived run logs were not retrievable from this workspace
(download requests ended with EOF), so its exact exception is not established.
The next run preserves bounded packaging errors and inspects three fixed JARs
from the already verified images to locate the real Vector4f definition. This
failure path does not automatically select or append a different framework JAR.

Run **36942634549** preserved the preparation failure: all three inspected JARs
from the pinned images failed the standard internal DEX checksum/signature check.
No application installation or execution took place. The next experiment allows
only explicit framework-header normalization: SHA-1 at bytes 12–31, then Adler-32
at bytes 8–11. Bytes 0–7 and 32 onward, including instructions, tables and data,
remain unchanged. Source partition/JAR/DEX hashes, stored header fields, payload
hash and changed byte range are recorded. Original APK DEX validation stays strict.
This supersedes the proposed whole-file byte-identical framework DEX addition;
only existing APK members and added framework instruction/data payloads remain
byte-identical. It is not proof that a preoptimized DEX body will pass ART or run.

Run **36943056110** located Vector4f in the original hzos-framework JAR:
SHA-256 `b1c5111bb301daf971b658414daf8e43a0b4cdac9ecc2e94a554d0c861607e42`,
2041 class definitions, including 1052 horizonos and 216 vros classes. Packaging
stopped at the conservative namespace gate because the JAR also defines Meta's
`android.app.VrosSystemServiceRegistry` and its nested classes. The next policy
pins that exact JAR and allows this explicitly named extension family, not
Android's `SystemServiceRegistry`, `ContextImpl` or arbitrary android.* classes.
It neither invokes that registry nor claims it can access package-private host
framework APIs from an app loader. Other forbidden definitions still fail closed.
Original code presence is not service registration or privilege acquisition.

Run **36943586300** stopped on additional Android virtual-camera definitions in
the same JAR. Rather than expanding namespace exceptions, the next experiment
excludes boot namespaces (including the previously allowed Meta registry extension)
using dexlib2 2.5.2 class selection. No class body is replaced or manually edited.
Selected classes must have identical canonical baksmali output before/after, and
the resulting definitions must exactly match the requested non-boot set. Reference
indices and DEX layout are reserialized: the derived payload is **not byte-identical**.
Canonical disassembly equality does not prove ART acceptance, ABI compatibility,
hidden-API access or service availability. Original APK DEX/resources stay unchanged.

Host tools are fetched from Maven Central using pinned published artifact SHA-1
values, with downloaded SHA-256 recorded. They are not bundled as runtime stubs.
Local Java compilation was unavailable; compilation, canonical comparison and ART
execution still require the next Actions result. Setup failures are now preserved
as bounded JSON so unavailable blob-log downloads cannot conceal their cause.

## Canonical mismatch: hidden-API metadata class association

Run **36951491015** found 1940 selected classes on each side, with 1417 differing
smali files. Its first difference changed `whitelist test-api` to `blacklist`
on `AbstractMessageLite$Builder.clone()`. The guard correctly stopped packaging.
Inspection of pinned dexlib2 2.5.2 DexWriter source shows that `writeClass` emits
superclasses/interfaces first, but the hidden-API offset table was written using
the preexisting lexical class list. The host-only patch sorts that list by the
actual emitted class_def index before writing the metadata. It does not remove
flags, loosen comparisons or change Android's hidden API enforcement.

The exact upstream source SHA-256 is
`7a15d75536dd7cee9d3ee65c02de9ddcdbec81456fb5fc0f0fbf4a5828e0f972`;
the upstream BSD license remains in the downloaded source. A separate synthetic
inheritance fixture must reproduce the mismatch with the original writer and
preserve both classes' exact flags with the patched writer. Full canonical smali
comparison of the original selected framework remains mandatory after that.

Run **36952121061** reproduced the unpatched serializer error in the standalone
fixture and passed the patched fixture. All **1940** selected classes then passed
exact canonical-smali comparison. The resulting APK installed, but its application
still crashed resolving Vector4f, despite that definition being present in the
appended DEX. Thus packaging presence and canonical equality did not establish
ART loading. The next probe captures filtered loader/installer logs immediately
after install and start, without excluding non-app UIDs. It does not ignore
verification failures or alter the Android boot class path.

Run **36952973469** captured the actual ART rejection during dexopt:
`Offset(1861525) should be aligned by 4 for maplist item of type 61440`
(`0xf000`, hidden-API metadata). Android installation returned Success, but that
was not successful DEX loading. The serializer now aligns the section before
recording its offset. This adds only necessary layout padding and preserves
original flags; it does not strip hidden-API data or disable host verification.
The isolated regression varies one to four transient instance fields, testing
metadata association and alignment across section-size residues. The original
writer must reproduce a mismatch and an alignment failure; the patched writer
must preserve exact field/method flags and four-byte alignment in every case.

Run **36953764788** validated the alignment fix: dexopt reports `PERFORMED`
instead of rejecting the DEX, the host regression passes, and the original
constructor advances from line 103 (`Vector4f`) to line 144, now missing
`com.oculus.os.ActivityManagerUtils`. This is still `APPLICATION_CRASH_RECORDED`.
The next experiment adds the separately pinned original
`/framework/com.oculus.os.platform.jar` (SHA256
`9659b2f81dd6ba59c4ea549e0229717e2a22e6cc31369b5735ddc4b90d495285`,
889 definitions in earlier verified inventory). Its required class must actually
be present; original APK and previously added DEX classes cannot be overwritten.
Boot namespaces remain excluded and selected definitions require canonical
preservation. Runtime also logs denied non-SDK calls including Parcel string8
and internal Preconditions/AnnotationValidations. Adding original classes does
not grant those APIs, register platform services, or prove UI execution.
