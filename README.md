# Mistral → WordPress (Django + PostgreSQL)

Django app that turns a script into a **WordPress draft** via Mistral + XML-RPC, stores rows in **PostgreSQL**, and emails you links to **review the draft in wp-admin** and **publish in one click** (Django signed URL → `wp.editPost`). Defaults match the standalone scripts’ env vars.

This project is set up to use:

- **Database name:** `mistraldb`
- **Database user:** `mistraldbuser`

---

## 1. Prerequisites

- **Python 3.10+** (3.12/3.13 OK)
- **PostgreSQL** installed and running (service listening on port `5432` by default)
- **pip**

On Windows, PostgreSQL installers add `psql` to your PATH, or use the full path, for example:

`"C:\Program Files\PostgreSQL\16\bin\psql.exe"`

Adjust the version folder (`16`, `17`, …) to match your install.

---

## 2. Create the database and user (PostgreSQL)

Connect as a **superuser** (often `postgres`):

```bash
psql -U postgres -h localhost -p 5432
```

Run (pick your own password and replace `your_password_here`):

```sql
CREATE ROLE mistraldbuser WITH LOGIN PASSWORD 'your_password_here';
CREATE DATABASE mistraldb OWNER mistraldbuser;
\q
```

### PostgreSQL 15+ (`public` schema permissions)

If `python manage.py migrate` fails with a permission error on `public`, run:

```bash
psql -U postgres -h localhost -p 5432 -d mistraldb
```

```sql
ALTER SCHEMA public OWNER TO mistraldbuser;
GRANT ALL ON SCHEMA public TO mistraldbuser;
\q
```

### Verify

```bash
psql -U mistraldbuser -h localhost -p 5432 -d mistraldb
```

(Enter `your_password_here` when prompted.) Type `\q` to exit.

### Connect with DBeaver (GUI)

