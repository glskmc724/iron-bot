import discord
import iron_token
import asyncio
import youtube

from discord.ui import Button, View
from discord import ButtonStyle

TOKEN = iron_token.TOKEN

def verify_channel(channel_id):
    filename = "channels.list"
    channel_list_file = open(filename, 'r')
    channel_list = channel_list_file.readlines()

    for channel in channel_list:
        if (channel[0] == '#'):
            continue
        elif (int(channel) == channel_id):
            return True
    return False


class Client(discord.Client):
    searched_list = dict()
    searching_list = dict()
    repeat_list = dict()
    message_list = dict()
    playing_list = dict()
    vc_list = dict()
    async def pause_callback(self, interaction):
        if (self.vc_list[interaction.channel_id].is_playing()):
            self.vc_list[interaction.channel_id].pause()
            await self.view_msg.edit(content = "Paused", view = await self.create_view())
        await interaction.response.defer()

    async def stop_callback(self, interaction):
        if (self.vc_list[interaction.channel_id].is_playing() or self.vc_list[interaction.channel_id].is_paused()):
            self.vc_list[interaction.channel_id].stop()
        await interaction.response.defer()

    async def resume_callback(self, interaction):
        if (self.vc_list[interaction.channel_id].is_paused()):
            self.vc_list[interaction.channel_id].resume()
            await self.view_msg.edit(content = "Playing", view = await self.create_view())
        await interaction.response.defer()

    async def search_callback(self, interaction):
        self.searched_list[interaction.channel_id] = True
        await interaction.response.send_message("Input music title for searching")

    async def create_view(self, channel_id):
        """ ⇄  ◁  II ▷ ↻ 🔍"""
        pause_btn = Button(label = "II Paused", style = ButtonStyle.secondary)
        pause_btn.callback = self.pause_callback
        stop_btn = Button(label = "□ Stop", style = ButtonStyle.secondary)
        stop_btn.callback = self.stop_callback
        resume_btn = Button(label = "▷ Skip", style = ButtonStyle.secondary)
        resume_btn.callback = self.resume_callback
        repeat_btn = Button(label = "↻ Repeat", style = ButtonStyle.secondary)
        repeat_btn.callback = None
        search_btn = Button(label = "🔍 Search", style = ButtonStyle.secondary)
        search_btn.callback = self.search_callback
        view = View()
        if (self.vc_list[channel_id].is_paused()):
            view.add_item(resume_btn)
        else:
            view.add_item(pause_btn)
        view.add_item(stop_btn)
        view.add_item(search_btn)
        return view

    async def create_content(self, youtube_content):
        title = youtube_content["snippet"]["title"]
        thumbnail = youtube_content["snippet"]["thumbnails"]["medium"]
        content = "{}\r\n{}".format(title, thumbnail["url"])
        return content

    async def create_embed(self, youtube_content):
        title = youtube_content["snippet"]["title"]
        thumbnail = youtube_content["snippet"]["thumbnails"]["medium"]
        embed = discord.Embed(title = title, description = "", color = discord.Color.random())
        embed.set_image(url = thumbnail["url"])
        return embed

    async def create_search_result(self, results):
        embed = discord.Embed(title = "Search Result", color = discord.Color.random())
        idx = 1
        for result in results["items"]:
            title = result["snippet"]["title"]
            output = "{}. {}".format(idx, title)
            embed.add_field(name = output, value = "", inline = False)
            idx += 1
        return embed

    async def on_ready(self):
        filename = "channels.list"
        channel_list_file = open(filename, 'r')
        channel_list = channel_list_file.readlines()

        for channel in channel_list:
            if (channel[0] == '#'):
                continue
            else:
                self.searched_list[int(channel)] = False
                self.searching_list[int(channel)] = False
                self.repeat_list[int(channel)] = False
                self.playing_list[int(channel)] = list()
                self.message_list[int(channel)] = list()
                self.vc_list[int(channel)] = False
        return

    async def on_message(self, message):
        if (message.author == self.user):
            return

        if (message.content == "!delete"):
            await message.channel.purge(limit = 1000)
            return

        if (verify_channel(message.channel.id) != True):
            return
        
        channel = self.get_channel(message.channel.id)
        #await channel.send(message.content)

        self.user_msg = message
        msgs = [self.user_msg]
        
        if (self.searched_list[message.channel.id] == True and self.searching_list[message.channel.id] == False):
            self.search_results = youtube.search_api(message.content, num_search = 5)
            self.searching_list[message.channel.id] = True
            embed = await self.create_search_result(self.search_results)
            msgs.append(await channel.send(embed = embed))
            return

        if (self.searched_list[message.channel.id] == True and self.searching_list[message.channel.id] == True):
            try:
                content = await self.create_content(self.search_results["items"][int(message.content) - 1])
                await channel.send(content = content)
                self.searched_list[message.channel.id] = False
                self.searching_list[message.channel.id] = False
                for msg in msgs:
                    await msg.delete()
                #message.content = content["snippet"]["title"]
                return
            except ValueError:
                msgs.append(await channel.send("Retry enter number"))
                return

        # find music
        res = youtube.search_api(message.content)
        self.playing_list[message.channel.id].append(res)

        # connect
        ch = self.get_channel(message.author.voice.channel.id)
        try:
            self.vc_list[message.channel.id] = await ch.connect()
        except discord.errors.ClientException:
            pass

        try:
            if (self.vc_list[message.channel.id].is_playing() or self.vc_list[message.channel.id].is_paused()):
                msgs.append(await channel.send(content = "Reserved: {}".format(res["items"][0]["snippet"]["title"])))
        except AttributeError:
            msgs.append(await channel.send(content = "You chat too fast"))
            return

        while True:
            if (self.playing_list[message.channel.id][0] == res):
                break
            else:
                await asyncio.sleep(0.1)

        # download music
        music = self.playing_list[message.channel.id][0]
        vidid = res["items"][0]["id"]["videoId"]
        link = "https://www.youtube.com/embed/{}".format(vidid)
        song = youtube.download(link)

        # holding
        while (self.vc_list[message.channel.id].is_playing() or self.vc_list[message.channel.id].is_paused()):
            await asyncio.sleep(0.1)

        # print description
        view = await self.create_view(message.channel.id)
        content = await self.create_content(music["items"][0])
        embed = await self.create_embed(music["items"][0])
        #self.view_msg = await channel.send(content = content, view = view)
        self.view_msg = await channel.send(embed = embed, view = view)
        msgs.append(self.view_msg)

        # playing
        self.playing_list[message.channel.id].remove(music)
        self.vc_list[message.channel.id].play(discord.FFmpegPCMAudio(executable = "ffmpeg", source = song))
        while (self.vc_list[message.channel.id].is_playing() or self.vc_list[message.channel.id].is_paused()):
            await asyncio.sleep(0.1)

        if (len(self.playing_list[message.channel.id]) == 0):
            await self.vc_list[message.channel.id].disconnect()

        for msg in msgs:
            await msg.delete()

intents = discord.Intents.default()
intents.message_content = True
client = Client(intents=intents)
client.run(TOKEN)
