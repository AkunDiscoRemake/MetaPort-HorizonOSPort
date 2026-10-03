# Native VR-focus port boundary

**Not a running focus service, not a functional APK.** The original shell still
blocks while registering its top-activity listener. No provider has been
published just to make that call return.

## Verified recovery

Run 37007778951 statically recovered all **455 functions identified by Ghidra**
in the pinned daemon and all **110 identified functions** in its Binder library.
This is not proof of every original function, correct inferred prototypes, or a
successful recompilation. Reports are under `analysis/builds/52168470052900520/`
as `focus-native-{inputs,server,interface,run}.json`.

Daemon SHA256: `14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418`.
Interface SHA256: `949bebe7639f07ec86c818456a41c403e6a946ed9073b162b3d46ee29291916c`.
ELF offsets below are relative to the original image, not Ghidra's relocated
addresses. Neither executable was run or packaged as an APK library.

| Original function | ELF offset | Boundary |
|---|---:|---|
| main.cfi | 0x2ef00 | Creates connection manager, client manager, focus policy, service and ServiceHost |
| ConnectionManager constructor | 0x15480 | Connects activity_native, display, package_native, permission, OculusWindowManager |
| computeFocusState | 0x25460 | Original focus policy, still not ported |
| registerVrTopActivityListener | 0x2bf40 | Permission check, caller PID, listener ownership and binder-death registration |
| checkCallingPermission | 0x2dd60 | PermissionCache/caller identity; must not become unconditional success |
| setAppState | 0x2c450 | Caller PID check, actual process UID, state update and notifications |
| onXrSessionStateChanged | 0x22510 | Visible membership and stopping transition |
| updateClient | 0x20a60 | UID/PID ordered set membership |
| BnVrFocusService::onTransact | 0xaa00 (interface ELF) | Original Binder decoding/dispatch, not yet integrated |

The name `Backend::HookMode` does **not** prove phone support: the recovered
constructor supplies `android::defaultServiceManager` and the five system-service
names above. Its backends still need actual app-scoped implementations. The
service's firmware init file runs as root/system; that does not grant a phone APK
those identities. Debug permissive focus properties are not a porting strategy
and have not been enabled.

## First executable state logic

`port/android/adapters/src/main/cpp/focus_session_state.hpp` is a project-owned
reimplementation of the observed session-membership reducer, not recovered source
relicensed as GPL, and not a Binder provider. It is not yet wired into VrShell.
It consumes trusted caller/process identity and actual service events; it creates
no processes, poses, focus grants, foreground app names or synthetic events.

The recovered **service-local** state values are 0 (visible) and 2 (stopping).
They must not be interpreted as the numeric OpenXR `XrSessionState` enum.

Instruction cross-checks in the pinned executable:
- `0x22540`: compare state register w3 with 2; `0x22548` rejects other nonzero values.
- `0x22584`/`0x225cc`: pack UID in low 32 bits, PID in high 32 bits.
- `0x225a0`: visible inserts through updateClient; `0x225e8` removes on stopping.
- `0x2260c`: stopping also calls maybeUpdateActivityState, even if membership was absent.
- `0x2c48c`/`0x2c490`: reject a requested PID differing from Binder's caller PID.
- `0x2c4b8`/`0x2c4bc`: missing observed UID follows the bad-optional-access path.
- `0x2c4d0`: only state 0 or 2 proceeds to top-activity notification/reporting.

The reducer returns required effects instead of pretending to execute the missing
activity/focus backend. Its future caller must consume those effects in the
original order, outside its state lock. Duplicate events still request original
notifications; an ignored state must not grant focus. The membership snapshot is
UID-then-PID ordered, preserving original set identity and deduplication.

`native/tests/focus_session_state_test.cpp` covers identity denial, unavailable
UID, duplicates, ignored states (including OpenXR-looking values), ordering,
stopping absent clients, and concurrent updates/snapshots. ASan/UBSan and TSan
runs pass locally. These are tests of the new reducer, **not** an original-binary
oracle or a phone/Horizon UI validation.

## Public Android window input backend

`AppWindowFocusBackend` observes actual `Application.ActivityLifecycleCallbacks`,
`ViewTreeObserver.OnWindowFocusChangeListener` and public `DisplayManager` events.
It reports only started activities seen after registration, their actual focused
windows, valid display IDs, component names and the process's real UID/PID.
It never invents an outside application's identity, treats activity resume as XR
visibility, or turns window focus into a tracking/access grant.

