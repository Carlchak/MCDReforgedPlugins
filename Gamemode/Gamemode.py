# -*- coding: utf-8 -*-
import time
from math import ceil

from JsonDataAPI import Json
from mcdreforged.plugin.server_interface import ServerInterface
from mcdreforged.api.command import *
from mcdreforged.api.decorator import new_thread

PLUGIN_METADATA = {
    'id': 'gamemode',
    'version': '0.0.1',
    'name': 'Gamemode',
    'description': 'Change to spectator mode for observe, teleport to origin position when change back to survival mode',
    'author': 'zhang_anzhi',
    'link': 'https://github.com/zhang-anzhi/MCDReforgedPlugins/tree/master/Gamemode',
    'dependencies': {
        'json_data_api': '*',
        'minecraft_data_api': '*',
    }
}

data = Json(PLUGIN_METADATA['name'])
DIMENSIONS = {
    '0': 'minecraft:overworld',
    '-1': 'minecraft:the_nether',
    '1': 'minecraft:the_end',
    'overworld': 'minecraft:overworld',
    'the_nether': 'minecraft:the_nether',
    'the_end': 'minecraft:the_end',
    'nether': 'minecraft:the_nether',
    'end': 'minecraft:the_end',
    'minecraft:overworld': 'minecraft:overworld',
    'minecraft:the_nether': 'minecraft:the_nether',
    'minecraft:the_end': 'minecraft:the_end'
}
HELP_MESSAGE = '''§6!!spec §7旁观/生存切换
§6!!tp <dimension> [position] §7传送至指定地点
§6!!back §7返回上个地点'''


def on_load(server: ServerInterface, old):
    global api, data
    api = server.get_plugin_instance('minecraft_data_api')
    data = Json(PLUGIN_METADATA['name'])

    @new_thread('Gamemode switch mode')
    def change_mode(src):
        # Survival now
        if src.player not in data.keys():
            sur_to_spec(server, src.player)
            src.reply('§a已切换至旁观模式')
        # Spectator now
        elif src.player in data.keys():
            use_time = ceil((time.time() - data[src.player]['time']) / 60)
            src.reply(f'§a您使用了§e{use_time}min')
            spec_to_sur(server, src.player)

    @new_thread('Gamemode tp')
    def tp(src, ctx):
        if src.player not in data.keys():
            src.reply('§c您只能在旁观模式下传送')
        elif ctx['dimension'] not in DIMENSIONS.keys():
            src.reply('§c没有此维度')
        else:
            pos = ' '.join((
                str(ctx.get('x', '0')),
                str(ctx.get('y', '80')),
                str(ctx.get('z', '0'))
            ))
            dim = DIMENSIONS[ctx['dimension']]
            data[src.player]['back'] = {
                'dim': DIMENSIONS[api.get_player_info(src.player, 'Dimension')],
                'pos': api.get_player_info(src.player, 'Pos')
            }
            data.save()
            server.execute(f'execute in {dim} run tp {src.player} {pos}')
            src.reply(f'§a传送至§e{dim}§a, 坐标§e{dim}')

    @new_thread('Gamemode back')
    def back(src):
        if src.player not in data.keys():
            return server.reply('§c您只能在旁观模式下传送')
        else:
            dim = data[src.player]['back']['dim']
            pos = [str(x) for x in data[src.player]['back']['pos']]
            data[src.player]['back'] = {
                'dim': DIMENSIONS[api.get_player_info(src.player, 'Dimension')],
                'pos': api.get_player_info(src.player, 'Pos')
            }
            data.save()
            server.execute(
                f'execute in {dim} run tp {src.player} {" ".join(pos)}')
            src.reply('§a已将您传送至上个地点')

    server.register_help_message('!!spec help', 'Gamemode插件帮助')
    server.register_command(
        Literal('!!spec').
            requires(lambda src: src.is_player).
            runs(change_mode).
            then(
            Literal('help').runs(lambda src: src.reply(HELP_MESSAGE))
        )
    )
    server.register_command(
        Literal('!!tp').
            requires(lambda src: src.is_player).
            then(
            Text('dimension').
                runs(tp).
                then(
                Float('x').
                    then(
                    Float('y').
                        then(
                        Float('z').runs(tp)
                    )
                )
            )
        )
    )
    server.register_command(
        Literal('!!back').requires(lambda src: src.is_player).runs(back)
    )


def sur_to_spec(server, player):
    dim = DIMENSIONS[api.get_player_info(player, 'Dimension')]
    pos = api.get_player_info(player, 'Pos')
    data[player] = {
        'dim': dim,
        'pos': pos,
        'time': time.time(),
        'back': {
            'dim': dim,
            'pos': pos
        }
    }
    server.execute(f'gamemode spectator {player}')
    data.save()


def spec_to_sur(server, player):
    dim = data[player]['dim']
    pos = [str(x) for x in data[player]['pos']]
    server.execute(
        'execute in {} run tp {} {}'.format(dim, player, ' '.join(pos)))
    server.execute(f'gamemode survival {player}')
    del data[player]
    data.save()


def on_player_joined(server, player, info):
    if player in data.keys():
        server.execute(f'gamemode spectator {player}')
