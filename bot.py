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
from bson.binary import Binary
import pickle

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
#GUILD = os.getenv('DISCORD_GUILD')

client = discord.Client()

connection = MongoClient()
db = connection['sind3d-db']
collection = db['sind3d-collection']

config = None
with open('config.json', 'r') as f:
    config = json.load(f)

def encode_data(data):
    json_data = json.dumps(data)
    link_data = base64.b64encode(str(json_data).encode('utf-8'))
    
    return link_data

@client.event
async def on_message(message):

    # avoid message from
    if message.author == client.user:
        return

    if '--sin3d-list' in message.content.lower():

        collaborators = collection.find()

        collaborators_list = ""
        counter = 0

        for collaborator in collaborators:
            if collaborator.discord:
                collaborators_list += "- " + collaborator.username + " (discord account)"
            else:
                collaborators_list += "- " + collaborator.user_id + " (anonymous)"

            counter += 1

        await message.channel.send("We have now {0} collaborators! Here their names:\n\n{1}\n\nThanks for your contributions!".format(counter, collaborators_list))

    if '--sin3d-custom' in message.content.lower():

        # get custom userid
        if ' ' not in message.content.lower():
            elements = message.content.lower().split(' ')
            userId = elements[1] # the second element

            results = collection.find_one({'user_id': message.author.id})
            
            if results is None:
                # add user with custom userId as collaborators
                collection.insert_one({'user_id': userId, 'username': message.author.name,'discord': False, 'config': config})

            user_config = config
            user_config['userId'] = userId

            # generate custom link
            generated_link_info = encode_data(user_config)
            generated_link = config['hostConfig'] + '/#/?q=' + bytes(generated_link_info).decode("utf-8")

            await message.author.send("Hello {0},\n\nHere your unique SIN3D-app link : \n{1}\n\n \
                                    If you do not remember it, please ask it again using (`--sin3d-link`) command.\n\n \
                                    Thanks in advance for your contribution!")
            
        else:
            await message.channel.send("We have now {0} collaborators! Here their names:\n\n{1}\n\nThanks for your contributions!".format(counter, collaborators_list))

    if '--sin3d-link' in message.content.lower():
        
        results = collection.find_one({'user_id': message.author.id})
        
        if results is None:
            # add user with id as collaborators
            collection.insert_one({'user_id': message.author.id, 'username': message.author.name,'discord': True, 'config': config})

        # custom user config with its own user ID
        userId = message.author.id
        user_config = config
        user_config['userId'] = userId

        # generate custom link
        generated_link_info = encode_data(user_config)
        generated_link = config['hostConfig'] + '/#/?q=' + bytes(generated_link_info).decode("utf-8")

        await message.author.send("Hello {0},\n\nHere your unique SIN3D-app link : \n{1}\n\n \
                                If you do not remember it, please ask it again using (`--sin3d-custom {{custom-identifier}}`) command.\n\n \
                                Thanks in advance for your contribution!".format(message.author.name, generated_link))

    if '--sin3d-help' in message.content.lower():
         await message.channel.send("Hi <@{0}>, " \
                "just to remember, you can use the following commands:\n" \
                "`--sin3d-link` : send you private message your SIN3D :link: linked to your discord account\n" \
                "`--sin3d-custom {{custom-identifier}}` : send you private message with your SIN3D :link: which uses your custom identifier :id:\n" \
                "`--sin3d-list` : gives information about all callobarators \n" \
                .format(message.author.id))

@client.event
async def on_ready():
    
    print(
        f'{client.user} is connected\n'
    )

client.run(TOKEN)
