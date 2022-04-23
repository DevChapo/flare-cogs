import asyncio
import discord
from redbot.core import bank, commands

class Giveaway(commands.Cog):
    """Cog for money giveaway"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def giveaway(self, ctx, amount: int):
        """
        This command initiates a giveaway for the amount specified.

        After initiation, the bot will add a reaction. For the next minute,
        everyone who reacts will be eligible for a split of the amount the
        user is giving away.

        **Example: =giveaway 1000000**
        """
        currency = await bank.get_currency_name(guild=ctx.guild)
        if await bank.get_balance(ctx.author) < amount:
            await ctx.send(f"{ctx.author.display_name} is too poor to give {amount} {currency} away.")
            return

        if amount < 0:
            await ctx.send(f"{ctx.author.display_name} is trying to steal from the poor!")
            return
        elif amount == 0:
            await ctx.send(f"Thank you for the lint in your pockets, {ctx.author.display_name}.")
            return

            """
            if await bank.get_balance(ctx.author) < amount * -1:
                await bank.withdraw_credits(ctx.author, await bank.get_balance(ctx.author))
            else:
                await bank.withdraw_credits(ctx.author, amount * -1)

            await ctx.send(f"{ctx.author.display_name} is trying to steal from the poor! FINED.")
            return
            """

        await bank.withdraw_credits(ctx.author, amount)
        msg = await ctx.send(f"Philanthropy! {ctx.author.display_name} is giving away {amount} {currency}! React Now!")
        await msg.add_reaction('✅')

        await asyncio.sleep(60)
        cache_msg = discord.utils.get(self.bot.cached_messages, id=msg.id)

        users = []
        recipients = []
        for reaction in cache_msg.reactions:
            if reaction.emoji == '✅':
                async for user in reaction.users():
                    if not user.bot:
                        recipients.append(user)

        if not recipients:
            await ctx.send(f"The giveaway ends with no recipients.")
            return

        payout = int(amount / len(recipients))
        if payout <= 0:
            await bank.deposit_credits(ctx.author, amount)
            await ctx.send(f"Returned {ctx.author.display_name}'s {amount} {currency} because they're too poor to do real charity.")
            return
        
        for user in recipients:
            users.append(user.display_name)
            await bank.deposit_credits(user, payout)
        
        users_string = ', '.join(users)
        string_end = f"{payout} {currency} from {ctx.author.display_name}'s giveaway."
        if len(users) == 1:
            string = f"{users_string} receives " + string_end
        else:
            string = f"{users_string} receive " + string_end
        
        await ctx.send(string)