Start it before the first activity, once an attached Application is available.
Android's public APIs cannot enumerate activities created before registration;
empty observations are not proof of no global foreground application. Multiple
own windows remain separate observations rather than choosing a fabricated
system-wide top activity. Snapshots contain no Activity/View references and their
lists are immutable. Stop/destroy removes both old and transferred view observers;
close unregisters lifecycle/display callbacks and emits `observing=false`.

This input backend is not yet wired into the original ConnectionManager or a
VrFocusService provider. In particular, the original shell's Application
constructor blocks *before* activity creation: adding this backend alone does not
resolve that bootstrap dependency. The instrumentation-only FocusTestActivity
exists solely to exercise real Android focus/stop/resume; it is never packaged
as the Horizon UI or a release/demo launcher.

### Window instrumentation investigation (2026-10-02)

Run `37009434351` executed all twelve owned cases on API 29 and 35, but
`realWindowFocusTracksStopAndResume` failed on both. The failure was the test's
assumption that stopping the subject leaves zero started app activities:
AndroidX ActivityScenario opens its own covering Activity to stop the subject.
The backend correctly observes app activities, including that covering window;
it must not filter these observations to make a test pass. The corrected test
checks loss/reacquisition of the subject's component and compares the backend's
started count against the independent instrumentation lifecycle monitor. This
correction passed in run `37010684552`: all twelve owned cases passed on each
of API 29 and API 35, including the independent started-activity count checks.
This is emulator validation of the app-local backend, not original service or
physical-phone validation. Bounded JUnit failure details
are now retained even when the suite-level failure counter is nonzero; that
counter still forces the gate to fail. None of this publishes a vrfocus service
or resolves the original ShellApplication constructor ANR.

## Binder endpoint and callback codec

`focus/protocol/VrFocusEndpoint.java` now decodes all eleven original transactions,
using the original interface descriptor and Android's public `Binder`/`Parcel`.
It captures the actual Binder caller PID/UID and requires a backend implementing
**every** operation and an operation-specific access check. There are no default
successful operations or provider publication. `FocusWire` writes the original
sized parcelables and one-way callbacks without defining duplicate classes in
`oculus.internal` or replacing the bundled SDK.

