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
