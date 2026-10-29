# r/termux — post prêt (de préférence APRÈS un test sur un vrai téléphone ; sinon garder la phrase « looking for testers »)

**Title:** Response cache + boot script for llama.cpp in Termux — looking for testers on real devices

**Body:**
> AI disclosure: code and post drafted with an AI assistant; tested on Linux, **not yet on a phone**.

SeedMesh (https://github.com/Kidaouene/seedmesh, Apache-2.0) caches llama.cpp answers in SQLite, so a repeated prompt returns in milliseconds instead of re-generating. The Termux-specific parts:
- `install_termux.sh` (installs deps with `pkg`, builds llama.cpp from source), `seedmesh start|stop|status`
- `android/termux_boot_seedmesh.sh` for **Termux:Boot** (takes `termux-wake-lock`, waits 20 s, starts services). Revert: delete the file.
- `android/adb_tune.sh status|apply|revert`: disables the phantom process killer the documented way (Android 12: `device_config max_phantom_processes`; 12L+: `settings_enable_monitor_phantom_procs false`), with automatic backup and exact revert.

On a desktop CPU: ~89 ms cache hit vs ~4 s generation (Qwen2.5-1.5B Q4_K_M). I have **no phone numbers yet**. If you try it, please run `python repro_check.py manifest` and share device/SoC/Android version, tok/s and whether Android killed the process.

Reminder: install Termux and its plugins from the same source (F-Droid or GitHub).