You can use **[DBeaver](https://dbeaver.io/)** to browse `mistraldb`, run SQL, and inspect Django tables after `migrate`.

#### What you need (nothing extra beyond this)

| Requirement | Notes |
|-------------|--------|
| **DBeaver installed** | Community edition is enough. |
| **PostgreSQL running** | Windows: *Services* (`services.msc`) → **postgresql**-*version* → Running. If the service is stopped, DBeaver cannot connect. |
| **Database and login role exist** | `mistraldb` + `mistraldbuser` (see SQL in section 2 above). DBeaver does not create them for you unless you run that SQL yourself (see below). |
| **Network** | Local: **Host** `localhost`, **Port** `5432`. Remote: use the server hostname/IP, open the firewall for `5432` if needed, and often enable **SSL** on the connection. |
| **JDBC driver** | First **Test Connection**: DBeaver prompts to download the PostgreSQL driver — you only need to accept once. |
| **Tables visible** | Django creates tables when you run `python manage.py migrate`. Before that, `mistraldb` may be empty under *Schemas → public → Tables*. |

You do **not** need a separate DBeaver plugin, Docker, or a paid DBeaver edition for basic browsing and SQL.

#### Suggested order (first time)

1. Install PostgreSQL and ensure its **service is running**.
2. Create `mistraldbuser` + `mistraldb` (via `psql` **or** DBeaver as `postgres` — next subsection).
3. In DBeaver, add a connection as **`mistraldbuser`** / **`mistraldb`** and **Test Connection**.
4. Run **`python manage.py migrate`** from the Django project, then refresh tables in DBeaver (F5) to see `blog_blogentry`, `auth_user`, etc.

#### Create the database using DBeaver (instead of `psql`)

1. New connection → **PostgreSQL** → **Main**: **Database** `postgres`, **Username** `postgres`, **Password** (superuser password) → Test → Finish.
2. Open **SQL Editor** for that connection (toolbar or right-click → **SQL Editor**).
3. Run:

   ```sql
   CREATE ROLE mistraldbuser WITH LOGIN PASSWORD 'your_password_here';
   CREATE DATABASE mistraldb OWNER mistraldbuser;
   ```

4. Add a **second** connection: **Database** `mistraldb`, **Username** `mistraldbuser`, **Password** `your_password_here` — use this for day-to-day work.

If **Test Connection** fails on `mistraldb` before the database exists, that is expected until step 3 completes.

#### Connection settings (app user)

1. Install DBeaver Community (or your edition) and open it.
2. Click **New Database Connection** (plug icon) → choose **PostgreSQL** → **Next**.
3. **Main** tab — match your Django `.env`:

   | Field | Value |
   |--------|--------|
   | **Host** | `localhost` (or `127.0.0.1`) |
   | **Port** | `5432` |
   | **Database** | `mistraldb` |
   | **Username** | `mistraldbuser` |
   | **Password** | the password from `CREATE ROLE` |

4. Local dev: **SSL** tab → often *Disable* or default. Hosted DB (RDS, Azure, etc.): enable **SSL** and use the provider’s CA if required.
5. **Test Connection** → download driver if prompted → **Finish**.
6. Navigate **Databases → mistraldb → Schemas → public → Tables** (refresh after `migrate`).

**JDBC URL** (for reference): `jdbc:postgresql://localhost:5432/mistraldb`

### Optional: use only the `postgres` user

If you prefer not to create `mistraldbuser`, you can `CREATE DATABASE mistraldb;` and set `PGUSER=postgres` and `PGPASSWORD=` accordingly in `.env`. Defaults in Django are tuned for `mistraldb` + `mistraldbuser`.

---

## 3. Configure environment variables

1. Copy `env.example` to **`mistral_wp_django/.env`** and/or merge into the **repo root** `.env` (settings load **repo root `.env` first**, then `mistral_wp_django/.env`).
2. Set at least:

| Variable | Example for this project |
|----------|---------------------------|
| `PGDATABASE` | `mistraldb` |
| `PGUSER` | `mistraldbuser` |
| `PGPASSWORD` | same as in `CREATE ROLE` |
| `PGHOST` | `localhost` |
| `PGPORT` | `5432` |
| `MISTRAL_API_KEY` | from Mistral console |
| `WORDPRESS_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APPLICATION_PASSWORD` | WordPress XML-RPC |
| `DJANGO_SECRET_KEY` | long random string (required in production) |
| `SITE_BASE_URL` | Public base URL of this Django app, **no trailing slash** (used in the email for the one-click publish link). Example: `http://127.0.0.1:8000` locally; use your LAN IP or HTTPS tunnel if you open mail on your phone. |
| `NOTIFICATION_EMAIL` | Inbox for draft notifications (default `vaatrak@gmail.com`). |
| `DEFAULT_FROM_EMAIL`, `EMAIL_*` | SMTP (e.g. Gmail + app password). See `env.example`. For dev, `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` prints mail to the terminal. |
| `EMAIL_USE_SSL` | Set `true` with port **465** and **`EMAIL_USE_TLS=false`** if you get **Connection unexpectedly closed** on 587. |
| `EMAIL_TIMEOUT` | SMTP socket timeout in seconds (default `60`). |
| `WORDPRESS_DEFAULT_CATEGORY` | Optional; used when the form leaves category blank. |

### Troubleshoot email

From `mistral_wp_django/`:

```bash
python manage.py test_email --dry-run   # show settings (password length only)
python manage.py test_email             # SMTP login + send test to NOTIFICATION_EMAIL
python manage.py test_email --verbose   # raw SMTP protocol on stderr
```

If the command succeeds but the web app still reports failures, restart `runserver` after `.env` changes and confirm the app loads the same `.env` (repo root vs `mistral_wp_django/.env`).

### Draft → email → one-click publish

1. Open **`/new/`**, paste your script, submit. Mistral generates content; **`wp.newPost`** creates a **draft** on WordPress.
2. An email goes to **`NOTIFICATION_EMAIL`** with: wp-admin edit URL, public `?p=` URL, and a **publish** URL on this Django site (`/publish/<entry-id>/<secret>/`).
3. Opening the publish URL calls **`wp.editPost`** to set **`post_status=publish`**, then invalidates the secret.

---

## 4. Install Python dependencies

```bash
cd mistral_wp_django
pip install -r requirements.txt
```

(Use a virtual environment if you prefer: `python -m venv .venv` then activate it before `pip install`.)

---

## 5. Apply database migrations

```bash
python manage.py migrate
```

This creates Django’s tables (including `blog_blogentry`) in **`mistraldb`**.

---

## 6. Create an admin user (optional but useful)

```bash
python manage.py createsuperuser
```

Use this to log in at `/admin/` and inspect `BlogEntry` rows.

---

## 7. Run the development server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/**

- **New draft** — paste a script (optional title/category). Creates a WordPress **draft**, saves a `BlogEntry`, sends **email** with review + publish links.
- **Entry** — preview stored content and copy links if needed.

---

## 8. Quick reference (all commands in order)

```bash
# 1) PostgreSQL (in psql as superuser)
CREATE ROLE mistraldbuser WITH LOGIN PASSWORD 'your_password_here';
CREATE DATABASE mistraldb OWNER mistraldbuser;
\q

# 2) App directory
cd mistral_wp_django

# 3) Env: copy env.example → .env and edit PGPASSWORD etc.

# 4) Python
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `fe_sendauth: no password supplied` | Set `PGPASSWORD` in `.env`. |
| `connection refused` | Start the PostgreSQL service; check `PGHOST` / `PGPORT`. |
| DBeaver “Connection refused” / timeout | Same as above; confirm host/port; for a remote server, allow firewall and use its hostname, not `localhost`. |
| DBeaver authentication failed | User/password mismatch; use `mistraldbuser` + role password, or `postgres` for admin tasks. |
| Migrate permission errors on PG 15+ | `ALTER SCHEMA public OWNER TO mistraldbuser;` (see section 2). |
| Mistral errors | Confirm `MISTRAL_API_KEY` in `.env` and model access. |
| WordPress errors | XML-RPC enabled; user can post. |

---

## Related files in the repo (unchanged)

- `generate_blog_entry.py` — standalone Mistral generation  
- `post_to_wordpress_xmlrpc.py` — standalone WordPress XML-RPC posting  

Logic lives in `blog/services/` for Django; keep secrets only in `.env`, not in git.
