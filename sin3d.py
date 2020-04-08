# bot.py
import os
import datetime
import json
import base64
import argparse
import shlex
import requests

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

rules = ['creator', 'admin']
output_folder = 'output'
output_results_folder = os.path.join(output_folder, 'results')
output_means_folder = os.path.join(output_folder, 'means')

connection = MongoClient()

db = connection['sin3d']

contributors_collection = db['sin3d-contributors']
management_collection = db['sin3d-management']
configurations_collection = db['sin3d-configuration']
data_collection = db['datas']

embed_color = 0x128ba6
diran_url_api = 'https://diran.univ-littoral.fr/api/'
diran_url_scenes_list = diran_url_api + 'listScenes'

default_config = None
with open('config.json', 'r') as f:
    default_config = json.load(f)


def check_guild_config(guild):

    guild_config = configurations_collection.find_one({'guild_id': guild.id})

    # check if guild configuration exists
    if guild_config is not None:
        print('Configuration found for', guild.name)
        print(guild_config['config'])
    else:
        print('Add default configuration for', guild.name)
        configurations_collection.insert_one({'guild_id': guild.id, 'guild_name': guild.name, 'config': default_config['config']})

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

    # extract current user role
    user_role = management_collection.find_one({'user_id': message.author.id})

    # extract creator user
    creator = management_collection.find_one({'role': 'creator'})

    if message.content.lower().startswith('--sin3d-list'):

        contributors = contributors_collection.find().sort('_id', -1)

        discord_contributors = ""
        anonymous_contributors = ""
        n_contributors = contributors.count()

        n_discord = 0
        n_anonymous = 0

        contributor_str = 'contributor' if n_contributors <= 1 else 'contributors'

        for contributor in contributors:
            if contributor['discord']:

                if n_discord < 5:
                    if len(contributor['guild_name']) > 0:
                        discord_contributors += ":white_small_square: " + contributor['username'] + " with (" + contributor['guild_name'] + ")\n"
                    else:
                        discord_contributors += ":white_small_square: " + contributor['username'] + "\n"

                n_discord += 1
            else:

                if n_anonymous < 5:
                    if len(contributor['guild_name']) > 0:
                        anonymous_contributors += ":white_small_square: " + contributor['user_id'] + " with (" + contributor['guild_name'] + ")\n"
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
            name="**Discord ({0})**{1}".format(n_discord, ', last five contributors' if n_discord >= 5 else ''), 
            value=discord_contributors, 
            inline=False)
        embed.add_field(
            name="**Anonymous ({0})**{1}".format(n_anonymous, ', last five contributors:' if n_anonymous >= 5 else ''), 
            value=anonymous_contributors, 
            inline=False)
        embed.set_footer(text="Thanks a lot for your contributions!") 
        
        await message.channel.send(embed=embed)

    if message.content.lower().startswith('--sin3d-default-custom'):

        # get custom userid
        splited_message = message.content.split(' ')

        if len(splited_message) > 4 and len(splited_message) <= 5:

            # check params and update guild configuration
            parser = argparse.ArgumentParser(description="Read and compute params for default custom link")

            # all default params use previous data
            parser.add_argument('--expeId', type=str, help='experiment id to use')
            parser.add_argument('--userId', type=str, help='user id for experiment')

            params = ' '.join(splited_message[1:])
            
            try:
                args = parser.parse_args(shlex.split(params))

                p_expeId = args.expeId
                p_userId = args.userId

                conf_to_update = default_config['config']

                conf_to_update['experimentId'] = p_expeId
                conf_to_update['userId'] = p_userId
                
                results = contributors_collection.find_one({'user_id': p_userId})
        
                if results is None:

                    # generate custom link
                    generated_link = generate_link(conf_to_update)
                    contributors_collection.insert_one({'user_id': p_userId, 'username': p_userId, 'guild_id': "", 'guild_name': "", 'discord': False, 'config': conf_to_update})

                    embed = discord.Embed(
                        title=':open_hands: {0}, your custom SIN3D-app link :open_hands:'.format(str(message.author)),  
                        description='You can now launch the app :paperclip:', 
                        color=embed_color,
                        url=generated_link)
                    embed.add_field(
                        name=":white_small_square: Information:", 
                        value="This link is unique but **not** associated with your **discord** account and cannot be regenerated", 
                        inline=False)
                    embed.add_field(
                        name=":white_small_square: Link generated data:", 
                        value="`expeId`: {0}\n`userId`: {1}".format(p_expeId, p_userId), 
                        inline=False)
                    embed.add_field(
                        name=":white_small_square: If you need to generate another one, please run again using new data:", 
                        value="`--sin3d-default-custom --expeId {{myexpeId}} --userId {{myuserId}}`", 
                        inline=False)
                    embed.set_footer(text="Thanks in advance for your contribution!") 

                else:
                    embed = discord.Embed(
                        title=':warning: Ooops, :id: asked already used :warning:', 
                        description='`{0}` identifier already exists'.format(p_userId), 
                        color=embed_color)
                    embed.add_field(
                        name=":white_small_square: If you need to generate another one, please run again using new data:", 
                        value="`--sin3d-default-custom --expeId {{myexpeId}} --userId {{myuserId}}`", 
                        inline=False)
                    embed.add_field(
                        name="\t__Example:__", 
                        value="\t`--sin3d-default-custom --expeId myexpeId --userId myuserId`",
                        inline=False)
                    embed.set_footer(text="All params are required") 
            except:
                embed = discord.Embed(
                    title=':warning: Unvalid use of command :warning:', 
                    description='It seems the params passed are not valid (need at least one param to update)', 
                    color=embed_color)
                embed.add_field(
                    name=":white_small_square: Please run again this command as shown in the example:", 
                    value="`--sin3d-default-custom --expeId {{myexpeId}} --userId {{myuserId}}`", 
                    inline=False)
                embed.add_field(
                    name="\t__Example:__", 
                    value="\t`--sin3d-default-custom --expeId myexpeId --userId myuserId`",
                    inline=False)
                embed.set_footer(text="All params are required") 
        else:
            embed = discord.Embed(
                title=':warning: Unvalid use of command :warning:', 
                description='It seems the params passed are not valid (need at least one param to update)', 
                color=embed_color)
            embed.add_field(
                name=":white_small_square: Please run again this command as shown in the example:", 
                value="`--sin3d-default-custom --expeId {{myexpeId}} --userId {{myuserId}}`", 
                inline=False)
            embed.add_field(
                name="\t__Example:__", 
                value="\t`--sin3d-default-custom --expeId myexpeId --userId myuserId`",
                inline=False)
            embed.set_footer(text="All params are required") 

        await message.author.send(embed=embed)

    if message.content.lower().startswith('--sin3d-custom'):

        # get custom userid
        splited_message = message.content.lower().split(' ')

        if len(splited_message) > 1 and len(splited_message) <= 2:

            userId = splited_message[1] # the second element

            common_guilds = []

            # find common guilds with current user
            for guild in client.guilds:
                if message.author in guild.members:
                    common_guilds.append(guild)

            if len(common_guilds) > 1:
                embed = discord.Embed(
                    title=':open_hands: {0}, your SIN3D-app links for each guild :open_hands:'.format(str(message.author)), 
                    description='You can now launch the app :paperclip: using appropriate link', 
                    color=embed_color)

                await message.author.send(embed=embed)

            for guild in common_guilds:

                results = contributors_collection.find_one({'user_id': userId, 'guild_id': guild.id})
                guild_config = configurations_collection.find_one({'guild_id': guild.id})

                user_config = None

                if results is None:
                    # add user with id as contributors
                    user_config = guild_config['config']
                    user_config['userId'] = userId
                    contributors_collection.insert_one({'user_id': userId, 'username': userId, 'guild_id': guild.id, 'guild_name': guild.name, 'discord': False, 'config': user_config})
                    
                    # generate custom user link
                    generated_link = generate_link(user_config)    

                    embed = discord.Embed(
                        title='Your custom SIN3D-app link associated with {0}'.format(guild.name), 
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
                        description='`{0}` identifier already exists for `{1}`'.format(userId, guild.name), 
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
                title=':warning: Invalid use of command :warning:', 
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
        
        common_guilds = []

        # find common guilds with current user
        for guild in client.guilds:
            if message.author in guild.members:
                common_guilds.append(guild)

        if len(common_guilds) > 1:

            embed = discord.Embed(
                title=':open_hands: {0}, your SIN3D-app links for each guild :open_hands:'.format(str(message.author)), 
                description='You can now launch the app :paperclip: using appropriate link', 
                color=embed_color)

            await message.author.send(embed=embed)

        for guild in common_guilds:

            results = contributors_collection.find_one({'user_id': message.author.id, 'guild_id': guild.id})
            guild_config = configurations_collection.find_one({'guild_id': guild.id})

            user_config = None

            if results is None:
                user_config = guild_config['config']
            else:
                user_config = results['config']
                
            # custom user config with its own discord user ID
            user_config['userId'] = message.author.id

            if results is None:
                # add user with id as contributors
                contributors_collection.insert_one({'user_id': message.author.id, 'username': str(message.author), 'guild_id': guild.id, 'guild_name': guild.name, 'discord': True, 'config': user_config})
 
            # generate custom link
            generated_link = generate_link(user_config)

            embed = discord.Embed(
                title='Your SIN3D-app link associated with `{0}`'.format(guild.name), 
                description='You can now launch the app :paperclip:', 
                color=embed_color,
                url=generated_link)
            embed.add_field(
                name=":white_small_square: Information:", 
                value="This link is associated to your **discord** account and **{0}** guild.".format(guild.name), 
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
            name=":white_small_square: Send your SIN3D app :link: associated with your guild and with custom :id: (**anonymous**)",
            inline=False)
        embed.add_field(
            value="\t`--sin3d-custom my-identifier`",
            name="\t__Example:__", 
            inline=False)
        embed.add_field(
            name=":white_small_square: Create custom a data with specific experiment and user :id:", 
            value="`--sin3d-default-custom --expeId {{myexpeId}} --userId {{myuserId}}`", 
            inline=False)
        embed.add_field(
            name="\t__Example:__", 
            value="\t`--sin3d-default-custom --expeId myexpeId --userId myuserId`",
            inline=False)
        embed.add_field(
            value="`--sin3d-list`",
            name=":white_small_square: Gives information about all callaborators", 
            inline=False)

        await message.channel.send(embed=embed)

        if user_role['role'] == 'admin' or user_role['role'] == 'creator':

            embed.add_field(
                name=":white_small_square: Please run again this command as shown in the example:", 
                value="`--sin3d-config-update {{guild-id}} --hostConfig {{host}} --experimentName {{expe}} --experimentId {{myexpeId}} --sceneName {{scene}}`", 
                inline=False)
            embed.add_field(
                name="\t__Example:__", 
                value="\t`--sin3d-config-update {{guild-id}} --hostConfig https://host.com --experimentName myexpe --experimentId myexpeId --sceneName myscene`",
                inline=False)
            embed.add_field(
                value="`--sin3d-config-list`",  
                name=":white_small_square: Gives an overview of all guilds configurations",
                inline=False)

            await message.author.send(embed=embed)

    # add admin to SIN3D-bot
    if message.content.lower().startswith('--sin3d-admin-add'):

        if user_role['role'] == 'creator': 

            elments = message.content.lower().split(' ')

            if len(elments) > 1 and len(elments) <= 2:

                user_id_to_add = elments[1]

                user_to_add = discord.utils.find(lambda m: m.id == int(user_id_to_add), client.users)

                # check if user can be added (has common guild with bot)
                if user_to_add:
                    
                    # check if user is not already added
                    check_user = management_collection.find_one({'user_id': user_id_to_add})

                    if check_user:
                        embed = discord.Embed(
                            title=':warning: User already has admin role :warning:', 
                            description='It seems {0} has already been granted'.format(str(user_to_add)), 
                            color=embed_color)
                    else:
                        management_collection.insert_one({
                            'user_id': user_to_add.id, 
                            'username': str(user_to_add), 
                            'role': 'admin', 
                            'added_by': message.author.id})

                        embed = discord.Embed(
                            title=':ballot_box_with_check: Update validated :ballot_box_with_check:', 
                            description='{0} has now admin role'.format(str(user_to_add)),
                            color=embed_color)
                        embed.add_field(
                            name=":white_small_square: You can take a view of the admin user list using:", 
                            value="`--sin3d-admin-list`", 
                            inline=False)
                        
                else:
                    embed = discord.Embed(
                        title=':warning: User cannot be added :warning:', 
                        description='It seems user with {0} :id: has no common guild with `SIN3D-bot`'.format(user_id_to_add), 
                        color=embed_color)
            else:
                embed = discord.Embed(
                    title=':warning: Unvalid use of command :warning:', 
                    description='It seems the user :id: passed is not valid', 
                    color=embed_color)
                embed.add_field(
                    name=":white_small_square: Please run again this command as shown in the example:", 
                    value="`--sin3d-admin-add {{user-identifier}}`", 
                    inline=False)
                embed.add_field(
                    name="\t__Example:__", 
                    value="\t`--sin3d-admin-add a1b2c3d4e5f6g7`",
                    inline=False)

        else:
            embed = discord.Embed(
                title=':warning: You cannot use this command :warning:', 
                description='You do not have enough rights for doing this', 
                color=embed_color)

        await message.author.send(embed=embed)

    # remove admin if exists
    if message.content.lower().startswith('--sin3d-admin-remove'):
        
        if user_role['role'] == 'creator': 

            elements = message.content.lower().split(' ')

            if len(elements) > 1 and len(elements) <= 2:
                
                user_id_to_check = elements[1]

                if int(user_id_to_check) == creator['user_id']:

                    embed = discord.Embed(
                        title=':warning: Unvalid use of command :warning:', 
                        description='You cannot delete the creator!', 
                        color=embed_color)
                    embed.add_field(
                        name=":white_small_square: Please run again this command as shown in the example:", 
                        value="`--sin3d-admin-remove {{user-identifier}}`", 
                        inline=False)
                    embed.add_field(
                        name="\t__Example:__", 
                        value="\t`--sin3d-admin-remove a1b2c3d4e5f6g7`",
                        inline=False)
                else:
                    check_user = management_collection.find_one({'user_id': int(user_id_to_check)})

                    # check if user can be added (has common guild with bot)
                    if check_user:
                        management_collection.find_one({'user_id': int(user_id_to_check)})

                        embed = discord.Embed(
                            title=':ballot_box_with_check: Admin user removed :ballot_box_with_check:', 
                            description='{0} has now admin roles removed'.format(check_user['username']),
                            color=embed_color)
                        embed.add_field(
                            name=":white_small_square: You can take a view of the admin user list using:", 
                            value="`--sin3d-admin-list`", 
                            inline=False)       
                    else:
                        embed = discord.Embed(
                            title=':warning: User cannot be removed :warning:', 
                            description='It seems user with {0} :id: has no admin rights'.format(user_id_to_check), 
                            color=embed_color)

            else:
                embed = discord.Embed(
                    title=':warning: Unvalid use of command :warning:', 
                    description='It seems the user :id: passed is not valid', 
                    color=embed_color)
                embed.add_field(
                    name=":white_small_square: Please run again this command as shown in the example:", 
                    value="`--sin3d-admin-remove {{user-identifier}}`", 
                    inline=False)
                embed.add_field(
                    name="\t__Example:__", 
                    value="\t`--sin3d-admin-remove a1b2c3d4e5f6g7`",
                    inline=False)
        else:
            embed = discord.Embed(
                title=':warning: You cannot use this command :warning:', 
                description='You do not have enough rights for doing this', 
                color=embed_color)
            embed.set_footer(text="Please contact {0} if you need to be upgraded".format(creator['username'])) 
            
        await message.author.send(embed=embed)

    # list all admins user
    if message.content.lower().startswith('--sin3d-admin-list'):
        
        if user_role['role'] == 'creator':

            admin_users = management_collection.find()

            embed = discord.Embed(
                title=':ledger: Admin users :ledger:', 
                description='All current admin users',
                color=embed_color)
            
            for user in admin_users:

                embed.add_field(
                    name=":white_small_square: {0}".format(user['username']), 
                    value="with `{0}` :id: (role `{1}`)".format(user['user_id'], user['role']),
                    inline=False)
        else:
            embed = discord.Embed(
                title=':warning: You cannot use this command :warning:', 
                description='You do not have enough rights for doing this', 
                color=embed_color)
            embed.set_footer(text="Please contact {0} if you need to be upgraded".format(creator['username'])) 
            
        await message.author.send(embed=embed)

    # display all available configurations
    if message.content.lower().startswith('--sin3d-config-list'):
        
        if user_role['role'] == 'creator' or user_role['role'] == 'admin':

            configurations = configurations_collection.find()

            embed = discord.Embed(
                title=':ledger: Guilds configurations :ledger:', 
                description='All available configurations',
                color=embed_color)
            
            for conf in configurations:

                 embed.add_field(
                    name=":white_small_square: {0} (`{1}`)".format(conf['guild_name'], conf['guild_id']), 
                    value="```json\n{0}\n```".format(json.dumps(conf['config'], indent=4)),
                    inline=False)
        else:
            embed = discord.Embed(
                title=':warning: You cannot use this command :warning:', 
                description='You do not have enough rights for doing this', 
                color=embed_color)
            embed.set_footer(text="Please contact {0} if you need to be upgraded".format(creator['username'])) 

        await message.author.send(embed=embed)
    
    # update a configuration with params
    if message.content.lower().startswith('--sin3d-config-update'):

        if user_role['role'] == 'creator' or user_role['role'] == 'admin':

            elements = message.content.split(' ')

            if len(elements) > 3:

                guild_id = elements[1]

                conf_to_update = configurations_collection.find_one({'guild_id': int(guild_id)})

                # check if user can be added (has common guild with bot)
                if conf_to_update:
                    
                    # check params and update guild configuration
                    parser = argparse.ArgumentParser(description="Read and compute params for configuration update")

                    # all default params use previous data
                    parser.add_argument('--hostConfig', type=str, help='host configuration', default=conf_to_update['config']['hostConfig'])
                    parser.add_argument('--experimentName', type=str, help='experiment to use for current guild', default=conf_to_update['config']['experimentName'])
                    parser.add_argument('--experimentId', type=str, help='experiment id to use for current guild', default=conf_to_update['config']['experimentId'])
                    parser.add_argument('--sceneName', type=str, help='start scene to use', default=conf_to_update['config']['sceneName'])

                    params = ' '.join(elements[2:])

                    try:
                        args = parser.parse_args(shlex.split(params))

                        p_host         = args.hostConfig
                        p_expe         = args.experimentName
                        p_expeId       = args.experimentId
                        p_startScene   = args.sceneName

                        response = requests.get(diran_url_scenes_list).json()

                        if p_startScene in response['data']:
                        
                            conf_to_update['config']['hostConfig'] = p_host
                            conf_to_update['config']['experimentName'] = p_expe
                            conf_to_update['config']['experimentId'] = p_expeId
                            conf_to_update['config']['sceneName'] = p_startScene

                            if conf_to_update['config']['hostConfig'][-1] == '/':
                                conf_to_update['config']['hostConfig'] = conf_to_update['config']['hostConfig'][:-1]

                            # update data
                            configurations_collection.update_one({'_id': conf_to_update['_id']}, {'$set': {'config': conf_to_update['config']}}, upsert=True)

                            embed = discord.Embed(
                                title=':ballot_box_with_check: Guild configuration updated :ballot_box_with_check:', 
                                description='`{0}` has a new configuration'.format(conf_to_update['guild_name']),
                                color=embed_color)
                            embed.add_field(
                                name="New configuration overview", 
                                value="```json\n{0}\n```".format(json.dumps(conf_to_update['config'], indent=4)), 
                                inline=False)
                        else:

                            embed = discord.Embed(
                                title=':warning: Unvalid scene param :warning:', 
                                description='Start scene is not known and cannot be used',
                                color=embed_color)
                        
                            embed.add_field(
                                name="Scenes list is available at:", 
                                value="{0}".format(diran_url_scenes_list), 
                                inline=False)
                    except:
                        embed = discord.Embed(
                            title=':warning: Unvalid use of command :warning:', 
                            description='It seems the params passed are not valid (need at least one param to update)', 
                            color=embed_color)
                        embed.add_field(
                            name=":white_small_square: Please run again this command as shown in the example:", 
                            value="`--sin3d-config-update {{guild-id}} --hostConfig {{host}} --experimentName {{expe}} --experimentId {{myexpeId}} --sceneName {{scene}}`", 
                            inline=False)
                        embed.add_field(
                            name="\t__Example:__", 
                            value="\t`--sin3d-config-update {{guild-id}} --hostConfig https://host.com --experimentName myexpe --experimentId myexpeId --sceneName myscene`",
                            inline=False)
                        embed.set_footer(text="You do not need to pass all params but at least one") 
                else:
                    embed = discord.Embed(
                        title=':warning: Guild configuration cannot be updated :warning:', 
                        description='It seems guild with {0} :id: doesn\'t have configuration'.format(guild_id), 
                        color=embed_color)
            else:
                embed = discord.Embed(
                    title=':warning: Unvalid use of command :warning:', 
                    description='It seems the params passed are not valid (need at least one param to update)', 
                    color=embed_color)
                embed.add_field(
                    name=":white_small_square: Please run again this command as shown in the example:", 
                    value="`--sin3d-config-update {{guild-id}} --hostConfig {{host}} --experimentName {{expe}} --experimentId {{myexpeId}} --sceneName {{scene}}`", 
                    inline=False)
                embed.add_field(
                    name="\t__Example:__", 
                    value="\t`--sin3d-config-update {{guild-id}} --hostConfig https://host.com --experimentName myexpe --experimentId myexpeId --sceneName myscene`",
                    inline=False)
                embed.set_footer(text="You do not need to pass all params but at least one") 

        else:
            embed = discord.Embed(
                title=':warning: You cannot use this command :warning:', 
                description='You do not have enough rights for doing this', 
                color=embed_color)
            embed.set_footer(text="Please contact {0} if you need to be upgraded".format(creator['username'])) 

        await message.author.send(embed=embed)

    if message.content.lower().startswith('--sin3d-results'):

        if user_role['role'] == 'creator' or user_role['role'] == 'admin':
            elements = message.content.split(' ')

            # if there is at least one experiment id
            if len(elements) > 1:

                experiments_identifier = elements[1:]

                print(experiments_identifier)

                experiment_results = data_collection.find({
                    'data.msg.experimentName': 'MatchExtractsWithReference', 
                    'data.msgId': 'EXPERIMENT_VALIDATED',
                    'data.experimentId':{
                        '$in': experiments_identifier
                    }
                    # '$not': { '$gt': 1.99 }
                })

                print(experiment_results.count())

                if not os.path.exists(output_results_folder):
                    os.makedirs(output_results_folder)

                n_files = len(os.listdir(output_results_folder)) + 1
                results_filename = 'experiments_results_' + str(n_files) + '.json'
                results_filepath = os.path.join(output_results_folder, results_filename)

                export_data = []

                for result in experiment_results:
                    export_data.append(result['data'])

                with open(results_filepath, 'w') as f:
                    f.write(json.dumps(export_data, indent=4))

                discord_file = discord.File(fp=results_filepath, filename=results_filename)

                embed = discord.Embed(
                    title=':ballot_box_with_check: Extraction done with success :ballot_box_with_check:', 
                    description='Here your extracted file data',
                    color=embed_color)

                await message.author.send(embed=embed, file=discord_file)
            else:
                embed = discord.Embed(
                    title=':warning: Unvalid use of command :warning:', 
                    description='It seems the params passed are not valid (need at least one param to extract data)', 
                    color=embed_color)
                embed.add_field(
                    name=":white_small_square: Please run again this command as shown in the example:", 
                    value="`--sin3d-results {{expeId1}} {{expeId2}} ... {{expeIdN}}`", 
                    inline=False)
                embed.add_field(
                    name="\t__Example:__", 
                    value="\t`--sin3d-results myexpeId1 myexpeId2`",
                    inline=False)
                embed.set_footer(text="You do not need to pass all params but at least one") 
                
                await message.author.send(embed=embed)
        else:
            embed = discord.Embed(
                title=':warning: You cannot use this command :warning:', 
                description='You do not have enough rights for doing this', 
                color=embed_color)
            embed.set_footer(text="Please contact {0} if you need to be upgraded".format(creator['username'])) 

            await message.author.send(embed=embed)

@client.event
async def on_guild_remove():

    # if not exists create configuration for all guild joined
    for guild in client.guilds:

        # check if guild configuration exists
        check_guild_config(guild)

@client.event
async def on_guild_join():

    # if not exists create configuration for all guild joined
    for guild in client.guilds:

        # check if guild configuration exists
        check_guild_config(guild)

@client.event
async def on_ready():
    
    print(
        f'{client.user} is connected\n'
    )

    # add of creator
    creator = management_collection.find_one({'role': 'creator'})

    if creator is None:
        user_creator = discord.utils.find(lambda m: m.id == int(default_config['creator']), client.users)
        
        if user_creator is not None:
            management_collection.insert_one({
                'user_id': user_creator.id, 
                'username': str(user_creator), 
                'role': 'creator', 
                'added_by': user_creator.id})

            print('Creator account is created')
        else:
            print('Creator user not found...')
            exit(0)

    elif creator['user_id'] != int(default_config['creator']):

        print('Remove previous creator! Creator is unique')
        management_collection.delete_one({'_id': creator['_id']})
    else:
        print('Current creator is {0}'.format(creator['username']))
        

    # if not exists create configuration for all guild joined
    for guild in client.guilds:

        # check if guild configuration exists
        check_guild_config(guild)

client.run(TOKEN)
