# 🚀 Ultimate Render.com Deployment Checklist

Follow these exact steps to launch **MarketNest** for free with a synchronized, ACID-compliant database.

---

## 🛠️ PHASE 1: Prepare your Code (Local)

1.  **Commit Everything**: Ensure your latest changes (including the `requirements.txt` I generated) are on GitHub.
2.  **Verify .env**: Confirm your local `.env` is **NOT** on GitHub (it should be in `.gitignore`).

---

## 🌐 PHASE 2: Deploy to Render (Web Dashboard)

1.  **Connect GitHub**: Log in to [Render](https://dashboard.render.com/) and click **New > Web Service**. 
    *   Connect your `TechMart` repository.
2.  **Configuration Settings**:
    *   **Name**: `marketnest-app`
    *   **Runtime**: `Python 3`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `gunicorn app:app`
3.  **Advanced Environment Variables**:
    Click **Advanced > Add Environment Variable** and add these from your `.env`:

| KEY | VALUE |
| :--- | :--- |
| **FLASK_SECRET_KEY** | (Generate a new secure string) |
| **MYSQL_HOST** | (Provided by Aiven/Render DB) |
| **MYSQL_USER** | (Provided by Aiven/Render DB) |
| **MYSQL_PASSWORD** | (Provided by Aiven/Render DB) |
| **MYSQL_DATABASE** | `marketnest` |
| **MYSQL_UNIX_SOCKET** | (Leave empty for production) |
| **GOOGLE_CLIENT_ID** | `757216489991-na3k1vgj24jlkhkodjdcg0d3kfvacegb.apps.googleusercontent.com` |
| **GOOGLE_CLIENT_SECRET** | (Your secret from .env) |
| **MAIL_USERNAME** | (Your Gmail address) |
| **MAIL_PASSWORD** | `oktb smhx lrdf xtfr` |

---

## 🏗️ PHASE 3: Synchronize the Database

Once your Aiven (or Render) database is live, you **MUST** run the schema to initialize the tables and the ACID notification triggers:

```bash
# From your local machine terminal:
mysql -h <YOUR_REMOTE_HOST> -u <USER> -p marketnest < schema.sql
```

> [!IMPORTANT]
> **Google OAuth Update**: 
> 1. Go to your [Google Cloud Console](https://console.cloud.google.com/).
> 2. Open **Credentials > OAuth 2.0 Client IDs**.
> 3. Add your Render URL to **Authorized Redirect URIs**: 
>    `https://marketnest-app.onrender.com/auth/callback`

---

## 💸 0. 100% Free Tier Architecture (Recommended)

To deploy MarketNest for zero cost while maintaining full **ACID Integrity**, use this synchronized stack:

*   **Hosting**: [Render](https://render.com/) (Free Tier Web Service). 
    *   *Note: Spins down after 15 mins of inactivity, but wakes up instantly on request.*
*   **Database**: [Aiven](https://aiven.io/mysql) (Free Managed MySQL Plan).
    *   *Note: Provides an "Always Free" 5GB managed instance with full InnoDB support.*
*   **Auth & Sync**: Google OAuth (Free) & Gmail SMTP (Free).

---

## 🏗️ 1. Technical Prerequisites

We've already synchronized your dependencies in the `requirements.txt` file.

- **WSGI Server**: We are using `gunicorn` to handle production-level traffic.
- **Database**: You will need a managed MySQL instance (e.g., **PlanetScale**, **Aiven**, or **Render Managed MySQL**).
- **Environment Secrets**: Do **NOT** commit your `.env` file to GitHub. Instead, you will set these as "Environment Variables" in your hosting provider's dashboard.

---

## 📦 2. Deployment Steps (Example: Render)

### STEP 1: Push your Code to GitHub
Ensure you have a `.gitignore` that includes `.venv/` and `.env`.
```bash
git add .
git commit -m "chore: prepare for production deployment"
git push origin main
```

### STEP 2: Provision a Managed MySQL Database
1. Create a "Web Service" or "PostgreSQL/MySQL" instance on your provider.
2. Note the **Hostname**, **Username**, **Password**, and **Database Name**.
3. **Important**: Run our `schema.sql` against your production DB to synchronize the identity and notification triggers.

### STEP 3: Configure "Web Service" on Render/Heroku
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`
- **Port**: `5001` (or the provider's default `$PORT`)

### STEP 4: Inject Environment Variables
Go to your provider's **Settings > Environment** and copy everything from your local `.env`:
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
- `MAIL_USERNAME` / `MAIL_PASSWORD`
- `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
- `FLASK_SECRET_KEY` (Generate a new, unique string for production)

---

## 🛡️ 3. Production ACID & Security Checklist

> [!IMPORTANT]
> **Database Locks**: Ensure your managed MySQL instance supports `InnoDB` (standard) to keep `SELECT ... FOR UPDATE` isolation active.
> **HTTPS**: Most PaaS (Render/Heroku) provide SSL by default. Ensure your Google OAuth **Redirect URI** is updated in the Google Cloud Console to use the `https://...` URL of your deployed app.
> **Migrations**: Always run our `schema.sql` on the production DB to ensure that the synchronized notification triggers and multi-role alerts are active globally.

---

## 💾 4. Database Export Command
If you want to move your current local `marketnest` data to the cloud, use this command:
```bash
mysqldump -u root -p marketnest > marketnest_backup.sql
```
Then import `marketnest_backup.sql` into your cloud database.