The field order is cross-checked against both pinned Java smali and the native
interface (not inferred from a component's flattened name):

- `ClientStatus`: size, PID, hasFocus (32-bit boolean).
- `ImmersiveApp`: size, packageName (UTF-16), PID, UID, isTopActivity.
- Typed-object presence is **outside** the sized payload.
- Top callback: transaction 1, one-way, string followed by typed ImmersiveApp.
- Focus callback: transaction 1, one-way, int.

`python3 -m horizon.ui.focus_wire_contract` checks the hashes of five Java
contracts and five inferred native functions, and checks each of the eleven
transaction IDs against the recovered native switch. Evidence is already in
`original-shell-rcpc-dependency-bundle.json` and `focus-native-interface.json`.
This does **not** execute the original SDK proxy or native daemon.

Intentional app-local hardening: PID/result vectors are bounded to 4096 entries;
null required listeners/vectors, truncated integers, one-way service requests
and trailing bytes are rejected before invoking policy operations. The native
argumentless methods do not all enforce trailing-data rejection, so this is not
a claim of byte-for-byte acceptance of every malformed original request.

Four new instrumentation cases exercise all eleven transactions, PID/UID
capture, field boundaries, UTF-16 data, failure-before-side-effect behavior,
one-way callbacks, and absence of accidental provider publication. Their backend
is explicitly a test fixture, not production focus logic. The runtime gate now
requires sixteen owned cases per API. Run `37021605827` passed all sixteen
on each of API 29 and API 35. Project checks (including native sanitizers) passed
in `37021605969`; these results still do not execute the original SDK proxy.

**Remaining bootstrap work:** actual focus policy and listener ownership/death
handling; integration with the real window/session backends; original-proxy
interoperability; publication before ShellApplication construction. The endpoint
is not packaged into or published to the original shell yet. No constructor wait
is bypassed, no XR/hand/tracking grants are fabricated, and no functional APK is
claimed.

## Listener ownership and death lifecycle

`FocusListeners` implements the next service component: real Binder death links,
actual calling PID/UID capture, permission-policy injection (no permissive
default), duplicate registration, and caller-wide removal for each channel.
Registration itself emits **no callback**. Source offsets: focus register/unregister
`0x2b8a0`/`0x2bd40`, top register/unregister `0x2bf40`/`0x2c320`, death notifier
`0x2ab10`, removal `0x2acc0`, notification `0x2a620`. Inferred C hashes are pinned
by `tests/test_focus_listener_evidence.py`.

An important recovered detail: `onVrFocusChanged(int)` carries the **focus type**
(the map key, 0 or 1), not a granted/denied boolean, PID, or XR session state.
The original notification method does not compute focus; clients must query the
policy afterward. The owned registry preserves this invalidation behavior and
signed type/PID ordering, including duplicate callbacks within each PID vector.

Deliberate public-API lifecycle adaptations, not exact daemon equivalence:

- Limits: 256 registrations total, 64 per PID/channel; UID guards against stale
  PID ownership. Permission checks run before type validation, as in the daemon.
- Reserve before `linkToDeath`, activate only after successful linking while
  alive. Death, close or unregistration during linking cannot resurrect an entry.
- Death removes **all** registrations of that exact Binder. Recovered native
  removal erases the first match per focus channel and the first top match per
  death invocation; the port does not retain dead duplicates between invocations.
- Binder linking, unlinking and callbacks execute outside the registry lock.
  Unregistration cancels not-yet-admitted snapshot entries; a delivery already
  admitted can finish afterward. There is no claim of a quiescent-return barrier.
- Recipient exceptions are counted and isolated; actual DeadObjectException
  also removes the dead Binder. Close unlinks and releases all registrations.

Five additional instrumentation tests cover duplicate/type routing, top payload,
permission refusal, budgets, cancellation during linking, callback reentrancy
across threads, exception isolation, and **actual death of a separate test-only
Android service process**. The disposable process never belongs to the user or
original firmware and is absent from production manifests. Gate: 21 owned cases
per API. Run `37120394692` passed all 21 on both API 29 and API 35, including
`actualRemoteProcessDeathRemovesAllBinderRegistrations`. The simulated link-race
case is separate and is not presented as real Binder death evidence. Android
build `37120394700` and project/native checks `37120394643` also passed.

This component does not implement focus policy, publish a provider, or resolve
the original constructor ANR. Integration with the endpoint and policy remains
required before the original shell can use it.

## Executable focus decision kernel

`focus_decision.hpp` reconstructs the normal (non-permissive) decision portion
of `computeFocusState` (`0x25460`). This is **not the complete FocusPolicy**:
`getImmersiveApp`, metadata/permission resolution, backend observation and
ClientManager state commits remain separate, unconnected requirements.

Recovered operations now executable against explicit trusted snapshots:

| Step | Type 0 | Type 1 |
|---|---|---|
| Base eligible identities | foreground activity, foreground panel, clients with top activities (slot 5) | same |
| Additional identities | window focus, resolved top activity, all clients with top activities (slot 6) | none from these sources |
| Immersive adjustment | none | first queried metadata identity matching immersive PID is inserted/erased according to main-display focus |
| Final override | observed background access for type 0 | observed background access for type 1 |
| Output | one result per resolved distinct UID/PID, signed UID then PID order | same |

Run **37121195806** resolved the exact relocated ConnectionManager vtable at
ELF `0x38928`, using exact executable function entries rather than nearest symbol
labels. Slot 5 targets `getClientsWithTopActivities` (`0x21600`); slot 6 targets
`getAllClientsWithTopActivities` (`0x21740`). They expose distinct sets at object
`+0xf0` and `+0x130` and must not be aliased. The kernel fields now use those
verified meanings. Slots 2/3/4 were also confirmed: foreground activities,
currently rendering clients, window focus. Rendering clients (slot 3) are **not**
a direct input to this decision method. This resolves the virtual-call names,
not the unported event sources/permissions that populate their sets.

Foreground/window meanings and background-access versus current-focus metadata
are independently supported by `FocusPolicy::dump` (`0x23cc0`).

`getClientSet` (`0x265e0`) omits failed metadata lookups and deduplicates exact
UID/PID identities. Its comparator (`0x26ac0`) and the decision code establish
that input PID ordering/duplicates are not preserved in the output. The kernel
accepts only already-resolved metadata and retains the first record for each
identity. The immersive comparison uses PID only to select the **first sorted
queried record**, then uses that record's UID/PID for the set operation. Authorized
background access runs afterward and can override main-display removal.

Instruction checks include `0x25b2c`/`0x25b30` (queried PID match), `0x260cc` and
`0x260f0` (background type lookup), and `0x26350`/`0x26358` (result PID/bool stores).
Native C and assembly provenance are pinned by `test_focus_decision_evidence.py`.
No debug-permissive property fallback is implemented or enabled. Unknown backend
feeds must not be passed as empty observations; the inputs have no default
constructor, and no production backend constructs this full snapshot yet.

Each result also requires the original ClientManager gained/lost bookkeeping
(slot 3/4) even on repeated queries. Returning rows alone does not execute those
side effects. Inputs are never updated in-place and the kernel retains no state.
Tests cover both branches, identity mismatch, ordering, duplicates, override
precedence, immersive absence/mismatch, invalid types and concurrent read-only
queries. ASan/UBSan and TSan passed locally; native suite now has 15 cases.
This is reconstructed-code testing, not comparison with a running original.

**Corrected semantic label:** Binder operations 10/11, grant/revoke tracking
service access, take a **display ID**, not a PID. Native `0x21880`/`0x21b20` log
`displayId` and maintain display access; the endpoint/backend parameter names and
fixtures now reflect this without changing the wire format or granting access.

The Binder provider is still unpublished and the original constructor ANR remains.

Validation of source `17faea6`: project/native checks `37121443278` and Android
build `37121443238` succeeded; Android regression `37121443260` passed the existing
21 owned cases on each API 29/35. Those Android cases do not execute the new
C++ decision kernel: its execution coverage is the separate 15-case host native
suite, including ASan/UBSan and TSan. No original-policy execution or private
service interoperability is inferred from these green checks.

## Immersive selection, history and decision-core connection

`focus_immersive.hpp` now implements the stable-snapshot selection rules from
`getImmersiveApp` (`0x22f40`), with `getTopActivityClient` (`0x26760`),
`getTopActivity` (`0x23b60`), `getPackageAsImmersiveApp` (`0x282e0`), exact process
name comparison (`0x27f50`) and ten-entry history (`0x28080`). `FocusPolicyCore`
connects the selected PID/top client to `decide_focus`; it overwrites externally
supplied immersive/top-client decision inputs instead of trusting stale values.

Selection priority, in original rendering-list order:

1. Rendering exception process matching the focused window's **PID** (not UID).
2. First rendering exception process, regardless of window focus.
3. The first UID/PID-sorted live metadata entry for **com.oculus.vrshell**, if its
   observed process name matches the top name or the top name is that package.
4. First rendering process whose observed process name exactly matches the top.
5. No immersive app. A formerly selected app is not retained just because alive.

The exception set is exactly `system_server`, `com.oculus.vralertservice`,
`com.oculus.os.vrlockscreen`, `com.android.settings`; this is a classification of
already observed clients, not creation of system identities. The decompiler
incorrectly gives `hasTopActivityException` a void return. Assembly `0x27dc4`
confirms `cset w0,ne` (membership true), and `0x230cc`/`0x23228` branch on true.
The shell-package lookup argument was also omitted from inferred C: `0x2330c`
loads literal data at `0x7d9f`, the same literal used by the explicitly decoded
`String16("com.oculus.vrshell")` comparison at `0x23450`/`0x23458`.

Top activity uses the last successful foreground metadata lookup's package name,
otherwise the primary-display fallback. Exception checks use metadata process
names; top matching uses the separately observed result of
`Process::getProcessName(pid,true)`. No component flattening, suffix stripping or
package-name substitution is guessed. Normalization/observation remains a backend
requirement. Original ClientManager snapshots prune dead processes (`0x13400`);
the helper requires already-filtered inputs and does not pretend to probe PIDs.

The original selection marks the chosen ImmersiveApp `isTopActivity=true` even
for an exception that does not match the actual top name. This internal policy
flag is preserved, **not** represented as proof of Android window focus or an
Android permission/tracking grant.

History records only nonempty selections when PID differs from the newest
record. UID/package/flag changes with the same PID do not add a record. Empty
selections clear current state but do not add a history gap; returning to the same
PID still does not duplicate the history entry. History is diagnostic, not a
source of permission, liveness or focus. Callers supply actual system-clock
observation times; tests supply explicit fixture timestamps. State/history updates
are mutex-serialized, return copies, and invoke no Binder/backend code under lock.

Tests cover priority, exact exception names, PID-only matching, shell fallback,
reverse foreground lookup, current-state clearing, PID-only history deduplication,
10-record eviction, invalid-type nonmutation, concurrent updates/readers, and
selection feeding the existing type-1 decision path. ASan/UBSan and TSan passed
locally; the native suite now has **17 cases**. Evidence hashes and key instructions
are guarded by `tests/test_focus_immersive_evidence.py`.

Scope remains reconstructed helper execution, **not original-binary parity**.
The coherent-snapshot API does not reproduce races between repeated live process
queries in the daemon. OS/process observations, metadata/permission resolution,
ClientManager gained/lost commits and Binder/bootstrap integration remain absent.
No vrfocus provider is published and no original APK is made functional by this
change alone.

`FocusPolicyCore`'s stateful implementation is in `focus_immersive.cpp`, shared
by the host sanitizer executable and the Android CMake library target. Thus the
NDK build checks the actual coordinator implementation, rather than merely
shipping an unused header. Android compile/runtime validation is pending for
this change; existing instrumentation does not call this C++ policy yet.

Validation completed for source **d87e1a5**: project/native run **37122883668**
passed (17 native sanitizer cases); Android build **37122883654** passed with
the arm64 NDK coordinator translation unit; adapter runtime **37122883673**
passed all 21 owned cases on each API 29/35. The instrumentation still does not
invoke the new coordinator or original daemon. This supersedes the pending
validation note above, not the integration limitations.

## Current-focus bookkeeping (2026-10-03)

`focus_current.hpp` implements the set mutations recovered from ClientManager
`addCurrentFocus` (ELF `0x12bc0`) and `removeCurrentFocus` (`0x12de0`). Both look
up the metadata cache by PID, then compare UID before inserting/erasing the focus
type. Missing records and UID mismatches do nothing; repeated operations are
idempotent. The focus-type set is separate from background-access permissions.
ARM64 `12bfc` loads identity PID at +4; `12d20`/`12d24`/`12d28` and
`12f38`/`12f3c`/`12f40` confirm the UID checks. Digests and instruction assertions
are in `tests/test_focus_current_evidence.py`.

`FocusPolicyCore::evaluate` now applies every decision row to a staged ledger
under its existing mutex and commits it with the selected current app/history.
No change-event optimization skips repeated queries. Record installation and
removal are explicit adapter lifecycle operations, not implementations of
`buildClientInfo`/`getClientInfo` or Android process observation. Installing a
new/rebuilt record clears its bookkeeping; callers must not reinstall on every
lookup and must invalidate records on process death/reuse, including reuse of
both PID and UID. Erasing with a different UID cannot delete a replacement.

Only the externally serialized helper and the core's locked accessors expose
this state. Accessors return copies; absence is distinct from an installed empty
set. Decisions never auto-create records and current-focus bookkeeping never
grants permission. The real metadata/liveness backend, Binder/JNI bridge and
pre-Application service publication remain unimplemented. No original daemon
execution or resolution of the constructor ANR is claimed.

Bookkeeping validation, source **d4de4df**: project/native **37124230529** passed
with 19 sanitizer cases; arm64 Android build **37124230516** passed; adapter
runtime **37124230539** passed 21 owned tests on each API 29/35. These Android
instrumentation tests do not invoke the ledger/coordinator or original firmware.

## Own-process Android metadata observations (2026-10-03)

`AppProcessMetadataBackend` now reads real public Android API observations for
its own process: `Process.myPid/myUid`, `Application.getProcessName`, application
package, `PackageManager.getPackagesForUid`, and `Context.checkPermission` for
`horizonos.permission.ACCESS_BACKGROUND_HEAD_TRACKING` and
`horizonos.permission.ACCESS_BACKGROUND_INPUT_TRACKING`. Those permission names
are present in original ClientManager initialization `0xf0d0`; the builder
`0x10aa0` asks for process UID/name, UID packages and permission checks.

This backend returns **raw permission results**, not background-access grants or
proof of Meta authorization. It never declares those permissions, adds an
allowlist or substitutes grants when they are absent. Results are freshly read;
missing package metadata or an application/UID mismatch fails explicitly. The
immutable result includes monotonic start/end observation times; Android calls
are sequential, not a globally atomic snapshot. No UI, poses or clients are
invented. Its scope is the current process; it cannot observe arbitrary PIDs.

Important remaining differences: the original name normalization helper is not
ported, so `androidProcessName` is deliberately not called `process_name_for_top`.
Original `getClientInfo` (`0x118e0`) copies a PID-indexed cached record on UID match,
refreshing the returned process name; UID mismatch erases the cache entry. It
must not be confused with this uncached public-API reader. Full metadata-cache
lifecycle, original package selection/allowlists, policy input assembly and
JNI/Binder integration remain unimplemented. A Context is required, so this
reader alone does not resolve bootstrap before Application construction.

Three new instrumentation cases exercise real own-process metadata, immutable
snapshots, actual permission results and explicit rejection of mismatched context
identity. The strict Android report gate now requires 24 owned cases per API.

Own-process reader validation, source **d27c633**: project/native **37125874985**,
Android arm64 build **37125874981**, and adapter instrumentation **37125874971**
all passed. Runtime executed 24 owned cases per API 29/35, including the three
new metadata-reader cases. Neither original firmware nor the new native policy
coordinator was invoked by these instrumentation cases.

## Own-client JNI registration (2026-10-03)

`NativeFocusClient` now takes the observed own PID/UID from
`AppProcessMetadataBackend` and registers that identity in a real native
`FocusPolicyCore` ledger. `focus_client_jni.cpp` independently checks `getpid()`
and `getuid()` before registration. Raw permission results and Android process
names are deliberately NOT converted into grants or normalized policy metadata.
`observeMetadata()` refreshes real Android observations without reinstalling the
record (which would clear its current-focus bookkeeping).

JNI uses a mutex-protected registry of opaque, non-reused positive tokens rather
than dereferencing Java-supplied pointers. It caps live instances at 32, rejects
unknown/closed tokens, makes destruction idempotent, and translates C++ allocation
and standard exceptions into Java exceptions. Java methods serialize reads and
close; each instance owns an independent core. This is not a global provider.
There are no callbacks under the registry lock or invented focus decisions.

Four new instrumentation cases require actual JNI execution: own identity round
trip/refresh, forged identity and stale-token rejection, close/read concurrency,
and bounded capacity/reclamation. The strict Android gate now requires 28 cases.
These exercise core registration/current-record lookup, **not evaluate/selection**.
An installed empty focus set is never returned as an observed service status.

Remaining: complete metadata conversion/cache/liveness, coherent observation
assembly, policy evaluation bindings, Binder service backend and pre-Application
publication. No constructor-ANR fix or functional original Horizon APK is claimed.

JNI registration validation, source **304f8fb**: project/native **37129323107**,
Android arm64 build **37129323137**, and runtime **37129323142** all passed.
Instrumentation executed 28 owned cases per API 29/35, including real native
registration/current-record lookup. Evaluation/selection and original firmware
are still not exercised by these Android cases. Consumer rules retain JNI names;
that rule is checked by host regression, not a minified consumer runtime test.

## JNI evaluation transport (2026-10-03)

`NativeFocusClient` now has package-private evaluation bindings using immutable
`FocusPolicyFrame`/`FocusPolicyResult` packets. The native implementation decodes
all channels before calling the same `FocusPolicyCore::evaluate` used by host
tests. It returns the derived top name, selected immersive app, ordered decision
rows, registered own-client focus mask, and ten-entry diagnostic history.
Background masks describe already-resolved trusted metadata; this is **not** a
permission-grant API. No Binder method accepts these packets. Other requested
identities are not implicitly installed in the bookkeeping ledger.

This is a new **internal transport**, not Meta's parcel ABI: versioned little-endian
32-bit words, epoch-millisecond timestamps (0..9223372036854), length-prefixed
standard UTF-8, maximum 64 KiB per packet, 256 rows per list, 1024 bytes per text.
Boolean tags must be 0/1; masks 0..3; focus types 0/1. A nullable window means an
explicitly observed absence; nullable foreground metadata entries mean failed
lookups. Required channel arrays cannot be null. Null/invalid/oversized/truncated
packets, invalid UTF-8 and trailing bytes are rejected before mutation. No
externally supplied immersive PID/top client can override the selector.
Java serialization freezes array contents and rejects malformed UTF-16; standard
UTF-8 (including NUL and supplementary characters) is preserved without JNI's
modified-UTF-8 string conversion. The result lists are immutable copies.

The registered client's initial empty bookkeeping set remains unavailable as an
evaluated status until a valid evaluation runs. Evaluation and native handle
lookup/destruction share the registry lock. Invalid input cannot change the
previous decision state. Allocation/delivery failure **after** a valid evaluation
can leave that evaluation committed; no cross-JNI transaction guarantee is made.
No external callbacks run during these operations.

Host ASan/UBSan now includes the packet decoder: truncation at every boundary,
invalid counts/types/masks/timestamps, UTF-8 edge cases, signed integer roundtrip,
and 10,000 deterministic packet mutations. Five Android instrumentation cases
exercise the actual JNI evaluation and readback, channel distinctions, both focus
types, ordered deduplication, background override ordering, selector/history,
Unicode, invalid-packet state preservation and evaluation/close concurrency.
The strict Android report gate requires **33 owned cases per API**.

**Still not a production observer/provider:** no Android component yet assembles
all the required coherent channels or normalized metadata. Frames in the new
instrumentation tests are deliberately labeled fixtures, not phone observations,
permissions or tracking grants. The production Binder backend/pre-Application
publication remain absent. This does not fix the original constructor ANR.

Readback also includes an own-client **evaluated-types mask**. An unqueried type
remains unknown, not an observed loss; a query containing only other identities
does not enable own-client evaluated-state access. The focus mask alone is
bookkeeping, never a substitute for those per-type validity bits or decision rows.

Evaluation transport validation, source **4153a8b**: project/native **37130802378**
passed with 20 native sanitizer cases; arm64 Android build **37130802346** passed;
runtime **37130802416** passed 33 owned cases on each API 29/35. Unlike the earlier
registration-only stage, these Android cases execute the C++ evaluation/selection
and history through JNI, using explicitly constructed fixtures. They do not
execute the original daemon, prove complete observation inputs or fix startup.

## Context-free core bring-up and service-state JNI (2026-10-03)

`NativeFocusClient.createBeforeApplication()` creates an own-process native core
using public OS PID/UID APIs, independently checked in native code. It does not
require Context or infer package names, permission results or focus. Metadata
reads fail explicitly until `attachMetadataContext` succeeds with matching real
identity. Attaching/replacing that reader never reinstalls the native client,
resets the ledger or resets service-state observations.

The JNI entry now owns the recovered `SessionState` reducer as well as the policy
core. Internal `applyAppState` receives the actual Binder caller PID/UID (or the
endpoint's immutable caller captured before dispatch), checks its own-process
scope and requested PID, then uses native `getuid()` as the observed UID. It
accepts only service-local 0/2 as membership-changing/notification-generating
states; other numbers remain ignored. No Activity lifecycle callback is mapped
onto these codes, and they are not OpenXR enum values.

Readback distinguishes **unknown** (no recognized event received) from observed
visible/stopped membership. An adapter-local generation advances for every
recognized event, including duplicates; it is not an original service field.
Required refresh/top-notification/report effects are returned explicitly; a
future backend still must execute them in recovered order outside locks. Reading
state does not replay effects. No policy evaluation or permission grant is
triggered by state reports; last evaluation bookkeeping is not a fresh OS status.
The SessionState `contains` lookup avoids allocation during this readback.

An instrumentation-only AppComponentFactory creates the core before calling
`super.instantiateApplication`. The test Application records identity availability
inside its constructor with `getBaseContext()==null`; the factory releases its
fixture core afterward. This changes **only the test APK manifest**, not the
original Horizon app or the production adapter manifest, and publishes no Binder.
Five new Android cases cover this ordering, late metadata attach, reducer effects,
identity denial without mutation, and independent-core/close concurrency. The
strict runtime gate now requires 38 owned cases per API; CI validation is pending.

This removes Context as a prerequisite for native core allocation, not the
remaining prerequisite of a complete policy/backend before original Application
construction. There is still no original service publication, complete coherent
observer, automatic effects consumer or successful original startup.

Context-free bring-up validation completed for source **fd9767b**: project/native
**37131841181**, Android arm64 build **37131841135**, and runtime **37131841147**
all passed. Instrumentation executed 38 owned cases per API 29/35, including the
constructor-time identity proof with no base Context. This supersedes the pending
CI note above, not the original-app/bootstrap/provider limitations. Service-state
inputs in these cases are explicit fixtures, not an executed original SDK session.

## Session-bound rendering input (2026-10-03)

ARM64 confirms that `getClientsCurrentlyRendering` (`0x21590`, instruction
`215b0`) reads the same `ConnectionManager +0x170` set updated by visible/stopping
at `22580`/`225d4`. `tests/test_focus_session_binding_evidence.py` pins both C
functions and those instructions. Session membership is therefore connected to
**rendering only**, not to any foreground/window/top/display/permission channel.

`FocusPolicyFrame.forSession` marks rendering as delegated with internal packet
tag `MPFS` (`0x5346504d`), distinct from the fully explicit `MPF1` packet. The
unbound evaluator rejects delegated packets rather than treating their empty
wire slot as an empty observation. `evaluateWithSession` checks that the snapshot
belongs to this native token and was produced after a recognized service event.
Native code repeats provenance/generation checks under the same registry lock
used by session updates and destruction, then supplies the actual membership to
`focus_session_binding.hpp` and evaluates without releasing that lock.

This path is explicitly own-process scoped. It requires exactly one resolved
live metadata record for the registered identity, rejects foreign identities in
all feeds and inconsistent resolved foreground metadata, and rejects an explicit
rendering list. Other channels, process-name normalization and resolved permission
masks must still come from a complete trusted producer. Stopping keeps live
metadata: the original shell fallback may still select the shell, and independent
window/foreground observations may still affect focus. No automatic grant or
forced loss is derived from session visibility alone.

The returned evaluation identifies the session generation used. Duplicate
recognized events advance it and invalidate old observations; ignored state codes
do not. Unknown, foreign or stale session observations fail before policy/history
mutation. This is coherence for **one channel**, not an atomic Android snapshot,
not freshness of other feeds, and not execution of the reducer's required effects.
Historical bookkeeping is still not current OS authorization.

Host sanitizers now include session binding (21 native cases total). Four new
Android cases cover selection/stop/shell-fallback behavior, stale/foreign snapshot
rejection, missing/inconsistent metadata and a native race where updates bypass
the Java monitor. The runtime gate requires 42 owned cases per API. Instrumentation
uses explicit remaining-channel/metadata fixtures; production assembly, effects
consumption and Binder publication remain incomplete. Original startup is unchanged.

Session-bound evaluation validation, source **d9fa72c**: project/native
**37133198483**, arm64 Android build **37133198509**, and runtime **37133198738**
all passed. Runtime executed 42 owned cases per API 29/35; native sanitizers
executed 21 cases. The race test bypasses the Java monitor for native updates.
These are owned adapter/policy tests with explicit remaining-channel fixtures,
not original firmware, physical-device or complete-provider validation.

## Positive own-window input bound to native evaluation (2026-10-03)

`NativeWindowFocusInput` relays real `AppWindowFocusBackend` callbacks/polls to
`NativeFocusClient`. It accepts positive own-process focused-window evidence on
Android's `Display.DEFAULT_DISPLAY` only. It does **not** claim global window
ownership, convert Activity lifecycle into XR state, or derive main-display focus.
The existing raw observer retains its other-display observations; this adapter's
scope is deliberately narrower. An empty, late-started or closed observer leaves
the channel **unknown**, not an observed absence of focus.

A native `WindowObservation` tracks one exclusive source, non-reused source
numbers and monotonically advancing observation generations. Refreshing or
closing invalidates previous observations; an old source cannot detach its
replacement. Java owns observer lifecycle on the main thread; closing the native
client first is handled by detaching the observer when it next reports/polls.
There are no notifications under native/client locks.

`FocusPolicyFrame.forObservedInputs` uses internal tag `MPFO` and delegates both
rendering and the window-client input. Other packet paths reject this tag rather
than reading its empty slots as observations. `evaluateWithObservedInputs` checks
both session and window provenance/generations under the native registry lock,
then supplies the actual own identity for the window channel before evaluating.
It still requires explicit independent activity/panel/top/display/permission and
normalized metadata inputs. This is consistency of delivered observations, not
an atomic lock on Android WindowManager or proof of complete input coverage.

Host sanitizers include source ownership/invalidation (22 native cases total).
Three new Android cases exercise actual Activity windows through JNI, show type
0 receiving window focus without inventing type 1 session/display eligibility,
check stale/closed/replaced observers and late-start unknown state, and exercise
thread ownership and client-close cleanup. The strict gate requires 45 owned
cases per API. The window source is real; remaining policy channels/metadata in
these tests are fixtures. No Binder provider/original-app publication is added.
