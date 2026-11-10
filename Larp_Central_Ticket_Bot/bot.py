"""Larp Central Ticket Bot — Discord private support tickets (discord.py 2.x)."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0") or "0")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0") or "0")
LOGO = Path(__file__).with_name("logo.png")

BRAND = 0xB8C2CC  # silver
GREEN = 0x55E88D  # cash green
CATEGORY_NAME = "🎫・larp-tickets"
TOPIC_OWNER = re.compile(r"(?:^|;)LARP_OWNER=(\d+)(?:;|$)")
TOPIC_CLAIMED = re.compile(r"(?:^|;)LARP_CLAIMED=(\d+)(?:;|$)")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("larp-central")


def owner_id(channel: discord.abc.GuildChannel) -> int | None:
    if not isinstance(channel, discord.TextChannel):
        return None
    m = TOPIC_OWNER.search(channel.topic or "")
    return int(m.group(1)) if m else None


def claimed_id(channel: discord.TextChannel) -> int:
    m = TOPIC_CLAIMED.search(channel.topic or "")
    return int(m.group(1)) if m else 0


def topic_for(owner: int, claimed: int = 0) -> str:
    return f"LARP_OWNER={owner};LARP_CLAIMED={claimed}"


def staff_role(guild: discord.Guild) -> discord.Role | None:
    return guild.get_role(STAFF_ROLE_ID) if STAFF_ROLE_ID else None


def is_staff(member: discord.Member) -> bool:
    return member.guild_permissions.manage_channels or (
        STAFF_ROLE_ID != 0 and any(r.id == STAFF_ROLE_ID for r in member.roles)
    )


def can_close(member: discord.Member, channel: discord.TextChannel) -> bool:
    return owner_id(channel) == member.id or is_staff(member)


def ticket_channel(interaction: discord.Interaction) -> discord.TextChannel | None:
    channel = interaction.channel
    return channel if isinstance(channel, discord.TextChannel) and owner_id(channel) else None


async def send_log(guild: discord.Guild, title: str, detail: str) -> None:
    if not LOG_CHANNEL_ID:
        return
    destination = guild.get_channel(LOG_CHANNEL_ID)
    if not isinstance(destination, discord.TextChannel):
        log.warning("LOG_CHANNEL_ID does not refer to a readable text channel")
        return
    try:
        await destination.send(
            embed=discord.Embed(title=title, description=detail, color=BRAND),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        log.exception("Could not send log message")


async def ensure_category(guild: discord.Guild) -> discord.CategoryChannel:
    for cat in guild.categories:
        if cat.name == CATEGORY_NAME:
            return cat
    # Category is created automatically; per-ticket visibility is enforced below.
    return await guild.create_category(CATEGORY_NAME, reason="Larp Central ticket setup")


async def open_ticket(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member):
        await interaction.response.send_message("Tickets only work inside a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    # Protect against multiple clicks opening duplicate channels.
    lock = bot.creation_locks.setdefault(guild.id, asyncio.Lock())
    async with lock:
        existing = next((c for c in guild.text_channels if owner_id(c) == member.id), None)
        if existing:
            await interaction.followup.send(f"You already have a ticket: {existing.mention}", ephemeral=True)
            return
        try:
            category = await ensure_category(guild)
            bot_member = guild.me
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    attach_files=True, embed_links=True,
                ),
            }
            if bot_member:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_channels=True,
                    read_message_history=True, embed_links=True,
                )
            role = staff_role(guild)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    attach_files=True,
                )
            safe_name = re.sub(r"[^a-z0-9-]", "-", member.name.lower()).strip("-")[:18] or "member"
            channel = await guild.create_text_channel(
                name=f"ticket-{safe_name}-{str(member.id)[-4:]}",
                category=category,
                topic=topic_for(member.id),
                overwrites=overwrites,
                reason=f"Ticket opened by {member} ({member.id})",
            )
            welcome = discord.Embed(
                title="✦ Welcome to your private ticket",
                description=(
                    f"Hey {member.mention}, thanks for reaching out to **Larp Central**.\n\n"
                    "Tell us what you need help with, and a team member will respond.\n"
                    "Use **Close Ticket** when everything's sorted."
                ),
                color=BRAND,
            )
            welcome.set_footer(text="LARP CENTRAL  •  PRIVATE SUPPORT")
            await channel.send(
                content=member.mention,
                embed=welcome,
                view=TicketControlsView(),
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
            await send_log(guild, "🎫 Ticket opened", f"Owner: {member.mention}\nChannel: {channel.mention}")
            await interaction.followup.send(f"✅ Your private ticket is ready: {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have the permissions to create tickets. Ask an admin to grant **Manage Channels**.",
                ephemeral=True,
            )
        except discord.HTTPException:
            log.exception("Ticket creation failed")
            await interaction.followup.send("I couldn't create your ticket. Please try again.", ephemeral=True)


async def close_ticket(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    guild = interaction.guild
    member = interaction.user
    if guild is None or not isinstance(member, discord.Member) or not can_close(member, channel):
        await interaction.response.send_message("You can't close this ticket.", ephemeral=True)
        return
    # Acknowledge before deleting the channel so the interaction doesn't fail.
    await interaction.response.send_message("🔒 Ticket closed. This channel is being removed.", ephemeral=True)
    await send_log(
        guild,
        "🔒 Ticket closed",
        f"Ticket owner ID: `{owner_id(channel)}`\nClosed by: {member.mention}\nChannel: `{channel.name}`",
    )
    try:
        await channel.delete(reason=f"Ticket closed by {member} ({member.id})")
    except discord.Forbidden:
        await interaction.followup.send("I need **Manage Channels** to remove this ticket.", ephemeral=True)
    except discord.HTTPException:
        log.exception("Ticket deletion failed")
        await interaction.followup.send("Couldn't remove the ticket channel.", ephemeral=True)


class CloseConfirmation(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=90)

    @discord.ui.button(label="Yes, close ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = ticket_channel(interaction)
        if not channel:
            await interaction.response.send_message("This isn't an active ticket.", ephemeral=True)
            return
        await close_ticket(interaction, channel)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Ticket left open.", view=None)
        self.stop()


async def ask_close(interaction: discord.Interaction) -> None:
    channel = ticket_channel(interaction)
    if channel is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Use this inside a ticket channel.", ephemeral=True)
        return
    if not can_close(interaction.user, channel):
        await interaction.response.send_message("Only the ticket owner or staff can close this ticket.", ephemeral=True)
        return
    await interaction.response.send_message(
        "**Close this ticket?** The channel will be deleted. Save any messages you need first.",
        view=CloseConfirmation(), ephemeral=True,
    )


async def claim_ticket(interaction: discord.Interaction) -> None:
    channel = ticket_channel(interaction)
    member = interaction.user
    if channel is None or not isinstance(member, discord.Member) or not is_staff(member):
        await interaction.response.send_message("Only staff can claim active tickets.", ephemeral=True)
        return
    claimed = claimed_id(channel)
    if claimed and claimed != member.id:
        await interaction.response.send_message(f"Already claimed by <@{claimed}>.", ephemeral=True)
        return
    if claimed == member.id:
        await interaction.response.send_message("You've already claimed this ticket.", ephemeral=True)
        return
    try:
        await channel.edit(topic=topic_for(owner_id(channel), member.id), reason=f"Claimed by {member}")
        await interaction.response.send_message(f"✅ {member.mention} claimed this ticket.")
    except discord.Forbidden:
        await interaction.response.send_message("I need **Manage Channels** to claim tickets.", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="OPEN A TICKET", emoji="🎫", style=discord.ButtonStyle.success, custom_id="larp_central:open:v1")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction)


class TicketControlsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="larp_central:close:v1")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ask_close(interaction)

    @discord.ui.button(label="Claim Ticket", emoji="🙋", style=discord.ButtonStyle.secondary, custom_id="larp_central:claim:v1")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await claim_ticket(interaction)


class LarpBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default(), help_command=None)
        self.creation_locks: dict[int, asyncio.Lock] = {}

    async def setup_hook(self) -> None:
        self.add_view(TicketPanelView())
        self.add_view(TicketControlsView())
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %s slash commands to guild %s", len(synced), GUILD_ID)
        else:
            synced = await self.tree.sync()
            log.info("Synced %s global slash commands", len(synced))


bot = LarpBot()


@bot.event
async def on_ready() -> None:
    if bot.user:
        log.info("Larp Central Ticket Bot connected as %s (%s)", bot.user, bot.user.id)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Larp Central tickets 🎫"))


@bot.tree.command(name="ticketpanel", description="Post the Larp Central ticket button in this channel (admin only)")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def ticketpanel(interaction: discord.Interaction):
    member = interaction.user
    if not isinstance(member, discord.Member) or not member.guild_permissions.manage_guild:
        await interaction.response.send_message("You need **Manage Server** to post the ticket panel.", ephemeral=True)
        return
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Run this in a server text channel.", ephemeral=True)
        return
    embed = discord.Embed(
        title="💸 LARP CENTRAL  |  SUPPORT",
        description=(
            "**Need help? You've come to the right place.**\n\n"
            "✦ Private assistance from our team\n"
            "✦ Quick, organised support\n"
            "✦ Your conversation stays in your ticket\n\n"
            "**Tap the green button below to get started.**"
        ),
        color=BRAND,
    )
    embed.add_field(name="HOW IT WORKS", value="**01** Open a ticket   •   **02** Describe your issue   •   **03** Get support", inline=False)
    embed.set_footer(text="LARP CENTRAL  •  OFFICIAL TICKET DESK")
    await interaction.response.defer(ephemeral=True)
    try:
        if LOGO.exists():
            embed.set_thumbnail(url="attachment://logo.png")
            await channel.send(embed=embed, view=TicketPanelView(), file=discord.File(LOGO, filename="logo.png"))
        else:
            await channel.send(embed=embed, view=TicketPanelView())
        await interaction.followup.send("✅ Ticket panel posted in this channel.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I need **Send Messages** and **Embed Links** here.", ephemeral=True)


@bot.tree.command(name="ticketclose", description="Close the current ticket")
@app_commands.guild_only()
async def ticketclose(interaction: discord.Interaction):
    await ask_close(interaction)


@bot.tree.command(name="ticketclaim", description="Claim the current ticket (staff)")
@app_commands.guild_only()
async def ticketclaim(interaction: discord.Interaction):
    await claim_ticket(interaction)


@bot.tree.command(name="ticketadd", description="Add a member to this ticket (staff)")
@app_commands.guild_only()
@app_commands.describe(member="Member to give access to")
async def ticketadd(interaction: discord.Interaction, member: discord.Member):
    channel = ticket_channel(interaction)
    actor = interaction.user
    if channel is None or not isinstance(actor, discord.Member) or not is_staff(actor):
        await interaction.response.send_message("Only staff can add people to tickets.", ephemeral=True)
        return
    try:
        await channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True,
                                      reason=f"Added to ticket by {actor}")
        await interaction.response.send_message(f"✅ {member.mention} was added to the ticket.")
    except discord.Forbidden:
        await interaction.response.send_message("I need **Manage Roles** to set ticket access.", ephemeral=True)


@bot.tree.command(name="ticketremove", description="Remove an invited member from this ticket (staff)")
@app_commands.guild_only()
@app_commands.describe(member="Member to remove from this ticket")
async def ticketremove(interaction: discord.Interaction, member: discord.Member):
    channel = ticket_channel(interaction)
    actor = interaction.user
    if channel is None or not isinstance(actor, discord.Member) or not is_staff(actor):
        await interaction.response.send_message("Only staff can remove people from tickets.", ephemeral=True)
        return
    if member.id == owner_id(channel):
        await interaction.response.send_message("You can't remove the ticket owner.", ephemeral=True)
        return
    if member == interaction.guild.me or is_staff(member):
        await interaction.response.send_message("You can't remove staff or the bot with this command.", ephemeral=True)
        return
    try:
        await channel.set_permissions(member, overwrite=None, reason=f"Removed from ticket by {actor}")
        await interaction.response.send_message(f"✅ {member.mention} was removed from the ticket.")
    except discord.Forbidden:
        await interaction.response.send_message("I need **Manage Roles** to change ticket access.", ephemeral=True)


@bot.tree.command(name="tickethelp", description="Show Larp Central ticket commands")
@app_commands.guild_only()
async def tickethelp(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Larp Central Ticket Bot**\n"
        "`/ticketpanel` — Admin: post the open-ticket panel\n"
        "`/ticketclose` — Owner or staff: close a ticket\n"
        "`/ticketclaim` — Staff: claim a ticket\n"
        "`/ticketadd @member` — Staff: invite a member\n"
        "`/ticketremove @member` — Staff: remove a member\n"
        "`/tickethelp` — Show this guide",
        ephemeral=True,
    )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.error("Slash command error: %r", error)
    message = "Something went wrong. Please try again or contact a server admin."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Put it in .env (local) or host environment variables.")
    bot.run(TOKEN, log_handler=None)
