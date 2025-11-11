

# bot.py
# All-in-one Discord bot (single-file). Read comments and configure below.
# Requires: discord.py (2.3+), Python 3.10+
# Install: pip install -U "discord.py"

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import json
import os
import datetime
from typing import Optional
import aiohttp
import requests
from discord.ui import View, Select
from discord import SelectOption
import atexit
from collections import defaultdict, deque
from datetime import timedelta
import random # NEU: Für Giveaways

# -----------------------
# CONFIG - set these!
# -----------------------
# Wichtig: TOKEN muss exakt in einer Zeile stehen, ohne versteckte Zeichen!
TOKEN = "token"

OWNER_ID = 1287018426803552276
MAIN_GUILD_ID = 1427308816944468019
WHITELIST_ROLE_ID = 1427308838922752111
# Dies ist der Webhook, der für COMMANDS-Logs verwendet wird!
WEBHOOK_URL_COMMAND_LOGS = "https://discord.com/api/webhooks/1427354498367623229/yuKHa8H-KDBEV8ZJDHZufkhehywl2xD27rKIDKTdMfJ9Mr_v0Ir04hE5DdlSr5rm932o"
# Dieser Webhook scheint für Uptime/Status-Meldungen reserviert zu sein
WEBHOOK_URL_STATUS = "https://discord.com/api/webhooks/1428436384485605399/VPLMtIoehARSNHws_pODvu3LCoCxVP6zdxdFQCy8ftHdGyGFntG5odJ5YyJwQiN933Vg"

SUPPORT_SERVER_LINK = "https://discord.gg/xwvBNFafMa"
# MONGO_URI, CHECK_INTERVAL, LOG_CHANNEL_ID wurden entfernt oder angepasst
CHECK_INTERVAL = 20 # Sekunden
LOG_CHANNEL_ID = 1429035464475803668
# -----------------------

intents = discord.Intents.all()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True

# Nur eine Bot-Instanz verwenden
bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------------------
# JSON-basierte Speicherung (Ersatz für MongoDB) 📝
# --------------------------------
DATA_FILE = "data.json"
PERMS_FILE = "perms.json" # Perforated permissions data file
Filterword_data = "filterwords.json"

DATA = {}
perms = {} # Globale Variable für perms

# --- Laden und Speichern (NEU/WIEDERHERGESTELLT) ---
def load_data():
    """Lädt DATA aus der JSON-Datei oder gibt leeres Dict zurück."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"WARNUNG: {DATA_FILE} ist leer oder fehlerhaft. Starte mit leerem Datensatz.")
                return {}
    return {}

# --- Function Block 1: Saving Main DATA ---
def save_data():
    """Speichert DATA in der JSON-Datei."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, indent=4)

# --- Function Block 2: Loading Filter Word Data ---
# This function must be at the same indentation level as the 'def save_data():' above
def load_data():
    # This block must be indented to be part of the function body
    if not os.path.exists(Filterword_data):
        return {}
    with open(Filterword_data, "r") as f:
        return json.load(f)

# --- Function Block 3: Saving Filter Word Data ---
def save_filter_words(data): # Renamed to avoid conflict with the first save_data()
    """Speichert die Filterwörter in ihrer eigenen JSON-Datei."""
    with open(Filterword_data, "w") as f:
        json.dump(data, f, indent=4)



DATA = load_data()


# --- Globale Bot-Konfigurations-Daten ---
GLOBAL_CONFIG = {
    "owner_id": OWNER_ID,
    "main_guild_id": MAIN_GUILD_ID,
    "whitelist_role_id": WHITELIST_ROLE_ID,
    "whitelisted_guilds": [],
    "blacklisted_guilds": [],
}

# --- MongoDB-Ladefunktion ersetzt durch JSON-Logik ---
def load_global_config():
    """Lädt die globalen (Bot-weiten) Konfigurationen aus DATA."""
    global GLOBAL_CONFIG, OWNER_ID, MAIN_GUILD_ID, WHITELIST_ROLE_ID

    # Fügt die Blacklist/Whitelist-Werte aus der DATA-Struktur hinzu
    GLOBAL_CONFIG.update({
        "whitelisted_guilds": DATA.get("whitelisted_guilds", []),
        "blacklisted_guilds": DATA.get("blacklisted_guilds", []),
    })

    OWNER_ID = GLOBAL_CONFIG["owner_id"]
    MAIN_GUILD_ID = GLOBAL_CONFIG["main_guild_id"]
    WHITELIST_ROLE_ID = GLOBAL_CONFIG["whitelist_role_id"]

load_global_config()

# --------------------------------
# Data storage (MongoDB Functions ersetzt)
# --------------------------------

# NEUE JSON Lese- und Schreiblogik für Gilden-Einstellungen
def get_guild_settings(guild_id: int) -> dict:
    """Holt die Einstellungen einer Gilde aus DATA oder erstellt/gibt Standardwerte zurück."""
    g = str(guild_id)
    DATA.setdefault("guild_settings", {})

    if g in DATA["guild_settings"]:
        return DATA["guild_settings"][g]

    default = {
        "guild_id": guild_id,
        "beta": False, # Beibehalten, aber im Check ignoriert (siehe can_use_commands)
        "webhook": None,
        "anti_nuke": False,
        "anti_spam": False
    }
    DATA["guild_settings"][g] = default
    save_data()
    return default

# --- HIER BEGINNEN DIE AUTOROLE FUNKTIONEN (ANGEPASST AN JSON) ---
def get_autorole_data(guild_id: int) -> list:
    """Holt die Liste der Autorollen-IDs für eine Gilde."""
    g = str(guild_id)
    DATA.setdefault("autorole_data", {})
    # Autorole-Daten im JSON-Format speichern wir als Liste von Role-IDs
    return DATA["autorole_data"].get(g, [])

def add_autorole(guild_id: int, role_id: int):
    """Fügt eine Rolle zur Autorole-Liste einer Gilde hinzu."""
    g = str(guild_id)
    DATA.setdefault("autorole_data", {})
    DATA["autorole_data"].setdefault(g, [])

    if role_id not in DATA["autorole_data"][g]:
        DATA["autorole_data"][g].append(role_id)
        save_data()

def remove_autorole(guild_id: int, role_id: int):
    """Entfernt eine Rolle aus der Autorole-Liste einer Gilde."""
    g = str(guild_id)
    DATA.setdefault("autorole_data", {})

    if g in DATA["autorole_data"] and role_id in DATA["autorole_data"][g]:
        DATA["autorole_data"][g].remove(role_id)
        save_data()
# --- HIER ENDEN DIE AUTOROLE FUNKTIONEN ---


# --- NEUE JSON FUNKTIONEN FÜR LOGS UND STICKY MESSAGES (INTEGRIERT VON TEIL 1) ---

def get_log_channel_id(guild_id: int) -> int | None:
    """Holt die Log-Kanal-ID aus DATA."""
    g = str(guild_id)
    DATA.setdefault("server_settings", {})
    return DATA["server_settings"].get(g, {}).get("log_channel_id")

def set_log_channel_id(guild_id: int, channel_id: int):
    """Setzt die Log-Kanal-ID in DATA."""
    g = str(guild_id)
    DATA.setdefault("server_settings", {})
    DATA["server_settings"].setdefault(g, {})
    DATA["server_settings"][g]["log_channel_id"] = channel_id
    save_data()

def get_sticky_message(channel_id: int) -> tuple[str, int] | None:
    """Holt Sticky-Content und letzte Message-ID für einen Kanal."""
    c = str(channel_id)
    DATA.setdefault("sticky_messages", {})
    # [content, last_id]
    data = DATA["sticky_messages"].get(c)
    if data:
        # Konvertiere ID beim Lesen zurück zu int
        return data[0], data[1]
    return None

def set_sticky_message(channel_id: int, content: str, last_sticky_id: int):
    """Setzt oder aktualisiert eine Sticky Message."""
    c = str(channel_id)
    DATA.setdefault("sticky_messages", {})
    # Speichere als Liste: [content, last_id]
    DATA["sticky_messages"][c] = [content, last_sticky_id]
    save_data()

def remove_sticky_message(channel_id: int):
    """Entfernt eine Sticky Message."""
    c = str(channel_id)
    DATA.setdefault("sticky_messages", {})
    if c in DATA["sticky_messages"]:
        del DATA["sticky_messages"][c]
        save_data()

# --- ENDE DER NEUEN JSON FUNKTIONEN ---


