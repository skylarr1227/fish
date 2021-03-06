#!/usr/bin/env python3

import os
import discord
from redbot.core import commands
from redbot.core import utils
import sqlite3 as sq

import pprint as pp

import pathlib
import random

BaseCog = getattr(commands, "Cog", object)


RATINGSFILE = os.path.join(str(pathlib.Path.home()), "bots.db")


names = [
    'bot',
    'human',
    'person',
    'thing',
    'boy',
    'girl',
    'robot',
    'flesh creature',
    'meat suit',
    'individual',
    'member of the collective',
    'unspeakable horror',
    'slut',
    'creature',
    'wonder boy',
    'wonder girl',
    'cat',
    'dolphin',
    'batman',
    'dragon',
    'abomination',
    'squid',
    'doggo',
    'kitter',
    'hoarder',
    'harlot',
    'cupcake',
    'noodle',
    'computer',
    'tentacle from the abyss',
    'worshiper of the sun',
    'acolyte of Sal-Shaggoth',
]

goodwords = [
    'good',
    'awesome',
    'excellent',
    'most excellent',
    'average',
    'solidly ok',
    'surpassed all expectations',
    'a+',
    'pleasantly surprising',
    'happy',
    'rockstar',
    'ninja',
    'perfect',
]

badwords = [
    'bad',
    'mediocre',
    'below average',
    'subpar',
    'awful',
    'horrifying',
    'naughty',
    'evil',
    'macabre',
    'disappointing',
    'depressing',
    'failing',
]


def user_exists(userid, cursor=None):
    if cursor is None:
        con = sq.connect(RATINGSFILE)
        c = con.cursor()
    else:
        c = cursor

    c.execute("SELECT * FROM ratings WHERE userid=?", (userid,))

    results = c.fetchall()

    exists = False

    if len(results) != 0:
        exists = True

    if cursor is None:
        con.close()

    return exists


def get_user_rating(userid, cursor=None):
    if cursor is None:
        con = sq.connect(RATINGSFILE)
        c = con.cursor()
    else:
        c = cursor

    c.execute("SELECT good, bad FROM ratings WHERE userid=?", (userid,))

    results = c.fetchall()

    rating = None

    if len(results) != 0:
        rating = (results[0][0], results[0][1])
    else:
        # Add if doesn't exist, hopefully prevent crashes
        c.execute(
            "INSERT INTO ratings(userid, good, bad) VALUES(?,?,?)", (userid, 0, 0)
        )
        con.commit()

    if cursor is None:
        con.close()

    return rating


class GoodBot(BaseCog):
    def __init__(self, bot):
        self.bot = bot

        con = sq.connect(RATINGSFILE)
        with con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS ratings("
                "id INT PRIMARY KEY,"
                "userid TEXT UNIQUE,"
                "good INT,"
                "bad INT"
                ")"
            )
            con.commit()

        self.previous_author = dict()
        self.noticed = set()

    @commands.command()
    async def rating(self, ctx, user: discord.Member = None):
        """
        Displays a user rating in the form <score> (<updoots>/<downdoots>/<totaldoots>)
        """
        if user is None:
            user = ctx.author

        if not user_exists(user.id):
            await ctx.send("{} hasn't been rated".format(user.mention))
            return

        good, bad = get_user_rating(user.id)

        await ctx.send("User {} has a score of {}".format(user.mention, good - bad))

    @commands.command()
    async def goodbots(self, ctx):
        con = sq.connect(RATINGSFILE)
        c = con.cursor()
        c.execute("SELECT userid, good, bad from ratings ORDER BY (good - bad) DESC")
        db_results = c.fetchall()
        results = []
        for userid, good, bad in db_results:
            try:
                user = ctx.guild.get_member(int(userid))
                if user is not None:
                    results.append((user.nick, good, bad, good - bad, 100 * (good - bad) / (good + bad)))
            except Exception as e:
                print(e)
                pass
        results.sort(key=lambda tup: -tup[-2])
        results = [
            "{}  -> {} - {} = {} ({:0.02f}% positive)".format(*row)
            for row in results]
        await ctx.send("Scores:")
        for i in range(0, len(results), 20):
            await ctx.send("```{}```".format('\n'.join(results[i:i+20])))
        con.close()

    @commands.command()
    async def see_previous(self, ctx):
        if ctx.message.author.id != "142431859148718080":
            return
        resolved_previous = {
            self.bot.get_guild(server_id).name: {
                self.bot.get_channel(channel_id)
                .name: self.bot.get_guild(server_id)
                .get_member(user_id)
                .name
                for channel_id, user_id in channels.items()
            }
            for server_id, channels in self.previous_author.items()
        }
        pretty_version = pp.pformat(resolved_previous)
        await ctx.send("```{}```".format(pretty_version))


