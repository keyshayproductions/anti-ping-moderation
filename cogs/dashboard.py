import discord
from discord.ext import commands
from cogs.strikes import load_data, save_data, get_guild_config


def build_dashboard_embed(cfg: dict, guild: discord.Guild) -> discord.Embed:
    protected = cfg.get("protected_roles", [])
    allowed = cfg.get("allowed_roles", [])
    punishment = cfg.get("punishment", "timeout")
    timeout_mins = cfg.get("timeout_minutes", 60)

    protected_str = " ".join(f"<@&{r}>" for r in protected) if protected else "_None set_"
    allowed_str = " ".join(f"<@&{r}>" for r in allowed) if allowed else "_None set_"

    if punishment == "timeout":
        punishment_str = f"Timeout ({timeout_mins} min)"
    else:
        punishment_str = punishment.capitalize()

    embed = discord.Embed(title="🛡️ Anti Ping Dashboard", color=discord.Color.blurple())
    embed.add_field(name="🔒 Protected Roles", value=protected_str, inline=False)
    embed.add_field(name="✅ Allowed to Ping", value=allowed_str, inline=False)
    embed.add_field(name="⚖️ Strike 3 Punishment", value=punishment_str, inline=False)
    embed.set_footer(text="Use the buttons below to configure settings.")
    return embed


class AddProtectedRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a role to protect...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        rid = self.values[0].id
        if rid not in cfg["protected_roles"]:
            cfg["protected_roles"].append(rid)
            save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class RemoveProtectedRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a role to unprotect...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        rid = self.values[0].id
        if rid in cfg["protected_roles"]:
            cfg["protected_roles"].remove(rid)
            save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class AddAllowedRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a role to allow pinging...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        rid = self.values[0].id
        if rid not in cfg["allowed_roles"]:
            cfg["allowed_roles"].append(rid)
            save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class RemoveAllowedRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select a role to remove from allowed...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        rid = self.values[0].id
        if rid in cfg["allowed_roles"]:
            cfg["allowed_roles"].remove(rid)
            save_data(data)
        await interaction.response.edit_message(
            embed=build_dashboard_embed(cfg, interaction.guild),
            view=DashboardView()
        )


class SelectProtectedView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=60)
        if mode == "add":
            self.add_item(AddProtectedRoleSelect())
        else:
            self.add_item(RemoveProtectedRoleSelect())


class SelectAllowedView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=60)
        if mode == "add":
            self.add_item(AddAllowedRoleSelect())
        else:
            self.add_item(RemoveAllowedRoleSelect())


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

    @discord.ui.button(label="🔒 Add Protected Role", style=discord.ButtonStyle.danger, row=0)
    async def add_protected(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SelectProtectedView("add"))

    @discord.ui.button(label="🔓 Remove Protected Role", style=discord.ButtonStyle.secondary, row=0)
    async def remove_protected(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SelectProtectedView("remove"))

    @discord.ui.button(label="✅ Add Allowed Role", style=discord.ButtonStyle.success, row=1)
    async def add_allowed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SelectAllowedView("add"))

    @discord.ui.button(label="❌ Remove Allowed Role", style=discord.ButtonStyle.secondary, row=1)
    async def remove_allowed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SelectAllowedView("remove"))

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