# Globale Tracker-Definitionen für Anti-Nuke (Channel-Löschung)
_deletion_tracker: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(lambda: deque()))
DELETE_WINDOW = timedelta(seconds=20)
DELETE_THRESHOLD = 2 # Anzahl der Channel-Löschungen in DELETE_WINDOW Sekunden

# --------------------------------
# Anti-spam detection
# --------------------------------
MESSAGE_TRACK = {}
ANTI_SPAM_THRESHOLD = 5
ANTI_SPAM_WINDOW = 5
ANTI_SPAM_TIMEOUT_SECONDS = 1 * 60 * 60

# NEU: Robuste Initialisierung der Gilden-Einstellungen
# Diese Funktion ruft jetzt die JSON-Funktion auf.
def ensure_guild_settings(guild_id: int):
    return get_guild_settings(guild_id)

# DATA beim Beenden speichern (Nun wieder wichtig für JSON)
@atexit.register
def exit_save_data():
    save_data()
    print("Alle Daten in data.json gespeichert.")

# --------------------------------
# Utility: permission checks & Webhooks
# --------------------------------
async def is_owner(user: discord.User):
    # Verwendet die global geladene Konfiguration
    return user.id == GLOBAL_CONFIG.get("owner_id", OWNER_ID)

async def is_blacklisted(guild_id: int):
    # Verwendet die global geladene Konfiguration
    return guild_id in GLOBAL_CONFIG.get("blacklisted_guilds", [])

async def user_has_whitelist_role(user: discord.User):
    """
    Checks if the user has the configured whitelist role in MAIN_GUILD.
    """
    # Verwendet die global geladene Konfiguration
    main_id = GLOBAL_CONFIG.get("main_guild_id", MAIN_GUILD_ID)
    role_id = GLOBAL_CONFIG.get("whitelist_role_id", WHITELIST_ROLE_ID)
    main = bot.get_guild(main_id)
    if not main:
        return False
    member = main.get_member(user.id)
    if not member:
        return False
    role = main.get_role(role_id)
    return role in member.roles if role else False

async def guild_is_whitelisted(guild_id: int):
    # Verwendet die global geladene Konfiguration
    return guild_id in GLOBAL_CONFIG.get("whitelisted_guilds", [])

async def can_use_commands(interaction: discord.Interaction):
    """
    Central gatekeeper for SLASH COMMANDS: returns (allowed: bool, reason: Optional[str])
    """
    user = interaction.user
    guild = interaction.guild
    gid = guild.id if guild else None

    if await is_owner(user):
        return True, None

    if gid and await is_blacklisted(gid):
        return False, "This server is blacklisted from using the bot."

    if not gid:
        # direct messages: disallow most commands by default
        return False, "Bot-commands are only available in servers."

    # Beta-Prüfung wurde entfernt/deaktiviert (auf Wunsch des Users)
    # Alle Commands sind jetzt für alle Server verfügbar (wenn nicht geblacklisted)
    # und durch ihre eigenen discord.py Permissions geschützt.
    return True, None


