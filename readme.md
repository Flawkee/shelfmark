# 📚 Shelfmark: Book Search & Request Tool

<img src="src/frontend/public/logo.png" alt="Shelfmark" width="200">

> [!IMPORTANT]
> **This is a fork** of [Shelfmark](https://github.com/calibrain/shelfmark) that adds deep library integration: [Kavita](https://github.com/Kareadita/Kavita) (eBooks/manga) and [Audiobookshelf](https://github.com/advplyr/audiobookshelf) (audiobooks) — single sign-on, per-format availability awareness, request-type controls, and library-aware notifications. See [Library Integration](#-library-integration-kavita--audiobookshelf) below.

> [!NOTE]
> The upstream project is in a stable state as of May 2026 but is not under active maintenance.

## 📖 Library Integration (Kavita + Audiobookshelf)

This fork connects Shelfmark to your reading servers so you stop requesting books and audiobooks you already own. [Kavita](https://github.com/Kareadita/Kavita) covers eBooks/manga; [Audiobookshelf](https://github.com/advplyr/audiobookshelf) covers audiobooks. Each runs as its own scheduled scan and its own availability signal.

### Availability awareness
- A scheduled sync scans your libraries and flags matching search results **per format**. Owned titles show an **eBook in Library** and/or **AudioBook in Library** button instead of *Get*, so they can't be re-requested. Each button links to your configured **Library URL** / **Audiobook Library URL** (General settings).
- A **Library X/N** chip shows how much of a series you already have.
- Matching handles books **and** manga — multi-volume series, titles with subtitles, and library qualifiers like `(Unabridged)` or `(2020)`.

### Request types & policy
- **Per-format requesting** — eBook and Audiobook are tracked separately. If a title is in your library in one format only, the **+ Get** button still appears for the missing format.
- **Require request type** *(admin, off by default)* — force users to explicitly choose eBook or Audiobook before submitting a request.
- **Allow requesting missing types** *(admin, on by default)* — let users request a format that isn't in their library yet, even when the other format already is.
- Admins see an **eBook / Audiobook badge** on every request in the review list.

### Kavita SSO
- Sign in with your Kavita account. A login-page source selector (Local / Kavita, admin-set default) lets local and Kavita users coexist; Kavita logins auto-provision a linked Shelfmark user, and admins keep full control over each user's role.
- **Audiobookshelf auto-provisioning** *(admin, off by default)* — on a successful Kavita login, create the same user in Audiobookshelf if they don't exist yet (Account Type *User*; Can Download, Access All Libraries, Access All Tags, Access Explicit Content), using the credentials that just passed Kavita SSO. Can only be enabled once Audiobookshelf is configured and reachable, and it's strictly best-effort — any Audiobookshelf failure never blocks the Kavita login.

### Notifications
- Get notified (any Apprise destination) when a **new** title is added — separate **eBook Added to Library** and **Audiobook Added to Library** events. Fires only on genuinely new items, never on the initial baseline scan.

### Configure
- **Settings → Kavita** and **Settings → Audiobookshelf** — connection (URL + API key, with a connection test), libraries to sync, cron schedule, and optional re-sync after a download completes.
- **Settings → Security** — set the auth method to *Kavita* for SSO, and enable Audiobookshelf auto-provisioning.
- **Settings → General** — set **Library URL** / **Audiobook Library URL** so the in-library buttons link out.
- **Settings → Users & Requests** — the request-type toggles.

Shelfmark is a self-hosted web interface for searching and requesting books and audiobooks across multiple sources. Bring your own sources, metadata providers, and download clients to build a single hub for your digital library. Supports multiple users with a built-in request system, so you can share your instance with others and let them browse and request books on their own.

Works great alongside the following library tools, with support for automatic imports:
- [Calibre](https://calibre-ebook.com/)
- [Calibre-Web](https://github.com/janeczku/calibre-web)
- [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated)
- [Grimmory](https://github.com/grimmory-tools/grimmory)
- [Audiobookshelf](https://github.com/advplyr/audiobookshelf) — audiobook availability awareness ([details](#-library-integration-kavita--audiobookshelf))
- [Kavita](https://github.com/Kareadita/Kavita) — SSO + eBook/manga availability awareness ([details](#-library-integration-kavita--audiobookshelf))

## ✨ Features

- **One-Stop Interface** - A clean, modern UI to search, browse, and download from multiple configured sources in one place
- **Multiple Sources** - Configurable web, torrent, usenet, and IRC source support
- **Audiobook Support** - Full audiobook search and download with dedicated processing
- **Flexible Search** - Search metadata providers (Hardcover, Open Library, Google Books) for rich book and audiobook discovery, or query configured sources directly
- **Multi-User & Requests** - Share your instance with others, let users browse and request books, and manage approvals with configurable notifications
- **Authentication** - Built-in login, OIDC single sign-on, proxy auth, Calibre-Web database, and **Kavita SSO**
- **Library Awareness** - Flags eBooks, manga & audiobooks already in your [Kavita](https://github.com/Kareadita/Kavita) and [Audiobookshelf](https://github.com/advplyr/audiobookshelf) libraries so users don't re-request them, with per-format buttons, request-type controls, and new-arrival notifications ([details](#-library-integration-kavita--audiobookshelf))
- **Real-Time Progress** - Unified download queue with live status updates across all sources
- **Network Flexibility** - Configurable proxy support, DNS settings, and optional Cloudflare handling for protected sources

## 🖼️ Screenshots

**Home screen**
![Home screen](README_images/homescreen.png 'Home screen')

**Search results**
![Search results](README_images/search-results.png 'Search results')

**Multi-source downloads**
![Multi-source downloads](README_images/multi-source.png 'Multi-source downloads')

**Download queue**
![Download queue](README_images/downloads.png 'Download queue')

## 🚀 Quick Start

> This fork is published to Docker Hub as **[`flawkee/shelfmark`](https://hub.docker.com/r/flawkee/shelfmark)** (`latest` plus version tags such as `1.3.0-c`). The instructions below use the fork image; the Kavita / Audiobookshelf features are all opt-in, so an unconfigured instance behaves exactly like upstream.

### Option A — Docker (recommended)

Prerequisites: Docker & Docker Compose.

1. Create a `docker-compose.yml`:
   ```yaml
   services:
     shelfmark:
       image: flawkee/shelfmark:latest
       container_name: shelfmark
       environment:
         PUID: 1000
         PGID: 1000
       ports:
         - "8084:8084"
       volumes:
         - ./config:/config # Config, database, and artwork cache
         - ./books:/books    # Downloaded books / audiobooks
       restart: unless-stopped
   ```

2. Start it:
   ```bash
   docker compose up -d
   ```

3. Open `http://localhost:8084` and configure the sources/settings you want.

To pin a version, swap `latest` for a tag (e.g. `flawkee/shelfmark:1.3.0-c`).

### Option B — Manual (no container)

Prerequisites: Python 3.14+, Node 24+, [uv](https://docs.astral.sh/uv/), and git.

```bash
git clone https://github.com/Flawkee/shelfmark.git
cd shelfmark

# 1. Python dependencies (add --extra browser for the built-in Cloudflare/Selenium stack)
uv sync --locked

# 2. Build the frontend and stage it where the backend serves it (./frontend-dist)
cd src/frontend && npm ci && npm run build && cd ../..
rm -rf frontend-dist && cp -r src/frontend/dist frontend-dist
#   Windows (PowerShell): Remove-Item -Recurse -Force frontend-dist; Copy-Item -Recurse src\frontend\dist frontend-dist

# 3. Point Shelfmark at local data dirs and run it
export CONFIG_DIR="$(pwd)/config"        # app config + database
export INGEST_DIR="$(pwd)/books"         # download destination
export USING_EXTERNAL_BYPASSER=true      # skip the built-in browser; omit if you ran `uv sync --extra browser`
uv run gunicorn \
  --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  --workers 1 -t 300 -b 0.0.0.0:8084 \
  shelfmark.main:app
```

Then open `http://localhost:8084`. (On Windows, set the env vars with `$env:CONFIG_DIR=...` before the `uv run` command.)

### Volume Setup

```yaml
volumes:
  - /your/config/path:/config # Config, database, and artwork cache directory
  - /your/download/path:/books # Downloaded books
  - /client/path:/client/path # Optional: For Torrent/Usenet downloads, match your client directory exactly.
```

> **Tip**: Point the download volume to your CWA or Grimmory ingest folder for automatic import.

> **Note**: CIFS shares require `nobrl` mount option to avoid database lock errors.

### Non-root container mode

- Start the container as `1000:1000` with Docker `user: "1000:1000"` or `docker run --user 1000:1000`.
- For Kubernetes, set `runAsUser: 1000`, `runAsGroup: 1000`, and `runAsNonRoot: true` together.
- `PUID`/`PGID` keep the default root startup flow.
- Mounted paths must already be writable by `1000:1000`.
- `USING_TOR=true` requires root startup.

## ⚙️ Configuration

### Search Modes

**Direct**
- Queries configured sources directly

**Universal** (recommended)
- Search via metadata providers (Hardcover, Open Library, Google Books) for richer results
- Aggregates releases from multiple configured sources
- Full audiobook support

### Environment Variables

Environment variables work for initial setup and Docker deployments. They serve as defaults that can be overridden in the web interface.

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_PORT` | Web interface port | `8084` |
| `INGEST_DIR` | Book download directory | `/books` |
| `TZ` | Container timezone | `UTC` |
| `PUID` / `PGID` | Runtime user/group for the default root-startup flow (also supports legacy `UID`/`GID`) | `1000` / `1000` |
| `SEARCH_MODE` | `direct` or `universal` | `universal` |
| `USING_TOR` | Enable Tor routing (requires root startup) | `false` |

See the full [Environment Variables Reference](docs/environment-variables.md) for all available options.

Some of the additional options available in Settings:
- **Prowlarr** - Configure indexers and download clients to download books and audiobooks
- **Additional audiobook sources** - Configure additional sources for audiobook discovery
- **IRC** - Add details for IRC book sources and download directly from the UI
- **Library Link** - Add a link to your Calibre-Web or Grimmory instance in the UI header
- **File processing** - Customiseable download paths, file renaming and directory creation with template-based renaming
- **Network Settings** - Custom proxy support (SOCKS5 + HTTP/S) and configurable DNS
- **Format & Language** - Filter downloads by preferred formats, languages and sorting order
- **Metadata Providers** - Configure API keys for Hardcover, Open Library, etc.

## 🐳 Docker Variants

### Standard
```bash
docker compose up -d
```

The full-featured image with all network capabilities included.

#### Tor Routing
Optional Tor support for network privacy:
```bash
curl -O https://raw.githubusercontent.com/calibrain/shelfmark/main/compose/docker-compose.tor.yml
docker compose -f docker-compose.tor.yml up -d
```

**Notes:**
- Requires root startup
- Requires `NET_ADMIN` and `NET_RAW` capabilities
- Timezone is auto-detected from Tor exit node
- Custom DNS/proxy settings are ignored when Tor is active

### Lite
A lighter image without the built-in browser automation. Ideal for:

- **External services** - Already running FlareSolverr or similar for other applications
- **Alternative sources** - Using Prowlarr, IRC, or other configured sources
- **Audiobooks** - Using Shelfmark primarily for audiobooks

```bash
curl -O https://raw.githubusercontent.com/calibrain/shelfmark/main/compose/docker-compose.lite.yml
docker compose -f docker-compose.lite.yml up -d
```

If you need browser-based access with the Lite image, configure an external resolver in Settings.

## 🔐 Authentication

Authentication is optional but recommended for shared or exposed instances. Multiple authentication methods are available in Settings:

**1. Single Username/Password**

**2. Proxy (Forward) Authentication**

Proxy auth trusts headers set by your reverse proxy (e.g. `X-Auth-User`). Ensure Shelfmark is not directly exposed, and configure your proxy to strip/overwrite these headers for all inbound requests.

**3. OIDC (OpenID Connect)**

Integrate with your identity provider (Authelia, Authentik, Keycloak, etc.) for single sign-on. Supports PKCE flow, auto-discovery, group-based admin mapping, and auto-provisioning of new users.

**4. Calibre-Web Database**

If you're running Calibre-Web, you can reuse its user database by mounting it:

```yaml
volumes:
  - /path/to/calibre-web/app.db:/auth/app.db:ro
```

### Multi-User Support

With any authentication method enabled, Shelfmark supports multi-user management with admin/user roles. Users can have per-user settings for download destinations, email recipients, and notification preferences. Non-admin users only see their own downloads and can submit book requests for admin review. Admins can configure request policies per source to control whether users can download directly, must submit a request, or are blocked entirely.

## Project Scope

Shelfmark is a manual search and download tool, the entry point to your book library, not a library manager. It finds books, downloads them, and sends them to a configured destination. That's the full scope.

Shelfmark intentionally does not:

- **Track or manage your library** - it doesn't know or care what you already own
- **Integrate with library software** - what happens after delivery is up to your library tool
- **Monitor authors, series, or new releases** - there is no background automation
- **Queue future downloads** - if a book isn't available now, Shelfmark won't watch for it

These are non-goals, not missing features.

## Contributing

Shelfmark's core feature set is complete. Development focuses on stability, bug fixes, quality-of-life improvements, and refining the search experience. Contributions in these areas are welcome, please file issues or submit pull requests on GitHub.

Feature requests that fall outside the project scope (library integration, automation, collection management) will be closed. If you're unsure whether something fits, open a discussion first.

## Health Monitoring

The application exposes a health endpoint at `/api/health` (no authentication required). Add a health check to your compose:

```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:8084/api/health"]
  interval: 30s
  timeout: 30s
  retries: 3
```

## Logging

Logs are available via:
- `docker logs <container-name>`
- `/var/log/shelfmark/` inside the container (when `ENABLE_LOGGING=true`)

Log level is configurable via Settings or `LOG_LEVEL` environment variable.

## Development

```bash
# Quality checks
make checks              # Run ALL static analysis (frontend + Python)
make python-checks       # Run Ruff, BasedPyright, and Vulture
make install-python-dev  # Sync Python runtime + dev tools with uv

# Frontend development
make install     # Install dependencies
make dev         # Start Vite dev server (localhost:5173)
make build       # Production build
make frontend-typecheck  # TypeScript checks

# Backend (Docker)
make up          # Start backend via docker-compose.dev.yml
make down        # Stop services
make refresh     # Rebuild and restart
make restart     # Restart container
```

The frontend dev server proxies to the backend on port 8084.

## License

MIT License - see [LICENSE](LICENSE) for details.

## ⚠️ Disclaimer

Shelfmark is a search interface that displays results from external metadata providers and sources. It does not host, store, or distribute any content. The developers are not responsible for how the tool is used or what is accessed through it.

Users are solely responsible for:
- Ensuring they have the legal right to download any material they access
- Complying with copyright laws and intellectual property rights in their jurisdiction
- Understanding and accepting the terms of any sources they configure

Use of this tool is entirely at your own risk.

## Support

For issues or questions, please [file an issue](https://github.com/calibrain/shelfmark/issues) on GitHub.
