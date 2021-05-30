import asyncio
import random
import time
from dataclasses import make_dataclass
from typing import Tuple

from sneklib import snekpi

Block = Tuple[int, int]


class Snek:
    """
    Base snek class that other snek classes should inherit from.
    It represents a generic snek, the objects that interact in a snek game trough a snek engine.
    It exposes:
    self.alive, self.whole and self.data attributes,
    self.move() and self.kill() methods,
    self.head, self.body, self.tail, self.future_head, self.future_whole properties,
    and a self.__repr__() method.
    """

    def __init__(self, whole=None, data=()):
        self.alive = True
        if whole is None:
            whole = []
        self.whole = whole
        self.data = data

    @property
    def head(self):
        """head of the snek, the first element of whole"""
        return self.whole[:1]

    @property
    def body(self):
        """body of the snek, all whole except for head and tail"""
        return self.whole[1:-1]

    @property
    def tail(self):
        """tail of the snek, the last element of whole"""
        return self.whole[-1:]

    @property
    def future_head(self):
        """what head will be when snek moves now"""
        return self.head

    @property
    def future_whole(self):
        """what whole will be if snek moves now"""
        return self.whole

    def move(self):
        """
        method for making the snek move. It returns two sequences,
        the first containing the blocks added to whole,
        the second the blocks removed from whole
        """
        res = ((), ())
        self.whole = self.future_whole
        return res

    def kill(self):
        """method for killing the snek"""
        self.alive = False

    def __repr__(self):
        return f"$data:{self.data}, whole:{self.whole}$"


class SnekEngine:
    """
    Base snek engine class that other snek engine classes should inherit from.
    A snek engine is where the actual game runs and where different sneks interact.
    It exposes:
    _snek_factory attribute in the class itself (although it can be modified within instances),
    self.sneks, self.other_sneks and self.game_tick attributes,
    self.create_snek(*args, **kwargs) and self.move() methods,
    and self.loop() asynchronous generator.
    """

    _snek_factory = Snek

    def __init__(self, sneks=(), other_objs=None, game_tick=1, infos=()):
        self.sneks = sneks
        if other_objs is None:
            other_objs = {}
        self.other_sneks = other_objs
        self.game_tick = game_tick
        self.infos = infos

    @property
    def all_blocks(self):
        """a list of all of the blocks for each snek object in the engine"""
        res = []
        for snek in self.sneks:
            res += snek.whole
        for kind in self.other_sneks.values():
            for snek_object in kind:
                res += snek_object.whole
        return res

    @property
    def all_objects(self):
        """all of the objects in the engine"""
        return self.sneks, self.other_sneks

    def create_snek(self, *args, **kwargs):
        """
        function for creating a new snek and adding it to self.sneks of the engine.
        It passes *args and **kwargs to the snek factory of the engine
        """
        res = self._snek_factory(*args, **kwargs)
        self.sneks.append(res)
        return res

    def move(self):
        """makes the game advance by one tick"""
        sneks = {}
        new_sneks = {}
        kinds = {kind: {} for kind in self.other_sneks}
        new_of_kinds = {kind: {} for kind in self.other_sneks}
        return sneks, new_sneks, kinds, new_of_kinds

    async def loop(self):
        """runs the game indefinitely"""
        while 1:
            yield self.move()
            await asyncio.sleep(self.game_tick)


Player = make_dataclass('Player', [('snek', Snek), ('sneks', dict), ('kinds', dict), ('last', float)])


