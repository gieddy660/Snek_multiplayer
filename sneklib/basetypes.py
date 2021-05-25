import asyncio
import random
import time
from dataclasses import make_dataclass

from sneklib import snekpi


class Snek:
    """Base snek class that other snek classes should inherit from,
    it exposes self.alive, self.whole and self.data attributes,
    self.move and self.kill methods, plus some convenience properties
    and a __repr__ method"""
    def __init__(self, whole=None, data=()):
        self.alive = True
        if whole is None:
            whole = []
        self.whole = whole
        self.data = data

    @property
    def head(self):
        return self.whole[:1]

    @property
    def body(self):
        return self.whole[1:-1]

    @property
    def tail(self):
        return self.whole[-1:]

    @property
    def future_head(self):
        return self.head

    @property
    def future_whole(self):
        return self.whole

    def move(self):
        res = ((), ())
        self.whole = self.future_whole
        return res

    def kill(self):
        self.alive = False

    def __repr__(self):
        return f"$data:{self.data}, whole:{self.whole}$"


class SnekEngine:
    _snek_factory = Snek

    def __init__(self, sneks=(), other_objs=None, game_tick=1):
        self.sneks = sneks
        if other_objs is None:
            other_objs = {}
        self.other_objects = other_objs
        self.game_tick = game_tick

    @property
    def infos(self):
        return ()

    @property
    def all_blocks(self):
        res = []
        for snek in self.sneks:
            res += snek.whole
        for kind in self.other_objects.values():
            for snek_object in kind:
                res += snek_object.whole
        return res

    @property
    def all_objects(self):
        return self.sneks, self.other_objects

    def create_snek(self, *args, **kwargs):
        res = self._snek_factory(*args, **kwargs)
        self.sneks.append(res)
        return res

    def move(self):
        sneks = {}
        new_sneks = {}
        kinds = {kind: {} for kind in self.other_objects}
        new_of_kinds = {kind: {} for kind in self.other_objects}
        return sneks, new_sneks, kinds, new_of_kinds

    async def loop(self):
        while 1:
            yield self.move()
            await asyncio.sleep(self.game_tick)


