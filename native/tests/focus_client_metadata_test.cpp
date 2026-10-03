// SPDX-License-Identifier: GPL-3.0-only
#include "focus_client_metadata.hpp"
#include <atomic>
#include <cassert>
#include <set>
#include <string>
#include <thread>
#include <vector>

using namespace metaport::focus;

int main() {
    // 1. Missing UID returns nullopt and never caches a record.
    ClientMetadataCache cache;
    assert(!resolve_client_metadata(ClientProcessObservation{100, std::nullopt, "app", {"pkg"}, true, true}).has_value());
    assert(!cache.build_client_info(ClientProcessObservation{100, std::nullopt, "app", {"pkg"}, true, true}).has_value());
    assert(cache.size() == 0);

    // 2. Single-package UID vs multi-package UID disambiguation (0x10cb8..0x10fd8).
    auto single = resolve_client_metadata(ClientProcessObservation{
        101, 10010, "custom.process:worker", {std::string("pkg.single\0trailing", 19)}, false, false});
    assert(single.has_value());
    assert((single->identity == Client{10010, 101}));
    assert(single->package_name == "pkg.single");
    assert(single->metadata_process_name == "custom.process:worker");
    assert(single->allowed_background_mask() == 0);

    // Multi-package UID: prefix before ':' matches one of the UID packages ->
    // package_name receives the full metadata_process_name (including ":sub").
    auto multi_match = resolve_client_metadata(ClientProcessObservation{
        102, 10011, "pkg.two:sub", {"pkg.one", "pkg.two", "pkg.three"}, false, false});
    assert(multi_match.has_value());
    assert(multi_match->package_name == "pkg.two:sub");

    // Multi-package UID: no prefix match -> package_name stays empty.
    auto multi_miss = resolve_client_metadata(ClientProcessObservation{
        103, 10011, "unmatched:sub", {"pkg.one", "pkg.two"}, false, false});
    assert(multi_miss.has_value());
    assert(multi_miss->package_name.empty());

    // Empty package list -> package_name stays empty unless system_server overrides.
    auto empty_pkgs = resolve_client_metadata(ClientProcessObservation{
        104, 10012, "native_proc", {}, false, false});
    assert(empty_pkgs.has_value());
    assert(empty_pkgs->package_name.empty());

    // 3. system_server override (0x10fdc..0x11084): overrides single/multi/empty packages.
    auto sys_server = resolve_client_metadata(ClientProcessObservation{
        105, 1000, "system_server", {"com.android.settings"}, false, false});
    assert(sys_server.has_value());
    assert(sys_server->package_name == "android.uid.system:1000");

    // Embedded NUL in "system_server\0extra" does NOT match full std::string equality.
    auto fake_sys_server = resolve_client_metadata(ClientProcessObservation{
        106, 1000, std::string("system_server\0extra", 19), {"pkg.only"}, false, false});
    assert(fake_sys_server.has_value());
    assert(fake_sys_server->package_name == "pkg.only");

    // 4. Background focus permissions, root, package allowlist, and daemon allowlist (0x11088..0x114a8).
    auto head_only = resolve_client_metadata(ClientProcessObservation{
        110, 10020, "app.head", {"app.head"}, true, false});
    assert(head_only->allowed_background_mask() == 1);

    auto input_only = resolve_client_metadata(ClientProcessObservation{
        111, 10021, "app.input", {"app.input"}, false, true});
    assert(input_only->allowed_background_mask() == 2);

    auto root_proc = resolve_client_metadata(ClientProcessObservation{
        112, 0, "root_helper", {}, false, false});
    assert(root_proc->allowed_background_mask() == 3);

    for (std::string_view pkg : kAllowlistedBackgroundPackages) {
        auto allow_pkg = resolve_client_metadata(ClientProcessObservation{
            113, 10050, std::string(pkg), {std::string(pkg)}, false, false});
        assert(allow_pkg->allowed_background_mask() == 3);
    }

    // Multi-package with ":sub" makes package_name "com.oculus.vrshell:sub", which does NOT
    // match exact std::unordered_set<std::string> lookup in DAT_0013d1c8.
    auto suffixed_shell = resolve_client_metadata(ClientProcessObservation{
        114, 10050, "com.oculus.vrshell:sub", {"com.oculus.vrshell", "other.pkg"}, false, false});
    assert(suffixed_shell->package_name == "com.oculus.vrshell:sub");
    assert(suffixed_shell->allowed_background_mask() == 0);

    // Daemon allowlist requires BOTH exact binary path AND exact UID (1041 or 1000).
    auto audio_ok = resolve_client_metadata(ClientProcessObservation{
        115, 1041, "/system/bin/audioserver", {}, false, false});
    assert(audio_ok->allowed_background_mask() == 3);
    auto audio_wrong_uid = resolve_client_metadata(ClientProcessObservation{
        116, 1000, "/system/bin/audioserver", {}, false, false});
    assert(audio_wrong_uid->allowed_background_mask() == 0);

    auto mr_ok = resolve_client_metadata(ClientProcessObservation{
        117, 1000, "/system_ext/bin/mrsystemservice", {}, false, false});
    assert(mr_ok->allowed_background_mask() == 3);
    auto mr_wrong_uid = resolve_client_metadata(ClientProcessObservation{
        118, 1041, "/system_ext/bin/mrsystemservice", {}, false, false});
    assert(mr_wrong_uid->allowed_background_mask() == 0);

    // 5. Cache lifecycle: buildClientInfo (0x10aa0), getClientInfo (0x118e0),
    // add/removeCurrentFocus (0x12bc0 / 0x12de0), and getSnapshot (0x13400).
    auto built = cache.build_client_info(ClientProcessObservation{
        200, 10100, "initial.proc", {"pkg.app"}, true, false});
    assert(built.has_value() && built->allowed_background_mask() == 1);
    assert(cache.add_current_focus(Client{10100, 200}, FocusType::Type0));
    assert(!cache.add_current_focus(Client{99999, 200}, FocusType::Type1));

    // getClientInfo refreshes returned copy's metadata_process_name without mutating map entry.
    auto looked_up = cache.get_client_info(Client{10100, 200}, "renamed.proc");
    assert(looked_up.has_value());
    assert(looked_up->metadata_process_name == "renamed.proc");
    assert(looked_up->current_focus_mask() == 1);
    assert(cache.peek_cached_for_pid(200)->metadata_process_name == "initial.proc");

    // buildClientInfo on cache hit delegates to getClientInfo: preserves current_focus
    // and refreshes returned copy's metadata_process_name without rebuilding permissions.
    auto hit = cache.build_client_info(ClientProcessObservation{
        200, 10100, "second.rename", {"other.ignored"}, false, true});
    assert(hit.has_value());
    assert(hit->package_name == "pkg.app");
    assert(hit->metadata_process_name == "second.rename");
    assert(hit->allowed_background_mask() == 1);
    assert(hit->current_focus_mask() == 1);

    // UID mismatch on getClientInfo erases the cached PID entry (0x11af8).
    assert(!cache.get_client_info(Client{10101, 200}, "stale").has_value());
    assert(!cache.peek_cached_for_pid(200).has_value());

    // Reinstall and test UID replacement inside buildClientInfo directly.
    cache.build_client_info(ClientProcessObservation{200, 10100, "old", {"pkg.old"}, false, false});
    cache.add_current_focus(Client{10100, 200}, FocusType::Type1);
    auto replaced = cache.build_client_info(ClientProcessObservation{
        200, 10200, "new", {"pkg.new"}, false, true});
    assert(replaced.has_value());
    assert((replaced->identity == Client{10200, 200}));
    assert(replaced->package_name == "pkg.new");
    assert(replaced->allowed_background_mask() == 2);
    assert(replaced->current_focus_mask() == 0);

    // getSnapshot prunes dead PIDs and orders surviving records by (uid, pid).
    cache.build_client_info(ClientProcessObservation{300, 10050, "alive.low.uid", {"pkg.a"}, false, false});
    cache.build_client_info(ClientProcessObservation{150, 10300, "dead.high.uid", {"pkg.b"}, false, false});
    auto snapshot = cache.get_snapshot([](std::int32_t pid) { return pid != 150; });
    assert(snapshot.size() == 2);
    assert((snapshot[0].identity == Client{10050, 300}));
    assert((snapshot[1].identity == Client{10200, 200}));
    assert(!cache.peek_cached_for_pid(150).has_value());

    // 6. Concurrent stress test for TSan.
    std::thread writer([&] {
        for (int i = 0; i < 300; ++i) {
            cache.build_client_info(ClientProcessObservation{
                400 + (i % 4), 10000 + (i % 2), "proc", {"pkg"}, (i & 1) != 0, (i & 2) != 0});
            cache.add_current_focus(Client{10000 + (i % 2), 400 + (i % 4)}, FocusType::Type0);
            cache.remove_current_focus(Client{10000 + (i % 2), 400 + (i % 4)}, FocusType::Type0);
        }
    });
    std::thread reader([&] {
        for (int i = 0; i < 300; ++i) {
            (void)cache.get_client_info(Client{10000 + (i % 2), 400 + (i % 4)}, "refresh");
            (void)cache.get_snapshot([](std::int32_t pid) { return (pid & 1) == 0; });
        }
    });
    writer.join();
    reader.join();
    return 0;
}
