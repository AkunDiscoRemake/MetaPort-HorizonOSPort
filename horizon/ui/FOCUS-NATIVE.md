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
