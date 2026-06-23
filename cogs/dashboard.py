import discord
from discord.ext import commands
from cogs.strikes import load_data, save_data, get_guild_config


def build_dashboard_embed(cfg: dict, guild: discord.Guild) -> discord.Embed:
    allowed_roles = cfg.get("allowed_admin_roles", [])
    punishment = cfg.get("punishment", "timeout")
    timeout_mins = cfg.get("timeout_minutes", 60)

    allowed_str = " ".join(f"<@&{r}>" for r in allowed_roles) if allowed_roles else "_Anyone (with Manage Messages)_"

    if punishment == "timeout":
        punishment_str = f"Timeout ({timeout_mins} min)"
    else:
        punishment_str = punishment.capitalize()

    embed = discord.Embed(title="🛡️ Anti Ping Dashboard", color=discord.Color.blurple())
    embed.add_field(
        name="📋 How it works",
        value="Give members the **AntiPing** role to protect them from being pinged.\n\n"
              "⚠️ **Important**: Go to Server Settings → Roles → AntiPing → Turn OFF \"Allow anyone to mention this role\"\n\n"
              "**OR** click the button below to auto-disable it.",
        inline=False
    )
    embed.add_field(name="🔓 Roles allowed to give strikes", value=allowed_str, inline=False)
    embed.add_field(name="⚖️ Strike 3 Punishment", value=punishment_str, inline=False)
    embed.set_footer(text="Use the buttons below to configure settings.")
    return embed


class AddAdminRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a role that can give strikes...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        rid = self.values[0].id
        if rid not in cfg["allowed_admin_roles"]:
            cfg["allowed_admin_roles"].append(rid)
            save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class RemoveAdminRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a role to remove...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        rid = self.values[0].id
        if rid in cfg["allowed_admin_roles"]:
            cfg["allowed_admin_roles"].remove(rid)
            save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class SelectAdminRoleView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=60)
        if mode == "add":
            self.add_item(AddAdminRoleSelect())
        else:
            self.add_item(RemoveAdminRoleSelect())


class SetPunishmentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="⏱️ Timeout", style=discord.ButtonStyle.primary)
    async def timeout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetTimeoutModal())

    @discord.ui.button(label="👢 Kick", style=discord.ButtonStyle.secondary)
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        cfg["punishment"] = "kick"
        save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )

    @discord.ui.button(label="🔨 Ban", style=discord.ButtonStyle.danger)
    async def ban_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        cfg["punishment"] = "ban"
        save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class SetTimeoutModal(discord.ui.Modal, title="Set Timeout Duration"):
    minutes = discord.ui.TextInput(label="Minutes", placeholder="e.g. 60")

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        try:
            mins = int(self.minutes.value.strip())
            cfg["punishment"] = "timeout"
            cfg["timeout_minutes"] = mins
            save_data(data)
            await interaction.response.edit_message(
                embed=build_dashboard_embed(cfg, interaction.guild),
                view=DashboardView()
            )
        except ValueError:
            await interaction.response.send_message("Enter a valid number.", ephemeral=True)


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="✅ Disable @mention on AntiPing", style=discord.ButtonStyle.success, row=0)
    async def disable_mention(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        antiping_role_id = cfg.get("antiping_role_id")

        if not antiping_role_id:
            await interaction.response.send_message("❌ AntiPing role not found.", ephemeral=True)
            return

        antiping_role = interaction.guild.get_role(antiping_role_id)
        if not antiping_role:
            await interaction.response.send_message("❌ AntiPing role not found.", ephemeral=True)
            return

        try:
            await antiping_role.edit(mentionable=False)
            await interaction.response.send_message("✅ AntiPing role is now unmentionable.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to edit the AntiPing role.", ephemeral=True)

    @discord.ui.button(label="➕ Add Admin Role", style=discord.ButtonStyle.primary, row=1)
    async def add_admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SelectAdminRoleView("add"))

    @discord.ui.button(label="➖ Remove Admin Role", style=discord.ButtonStyle.secondary, row=1)
    async def remove_admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SelectAdminRoleView("remove"))

    @discord.ui.button(label="⚖️ Set Punishment", style=discord.ButtonStyle.primary, row=2)
    async def set_punishment(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SetPunishmentView())


class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="dashboard", description="Configure Anti Ping settings.")
    @discord.app_commands.default_permissions(administrator=True)
    async def dashboard(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        save_data(data)
        await interaction.response.send_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView(),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
