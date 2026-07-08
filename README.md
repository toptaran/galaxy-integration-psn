# GOG Galaxy PlayStation Network Integration

Community plugin for **GOG Galaxy 2.1.3+** that syncs your PlayStation Network library, play time, and trophies into Galaxy.

**Plugin GUID:** `38087aea-3c30-439f-867d-ddf9fae8fe6f`

## Requirements

- GOG Galaxy **2.1.3 or newer** (ships with Python 3.13)
- **Not compatible with GOG Galaxy 2.0.x** (Python 3.7) — update Galaxy before installing
- Windows 10/11 64-bit or macOS Sonoma 14+

## Install from GitHub Release (recommended)

1. Download **`windows.zip`** or **`macos.zip`** from the [latest release](https://github.com/FriendsOfGalaxy/galaxy-integration-psn/releases/latest).
2. Fully quit GOG Galaxy.
3. Extract the zip into a new folder under the plugins directory:

   Windows: `%LOCALAPPDATA%\GOG.com\Galaxy\plugins\installed\psn_38087aea-3c30-439f-867d-ddf9fae8fe6f`

   macOS: `~/Library/Application Support/GOG.com/Galaxy/plugins/installed/psn_38087aea-3c30-439f-867d-ddf9fae8fe6f`

   The folder must contain `manifest.json` and `plugin.py` at the top level (not nested inside another folder).

4. Restart Galaxy → **Add games and friends** → connect **PlayStation Network**.

To update: quit Galaxy, replace the plugin folder contents with the new release zip, restart.

### Migrating from the pre-1.1.0 GUID

If you installed a community build under `psn_e4b92a16-7f3c-4d8a-9e1b-2c6f8a3d5e7b`, quit Galaxy, delete that folder, install into `psn_38087aea-3c30-439f-867d-ddf9fae8fe6f` above, move `npsso.token` if you use one, then reconnect PSN in Galaxy. `invoke install` removes the legacy folder automatically when Galaxy is quit.

## Install from source

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python **3.13** for development (matches GOG Galaxy's bundled runtime).

```bash
git clone https://github.com/FriendsOfGalaxy/galaxy-integration-psn
cd galaxy-integration-psn
git checkout galaxy-2.1
uv venv --python 3.13
uv pip install -r requirements/dev.txt
```

`invoke` is installed into `.venv`, not globally. Activate the venv before running it:

```powershell
# Windows (PowerShell)
.venv\Scripts\activate
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Your prompt should show `(.venv)`. Then fully quit GOG Galaxy and install the plugin:

```bash
invoke install
```

Alternatively, skip activation and use `uv run` (works for all `invoke` commands below):

```bash
uv run invoke install
```

## Authentication (NPSSO)

Sony blocks sign-in inside Galaxy's embedded browser. Use an NPSSO token from your **system browser**.

### Recommended: token file

1. Sign in at [store.playstation.com](https://store.playstation.com/)
2. Open [ca.account.sony.com/api/v1/ssocookie](https://ca.account.sony.com/api/v1/ssocookie) and copy the `npsso` value
3. Save it as `npsso.token` (one line, no quotes) in the plugin folder above
4. Restart Galaxy and click **Connect** — no popup needed

See `src/npsso.token.example`. Tokens last ~2 months. Delete `npsso.token` or disconnect to sign out.

### Alternative: Galaxy auth window

Click **Connect** → use **Open** (or **Copy**) for the store and NPSSO pages in your system browser → paste the token into the form → **Connect**.

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Library (PS4/PS5 purchases) | ✅ | Paginated GraphQL |
| Recently played games | ✅ | REST API, full pagination |
| PS3 / PS Vita trophy titles | ✅ | From trophy library (legacy NPWR IDs) |
| Game time | ✅ | Play duration + last played |
| Trophies / achievements | ✅ | Per-game import with GOG-compatible IDs |
| Friend leaderboards | ✅ | Per-game trophy % and play time vs PSN friends |
| Friends sidebar | ❌ | PSN friends import; Galaxy rarely shows them in the main Friends panel |
| Install / launch | ❌ | Not supported (PSN is a remote library) |
| PS Plus flag | ⚠️ | Often unavailable from profile API |
| PS Plus catalog games | ⚠️ | Best-effort from store page |

First sync can take several minutes on large libraries (600+ titles). Trophy import runs per game and reports progress in the plugin log.

## How trophies appear in Galaxy

Two systems must agree:

1. **This plugin (PSN API)** — reports which trophies you unlocked (`NPWR12345_00_3` + unlock time) for each game ID (`CUSA…` / `PPSA…`).
2. **GOG GamesDB** — supplies the trophy list Galaxy displays (names, icons, rarity, completion %).

When GOG has a trophy catalog for your PSN title ID, progress matches (e.g. older PS4 games). When GOG does **not** have that catalog yet, Galaxy shows **Achievements N/A** even though the plugin sent unlock data. Game time still works because it does not depend on the trophy catalog.

This is a Galaxy platform limitation, not a sync failure. Reporting missing titles to GOG support (with the PSN ID from logs) helps.

## Unknown games in Galaxy

Galaxy resolves cover art and metadata via its GamesDB (`external_releases` for PSN title IDs). **UNKNOWN GAME** tiles usually mean GOG has not catalogued that title yet — common for PS3, PS Vita, and niche PS4/PS5 releases. The plugin still sends the correct name; Galaxy just cannot merge it into a known entry.

Seeing many unknown tiles alongside a large library is expected and often a sign the PS3/Vita expansion is working.

## Logs

`%PROGRAMDATA%\GOG.com\Galaxy\logs\plugin-psn-38087aea-3c30-439f-867d-ddf9fae8fe6f.log`

Useful lines after sync:

- `Total library titles: …` — merged library size
- `Trophies for CUSA…: N unlocked` — per-game trophy fetch
- `Trophy import finished: N games with unlocks (M total trophies), K games empty` — import summary

## Development

With the venv activated (see **Install from source**), or prefix commands with `uv run`:

```bash
invoke test      # unit tests
invoke build     # build/ folder only
invoke release   # build/ + dist/windows.zip or dist/macos.zip
invoke install   # build + copy to Galaxy plugins dir (quit Galaxy first)
```

Builds use **uv** to install Python 3.13 wheels into `build/`. Tag a release with `git tag v1.1.0 && git push origin v1.1.0` to trigger GitHub Actions, which publishes `windows.zip` and `macos.zip`.

## Credits

Partially based on work by others:

- https://github.com/jhewt/gumer-psn
- https://github.com/Tustin/psn-php
- https://github.com/mgp25/psn-api
- https://github.com/adrianzhang/wechat-psn-backend

## Disclaimer

Unofficial community integration using reverse-engineered PSN endpoints. Not affiliated with Sony or GOG. Use at your own risk.
