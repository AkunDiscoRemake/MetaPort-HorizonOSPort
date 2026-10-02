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
requires sixteen owned cases per API; the new cases require a fresh CI run.

**Remaining bootstrap work:** actual focus policy and listener ownership/death
handling; integration with the real window/session backends; original-proxy
interoperability; publication before ShellApplication construction. The endpoint
is not packaged into or published to the original shell yet. No constructor wait
is bypassed, no XR/hand/tracking grants are fabricated, and no functional APK is
claimed.