def generate_handlers(bot, gb_instance):
    async def goodbot(message, reaction=None, action=None):
        # Prevent snek from voting on herself or counting
        # if bot.user.id == message.author.id:
        #     return

        # Prevent acting on DM's
        if message.guild is None:
            return

        clean_message = message.clean_content.lower()
        server = message.guild.id
        channel = message.channel.id

        rating = None
        if "good bot" in clean_message:
            rating = (1, 0)
        elif "bad bot" in clean_message:
            rating = (0, 1)
        else:
            prev_author = message.author.id
            if server not in gb_instance.previous_author:
                gb_instance.previous_author[server] = dict()
            gb_instance.previous_author[server][channel] = prev_author

        if (
            (rating is not None)
            and (gb_instance.previous_author[server].get(channel) is not None)
            and (gb_instance.previous_author[server][channel] != message.author.id)
        ):
            await rate_user(gb_instance.previous_author[server][channel], rating)

    async def rate_user(userid, rating):
        con = sq.connect(RATINGSFILE)
        c = con.cursor()
        if not user_exists(userid):
            c.execute(
                "INSERT INTO ratings(userid, good, bad) VALUES(?,?,?)",
                (userid, *rating),
            )
            con.commit()
        else:
            oldgood, oldbad = get_user_rating(userid, cursor=c)
            good, bad = (oldgood + rating[0], oldbad + rating[1])
            # MM: You've had your fun
            # if ((userid == '142431859148718080') and ((good - bad) <= 0)):
            #     bad = good - 3
            c.execute(
                "UPDATE ratings SET good=?, bad=? WHERE userid=?", (good, bad, userid)
            )
            con.commit()
        con.close()

    async def parse_reaction_add(reaction, user):
        # Prevent acting on DM's
        if reaction.message.guild is None:
            return

        server = reaction.message.guild.id
        channel = reaction.message.channel.id

        rating = None  # (+, -)
        # MM: you've had your fun
        # Upvote SpatulaFish
        # if reaction.emoji in ['👎', '👍'] and reaction.message.author.id == '142431859148718080':
        #     rating = (1, 0)
        if reaction.emoji == "👎":
            # MM proposal:
            # Element of randomness: Self downvotes could result in updoot
            if user.id == reaction.message.author.id:
                if random.random() < 0.5:
                    rating = (1, 0)
                else:
                    rating = (0, 1)
            else:
                rating = (0, 1)
            # MM proposal:
            # Just call the poor sod a bad bot
            # if ((reaction.message.author.id != '142431859148718080') and (reaction.count >= 5)):
            #     await bot.delete_message(reaction.message)
            if (reaction.count >= 7) and (
                reaction.message.id not in gb_instance.noticed
            ):
                phrase = '{} IS A {} {}'.format(reaction.message.author.mention, random.choice(badwords).upper(), random.choice(names).upper())
                await bot.send_filtered(
                    reaction.message.channel,
                    content=phrase,
                )
                gb_instance.noticed.add(reaction.message.id)
        elif reaction.emoji == "👍":
            # Downvote for self votes
            if user.id == reaction.message.author.id:
                rating = (0, 1)
            else:
                rating = (1, 0)
            if (reaction.count >= 7) and (
                reaction.message.id not in gb_instance.noticed
            ):
                phrase = '{} IS A {} {}'.format(reaction.message.author.mention, random.choice(goodwords).upper(), random.choice(names).upper())
                await bot.send_filtered(
                    reaction.message.channel,
                    content=phrase,
                )
                gb_instance.noticed.add(reaction.message.id)

        if rating is not None:
            await rate_user(reaction.message.author.id, rating)

    async def parse_reaction_remove(reaction, user):
        # Prevent acting on DM's
        if reaction.message.guild is None:
            return

        server = reaction.message.guild.id
        channel = reaction.message.channel.id

        rating = None
        # do nothing for remove, already punished once for self votes
        if user.id == reaction.message.author.id:
            return
        elif reaction.emoji == "👎":
            rating = (1, 0)
        elif reaction.emoji == "👍":
            rating = (0, 1)
        else:
            return

        await rate_user(reaction.message.author.id, rating)

    return goodbot, parse_reaction_add, parse_reaction_remove
