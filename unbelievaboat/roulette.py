import asyncio
import datetime
import random
import re
import discord
import tabulate

from math import ceil

from redbot.core import bank, checks, commands
from redbot.core.errors import BalanceTooHigh
from redbot.core.utils.chat_formatting import box, humanize_number, humanize_timedelta
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu

from .abc import MixinMeta
from .checks import check_global_setting_admin, roulette_disabled_check, wallet_disabled_check

NUMBERS = {
    0: "green",
    1: "red",
    3: "red",
    5: "red",
    7: "red",
    9: "red",
    12: "red",
    14: "red",
    16: "red",
    18: "red",
    19: "red",
    21: "red",
    23: "red",
    25: "red",
    27: "red",
    30: "red",
    32: "red",
    34: "red",
    36: "red",
    2: "black",
    4: "black",
    6: "black",
    8: "black",
    10: "black",
    11: "black",
    13: "black",
    15: "black",
    17: "black",
    20: "black",
    22: "black",
    24: "black",
    26: "black",
    28: "black",
    29: "black",
    31: "black",
    33: "black",
    35: "black",
}

EMOJIS = {"black": "\u2B1B", "red": "\U0001F7E5", "green": "\U0001F7E9"}

COLUMNS = [
    [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
    [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
]

BET_TYPES = {
    "red": "color",
    "black": "color",
    "1st dozen": "dozen",
    "2nd dozen": "dozen",
    "3rd dozen": "dozen",
    "odd": "odd_or_even",
    "even": "odd_or_even",
    "1st half": "halfs",
    "2nd half": "halfs",
    "1st column": "column",
    "2nd column": "column",
    "3rd column": "column",
}


class Roulette(MixinMeta):
    """Roulette Game."""

    async def roulettewithdraw(self, ctx, bet):
        if not await self.walletdisabledcheck(ctx):
            await self.walletwithdraw(ctx.author, bet)
        else:
            await bank.withdraw_credits(ctx.author, bet)

    async def single_bet(self, ctx, amount: int, selection):
        """
        This function processes a single bet, which can sometimes be part of a larger bet string.
        """
        bet_key = 'number'
        if str(selection).lower() in BET_TYPES:
            bet_key = BET_TYPES[selection.lower()]
        elif selection == '0':
            bet_key = 'zero'

        try:
            selection = int(selection)
            if selection < 0 or selection > 36:
                return f"{ctx.author.display_name}, your bet ({selection}) must be between 0 and 36."
        except ValueError:
            pass

        for better in self.roulettegames[ctx.guild.id][bet_key]:
            if better.get(selection, False) and better[selection]["user"] == ctx.author.id:
                return f"{ctx.author.display_name}, you cannot make a duplicate bet on ({selection})."

        try:
            await self.roulettewithdraw(ctx, amount)
            self.roulettegames[ctx.guild.id][bet_key].append({selection: {"user": ctx.author.id, "amount": amount}})
            return True
        except ValueError:
            return f"{ctx.author.display_name}, you do not have enough funds to complete this bet ({selection})."

    async def betting(self, ctx, amount: int, bet: str):
        """
        This function processes the overall =roulette bet

        e.g.
        =rbet 100 1, 2, 3
        =rbet 100 1 2 3
        =rbet 100 even
        """
        success = []
        failure = []

        bets = bet.split(',')
        for b in bets:
            parsed_bet = ""
            trimmed_bet = b.strip()
            if len(trimmed_bet):
                if str(trimmed_bet).lower() in BET_TYPES:
                    parsed_bet = trimmed_bet.lower()
                else:
                    try:
                        parsed_bet = int(trimmed_bet)
                    except ValueError:
                        failure.append(f"{ctx.author.display_name}, invalid bet ({trimmed_bet}).")
                if isinstance(parsed_bet, int) or parsed_bet:
                    bet_placed = await self.single_bet(ctx, amount, parsed_bet)
                    if bet_placed is True:
                        success.append(parsed_bet)
                    else:
                        failure.append(bet_placed)

        if len(success):
            await ctx.send(f"{ctx.author.display_name} placed a {humanize_number(amount)} {await bank.get_currency_name(ctx.guild)} bet on {', '.join(map(str, success))} for a total of {humanize_number(len(success) * amount)} {await bank.get_currency_name(ctx.guild)}.")
        if len(failure):
            length_limited_message = ""
            failure_count = len(failure)
            for i, fail in enumerate(failure):
                if (len(length_limited_message) + len(fail) < 1900):
                    length_limited_message = length_limited_message + '\n' + fail
                else:
                    # Messages overflows, send it and reset the length_limited_message
                    await ctx.send(length_limited_message)
                    length_limited_message = fail

                # Last element in array, make sure the message is sent
                if (failure_count-1 == i and len(length_limited_message)):
                    await ctx.send(length_limited_message)


    async def payout(self, ctx, number, game_bets):
        msg = []
        conf = await self.configglobalcheck(ctx)
        payouts = await conf.roulette_payouts()
        color = NUMBERS[number]

        # Determine odd/even; exclude 0
        if number == 0:
            odd_even = None
        elif number % 2 != 0:
            odd_even = "odd"
        else:
            odd_even = "even"

        # Determine 1st half/2nd half; exclude 0
        if number == 0:
            half = None
        elif number <= 18:
            half = "1st half"
        else:
            half = "2nd half"

        dozen = "N/A"
        if game_bets["dozen"]:
            if number == 0:
                dozen = "No dozen winning bet."
            elif number <= 12:
                dozen = "1st dozen"
            elif number <= 24:
                dozen = "2nd dozen"
            else:
                dozen = "3rd dozen"
        column = "N/A"
        if game_bets["column"]:
            if number == 0:
                pass
            elif number in COLUMNS[0]:
                column = "1st column"
            elif number in COLUMNS[1]:
                column = "2nd column"
            else:
                column = "3rd column"
        payout_types = {
            "zero": number,
            "color": color,
            "number": number,
            "odd_or_even": odd_even,
            "halfs": half,
            "dozen": dozen,
            "column": column,
        }

        players = {}
        for k, v in game_bets.items():
            if type(v) is bool:
                continue
            
            for item in v:
                for key, val in item.items():
                    players[ctx.guild.get_member(val['user'])] = 0

        for bettype, value in payout_types.items():
            for bet in game_bets[bettype]:
                bet_type = list(bet.keys())[0]
                if bet_type == value:
                    betinfo = list(bet.values())[0]
                    user = ctx.guild.get_member(betinfo["user"])
                    print("---------")
                    print("BetInfo:")
                    print(betinfo)
                    print("BetType:")
                    print(bettype)
                    print("Payouts:")
                    print(payouts)
                    print("---------")
                    payout = betinfo["amount"] + (betinfo["amount"] * payouts[bettype])
                    players[user] += payout
                    if not await self.walletdisabledcheck(ctx):
                        user_conf = await self.configglobalcheckuser(user)
                        wallet = await user_conf.wallet()
                        try:
                            await self.walletdeposit(ctx, user, payout)
                        except ValueError:
                            max_bal = await conf.wallet_max()
                            payout = max_bal - wallet
                    else:
                        try:
                            await bank.deposit_credits(user, payout)
                        except BalanceTooHigh as e:
                            payout = e.max_bal - await bank.get_balance(user)
                            await bank.set_balance(user, e.max_bal)
                    msg.append([bet_type, humanize_number(payout), user.display_name])
                else:
                    betinfo = list(bet.values())[0]
                    user = ctx.guild.get_member(betinfo['user'])
                    players[user] -= betinfo['amount']
                    
        await self.update_leaderboard(players)
        return msg

    async def update_leaderboard(self, players):
        if not players:
            return

        for player in players.keys():
            conf = await self.configglobalcheckuser(player)
            stats = await conf.roulette_stats()

            stats['games'] += 1
            stats['total'] += players[player]

            await conf.roulette_stats.set(stats)        

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @roulette_disabled_check()
    async def roulette(self, ctx, amount: int, *, bet):
        """Bet on the roulette wheel.

        **Current supported bets**:
        Single   - Any single number.
        Colors   - Red/Black
        Halfs    - 1st/2nd half
        Even Odd - Even or Odd
        Dozens   - 1st/2nd/3rd Dozen (Groups of 12)
        Colums   - 1st/2nd/3rd Column.
        - This is based on the English version of the roulette wheel.
        """
        if ctx.guild.id not in self.roulettegames:
            await self.roulette_start(ctx)
        if self.roulettegames[ctx.guild.id]["started"]:
            return await ctx.send(f"{ctx.author.display_name}, the wheel is already spinning.")
        conf = await self.configglobalcheck(ctx)
        betting = await conf.betting()
        minbet, maxbet = betting["min"], betting["max"]
        if amount < minbet:
            return await ctx.send(f"{ctx.author.display_name}, your bet must be greater than {humanize_number(minbet)}.")
        if amount > maxbet:
            return await ctx.send(f"{ctx.author.display_name}, your bet must be less than {humanize_number(maxbet)}.")
        return await self.betting(ctx, amount, bet)

    async def roulette_spin(self, ctx, time):
        async with ctx.typing():
            await asyncio.sleep(time)
        self.roulettegames[ctx.guild.id]["started"] = True
        emb = discord.Embed(
            color=discord.Color.red(),
            title="Roulette Wheel",
            description="The wheel begins to spin.",
        )
        msg = await ctx.send(embed=emb)
        await asyncio.sleep(random.randint(3, 8))
        number = random.randint(0, 36)
        payouts = await self.payout(ctx, number, self.roulettegames[ctx.guild.id])
        emoji = EMOJIS[NUMBERS[number]]
        emb = discord.Embed(
            color=discord.Color.red(),
            title="Roulette Wheel",
            description="The wheel lands on {} {} {}\n\n**Winnings**\n{}".format(
                NUMBERS[number],
                number,
                emoji,
                box(
                    tabulate.tabulate(payouts, headers=["Bet", "Amount Won", "User"]),
                    lang="prolog",
                )
                if payouts
                else "None.",
            ),
        )
        await msg.edit(embed=emb)
        del self.roulettegames[ctx.guild.id]

    @roulette_disabled_check()
    @roulette.command(name="debug")
    async def roulette_debug(self, ctx):
        """Debugging."""
        guild = ctx.guild
        user = ctx.guild.get_member(209071317905965056)
        conf = await self.configglobalcheckuser(user)
        stats = await conf.roulette_stats()
        await ctx.send(stats)

    @roulette_disabled_check()
    @roulette.command(name="start")
    async def roulette_start(self, ctx):
        """Start a game of roulette."""
        if ctx.guild.id not in self.roulettegames:
            self.roulettegames[ctx.guild.id] = {
                "zero": [],
                "color": [],
                "number": [],
                "dozen": [],
                "odd_or_even": [],
                "halfs": [],
                "column": [],
                "started": False,
            }
        else:
            return await ctx.send("There is already a roulette game on.")
        conf = await self.configglobalcheck(ctx)
        time = await conf.roulette_time()
        await ctx.send(
            "The roulette wheel will be spun in {} seconds.".format(time), delete_after=time
        )
        # set 5 to time
        asyncio.create_task(self.roulette_spin(ctx, time))

    @roulette_disabled_check()
    @roulette.command(name="leaderboard")
    async def roulette_leaderboard(self, ctx, top: int = 10):
        """Print the leaderboard.
        
        Defaults to top 10.

        Examples:
         - `[p]roulette leaderboard`
         - `[p]roulette leaderboard 50`
        
        Arguments:
         - `<top>` How many positions on the leaderboard to show.
        """

        guild = ctx.guild
        author = ctx.author
        embed_requested = await ctx.embed_requested()
        footer_message = ("Page {page_num}/{page_len}.")

        if top < 1:
            top = 10

        base_embed = discord.Embed(title=("Roulette Leaderboard"))
        if await bank.is_global():
            raw_accounts = await self.config.all_users()
            if guild is not None:
                tmp = raw_accounts.copy()
                for acc in tmp:
                    if not guild.get_member(acc):
                        del raw_accounts[acc]
        else:
            raw_accounts = await self.config.all_members(guild)

        roulette_list = sorted(raw_accounts.items(), key=lambda x: x[1]["roulette_stats"]["total"], reverse=True)[:top]
        base_embed.set_author(name=guild.name)

        try:
            total_len = len(str(roulette_list[0][1]["roulette_stats"]["total"]))
        except IndexError:
            return await ctx.send("There are no users on the roulette leaderboard.")

        pound_len = len(str(len(roulette_list)))
        header = "\n{pound:{pound_len}}{score:{total_len}}{name:15}\n".format(
            pound="#",
            name="Name",
            score="Total",
            total_len=total_len+6,
            pound_len=pound_len+3
        )
        highscores = []
        pos = 1
        temp_msg = header

        for acc in roulette_list:
            if acc[0] == 209071317905965056:
                await ctx.send(acc[1]['roulette_stats'])
                
            if acc[1]['roulette_stats']['games'] <= 0:
                continue

            try:
                name = guild.get_member(acc[0]).display_name
            except AttributeError:
                user_id = ""
                if await ctx.bot.is_owner(ctx.author):
                    user_id = f"({str(acc[0])})"
                name = f"{acc[1]['name']} {user_id}"

            total = acc[1]["roulette_stats"]["total"]
            total = humanize_number(total)
            
            if acc[0] != author.id:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{total: <{total_len+5}} {name}\n"
                )
            else:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{total: <{total_len+5}} "
                    f"<<{author.display_name}>>\n"
                )

            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text = footer_message.format(
                            page_num=len(highscores) + 1,
                            page_len=ceil(len(roulette_list) / 10)
                        )
                    )
                    highscores.append(embed)
                else:
                    highscores.append(box(temp_msg, lang="md"))
                temp_msg = header
            pos += 1

        if temp_msg != header:
            if embed_requested:
                embed = base_embed.copy()
                embed.description = box(temp_msg, lang="md")
                embed.set_footer(
                    text=footer_message.format(
                        page_num=len(highscores) + 1,
                        page_len=ceil(len(roulette_list) / 10)
                    )
                )
                highscores.append(embed)
            else:
                highscores.append(box(temp_msg, lang="md"))

        if highscores:
            await menu(ctx, highscores, DEFAULT_CONTROLS)
        else:
            await ctx.send("Nothing found.")

        #await ctx.send(roulette_list)



    @checks.admin_or_permissions(manage_guild=True)
    @check_global_setting_admin()
    @commands.guild_only()
    @commands.group()
    async def rouletteset(self, ctx):
        """Manage settings for roulette."""

    @roulette_disabled_check()
    @check_global_setting_admin()
    @commands.guild_only()
    @rouletteset.command()
    async def time(
        self,
        ctx,
        time: commands.TimedeltaConverter(
            minimum=datetime.timedelta(seconds=30),
            maximum=datetime.timedelta(minutes=5),
            default_unit="seconds",
        ),
    ):
        """Set the time for roulette wheel to start spinning."""
        seconds = time.total_seconds()
        conf = await self.configglobalcheck(ctx)
        await conf.roulette_time.set(seconds)
        await ctx.tick()

    @check_global_setting_admin()
    @commands.guild_only()
    @rouletteset.command()
    async def toggle(self, ctx):
        """Toggle roulette on and off."""
        conf = await self.configglobalcheck(ctx)
        toggle = await conf.roulette_toggle()
        if toggle:
            await conf.roulette_toggle.set(False)
            await ctx.send("Roulette has been disabled.")
        else:
            await conf.roulette_toggle.set(True)
            await ctx.send("Roulette has been enabled.")

    @roulette_disabled_check()
    @check_global_setting_admin()
    @commands.guild_only()
    @rouletteset.command()
    async def payouts(self, ctx, type, payout: int):
        """Set payouts for roulette winnings.

        Note: payout is what your prize is multiplied by.
        Valid types:
        zero
        single
        color
        dozen
        odd_or_even
        halfs
        column
        """
        types = ["zero", "number", "color", "dozen", "odd_or_even", "halfs", "column"]
        if type not in types:
            return await ctx.send(
                f"{ctx.author.display_name}, that's not a valid payout type. The available types are `{', '.join(types)}`"
            )
        conf = await self.configglobalcheck(ctx)
        async with conf.roulette_payouts() as payouts:
            payouts[type] = payout
        await ctx.tick()

    @rouletteset.command(name="settings")
    async def _settings(self, ctx):
        """Roulette Settings."""
        conf = await self.configglobalcheck(ctx)
        enabled = await conf.roulette_toggle()
        payouts = await conf.roulette_payouts()
        time = await conf.roulette_time()
        embed = discord.Embed(color=ctx.author.color, title="Roulette Settings")
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled")
        embed.add_field(name="Time to Spin", value=humanize_timedelta(seconds=time))
        payoutsmsg = "".join(
            f"**{payout.replace('_', ' ').title()}**: {payouts[payout]}\n"
            for payout in sorted(payouts, key=lambda x: payouts[x], reverse=True)
        )

        embed.add_field(name="Payout Settings", value=payoutsmsg)
        await ctx.send(embed=embed)

