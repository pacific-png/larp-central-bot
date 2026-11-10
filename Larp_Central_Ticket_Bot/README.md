# Larp Central Ticket Bot 🎫

A Discord ticket bot with the **Larp Central** silver-and-black panel and green cash logo. Uses `discord.py` slash commands and persistent buttons (buttons work after restarts).

## Features
- A branded **Open a Ticket** panel with your Larp Central logo.
- Each ticket is a private text channel (hidden from other members).
- One open ticket per user.
- Staff can **claim**, **add members**, or **remove members**.
- Users and staff can **close** tickets with a confirmation.
- Optional open/close logs in your chosen staff-only log channel.
- Ticket channels remain on Discord across bot restarts. Button handlers are restored automatically.
- No database or privileged Discord intents required.

## Step 1 — Create the Discord bot
1. Open https://discord.com/developers/applications and create a **New Application** called **Larp Central Ticket Bot**.
2. In the **Bot** section, set the bot **username** to `Larp Central Ticket Bot` (if available). Copy the bot token. **Never share the token**, paste it into a chat, or add it to GitHub.
3. In the **Installation** section, for **Guild Install**, choose the scopes `bot` and `applications.commands`.
4. Give the bot these permissions: **View Channels**, **Send Messages**, **Embed Links**, **Read Message History**, **Attach Files**, **Manage Channels**, and **Manage Roles** (for ticket access permissions).
5. Copy the installation link and invite the bot to your server.
6. Ensure the bot role is above roles it needs to manage where relevant; don't give the bot Administrator permission.

## Step 2 — Configure
Copy `.env.example` to `.env` and edit it:

```env
DISCORD_TOKEN=your_real_token
GUILD_ID=your_discord_server_id
STAFF_ROLE_ID=your_staff_role_id
LOG_CHANNEL_ID=optional_private_log_channel_id
```

- `GUILD_ID` is recommended: makes slash commands appear quickly in that server. Use the **Server ID**, not a channel ID. If you leave it as `0`, commands sync globally and can take longer to appear.
- `STAFF_ROLE_ID` is optional. People with **Manage Channels** can manage tickets even without a staff role ID.
- `LOG_CHANNEL_ID` is optional. If used, make the log channel visible only to staff.
- To copy IDs, turn on **Discord Settings → Advanced → Developer Mode** and right-click a server, role, or channel.

## Step 3 — Run on your computer
Install Python 3.12 or newer. In the bot folder:

```bash
python -m pip install -r requirements.txt
python bot.py
```

On Windows, if `python` is not found, install Python from https://www.python.org/downloads/ and check **Add Python to PATH**.

It only runs while the computer and terminal process remain on, unless deployed to a 24/7 host.

## Step 4 — Keep it online all the time (Railway)
Railway: https://railway.com/

1. Create a **private GitHub repository** and upload this project (include `Dockerfile`, `requirements.txt`, `bot.py`, `logo.png`, but **never upload `.env`**).
2. Create a new Railway project, choose **Deploy from GitHub repo**, and select the repo.
3. In the service's **Variables** tab, add `DISCORD_TOKEN`, `GUILD_ID`, `STAFF_ROLE_ID`, and optionally `LOG_CHANNEL_ID`.
4. Railway detects the `Dockerfile`. The container launches with `python bot.py`. This is a background worker and **doesn't need a website, domain, or HTTP server**.
5. Set **one replica**, keep service sleeping disabled, and enable the appropriate restart policy in **Service Settings**. Railway's `Always` restart setting is available on paid plans.
6. Check **Deploy Logs** for `Larp Central Ticket Bot connected` and `Synced ... slash commands`.

**Note:** Railway costs and plan restrictions may apply. Running the project locally or creating the ZIP doesn't deploy or host the bot. Deployment needs your own Discord bot token, server access, and hosting account.

## Step 5 — Post your panel
In your Discord server, go to your chosen `#tickets` or `#support` channel and run:

`/ticketpanel`

Members can now use **OPEN A TICKET**. A private `ticket-username-1234` channel is created in `🎫・larp-tickets`.

## Slash commands
| Command | Access | Purpose |
| --- | --- | --- |
| `/ticketpanel` | Manage Server | Post a branded panel |
| `/ticketclose` | Ticket owner or staff | Confirm and delete a ticket |
| `/ticketclaim` | Staff | Assign a ticket to yourself |
| `/ticketadd @member` | Staff | Give someone access |
| `/ticketremove @member` | Staff | Remove invited access |
| `/tickethelp` | Everyone | Show the commands |

### Notes
- Closing a ticket permanently deletes its channel. There is **no message transcript backup**. Save anything important before closing.
- The optional log channel records ticket creation and closure, not message contents.
- No web server or `MESSAGE CONTENT INTENT` is required.
- This is an independent community bot, not an official Discord support service.
- Treat the bot token like a password. If exposed, reset it immediately from the Discord Developer Portal.