class Server:
    DIRECTION = {b'\x01': 'u', b'\x02': 'l', b'\x03': 'd', b'\x04': 'r'}
    KILL_TIME = 10
    KICK_TIME = KILL_TIME + 10

    Player = make_dataclass('Player', [('snek', Snek), ('sneks', dict), ('kinds', dict), ('last', float)])

    def __init__(self, address, engine, max_connections=5):
        self.address = address
        self.engine = engine
        self.max_connections = max_connections
        self.players = {}
        self.cases = {0: self.register, 1: self.set_dir, 2: self.engine_info,
                      3: self.get_state_current, 4: self.get_state_updated,
                      254: self.get_state_current_old, 255: self.get_state_updated_old}

    def run(self):
        asyncio.run(self.loop())

    async def loop(self):
        await asyncio.gather(self.server_loop(), self.game_loop(), self.user_interface_loop())

    # TODO improve UI
    async def user_interface_loop(self):
        while 1:
            print('-----------------------------------------------------')
            for hash_id, player in self.players.items():
                snek = player.snek
                print(f"{hash_id}: '{snek.data['name']}'.{'alive' if snek.alive else 'dead'}"
                      f", seen last time {time.time() - player.last} seconds ago")
            await asyncio.sleep(2)

    async def game_loop(self):
        async for sneks, new_sneks, kinds, new_of_kinds in self.engine.loop():
            keep_players = {}
            for hash_id, player in self.players.items():
                for snek, (news, olds) in sneks.items():
                    player.sneks[snek][0] += news
                    player.sneks[snek][1] += olds
                player.sneks.update(new_sneks)
                for kind, elements in kinds.items():
                    for element, (news, olds) in elements.items():
                        player.kinds[kind][element][0] += news
                        player.kinds[kind][element][1] += olds
                for kind, new_elements in new_of_kinds.items():
                    player.kinds[kind].update(new_elements)

                if time.time() - player.last > self.KILL_TIME:
                    player.snek.kill()

                if time.time() - player.last < self.KICK_TIME:
                    keep_players[hash_id] = player
            self.players = keep_players

    async def server_loop(self):
        pass

    # TODO: add exception handling
    def decode(self, c, args):
        if c == 0:
            return args.decode('utf8'),
        elif c == 1:
            return self.players[args[:8]], self.DIRECTION[args[8:9]]
        elif c == 2:
            return ()
        elif c == 3:
            if args:
                return self.players[args[:8]],
            return Server.Player(Snek(), {}, {}, 0),
        elif c == 4:
            return self.players[args[:8]],
        elif c == 254:
            if args:
                return self.players[args[:8]],
            return Server.Player(Snek(), {}, {}, 0),
        elif c == 255:
            return self.players[args[:8]],
        raise LookupError(f'invalid command: {c}')

    def register(self, name):
        hash_id = random.getrandbits(64).to_bytes(8, 'big')
        if hash_id in self.players:
            return b''
        if len(self.players) > self.max_connections:
            return b''

        snek = self.engine.create_snek(name=name)
        if not snek:
            return b''

        for player in self.players.values():
            player.sneks[snek] = [[], []]
        player = Server.Player(snek, {}, {}, time.time())
        self.name_to_rename(player)
        self.players[hash_id] = player
        return hash_id

    @staticmethod
    def set_dir(player, direction):  # add exception handling
        player.snek.dir = direction
        return b'\x00'

    def engine_info(self):
        encoded_data = snekpi.encode_json(self.engine.infos)
        return encoded_data

    def get_state_current(self, player):
        player_snek = player.snek
        sneks, kinds = self.engine.all_objects
        res = b''

        res += snekpi.encode_whole_object(player_snek)

        res += snekpi.encode_whole_list((snek for snek in sneks if snek is not player_snek))

        for elements in kinds.values():
            res += snekpi.encode_whole_list(elements)

        return res

    @staticmethod
    def get_state_updated(player):
        player_snek = player
        sneks = player
        kinds = player
        res = b''

        res += snekpi.encode_partial_object(player_snek, sneks[player_snek][0], sneks[player_snek][1])

        res += snekpi.encode_partial_list(((snek, news, olds) for snek, (news, olds) in sneks.items()))

        for elements in kinds.values():
            res += snekpi.encode_partial_list((element, news, olds) for element, (news, olds) in elements.items())

        return res

    def get_state_current_old(self, player):
        alive = player.snek.alive
        blocks = self.engine.all_blocks
        res = b''

        res += alive.to_bytes(1, 'big')
        res += snekpi.encode_blocks(blocks, [])

        return res

    @staticmethod
    def get_state_updated_old(player):  # news and olds might contain repeated elements, is that a problem?
        alive = player.snek.alive
        news = []
        olds = []
        for news_, olds_ in player.sneks.values():
            news += news_
            olds += olds_
        for elements in player.kinds.values():
            for news_, olds_ in elements.values():
                news += news_
                olds += olds_
        res = b''

        res += alive.to_bytes(1, 'big')
        res += snekpi.encode_blocks(news, olds)

        return res

    def name_to_rename(self, player):
        sneks_, kinds_ = self.engine.all_objects
        sneks = {}
        kinds = {}
        for snek in sneks_:
            sneks[snek] = [[], []]
        for kind, elements in kinds_.items():
            kinds[kind] = {}
            for element in elements:
                kinds[kind][element] = [[], []]

        player.sneks = sneks
        player.kinds = kinds

    def deal_with_player(self, c, _args):
        args = self.decode(c, _args)
        answer = self.cases[c](*args)

        # cleanup for the player (e.g. last, ...)
        if c in {3, 4, 254, 255}:
            self.name_to_rename(args[0])

        if c in {1, 3, 4, 254, 255}:
            args[0].last = time.time()

        if len(args) > 0 and isinstance(args[0], Snek) and not args[0].alive:
            del self.players[_args[:8]]

        return answer
