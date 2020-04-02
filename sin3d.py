# bot.py
import os
import datetime
import json
import base64

import discord
import asyncio
import time
from dotenv import load_dotenv


# db connection
from pymongo import MongoClient
from pymongo.collection import Collection
from bson.binary import Binary
import pickle

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
#GUILD = os.getenv('DISCORD_GUILD')

client = discord.Client()

connection = MongoClient()
db = connection['sind3d-db']
collection = db['sind3d-collection']

embed_color = 0x128ba6

config = None
with open('config.json', 'r') as f:
    config = json.load(f)

def encode_data(data):
    json_data = json.dumps(data)
    link_data = base64.b64encode(str(json_data).encode('utf-8'))
    
    return link_data

def generate_link(data):
    # generate custom link
    generated_link_info = encode_data(data)
    generated_link = data['hostConfig'] + '/#/?q=' + bytes(generated_link_info).decode("utf-8")

    return generated_link

@client.event
async def on_message(message):

    # avoid message from
    if message.author == client.user:
        return

    if message.content.lower().startswith('--sin3d-list'):

        contributors = collection.find()

        discord_contributors = ""
        anonymous_contributors = ""
        n_contributors = contributors.count()

        n_discord = 0
        n_anonymous = 0

        contributor_str =  'contributor' if n_contributors <= 1 else 'contributors'

        for contributor in contributors:
            if contributor['discord']:
                discord_contributors += ":white_small_square: " + contributor['username'] + "\n"
                n_discord += 1
            else:
                anonymous_contributors += ":white_small_square: " + contributor['user_id'] + "\n"
                n_anonymous += 1

        anonymous_contributors = 'No anonymous contributors yet' if anonymous_contributors == "" else anonymous_contributors
        discord_contributors = 'No dicord contributors yet' if discord_contributors == "" else discord_contributors

        embed = discord.Embed(
            title=':handshake: We have now {0} {1}! :handshake: '.format(n_contributors, contributor_str), 
            description=':earth_africa: List of {0} :earth_africa:'.format(contributor_str), 
            color=embed_color)
        embed.add_field(
            name="Discord ({0})".format(n_discord), 
            value=discord_contributors, 
            inline=False)
        embed.add_field(
            name="Anonymous ({0})".format(n_anonymous), 
            value=anonymous_contributors, 
            inline=False)
        embed.set_footer(text="Thanks a lot for your contributions!") 
        
        await message.channel.send(embed=embed)

    if message.content.lower().startswith('--sin3d-custom'):

        # get custom userid
        splited_message = message.content.lower().split(' ')

        if len(splited_message) > 1 and len(splited_message) <= 2:
            userId = splited_message[1] # the second element

            results = collection.find_one({'user_id': userId})
            
            if results is None:
                # add user with custom userId as contributors
                collection.insert_one({'user_id': userId, 'username': userId, 'discord': False, 'config': config})

                user_config = config
                user_config['userId'] = userId

                # generate custom user link
                generated_link = generate_link(user_config)    

                embed = discord.Embed(
                    title=':open_hands: Your SIN3D-app link with `{0}` :id: :open_hands:'.format(userId), 
                    description='You can now launch the app :paperclip:', 
                    color=embed_color,
                    url=generated_link)
                embed.add_field(
                    name=":white_small_square: Information:", 
                    value="This link is unique, **anonymous** and **cannot** be regenerated.", 
                    inline=False)
                embed.add_field(
                    name=":white_small_square: If you need another :id:, please use again:", 
                    value="`--sin3d-custom {{custom-identifier}}`", 
                    inline=False)
                embed.set_footer(text="Thanks in advance for your contribution!") 

                await message.author.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=':warning: Ooops, :id: asked already used :warning:', 
                    description='`{0}` identifier already exists'.format(userId), 
                    color=embed_color)
                embed.add_field(
                    name=":white_small_square: If you need to generate another one, please run again using a new :id: :", 
                    value="`--sin3d-custom {{custom-identifier}}`", 
                    inline=False)
                embed.add_field(
                    value="\t`--sin3d-custom my-identifier`",
                    name="\t__Example:__", 
                    inline=False)
                embed.set_footer(text="Please, use your previous identifier if it is not lost!") 

                await message.author.send(embed=embed)
            
        else:
            embed = discord.Embed(
                title=':warning: Unvalid use of command :warning:', 
                description='It seems the :id: passed is not valid', 
                color=embed_color)
            embed.add_field(
                name=":white_small_square: Please run again this command as shown in the example:", 
                value="`--sin3d-custom {{custom-identifier}}`", 
                inline=False)
            embed.add_field(
                value="\t`--sin3d-custom my-identifier`",
                name="\t__Example:__", 
                inline=False)
            embed.set_footer(text="Please, use your previous username if it is not lost!") 

            await message.author.send(embed=embed)

    if message.content.lower().startswith('--sin3d-link'):
        
        results = collection.find_one({'user_id': message.author.id})
        
        if results is None:
            # add user with id as contributors
            collection.insert_one({'user_id': message.author.id, 'username': str(message.author),'discord': True, 'config': config})

        # custom user config with its own user ID
        userId = message.author.id
        user_config = config
        user_config['userId'] = userId

        # generate custom link
        generated_link = generate_link(user_config)

        embed = discord.Embed(
            title=':open_hands: {0}, your SIN3D-app link :open_hands:'.format(str(message.author)), 
            description='You can now launch the app :paperclip:', 
            color=embed_color,
            url=generated_link)
        embed.add_field(
            name=":white_small_square: Information:", 
            value="This link is associated to your **discord** account.", 
            inline=False)
        embed.add_field(
            name=":white_small_square: If you do not remember it, please ask it again using:", 
            value="`--sin3d-link`", 
            inline=False)
        embed.set_footer(text="Thanks in advance for your contribution!") 

        await message.author.send(embed=embed)

    if message.content.lower().startswith('--sin3d-help'):

        embed = discord.Embed(
            title=':ledger: SIN3D-bot documentation :ledger:', 
            description=':computer: All available commands :computer:',
            color=embed_color)
        embed.add_field(
            value="`--sin3d-link`",  
            name=":white_small_square: Send your SIN3D app :link: linked to your **discord** account",
            inline=False)
        embed.add_field(
            value="`--sin3d-custom {{custom-identifier}}`",
            name=":white_small_square: Send your SIN3D app :link: with custom :id: (**anonymous**)",
            inline=False)
        embed.add_field(
            value="\t`--sin3d-custom my-identifier`",
            name="\t__Example:__", 
            inline=False)
        embed.add_field(
            value="`--sin3d-list`",
            name=":white_small_square: Gives information about all callaborators", 
            inline=False)
        embed.set_footer(text="That was a pleasure!") #if you like to

        await message.channel.send(embed=embed)

@client.event
async def on_ready():
    
    print(
        f'{client.user} is connected\n'
    )

client.run(TOKEN)