class Server:
    """
    Base server class. Should be derived only for implementing new communication
    protocols not already implemented in sneklib/servers.
    It exposes:
    DIRECTION, KILL_TIME, KICK_TIME constants (that can be redefined for each server instance),
    Player dataclass (with attributes snek, sneks kinds and last attributes)
    self.address, self.engine, self.max_connections, self.players attributes,
    self.run() and self.deal_with_request(c, _args) methods,
    and self.loop(), self.user_interface_loop(), self.game_loop() and self.server_loop() asynchronous methods.
    """

    DIRECTION = {b'\x01': 'u', b'\x02': 'l', b'\x03': 'd', b'\x04': 'r'}
    KILL_TIME = 10
    KICK_TIME = KILL_TIME + 10

    def __init__(self, address, engine, max_connections=5):
        self.address = address
        self.engine: SnekEngine = engine
        self.max_connections = max_connections
        self.players = {}
        self.__cases = {0: self.__register, 1: self.__set_dir, 2: self.__engine_info,
                        3: self.__get_state_current, 4: self.__get_state_updated,
                        254: self.__get_state_current_old, 255: self.__get_state_updated_old}

    def run(self):
        """function called to start the server"""
        asyncio.run(self.loop())

    async def loop(self):
        """runs the server indefinitely"""
        await asyncio.gather(self.server_loop(), self.game_loop(), self.user_interface_loop())

    # TODO improve UI
    async def user_interface_loop(self):
        """shows players connected to the server"""
        while 1:
            print('-----------------------------------------------------')
            for hash_id, player in self.players.items():
                snek = player.snek
                print(f"{hash_id}: '{snek.data['name']}'.{'alive' if snek.alive else 'dead'}"
                      f", seen last time {time.time() - player.last} seconds ago")
            await asyncio.sleep(2)

    async def game_loop(self):
        """loop for gathering data from the game engine"""
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
        """server loop to communicate with players"""
        pass

    # TODO: add exception handling

    def deal_with_request(self, c, _args):
        """
        Method that should be called by a function that reads requests from a client.
        Parameter c is the command from the player as an int;
        _args is the rest of the bytes read from the player.
        It returns the answer message as bytes that should be relayed as is to the player.
        """
        args = self.__decode(c, _args)
        answer = self.__cases[c](*args)

        # cleanup for the player (e.g. last, ...)
        if c in {3, 4, 254, 255}:
            self.__set_player(args[0])

        if c in {1, 3, 4, 254, 255}:
            args[0].last = time.time()

        if len(args) > 0 and isinstance(args[0], Snek) and not args[0].alive:
            del self.players[_args[:8]]

        return answer

    def __decode(self, c, args):
        """decodes the request from the player"""
        if c == 0:
            return args.decode('utf8'),
        elif c == 1:
            return self.players[args[:8]], self.DIRECTION[args[8:9]]
        elif c == 2:
            return ()
        elif c == 3:
            if args:
                return self.players[args[:8]],
            return Player(Snek(), {}, {}, 0),
        elif c == 4:
            return self.players[args[:8]],
        elif c == 254:
            if args:
                return self.players[args[:8]],
            return Player(Snek(), {}, {}, 0),
        elif c == 255:
            return self.players[args[:8]],
        raise LookupError(f'invalid command: {c}')

    def __set_player(self, player):
        """resets player.sneks and player.kinds attributes"""
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

    def __register(self, name):
        """registers player to the server"""
        hash_id = random.getrandbits(64).to_bytes(8, 'big')
        if hash_id in self.players:
            return b''
        if len([1 for player in self.players.values() if player.snek.alive]) > self.max_connections:
            return b''

        snek = self.engine.create_snek(name=name)
        if not snek:
            return b''

        for player in self.players.values():
            player.sneks[snek] = [[], []]
        player = Player(snek, {}, {}, time.time())
        self.__set_player(player)
        self.players[hash_id] = player
        return hash_id

    @staticmethod
    def __set_dir(player, direction):  # add exception handling
        """sets player's snek direction"""
        player.snek.dir = direction
        return b'\x00'

    def __engine_info(self):
        """sends infos about the game engine"""
        encoded_data = snekpi.encode_json(self.engine.infos)
        return encoded_data

    def __get_state_current(self, player):
        """sends current state of the game"""
        player_snek = player.snek
        sneks, kinds = self.engine.all_objects
        res = b''

        res += snekpi.encode_whole_snek(player_snek)

        res += snekpi.encode_whole_list((snek for snek in sneks if snek is not player_snek))

        for elements in kinds.values():
            res += snekpi.encode_whole_list(elements)

        return res

    @staticmethod
    def __get_state_updated(player):
        """sends updated state of the game since last time that self.set_player was called on the player"""
        player_snek = player
        sneks = player
        kinds = player
        res = b''

        res += snekpi.encode_partial_snek(player_snek, sneks[player_snek][0], sneks[player_snek][1])

        res += snekpi.encode_partial_list(((snek, news, olds) for snek, (news, olds) in sneks.items()))

        for elements in kinds.values():
            res += snekpi.encode_partial_list((element, news, olds) for element, (news, olds) in elements.items())

        return res

    def __get_state_current_old(self, player):
        """sends current blocks in the game"""
        alive = player.snek.alive
        blocks = self.engine.all_blocks
        res = b''

        res += alive.to_bytes(1, 'big')
        res += snekpi.encode_blocks(blocks, [])

        return res

    @staticmethod
    def __get_state_updated_old(player):  # news and olds might contain repeated elements, is that a problem?
        """sends new and old blocks since last time that self.set_player was called on the player"""
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