def load_perms():
    if os.path.exists(PERMS_FILE):
        with open(PERMS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {} # Fehlerhaft/leere Datei
    return {}

def save_perms(data):
    with open(PERMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

perms = load_perms()

def has_permission(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    # Always allow server owner or bot owner
    if interaction.user.id == interaction.guild.owner_id or interaction.user.id == GLOBAL_CONFIG.get("owner_id", OWNER_ID):
        return True

    # Check saved perms
    if guild_id in perms and user_id in perms[guild_id]:
        return True

    return False

# === Custom Command Check Decorator (Bot-User Perms) ===
def perms_check():
    async def predicate(interaction: discord.Interaction):
        if has_permission(interaction):
            return True
        raise app_commands.CheckFailure()
    return app_commands.check(predicate)

# Custom Command Check Decorator (Whitelist/Beta Check)
def whitelist_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        ok, reason = await can_use_commands(interaction)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


async def log_command_webhook(user: discord.User, command_name: str, guild_id: int = None):
    """Sendet eine Nachricht an den COMMAND-Log-Webhook über jeden ausgeführten Command."""
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(WEBHOOK_URL_COMMAND_LOGS, session=session)
        guild_name = bot.get_guild(guild_id).name if guild_id and bot.get_guild(guild_id) else "DM/Unknown"

        embed = discord.Embed(
            title="Command Executed 💻",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="User", value=f"{user.mention} ({user})", inline=False)
        embed.add_field(name="Command", value=f"`{command_name}`", inline=False)
        embed.add_field(name="Guild", value=f"{guild_name} ({guild_id})" if guild_id else "DM", inline=False)

        try:
            await webhook.send(embed=embed)
        except Exception:
            # Ignoriere Fehler beim Senden des Log-Webhooks
            pass

# usage logging (ANGEPASST AN JSON)
def log_usage(guild_id: int, user_id: int, cmd_name: str):
    """Speichert Nutzungsstatistiken in der DATA 'usage_stats'."""
    # Speichern nicht mehr direkt in einer Collection, sondern in DATA
    DATA.setdefault("usage_stats", {})
    key = f"{guild_id}_{user_id}_{cmd_name}"

    current = DATA["usage_stats"].get(key, {"count": 0, "last_used": None})
    current["count"] += 1
    current["last_used"] = datetime.datetime.utcnow().isoformat()
    DATA["usage_stats"][key] = current
    # Hier speichern wir nicht jedes Mal, um die Performance zu verbessern,
    # da die Speicherung beim Beenden erfolgt (exit_save_data).


# send webhook log if configured (ACHTUNG: Async gemacht)
async def send_webhook_log(guild_id: int, content: str):
    """Sendet einen Log-Webhook, falls in den Gilden-Einstellungen konfiguriert."""
    settings = get_guild_settings(guild_id) # Holt die aktuellen Einstellungen
    webhook_url = settings.get("webhook")

    if webhook_url:
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(content)
        except Exception:
            pass

# DM helper
async def safe_dm(user: discord.User, text: str):
    try:
        await user.send(text)
    except Exception:
        pass

# --- NEUE HELPER FUNKTIONEN (FÜR LOGS UND GIVEAWAY-DAUER) ---

# --- HELPER: LOG SEND (VERWENDET JETZT JSON-LOGIK) ---
async def send_log(guild_id: int, embed: discord.Embed):
    log_channel_id = get_log_channel_id(guild_id)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(embed=embed)


# --- PARSE DURATION (FÜR GIVEAWAYS) ---
def parse_duration(duration_str: str) -> timedelta | None:
    try:
        # Erlaube "s" für Sekunden, falls benötigt
        if duration_str.endswith('s'):
            return timedelta(seconds=int(duration_str[:-1]))
        elif duration_str.endswith('m'):
            return timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith('h'):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith('d'):
            return timedelta(days=int(duration_str[:-1]))
        return None
    except ValueError:
        return None

# --- ENDE DER NEUEN HELPER FUNKTIONEN ---


# --------------------------------
# BOT EVENTS
# --------------------------------

# === Global Command Check ===
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        # Die Fehlermeldung wird bereits von whitelist_only() oder perms_check() gesendet
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
    else:
        # Andere Fehler loggen
        print(f"App Command Error in {interaction.command.name}: {error}")
        if not interaction.response.is_done():
              await interaction.response.send_message(f"❌ An unexpected error occurred: {error}", ephemeral=True)


# --------------------------------
# Anti-spam/Anti-Nuke message detection (Konsolidiert) und STICKY MESSAGE
# --------------------------------
@bot.event
async def on_message(message: discord.Message):
    # ignore bots
    if message.author.bot or not message.guild:
        # Nur Prefix-Commands in DMs verarbeiten
        if not message.guild:
            await bot.process_commands(message)
        return

    gid = message.guild.id
    aid = message.author.id
    now = discord.utils.utcnow().timestamp()

    # Sticky Message Logik
    result = get_sticky_message(message.channel.id)
    if result:
        sticky_content, last_sticky_id = result
        try:
            # Die alte Sticky Message löschen
            old = await message.channel.fetch_message(last_sticky_id)
            await old.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
             # Der Bot darf die Nachricht nicht löschen (kann bei einem Neustart passieren)
             pass 
        # Die neue Sticky Message senden
        new = await message.channel.send(sticky_content)
        set_sticky_message(message.channel.id, sticky_content, new.id) # Neue ID speichern

    # Holt die Einstellungen aus DATA
    settings = get_guild_settings(gid)

    if settings.get("anti_spam", False) or settings.get("anti_nuke", False):

        # Anti-Spam Logik (Message-Tracking)
        if settings.get("anti_spam", False):
            MESSAGE_TRACK.setdefault(gid, {})
            MESSAGE_TRACK[gid].setdefault(aid, [])
            MESSAGE_TRACK[gid][aid].append(now)
            # trim old
            MESSAGE_TRACK[gid][aid] = [t for t in MESSAGE_TRACK[gid][aid] if now - t <= ANTI_SPAM_WINDOW]

            if len(MESSAGE_TRACK[gid][aid]) >= ANTI_SPAM_THRESHOLD:
                # attempt to timeout user for 1 hour
                member = message.guild.get_member(aid)
                if member:
                    try:
                        until = discord.utils.utcnow() + datetime.timedelta(seconds=ANTI_SPAM_TIMEOUT_SECONDS)
                        await member.edit(timed_out_until=until, reason="Anti-Spam triggered (spam).")

                        # DM server owner
                        owner = message.guild.owner
                        if owner:
                            await safe_dm(owner, f"Anti-Spam: User {member} was timed out for spam in {message.guild.name}.")

                        # log via webhook if set (DEIN ALTES SYSTEM)
                        await send_webhook_log(gid, f"Anti-Spam: {member} timed out in {message.guild.name} for spam.")

                        # NEUES SYSTEM: Log über den neuen /set_logs_channel
                        log_embed = discord.Embed(title="🚨 Anti-Spam Action", description=f"**User:** {member.mention}\n**Action:** Timed out (1 hour)\n**Reason:** Mass Spamming", color=discord.Color.red())
                        await send_log(gid, log_embed)

                    except Exception:
                        pass
                # clear messages to prevent repeated timeouts
                MESSAGE_TRACK[gid][aid] = []

    # process commands normally
    await bot.process_commands(message)

# --------------------------------
# Anti-nuke channel delete detection
# --------------------------------
@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    guild = channel.guild
    gid = guild.id
    deleter = None

    # 1. Prüfen, ob Anti-Nuke aktiviert ist (Holt aus DATA)
    settings = get_guild_settings(gid)
    if not settings.get("anti_nuke", False):
        return

    # 2. Deleter finden
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            deleter = entry.user
            break

        if deleter is None or deleter.bot: # Ignoriere Bots
            return

    except Exception as e:
        print(f"Error getting audit log in on_guild_channel_delete: {e}")
        return

    # 3. ANTI-NUKE Logik (Massendelete-Erkennung)
    now = discord.utils.utcnow()
    dq: deque = _deletion_tracker[guild.id][deleter.id]

    # Speichere Löschzeitpunkt und Channel-ID
    dq.append((now, channel.id))

    # Alte Einträge entfernen
    while dq and now - dq[0][0] > DELETE_WINDOW:
        dq.popleft()

    # Zähle eindeutige Channels im Zeitfenster
    unique_channels = {cid for (_, cid) in dq}

    if len(unique_channels) > DELETE_THRESHOLD:
        # Massenlöschung erkannt - Aktion ausführen
        try:
            member = guild.get_member(deleter.id) or await guild.fetch_member(deleter.id)

            # Wichtige Überprüfung: Nicht den Bot-Owner oder Server-Owner bestrafen
            if member is None or member == guild.owner or member.id == GLOBAL_CONFIG.get("owner_id", OWNER_ID):
                await send_webhook_log(
                    guild.id,
                    f"anti_nuke: attempted to kick {deleter} but target is owner/bot-owner"
                )
                return

            await guild.kick(member, reason="Anti-nuke: mass channel deletion")
            await send_webhook_log(
                guild.id,
                f"anti_nuke: kicked {deleter.mention} ({deleter.id}) for mass channel deletion"
            )
            # NEUES SYSTEM: Log über den neuen /set_logs_channel
            log_embed = discord.Embed(title="💣 Anti-Nuke Kick", description=f"**User:** {deleter.mention}\n**Action:** Kicked\n**Reason:** Mass Channel Deletion", color=discord.Color.dark_red())
            await send_log(gid, log_embed)

            # Tracker für diesen Benutzer zurücksetzen
            _deletion_tracker[guild.id].pop(deleter.id, None)  

        except Exception as e:
            await send_webhook_log(
                guild.id,
                f"anti_nuke: failed to kick {deleter.mention} - {e}"
            )

# --------------------------------
# GLOBAL PREFIX COMMAND CHECK (Blacklist)
# --------------------------------
@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Behandelt Commands.CheckFailure, um Blacklist-Meldungen zu unterdrücken."""
    if isinstance(error, commands.CheckFailure) and str(error) == "Blacklisted":
        return

@bot.event
async def on_command(ctx: commands.Context):
    """Führt Blacklist-Prüfung für JEDEN Prefix-Command aus."""
    if not ctx.guild:
        return # Commands in DMs zulassen

    # Erlaube dem Owner IMMER, die Blacklist-Commands zu nutzen, um die Blacklist zu verwalten
    if await is_owner(ctx.author) and ctx.command and ctx.command.name in ["blacklist", "Rblacklist", "removeblacklist"]:
        return

    # Prüfe, ob der Server geblacklisted ist
    if await is_blacklisted(ctx.guild.id):
        # Sende Nachricht und wirf CheckFailure, um die Ausführung zu stoppen
        try:
            # Nur senden, wenn es nicht gerade ein !blacklist command ist, den der Owner ausführt
            if not await is_owner(ctx.author):
                await ctx.send("❌ This server is excluded from the use of the bot.", delete_after=10)
        except Exception:
            pass # Kann nicht antworten

        # Wichtig: Commands abbrechen
        raise commands.CheckFailure("Blacklisted")

# --------------------------------
# On ready: sync commands
# --------------------------------
@bot.event
async def on_ready():
    # Alle folgenden Zeilen MÜSSEN 4 Leerzeichen eingerückt sein
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced. Total: {len(synced)}")
    except Exception as e:
        print("Error during command sync:", e)
# KEINE ZUSÄTZLICHEN LEERZEICHEN HIER!
# --------------------------------
# Moderation commands (TEIL 1 - ZUSAMMENFASSUNG)
# --------------------------------
@bot.tree.command(name="kick", description="Kick a member (requires bot permissions).")
@app_commands.describe(member="Member to kick", reason="Reason")
@whitelist_only()
@perms_check()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided"):
    await log_command_webhook(interaction.user, "/kick", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "kick")

    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You don't have permission to kick members!", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.mention} was kicked. Reason: {reason}")
        # Log-Aufruf
        log_embed = discord.Embed(title="🔨 Member Kicked", description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.red())
        await send_log(interaction.guild.id, log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Could not kick {member.mention}: {e}", ephemeral=True)


@bot.tree.command(name="ban", description="Ban a member.")
@app_commands.describe(member="Member to ban", reason="Reason", delete_days="Days of messages to delete (0-7)")
@whitelist_only()
@perms_check()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided", delete_days: int = 0):
    await log_command_webhook(interaction.user, "/ban", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "ban")

    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ You don't have permission to ban members!", ephemeral=True)
        return

    try:
        # discord.py verlangt `delete_message_days`
        await member.ban(reason=reason, delete_message_days=max(0, min(7, delete_days)))
        await interaction.response.send_message(f"✅ {member.mention} was banned. Reason: {reason}")
        # Log-Aufruf
        log_embed = discord.Embed(title="🔨 Member Banned", description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}", color=discord.Color.dark_red())
        await send_log(interaction.guild.id, log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Could not ban {member.mention}: {e}", ephemeral=True)


        # === /filterwords COMMAND ===
@bot.tree.command(name="filterwords", description="Add a filtered word and set punishment (Kick, Timeout, Ban).")
@app_commands.describe(
    word="The word you want to filter.",
    punishment="Select the punishment type.",
    duration="Optional duration for Timeout/Ban (e.g. 10m, 1h, 1d)."
)
@app_commands.choices(punishment=[
    app_commands.Choice(name="Kick", value="kick"),
    app_commands.Choice(name="Timeout", value="timeout"),
    app_commands.Choice(name="Ban", value="ban"),
])
async def filterwords(interaction: discord.Interaction, word: str, punishment: app_commands.Choice[str], duration: str = None):
    # TODO: Add permission checks here (e.g., is_owner or Moderator role)

    data = load_data()
    guild_id = str(interaction.guild.id)

    # Check duration
    seconds = None
    if duration:
        try:
            unit = duration[-1].lower()
            value = int(duration[:-1])
            if unit == "s":
                seconds = value
            elif unit == "m":
                seconds = value * 60
            elif unit == "h":
                seconds = value * 3600
            elif unit == "d":
                seconds = value * 86400
            else:
                raise ValueError
        except:
            return await interaction.response.send_message(
                "❌ Invalid duration. Use formats like `10m`, `1h`, or `2d`.",
                ephemeral=True
            )

    # Check if guild is in data and initialize if not
    if guild_id not in data:
        data[guild_id] = []

    # Check if the word already exists. If so, update it to prevent duplicates.
    word_lower = word.lower()
    new_entry = {
        "word": word_lower,
        "punishment": punishment.value,
        "duration": seconds
    }

    found = False
    for i, item in enumerate(data[guild_id]):
        if item['word'] == word_lower:
            data[guild_id][i] = new_entry  # Update the existing entry
            found = True
            break

    if found:
        save_data(data)
        embed = discord.Embed(
            title="⚠️ Filterword Updated",
            description=f"Word `{word}` was updated.",
            color=discord.Color.gold()
        )
        return await interaction.response.send_message(embed=embed)

    # If the word is new, append it
    data[guild_id].append(new_entry)
    save_data(data)

    embed = discord.Embed(
        title="🚫 Filterword Added",
        description=f"**Word:** `{word}`\n**Punishment:** `{punishment.name}`",
        color=discord.Color.red()
    )
    if duration:
        embed.add_field(name="Duration", value=duration)
    embed.set_footer(text=f"Added by {interaction.user}")

    await interaction.response.send_message(embed=embed)

# === /filterwords_remove COMMAND (FIXED) ===
@bot.tree.command(name="filterwords_remove", description="Remove a filtered word from your server's list.")
async def filterwords_remove(interaction: discord.Interaction):
    # TODO: Add permission checks here.

    data = load_data()
    guild_id = str(interaction.guild.id)

    if guild_id not in data or len(data[guild_id]) == 0:
        return await interaction.response.send_message("ℹ️ No filter words set for this server.", ephemeral=True)

    # Dropdown with saved words - FIX: Use index as unique value
    options = []
    # Use enumerate to get a unique index for each filter word
    for index, entry in enumerate(data[guild_id]):
        # The label is user-friendly (word + punishment)
        label = f'{entry["word"]} ({entry["punishment"]})'
        # The value MUST be unique, so we use the index as a string
        options.append(discord.SelectOption(
            label=label[:100], # Labels must be 100 characters max
            value=str(index)
        ))

    class WordSelect(discord.ui.Select):
        def __init__(self):
            super().__init__(placeholder="Select a word to remove...", options=options)

        async def callback(self, interaction2: discord.Interaction):
            # The value is the unique index we set
            selected_index_str = self.values[0]
            selected_index = int(selected_index_str)

            # Retrieve the word that was at that index (before removal)
            word_to_remove = data[guild_id][selected_index]["word"]

            # Remove the entry by index
            del data[guild_id][selected_index] 
            save_data(data)

            # Send confirmation and remove the dropdown
            await interaction2.response.edit_message(content=f"✅ Removed filtered word: `{word_to_remove}`", view=None)

    view = discord.ui.View()
    view.add_item(WordSelect())
    await interaction.response.send_message("🗑️ Select a filter word to remove:", view=view, ephemeral=True)



@bot.tree.command(name="timeout", description="Timeout a member for duration in seconds.")
@app_commands.describe(member="Member to timeout", seconds="Seconds to timeout", reason="Reason")
@whitelist_only()
@perms_check()
async def timeout(interaction: discord.Interaction, member: discord.Member, seconds: int = 60, reason: Optional[str] = "No reason provided"):
    await log_command_webhook(interaction.user, "/timeout", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "timeout")

    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ You don't have permission to timeout members!", ephemeral=True)
        return

    try:
        until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
        await member.edit(timed_out_until=until, reason=reason)
        await interaction.response.send_message(
            f"✅ {member.mention} got timed out for {seconds} seconds. Reason: {reason}"
        )
        # Log-Aufruf
        log_embed = discord.Embed(title="⏳ Member Timed Out", description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Duration:** {seconds}s\n**Reason:** {reason}", color=discord.Color.orange())
        await send_log(interaction.guild.id, log_embed)
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error with {member.mention}: {e}", ephemeral=True
        )

@bot.tree.command(name="warn", description="Warn a member (stored in DB).")
@app_commands.describe(member="Member to warn", reason="Reason")
@whitelist_only()
@perms_check()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = "No reason provided"):
    # 1. Logging and Data Processing (AN DIE JSON-STRUKTUR ANGEPASST)
    await log_command_webhook(interaction.user, "/warn", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "warn")

    g = str(interaction.guild.id)
    DATA.setdefault("warnings", {})
    DATA["warnings"].setdefault(g, {})
    DATA["warnings"][g].setdefault(str(member.id), [])
    warn_obj = {"by": interaction.user.id, "reason": reason, "time": discord.utils.utcnow().isoformat()}  
    DATA["warnings"][g][str(member.id)].append(warn_obj)
    save_data() # Speichert die Warnings

    # ---

    # 2. Create the Embed for the channel confirmation
    embed = discord.Embed(
        title="⚠️ Member Warned",
        description=f"**{member.display_name}** has been successfully warned.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Warned Member", value=f"{member.mention} (`{member.id}`)", inline=False)
    embed.add_field(name="Warned By", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Server: {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    # 3. Send the Embed to the channel
    # ephemeral=False ensures other Moderators/Admins can see the public confirmation
    await interaction.response.send_message(embed=embed, ephemeral=False)  

    # Log-Aufruf
    await send_log(interaction.guild.id, embed)

    # ---

    # 4. Notify the warned user via DM (Important for transparency)
    try:
        dm_embed = discord.Embed(
            title="⚠️ You have been warned!",
            description=f"You have received a warning on the server **{interaction.guild.name}**.",
            color=discord.Color.red()
        )
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Warned By", value=interaction.user.display_name, inline=False)
        dm_embed.set_footer(text="Please adhere to the rules to avoid further sanctions.")
        dm_embed.timestamp = discord.utils.utcnow()

        await member.send(embed=dm_embed)

    except discord.Forbidden:
        # Handles the case where the user has DMs blocked
        followup_embed = discord.Embed(
            description=f"❗️ **Note:** Could not send a private message to **{member.display_name}**.",
            color=discord.Color.yellow()
        )
        # Send this warning as a followup message that only the moderator sees
        await interaction.followup.send(embed=followup_embed, ephemeral=True)

@bot.tree.command(name="slowmode", description="Toggle slowmode for this channel (on/off).")
@app_commands.describe(mode="on or off", seconds="If on, slowmode seconds")
@whitelist_only()
@perms_check()
async def slowmode(interaction: discord.Interaction, mode: str, seconds: Optional[int] = 5):
    await log_command_webhook(interaction.user, "/slowmode", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "slowmode")

    ch = interaction.channel
    if not isinstance(ch, discord.TextChannel):
        await interaction.response.send_message("❌ This command works in text channels only.", ephemeral=True)
        return

    try:
        if mode.lower() == "on":
            delay = max(0, seconds)
            await ch.edit(slowmode_delay=delay)
            await interaction.response.send_message(f"✅ Slowmode enabled: {delay}s")
        elif mode.lower() == "off":
            await ch.edit(slowmode_delay=0)
            await interaction.response.send_message("✅ Slowmode disabled.")
        else:
            await interaction.response.send_message("❌ Invalid mode. Use `on` or `off`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Could not change slowmode: {e}", ephemeral=True)

# --------------------------------
# Moderation commands (TEIL 2 - Fortsetzung)
# --------------------------------
@bot.tree.command(name="clear", description="Deletes a number of messages in the channel")
@app_commands.describe(amount="Number of messages to delete (max 100)")
@whitelist_only()
@perms_check()
async def clear(interaction: discord.Interaction, amount: int):
    await log_command_webhook(interaction.user, "/clear", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "clear")

    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You don't have permission to manage messages!", ephemeral=True)
        return

    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ You can delete between 1 and 100 messages.", ephemeral=True)
        return

    # Defer, bevor die Nachrichten gelöscht werden, falls es länger dauert
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        # Lösche die angegebene Anzahl von Nachrichten + 1 für den Slash-Command selbst
        deleted = await interaction.channel.purge(limit=amount + 1)

        # Sende Followup-Nachricht, ziehe 1 für den Command-Aufruf ab
        deleted_count = len(deleted) - 1
        await interaction.followup.send(f"✅ Deleted {deleted_count} messages.", ephemeral=True)

        # Log-Aufruf
        log_embed = discord.Embed(title="🧹 Messages Cleared", description=f"**Amount:** {deleted_count}\n**Channel:** {interaction.channel.mention}\n**Moderator:** {interaction.user.mention}", color=discord.Color.blue())
        await send_log(interaction.guild.id, log_embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Could not delete messages: {e}", ephemeral=True)


## 🔨 Unban (NEU - INTEGRATION)
@bot.tree.command(name="unban", description="Unbans a user by ID.")
@app_commands.describe(user_id="The ID of the user to unban")
@app_commands.checks.has_permissions(ban_members=True)
@whitelist_only()
@perms_check()
async def unban(interaction: discord.Interaction, user_id: str):
    await log_command_webhook(interaction.user, "/unban", interaction.guild_id)
    log_usage(interaction.guild_id, interaction.user.id, "unban")

    await interaction.response.defer(ephemeral=True)
    try:
        user = await bot.fetch_user(user_id)
        await interaction.guild.unban(user)
        embed = discord.Embed(title="✅ User Unbanned", description=f"{user.name} has been unbanned.", color=discord.Color.green())
        await interaction.followup.send(embed=embed)

        # Log in den neu konfigurierten Log-Kanal
        log = discord.Embed(title="🔨 User Unbanned", description=f"**User:** {user}\n**Moderator:** {interaction.user.mention}", color=discord.Color.green())
        await send_log(interaction.guild_id, log)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


# --------------------------------
# Anti-nuke/Anti-spam control
# --------------------------------
@bot.tree.command(name="anti_nuke", description="Toggle anti-nuke detection on/off for this guild.")
@app_commands.describe(mode="on/off")
@whitelist_only()
@perms_check()
async def anti_nuke_toggle(interaction: discord.Interaction, mode: str):
    await log_command_webhook(interaction.user, "/anti_nuke", interaction.guild.id)
    log_usage(interaction.guild.id, interaction.user.id, "anti_nuke")

    settings = ensure_guild_settings(interaction.guild.id)
    s = str(interaction.guild.id)

    mode_val = mode.lower() == "on"
    DATA["guild_settings"][s]["anti_nuke"] = mode_val
    save_data() # Speichert die geänderten Einstellungen

    if mode_val:
        await interaction.response.defer(ephemeral=True, thinking=True)

        failed = []
        changed = 0

        # Iteration, um potenziell gefährliche Permissions zu entfernen
        for role in interaction.guild.roles:
            try:
                # Prüfen, ob der Bot die Rolle bearbeiten kann und ob die Rolle External Apps hat
                if role.is_default() or role.managed or role >= interaction.guild.me.top_role:
                    continue # Überspringe verwaltete Rollen oder Rollen höher als der Bot

                perms_role = role.permissions
                # Überprüfe auf Admin, Manage Roles/Channels etc. - hier wird nur 'use_external_apps' überprüft
                # HINWEIS: 'use_external_apps' ist möglicherweise veraltet/nicht die richtige Anti-Nuke-Perm,
                # aber die Logik wird beibehalten. Ein besserer Check wäre 'administrator' oder 'manage_guild'.
                if getattr(perms_role, "use_external_apps", None) is True:  
                    new_perms = discord.Permissions(permissions=perms_role.value) # Kopie der Permissions
                    setattr(new_perms, "use_external_apps", False) # Setze die spezifische Permission auf False
                    await role.edit(permissions=new_perms, reason="Anti-nuke: disable Use External Apps")
                    changed += 1
            except Exception as e:
                failed.append((role.id, str(e)))

        details = ""
        if failed:
            details = "; ".join([f"role:{rid} err:{err}" for rid, err in failed])
            await send_webhook_log(
                interaction.guild.id,
                f"anti_nuke: Fehler beim Bearbeiten der Rollen: {details}"
            )


        await interaction.followup.send(
            f"✅ Anti-Nuke **activated**. "
            f"`{changed}` Roles have been changed to protect the server. "
            f"{len(failed)} Roles could not be changed."
        )

        # Log-Aufruf
        log_embed = discord.Embed(title="🛡️ Anti-Nuke Activated", description=f"**Moderator:** {interaction.user.mention}\n**Roles Modified:** {changed}", color=discord.Color.green())
        await send_log(interaction.guild.id, log_embed)


    else:
        await interaction.response.send_message(
            "✅ Anti-Nuke **disabled**. protection is switched off ."
        )
        # Log-Aufruf
        log_embed = discord.Embed(title="🚫 Anti-Nuke Deactivated", description=f"**Moderator:** {interaction.user.mention}", color=discord.Color.dark_red())
        await send_log(interaction.guild.id, log_embed)

    await send_webhook_log(interaction.guild.id, f"/anti_nuke {mode}")

# === Command: /anti_spam toggle ===
@bot.tree.command(name="anti_spam", description="Toggle anti-spam detection on/off for this guild.")
@app_commands.describe(mode="on/off")
@perms_check()
@whitelist_only()
async def anti_spam_toggle(interaction: discord.Interaction, mode: str):
    await log_command_webhook(interaction.user, "/anti_spam", interaction.guild.id)
    log_usage(interaction.guild.id, interaction.user.id, "anti_spam_toggle")

    settings = ensure_guild_settings(interaction.guild.id)
    s = str(interaction.guild.id)

    mode_val = mode.lower() == "on"
    DATA["guild_settings"][s]["anti_spam"] = mode_val
    save_data() # Speichert die geänderten Einstellungen

    if mode_val:
        await interaction.response.send_message("✅ Anti-Spam **activated**.")
        log_embed = discord.Embed(title="🛡️ Anti-Spam Activated", description=f"**Moderator:** {interaction.user.mention}", color=discord.Color.green())
    else:
        await interaction.response.send_message("✅ Anti-Spam **disabled**.")
        log_embed = discord.Embed(title="🚫 Anti-Spam Deactivated", description=f"**Moderator:** {interaction.user.mention}", color=discord.Color.dark_red())

    await send_log(interaction.guild.id, log_embed)


# --------------------------------
# Backup & Restore (ANGEPASST AN JSON)
# --------------------------------
@bot.tree.command(name="backup", description="Create a backup of roles & channels for 24 Hours.")
@whitelist_only()
@perms_check()
async def backup_cmd(interaction: discord.Interaction):
    await log_command_webhook(interaction.user, "/backup", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "backup")

    g = interaction.guild
    if not g:
        await interaction.response.send_message("Must be used in a guild.", ephemeral=True); return

    data = {
        "time": discord.utils.utcnow().isoformat(),
        "roles": [],
        "channels": []
    }

    await interaction.response.defer(ephemeral=True) # Defer, falls es lange dauert

    for role in g.roles:
        # HIER: Bot-Rolle und @everyone überspringen
        if role.is_default() or role.managed or role.id == g.id: # g.id ist die @everyone Rolle
            continue
        data["roles"].append({
            "name": role.name,  
            "permissions": role.permissions.value,  
            "mentionable": role.mentionable,  
            "hoist": role.hoist,
            "color": role.color.value
        })

    for ch in g.channels:
        if isinstance(ch, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel, discord.ForumChannel, discord.StageChannel)):
            # Ein bisschen mehr Information speichern
            # HINWEIS: Hier fehlen Channel-Permissions (Overrides)! Für ein echtes Backup wären diese nötig.
            data["channels"].append({
                "name": ch.name,  
                "type": ch.type.name,  
                "position": ch.position,
                "category_name": ch.category.name if ch.category else None,
                "topic": getattr(ch, "topic", None)
            })

    DATA.setdefault("backups", {})
    DATA["backups"][str(g.id)] = data # Speichert Backup in DATA
    save_data() # Speichert die Backups

    # END-ANTWORT mit followup senden
    await interaction.followup.send("✅ Backup created (stored in data.json).")

    # Log-Aufruf
    log_embed = discord.Embed(title="💾 Backup Created", description=f"**Roles:** {len(data['roles'])}\n**Channels:** {len(data['channels'])}", color=discord.Color.blue())
    await send_log(g.id, log_embed)
    await send_webhook_log(g.id, "/backup")

@bot.tree.command(name="restore", description="Restore backup (best-effort).")
@whitelist_only()
@perms_check()
async def restore_cmd(interaction: discord.Interaction):
    await log_command_webhook(interaction.user, "/restore", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "restore")

    g = interaction.guild
    if not g:
        await interaction.response.send_message("Must be used in a guild.", ephemeral=True)
        return

    backup = DATA.get("backups", {}).get(str(g.id))
    if not backup:
        await interaction.response.send_message("No backup found.", ephemeral=True)
        return

    # Defer, da dieser Vorgang lange dauern kann
    await interaction.response.defer(ephemeral=True)

    created_roles = 0
    created_channels = 0

    # Restore Roles
    for r in backup.get("roles", []):
        if discord.utils.get(g.roles, name=r["name"]):
            continue
        try:
            permissions = discord.Permissions(permissions=r["permissions"])
            await g.create_role(
                name=r["name"],  
                permissions=permissions,
                hoist=r.get("hoist", False),  
                mentionable=r.get("mentionable", False),
                color=discord.Color(r.get("color", 0))
            )
            created_roles += 1
        except Exception:
            pass

    # Restore Channels (Categories zuerst, um Kanäle richtig zuzuordnen)
    categories = {} # Zur Speicherung erstellter Kategorien

    # 1. Kategorien erstellen
    for c in backup.get("channels", []):
        if c["type"] == "category":
            existing_cat = discord.utils.get(g.channels, name=c["name"])
            if existing_cat:
                 categories[c["name"]] = existing_cat # Bestehende Kategorie speichern
                 continue
            try:
                new_cat = await g.create_category(c["name"], position=c.get("position"))
                categories[c["name"]] = new_cat
                created_channels += 1
            except Exception:
                pass

    # 2. Text- und Voice-Channels erstellen
    for c in backup.get("channels", []):
        if c["type"] in ("text", "voice"):
            if discord.utils.get(g.channels, name=c["name"]):
                continue

            parent = categories.get(c.get("category_name"))

            try:
                if c["type"] == "text":
                    await g.create_text_channel(c["name"], category=parent, position=c.get("position"), topic=c.get("topic"))
                elif c["type"] == "voice":
                    await g.create_voice_channel(c["name"], category=parent, position=c.get("position"))
                created_channels += 1
            except Exception:
                pass

    # END-ANTWORT mit followup senden
    await interaction.followup.send(f"✅ Restore completed. Created **{created_roles}** roles and **{created_channels}** channels.")

    # Log-Aufruf
    log_embed = discord.Embed(title="🔄 Backup Restored", description=f"**Roles Created:** {created_roles}\n**Channels Created:** {created_channels}", color=discord.Color.green())
    await send_log(g.id, log_embed)
    await send_webhook_log(g.id, "/Restore")

# --------------------------------
# Utility Commands (Fortsetzung)
# --------------------------------

# === Command: /perms user ===
@bot.tree.command(name="perms", description="Allow another user to use the bot commands.")
@app_commands.describe(user="Select a user to grant bot command permissions")
@whitelist_only()
@perms_check()
async def perms_cmd(interaction: discord.Interaction, user: discord.User):
    await log_command_webhook(interaction.user, "/perms", interaction.guild.id)
    log_usage(interaction.guild.id, interaction.user.id, "perms")

    guild_id = str(interaction.guild.id)
    if guild_id not in perms:
        perms[guild_id] = []

    if str(user.id) in perms[guild_id]:
        await interaction.response.send_message(f"🔹 {user.mention} already has access.", ephemeral=True)
        return

    perms[guild_id].append(str(user.id))
    save_perms(perms) # HIER WICHTIG: Speichert die Perforated Permissions
    await interaction.response.send_message(f"✅ {user.mention} can now use all bot commands from VortelBot.", ephemeral=True)


## ⚙️ Logs - set_logs_channel (NEU - INTEGRATION)
@bot.tree.command(name="set_logs_channel", description="Sets the channel for bot logs (Giveaways, Sticky, Mod-Aktionen).")
@app_commands.checks.has_permissions(administrator=True)
@whitelist_only()
@perms_check()
async def set_logs_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await log_command_webhook(interaction.user, "/set_logs_channel", interaction.guild_id)
    log_usage(interaction.guild_id, interaction.user.id, "set_logs_channel")

    set_log_channel_id(interaction.guild_id, channel.id) # JSON Funktion aufrufen

    embed = discord.Embed(title="⚙️ Log Channel Set", description=f"Logs will now be sent to {channel.mention}", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)


## 🎁 Giveaway Create (NEU - INTEGRATION)
@bot.tree.command(name="giveaway_create", description="Creates a new giveaway.")
@app_commands.checks.has_permissions(manage_guild=True)
@whitelist_only()
@perms_check()
async def giveaway_create(interaction: discord.Interaction, duration: str, winners: app_commands.Range[int, 1, 100], prize: str, host: discord.Member = None):
    await log_command_webhook(interaction.user, "/giveaway_create", interaction.guild_id)
    log_usage(interaction.guild_id, interaction.user.id, "giveaway_create")

    duration_td = parse_duration(duration)
    if duration_td is None:
        return await interaction.response.send_message("❌ Invalid duration format. Use 30m, 1h, or 1d.", ephemeral=True)

    await interaction.response.defer()
    end_time = datetime.datetime.now() + duration_td
    host = host or interaction.user

    embed = discord.Embed(
        title=f"🎁 GIVEAWAY: {prize}",
        description=f"React with 🎉 to enter!\nWinners: **{winners}**\nEnds: {discord.utils.format_dt(end_time, 'R')}",
        color=discord.Color.yellow()
    )
    embed.set_footer(text=f"Host: {host.name} • Vortel Bot")

    message = await interaction.channel.send(embed=embed)
    await message.add_reaction("🎉")
    await interaction.followup.send(f"✅ Giveaway started in {interaction.channel.mention}!", ephemeral=True)

    # Log in den neu konfigurierten Log-Kanal
    log_embed = discord.Embed(title="📢 Giveaway Started", description=f"Prize: **{prize}**\nHost: {host.mention}\nChannel: {interaction.channel.mention}", color=discord.Color.yellow())
    await send_log(interaction.guild_id, log_embed)

    await asyncio.sleep(duration_td.total_seconds())

    # Giveaway-Auswertung
    message = await interaction.channel.fetch_message(message.id)
    reaction = discord.utils.get(message.reactions, emoji="🎉")

    if not reaction:
        return await interaction.channel.send(f"❌ Nobody entered for **{prize}**.")

    users = [u async for u in reaction.users() if not u.bot]
    if len(users) == 0:
        return await interaction.channel.send(f"❌ No participants for **{prize}**.")

    final_winners = min(winners, len(users))

    chosen = random.sample(users, final_winners)
    winner_mentions = ", ".join(u.mention for u in chosen)

    result_embed = discord.Embed(
        title="🎉 GIVEAWAY ENDED!",
        description=f"**Prize:** {prize}\n**Winner(s):** {winner_mentions}\nHosted by: {host.mention}",
        color=discord.Color.green()
    )
    result_embed.set_footer(text="Thanks for participating!")
    await interaction.channel.send(embed=result_embed)
    await interaction.channel.send(f"🎊 Congrats {winner_mentions}! You won **{prize}**!")

    # Log in den neu konfigurierten Log-Kanal
    log_embed = discord.Embed(title="🏁 Giveaway Ended", description=f"Prize: **{prize}**\nWinner(s): {winner_mentions}\nHost: {host.mention}", color=discord.Color.green())
    await send_log(interaction.guild_id, log_embed)


## 🎲 Giveaway Reroll (NEU - INTEGRATION)
@bot.tree.command(name="giveaway_reroll", description="Rerolls a giveaway winner.")
@app_commands.checks.has_permissions(manage_guild=True)
@whitelist_only()
@perms_check()
async def giveaway_reroll(interaction: discord.Interaction, message_id: str):
    await log_command_webhook(interaction.user, "/giveaway_reroll", interaction.guild_id)
    log_usage(interaction.guild_id, interaction.user.id, "giveaway_reroll")

    await interaction.response.defer(ephemeral=True)
    try:
        message = await interaction.channel.fetch_message(int(message_id))
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction:
            return await interaction.followup.send("❌ No 🎉 reactions found.", ephemeral=True)

        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            return await interaction.followup.send("❌ No participants found.", ephemeral=True)

        new_winner = random.choice(users)
        await message.channel.send(f"🎲 New winner: {new_winner.mention}!")
        await interaction.followup.send(f"✅ Reroll done: {new_winner.mention}", ephemeral=True)

        # Log in den neu konfigurierten Log-Kanal
        log_embed = discord.Embed(title="🔁 Giveaway Rerolled", description=f"New Winner: {new_winner.mention}\nMessage: [Jump to giveaway]({message.jump_url})", color=discord.Color.orange())
        await send_log(interaction.guild_id, log_embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

## 📌 Sticky Message (NEU - INTEGRATION)
@bot.tree.command(name="sticky_message", description="Sets a sticky message.")
@app_commands.describe(message_id="ID of the message to make sticky")
@app_commands.checks.has_permissions(manage_messages=True)
@whitelist_only()
@perms_check()
async def sticky_message(interaction: discord.Interaction, message_id: str):
    await log_command_webhook(interaction.user, "/sticky_message", interaction.guild_id)
    log_usage(interaction.guild_id, interaction.user.id, "sticky_message")

    await interaction.response.defer(ephemeral=True)

    try:
        msg = await interaction.channel.fetch_message(int(message_id))
    except Exception:
        return await interaction.followup.send("❌ Could not find message with the provided ID.", ephemeral=True)

    # Sende die erste Sticky Message
    sticky = await interaction.channel.send(msg.content)

    # Speichere die Sticky-Info in JSON
    set_sticky_message(interaction.channel.id, msg.content, sticky.id) 

    embed = discord.Embed(title="📌 Sticky Set", description=f"Sticky message set in {interaction.channel.mention}", color=discord.Color.yellow())
    await interaction.followup.send(embed=embed)
    await send_log(interaction.guild_id, embed)


## 🧹 Sticky Remove (NEU - INTEGRATION)
@bot.tree.command(name="sticky_remove", description="Removes sticky message.")
@app_commands.checks.has_permissions(manage_messages=True)
@whitelist_only()
@perms_check()
async def sticky_remove(interaction: discord.Interaction):
    await log_command_webhook(interaction.user, "/sticky_remove", interaction.guild_id)
    log_usage(interaction.guild_id, interaction.user.id, "sticky_remove")

    data = get_sticky_message(interaction.channel.id)
    if not data:
        return await interaction.response.send_message("❌ No sticky message set in this channel.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    # Versuche, die letzte gesendete Sticky Message zu löschen
    try:
        old = await interaction.channel.fetch_message(data[1])
        await old.delete()
    except discord.NotFound:
        pass # Ignoriere, wenn sie bereits gelöscht wurde
    except discord.Forbidden:
        pass # Ignoriere, wenn die Bot-Permission fehlt

    # Entferne den Eintrag aus JSON
    remove_sticky_message(interaction.channel.id)

    await interaction.followup.send("✅ Sticky message removed.", ephemeral=True)
    await send_log(interaction.guild_id, discord.Embed(title="🧹 Sticky Removed", description=f"In Channel: {interaction.channel.mention}", color=discord.Color.red()))

@bot.tree.command(name="server_info", description="Show a detailed server panel like Discord")
@whitelist_only()
@perms_check()
async def server_info(interaction: discord.Interaction):
    await log_command_webhook(interaction.user, "/server_info", interaction.guild.id)
    log_usage(interaction.guild.id, interaction.user.id, "server_info")

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Could not get server info.", ephemeral=True)
        return

    # Member & Bot count
    total_members = guild.member_count
    bot_count = sum(1 for m in guild.members if m.bot)
    human_count = total_members - bot_count

    # Channel counts
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel) and not c.is_news()])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    categories = len([c for c in guild.categories])
    news_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel) and c.is_news()])
    forum_channels = len([c for c in guild.channels if isinstance(c, discord.ForumChannel)])
    stages = len([c for c in guild.channels if isinstance(c, discord.StageChannel)])

    # Discord Timestamp
    timestamp = int(guild.created_at.timestamp())

    embed = discord.Embed(
        title=f"🤖 Server Info for {guild.name}",
        description=f"Server ID: `{guild.id}`",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )

    # Server Icon als Thumbnail
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    # Server Banner
    if guild.banner:
        embed.set_image(url=guild.banner.url)

    # Server Infos
    embed.add_field(
        name="Owner",
        value=f"👑 {guild.owner.mention} (`{guild.owner.id}`)",
        inline=False
    )
    embed.add_field(
        name="Created",
        value=f"🗓️ <t:{timestamp}:D> (<t:{timestamp}:R>)", # Datum und Relative Zeit
        inline=False
    )
    embed.add_field(name="\u200b", value="--- **Overview** ---", inline=False) # Trennung

    # Mitglieder & Rollen
    embed.add_field(
        name="Members",
        value=f"👥 **Total:** {total_members}\n🧍 **Humans:** {human_count}\n🤖 **Bots:** {bot_count}",
        inline=True
    )
    embed.add_field(
        name="Roles & Boosts",
        value=f"🏷️ **Total Roles:** {len(guild.roles)}\n✨ **Boosts:** {guild.premium_subscription_count} (Level {guild.premium_tier})",
        inline=True
    )

    embed.add_field(name="\u200b", value="--- **Channels** ---", inline=False)

    # Channels
    embed.add_field(
        name="Text Channels",
        value=f"💬 {text_channels}",
        inline=True
    )
    embed.add_field(
        name="Voice Channels",
        value=f"🔊 {voice_channels}",
        inline=True
    )
    embed.add_field(
        name="Categories",
        value=f"📁 {categories}",
        inline=True
    )

    embed.add_field(
        name="Other Channels",
        value=f"🗞️ **News:** {news_channels}\n#️⃣ **Forums:** {forum_channels}\n🎙️ **Stages:** {stages}",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

# --------------------------------
# AUTOROLE COMMAND & EVENT (ANGEPASST AN JSON)
# --------------------------------

@bot.tree.command(name="autorole", description="Setzt eine automatische Rolle für neue Mitglieder.")
@app_commands.describe(role="Die Rolle, die neue Mitglieder automatisch bekommen sollen.")
@whitelist_only()
@perms_check()
async def autorole_cmd(interaction: discord.Interaction, role: discord.Role):
    await log_command_webhook(interaction.user, "/autorole", interaction.guild.id)
    log_usage(interaction.guild.id, interaction.user.id, "autorole")

    # Fügt die neue Rolle hinzu (unterstützt Mehrfach-Autorole)
    add_autorole(interaction.guild.id, role.id)

    await interaction.response.send_message(
        f"✅ Autorole **{role.name}** wurde hinzugefügt. Neue Mitglieder erhalten diese Rolle.",
        ephemeral=True
    )

@bot.event
async def on_member_join(member: discord.Member):
    # 1. Daten: Holen der Liste der Autorollen-IDs für diese Gilde
    guild_id = member.guild.id

    # Nutze die JSON-Funktion, die eine Liste von Role-IDs zurückgibt
    role_ids = get_autorole_data(guild_id)

    if not role_ids:
        # Keine Autorollen für diese Gilde konfiguriert
        return

    roles_to_add = []

    # Iteriere über alle konfigurierten Rollen-IDs
    for role_id in role_ids:
        role = member.guild.get_role(role_id)

        if role:
            # 2. Prüfen der Hierarchie (Bot muss die Rolle vergeben können)
            if role < member.guild.me.top_role:
                roles_to_add.append(role)
            else:
                print(f"❌ Rolle '{role.name}' (ID: {role.id}) ist höher oder gleich der Bot-Rolle. Kann nicht vergeben werden.")
        else:
            print(f"⚠️ Rolle mit ID {role_id} nicht gefunden in Guild {guild_id}.")

    # 3. Rollen zuweisen, falls welche gefunden wurden
    if roles_to_add:
        try:
            # Fügt alle gesammelten Rollen gleichzeitig hinzu
            await member.add_roles(*roles_to_add)  
            role_names = ", ".join([r.name for r in roles_to_add])
            print(f"✅ {member} hat folgende Autorollen zugewiesen bekommen: {role_names}")
            # Log-Aufruf
            log_embed = discord.Embed(title="➕ Member Joined (Autorole)", description=f"**User:** {member.mention}\n**Roles Assigned:** {role_names}", color=discord.Color.green())
            await send_log(guild_id, log_embed)

        except discord.Forbidden:
            print("❌ Keine Berechtigung, um die Rolle(n) zu vergeben (Prüfe die Bot-Rolle/Berechtigungen).")
        except Exception as e:
            print(f"Fehler beim Zuweisen der Rolle(n): {e}")


# --------------------------------
# OWNER PREFIX COMMANDS: !blacklist & !Rblacklist (ANGEPASST AN JSON)
# --------------------------------
@bot.command(name="blacklist", help="Owner: Blacklist a guild (bot will refuse to operate there). Usage: !blacklist <guild_id>")
async def blacklist_prefix(ctx: commands.Context, guild_id: int):
    # 1. OWNER-Check
    if not await is_owner(ctx.author):
        await ctx.send("❌ Only the Bot owner can do it. WHY U WANT TO DO IT?")
        return

    # 2. Blacklist-Logik
    DATA.setdefault("blacklisted_guilds", [])
    if guild_id in DATA["blacklisted_guilds"]:
        await ctx.send(f"❌ Die Gilde mit ID `{guild_id}` ist bereits auf der Blacklist.")
        return

    DATA["blacklisted_guilds"].append(guild_id)
    save_data() # Speichert die Blacklist
    load_global_config() # Globale Config neu laden, damit is_blacklisted die neue Liste verwendet

    # 3. Log und Bestätigung
    await ctx.send(f"✅ Gilde mit ID `{guild_id}` erfolgreich zur **Blacklist** hinzugefügt.")

    # Logging
    await log_command_webhook(ctx.author, f"!blacklist {guild_id}", ctx.guild.id if ctx.guild else None)
    log_usage(ctx.guild.id if ctx.guild else 0, ctx.author.id, "blacklist_prefix")

@bot.command(name="Rblacklist", aliases=["removeblacklist"], help="Owner: Remove a guild from the blacklist. Usage: !Rblacklist <guild_id>")
async def remove_blacklist_prefix(ctx: commands.Context, guild_id: int):
    # 1. OWNER-Check
    if not await is_owner(ctx.author):
        await ctx.send("❌ Nur der Bot-Owner kann diesen Command verwenden.")
        return

    # 2. Rblacklist-Logik
    if guild_id not in DATA.get("blacklisted_guilds", []):
        await ctx.send(f"❌ Die Gilde mit ID `{guild_id}` ist nicht auf der Blacklist.")
        return

    DATA["blacklisted_guilds"].remove(guild_id)
    save_data() # Speichert die Blacklist
    load_global_config() # Globale Config neu laden, damit is_blacklisted die neue Liste verwendet

    # 3. Log und Bestätigung
    await ctx.send(f"✅ Gilde mit ID `{guild_id}` erfolgreich von der **Blacklist** entfernt.")

    # Logging
    await log_command_webhook(ctx.author, f"!Rblacklist {guild_id}", ctx.guild.id if ctx.guild else None)
    log_usage(ctx.guild.id if ctx.guild else 0, ctx.author.id, "Rblacklist_prefix")

# --------------------------------
# Help Command
# --------------------------------
# --------------- Information Command ---------------
@bot.tree.command(name="information", description="Shows information about the bot.")
async def information(interaction: discord.Interaction):
    DEVELOPER_NAME = "Devskxx | Vortel Bot"  # Name des Entwicklers
    total_servers = len(bot.guilds)
    total_members = sum(g.member_count for g in bot.guilds)

    embed = discord.Embed(
        title="🤖 Vortel Bot Information",
        description="Here are some key details about the bot:",
        color=discord.Color.blurple()
    )
    embed.add_field(name="📊 Servers", value=f"{total_servers}", inline=True)
    embed.add_field(name="👥 Total Members", value=f"{total_members}", inline=True)
    embed.add_field(name="👑 Developer", value=DEVELOPER_NAME, inline=True)
    embed.add_field(name="🔗 Support Server", value=f"[Join here]({SUPPORT_SERVER_LINK})", inline=False)
    embed.set_footer(text="Vortel Bot © 2025", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

    # Logging
    print(f"[LOGS] /information used by {interaction.user} in {interaction.guild.name}")


# --------------- Support Server Command ---------------
@bot.tree.command(name="support_server", description="Shows the support server link.")
async def support_server(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛠️ Vortel Support Server",
        description=f"If you need help or want to report a bug, join our support server:\n\n🔗 [Join Support Server]({SUPPORT_SERVER_LINK})",
        color=discord.Color.green()
    )
    embed.set_footer(text="Vortel Bot Support", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

    # Logging
    print(f"[LOGS] /support_server used by {interaction.user} in {interaction.guild.name}")


@bot.tree.command(name="help", description="Zeigt eine Übersicht aller Commands an.")
@whitelist_only()
@perms_check()
async def help_command(interaction: discord.Interaction):
    # Log-Aufruf (Start des Funktionskörpers)
    await log_command_webhook(interaction.user, "/help", interaction.guild.id if interaction.guild else None)
    log_usage(interaction.guild.id, interaction.user.id, "help")

    # Manuelle Kategorisierung der Commands
    commands_map = {

        "🔨 Moderation Commands": [
            ("kick", "Kicks a member from the server."),
            ("ban", "Bans a member from the server."),
            ("unban", "Unbans a user by ID."),
            ("timeout", "Puts a member in timeout (mute)."),
            ("warn", "Warns a member (stored in the database)."),
            ("slowmode", "Enables/Disables slowmode for the current channel."),
            ("clear", "Deletes a specified number of messages in the channel.")
        ],

        "🛡️ Anti-Nuke & Backup": [
            ("anti_nuke", "Enables/Disables anti-nuke detection for this server."),
            ("anti_spam", "Enables/Disables anti-spam message detection."),
            ("backup", "Creates a backup of roles and channels."),
            ("restore", "Attempts to restore the latest backup."),
        ],

        "🎁 Giveaway & Sticky": [
            ("giveaway_create", "Starts a new giveaway."),
            ("giveaway_reroll", "Rerolls a winner for a giveaway."),
            ("sticky_message", "Sets a message to stick at the bottom of the channel."),
            ("sticky_remove", "Removes the sticky message from the channel."),
        ],

        "⚙️ Utility": [
            ("help", "Displays this help overview."),
            ("server_info", "Shows detailed information about the server."),
            ("autorole", "Sets a role that will automatically be assigned to new members."),
            ("set_logs_channel", "Sets the channel for bot logs (Giveaway, Mod-Aktionen)."),
            ("perms", "give someone access to use all commands from VortelBot "),
            ("information", "show all information about VortelBot "),
            ("support_server", "send the link for our Support Server "),


        ],

    }


    help_embed = discord.Embed(
        title=f"🤖 Command overview for {bot.user.name}",
        description="Here is a list of all commands. All commands are slash commands.",
        color=0x42B983 # Grünliche Farbe
    )

    # Füge Commands als Felder hinzu
    for category, cmds in commands_map.items():
        command_list = []
        for name, description in cmds:
            command_list.append(f"**/{name}**\n*{description}*")

        # Füge das Feld hinzu, wenn die Liste nicht leer ist
        if command_list:
            help_embed.add_field(
                name=category,
                value='\n\u200b'.join(command_list), # "\n\u200b" sorgt für den Zeilenumbruch und Abstand
                inline=False # Jede Kategorie in einer neuen Zeile
            )

    help_embed.set_footer(
        text="The availability of commands may depend on the server settings.",
        icon_url=interaction.user.display_avatar.url
    )

    await interaction.response.send_message(embed=help_embed, ephemeral=True)


# =====================================================
# GUILD JOIN EVENT
# =====================================================

@bot.event
async def on_guild_join(guild: discord.Guild):
    # VERSICHERUNG: Stelle sicher, dass für die neue Gilde Standard-Einstellungen in DATA erstellt werden
    ensure_guild_settings(guild.id)

    # Versuch 1: Log-Kanal finden
    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    if not log_channel:
        print(f"❌ Log channel not found (ID: {LOG_CHANNEL_ID}) - Das Event wurde ausgelöst, aber der Zielkanal fehlt!")
        return

    invite_link = None

    # Versuch 2: Invite-Link erstellen
    try:
        # Finde den ersten Textkanal, in dem der Bot die Berechtigung zur Erstellung hat
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).create_instant_invite:
                # Erstelle den Invite
                invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
                invite_link = invite.url
                break  # Nimm den ersten funktionierenden Kanal
    except Exception as e:
        print(f"⚠️ Error creating invite for {guild.name}: {e}")

    # Versuch 3: Log-Nachricht senden
    try:
        if invite_link:
            await log_channel.send(f"✅ Bot joined **{guild.name}**! Invite: {invite_link}")
        else:
            await log_channel.send(f"⚠️ Could not create invite for **{guild.name}** (Keine Berechtigung gefunden).")
    except Exception as e:
        print(f"❌ Error sending log message: {e}")

# =====================================================
# BOT RUN
# =====================================================

if __name__ == "__main__":
    if TOKEN:
        try:
            bot.run(TOKEN)
        except discord.LoginFailure:
            print("ERROR: Invalid token provided. Please check your TOKEN variable.")
        except Exception as e:
            print(f"An unexpected error occurred during bot execution: {e}")
    else:
        print("ERROR: TOKEN is not set. Please set the TOKEN variable.")
