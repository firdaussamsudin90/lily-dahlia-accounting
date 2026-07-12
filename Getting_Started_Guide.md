# Getting Started — Cloud Deployment

This app moved from "runs on your Mac" to "runs in the cloud" because there wasn't enough
free disk space on this machine to run it locally. The data now lives in **Supabase**
(a hosted Postgres database + file storage), and the app itself is hosted for free on
**Streamlit Community Cloud**. Nothing is stored on your Mac anymore except a copy of the code.

You'll need to do a few things yourself — they require your own accounts, so I can't do them
for you. Everything below is free (Supabase and Streamlit Community Cloud both have free tiers
that are plenty for a single small business's bookkeeping).

## 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and sign up (GitHub login is fastest).
2. Click **New project**. Pick any name (e.g. `lily-dahlia-accounting`), set a database
   password (save it somewhere — you'll need it in a moment), pick the region closest to you,
   and create the project. It takes a minute or two to provision.
3. Once it's ready, go to **Settings → Database**. Under **Connection string**, choose the
   **URI** tab and the **Session pooler** connection mode. Copy that string — it looks like:
   ```
   postgresql://postgres.xxxxxxxx:[YOUR-PASSWORD]@aws-0-xx-xxxx-1.pooler.supabase.com:5432/postgres
   ```
   Replace `[YOUR-PASSWORD]` with the database password you set in step 2. This is your
   `DATABASE_URL`.
4. Go to **Settings → API**. Copy the **Project URL** (`SUPABASE_URL`) and the
   **`service_role` key** (`SUPABASE_SERVICE_KEY`) — NOT the `anon` key. The service_role key
   is powerful (it bypasses row-level security), which is fine here since only the app server
   uses it, never a browser.
5. Go to **Storage** (left sidebar) → **New bucket**. Name it exactly `lily-dahlia-files`.
   Leave it **not public** (private) — the app fetches files server-side with the service key,
   so a public bucket isn't needed and would expose receipts/vouchers to anyone with the link.

You now have four values: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and you'll
pick a fourth yourself in step 3 (`APP_PASSWORD`).

## 2. Test locally against Supabase (optional but recommended)

1. Copy the template: `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`
2. Open `.streamlit/secrets.toml` and fill in the four values from step 1 (pick any
   `APP_PASSWORD` you like for now).
3. Run `./run.sh` and open `localhost:8501`. Try uploading a statement, attaching a document,
   generating the payroll register. This confirms everything works against your real Supabase
   project before it's live on the internet.
4. `.streamlit/secrets.toml` is in `.gitignore` — it will never be committed or pushed.

## 3. Push the code to GitHub

1. Go to [github.com/new](https://github.com/new) and create a new repository (private is
   recommended, since the code references real business categories/vendors even though the
   actual financial data lives in Supabase, not in the repo). Don't initialize it with a
   README — this project already has files.
2. Copy the repository URL it gives you (e.g. `https://github.com/yourname/lily-dahlia-accounting.git`).
3. In this project folder, run:
   ```
   git remote add origin <the URL you copied>
   git push -u origin main
   ```
   (You may be prompted to log in to GitHub — follow the browser prompt it gives you.)

## 4. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **New app**, choose the repository you just pushed, branch `main`, and main file
   path `app.py`.
3. Before clicking Deploy, open **Advanced settings → Secrets** and paste in (with your real
   values, same format as `.streamlit/secrets.toml.example`):
   ```toml
   DATABASE_URL = "postgresql://..."
   SUPABASE_URL = "https://xxxxxxxx.supabase.co"
   SUPABASE_SERVICE_KEY = "..."
   APP_PASSWORD = "choose-a-real-password"
   ```
4. Click **Deploy**. The first build takes a couple of minutes. You'll get a URL like
   `https://yourname-lily-dahlia-accounting.streamlit.app`.
5. Open the URL, enter the `APP_PASSWORD` you set, and you're in. Share the URL and password
   with Diyanna if she needs access too — that's the whole "multi-user" story for now (single
   shared password, no individual accounts), consistent with this being a small internal tool.

## Ongoing use

- **Redeploying**: any time you (or I, in a future session) push new commits to the `main`
  branch on GitHub, Streamlit Community Cloud redeploys automatically within a minute or two.
- **Your data is safe across redeploys** — it lives in Supabase, not on the app server, so
  restarts/redeploys/sleep-wake cycles don't touch it.
- **Free tier limits to know about**: Streamlit Community Cloud apps sleep after a period of
  inactivity and take ~30-60 seconds to wake up on the next visit — normal, not a bug. Supabase's
  free tier includes 500MB database + 1GB file storage, which comfortably covers a small
  business's monthly bank statements, receipts, and vouchers for a long time; if you ever get
  close to the limit, Supabase's dashboard will show usage and you can upgrade that project
  alone (~$25/mo) without touching anything else.
- **Backups**: Supabase takes daily backups automatically on the free tier (with limited
  retention) — no action needed, but it's worth knowing it's not indefinite history.

## If something breaks

Come back to this conversation (or start a new one) and describe what happened — I can read
the Streamlit Community Cloud deploy logs with you, or connect back to your Supabase project if
you share the credentials again, to debug it.
