import asyncio
import json
import random
import time
from dataclasses import make_dataclass
from functools import partial

import snekpi


# pacman effect -> snek wraps to the other side when it exits


class Snek(snekpi.BaseSnek):
    MOVEMENT = {'u': (0, -1), 'l': (-1, 0), 'd': (0, 1), 'r': (1, 0), 'lol': (0, -3)}

    def __init__(self, direction='u', pos=(0, 0), name=''):
        """ snek spawns vertical, facing up, 3 blocks high """
        data = {'name': name}
        whole = [(pos[0], pos[1] + b) for b in range(3)]
        super().__init__(whole=whole, data=data)
        self.dir = direction

        self.will_grow = False

    @property
    def future_head(self):
        zip_ = zip(self.head[0], type(self).MOVEMENT[self.dir])
        t = [tuple(a + b for a, b in zip_)]
        return t

    @property
    def future_body(self):
        if self.will_grow:
            return self.future_head + self.whole
        else:
            return self.future_head + self.head + self.body

    def move(self):
        res = ((self.future_head,), ()) if self.will_grow else ((self.future_head,), (self.tail,))
        super().move()
        self.will_grow = False
        return res

    def __rshift__(self, other):
        if other is self:
            return self.future_head[0] in (other.head + other.body)
        return self.future_head[0] in (other.future_head + other.head + other.body)


class PacManSnek(Snek):
    def __init__(self, dimensions, direction='u', pos=(0, 0)):
        super().__init__(direction, pos)
        self.dimensions = dimensions

    @property
    def future_head(self):
        zip_ = zip(self.head[0], type(self).MOVEMENT[self.dir], self.dimensions)
        t = [tuple((a + b) % c for a, b, c in zip_)]
        return t


class Food(snekpi.BaseSnek):
    def __init__(self, pos=(0, 0)):
        whole = [pos]
        super().__init__(whole=whole)

# TODO: testing


class SnekEngine:
    _snek_factory = Snek
    mode = 0

    def __init__(self, width, height, max_food, game_tick, sneks=(), foods=()):
        self.width = width
        self.height = height
        self.target_food = max_food
        self.sneks = list(sneks)
        self.foods = list(foods)
        self.game_tick = game_tick

    def snek_within(self, snek):
        return 0 <= snek.future_head[0][0] < self.width and 0 <= snek.future_head[0][1] < self.height

    @property
    def infos(self):
        return {'mode': self.mode, 'width': self.width, 'height': self.height}

    @property
    def all_blocks(self):
        res = []
        for snek in self.sneks:
            res += snek.whole
        for food in self.foods:
            res += food.whole
        return res

    @property
    def all_objects(self):
        return self.sneks, {Food: self.foods}

    def move(self):
        # 0: news, 1: olds
        sneks = {}
        foods = {}
        new_foods = {}

        # kill sneks
        keep_sneks = []
        for s1 in self.sneks:
            sneks[s1] = [[], []]
            if not self.snek_within(s1) or any((s1 >> s2 for s2 in self.sneks)) or not s1.alive:
                s1.kill()
                sneks[s1][1] += s1.whole
            else:
                keep_sneks.append(s1)
        self.sneks = keep_sneks

        # eat food
        keep_foods = []
        for food in self.foods:
            foods[food] = [[], []]
            for s1 in self.sneks:
                if s1 >> food:
                    s1.will_grow = True
                    food.kill()
                    foods[food][1] += food.whole
                    break
            else:
                keep_foods.append(food)
        self.foods = keep_foods

        # move sneks
        for snek in self.sneks:
            news, olds = snek.move()
            sneks[snek][0] += news
            sneks[snek][1] += olds

        # create food
        if len(self.foods) < self.target_food:
            food = self.create_food()
            if food is not None:
                new_foods[food] = [food.whole, []]

        return sneks, (), {Food: foods}, {Food: new_foods}

    def create_snek(self, *args, **kwargs):
        t = []
        for y in range(3, self.height-3):
            for x in range(self.width):
                if (x, y) not in self.all_blocks:
                    t.append((x, y))

        if t:
            res = self._snek_factory(pos=random.choice(t), *args, **kwargs)
            self.sneks.append(res)
            return res
        return None  # IDEA: maybe raise instead

    def create_food(self):
        t = []
        for y in range(self.height-3):
            for x in range(self.width):
                if (x, y) not in self.all_blocks:
                    t.append((x, y))

        if t:
            res = Food(pos=random.choice(t))
            self.foods.append(res)
            return res
        return None  # IDEA: maybe raise instead

    async def loop(self):
        while 1:
            yield self.move()
            await asyncio.sleep(self.game_tick)


class PacManSnekEngine(SnekEngine):
    _snek_factory = PacManSnek
    mode = 1

    def __init__(self, width, height, max_food, game_tick, sneks=(), foods=()):
        super().__init__(width, height, max_food, game_tick, sneks, foods)
        self._snek_factory = partial(self._snek_factory, dimensions=(width, height))  # ugly?

# TODO: testing


class Server:
    PLAYER_HASH_SIZE = 8
    DIR_MESSAGE_SIZE = 1
    DEAD, ALIVE = b'\x00', b'\x01'
    DIRECTION = {b'\x01': 'u', b'\x02': 'l', b'\x03': 'd', b'\x04': 'r', b'\x05': 'lol'}
    KILL_TIME = 10

    Player = make_dataclass('Player', [('snek', snekpi.BaseSnek), ('sneks', dict), ('kinds', dict), ('last', float)])

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
        server = await asyncio.start_server(self.dispatch, self.address[0], self.address[1],
                                            backlog=self.max_connections)
        async with server:
            await server.start_serving()  # DEBUG: seems like it's working, but keep under control
            async for sneks, new_sneks, kinds, new_of_kinds in self.engine.loop():  # TODO: restructure completely
                keep_players = {}
                for hash_id, player in self.players.items():
                    for snek in sneks:
                        player.sneks[snek][0] += snek[0]
                        player.sneks[snek][1] += snek[1]
                    player.sneks.update(new_sneks)
                    for kind, elements in kinds.items():
                        for element in elements:
                            player.kinds[kind][0] += element[0]
                            player.kinds[kind][1] += element[1]
                    for kind, new_elements in new_of_kinds.items():
                        player.kinds[kind].update(new_elements)

                    if time.time() - player.last > Server.KILL_TIME:
                        player.snek.kill()
                    else:
                        keep_players[hash_id] = player

                server.players = keep_players

    # TODO: add exception handling

    @classmethod
    def decode(cls, c, args):
        if c == 0:
            return args.decode('utf8'),
        elif c == 1:
            return args[:8], cls.DIRECTION[args[8]]
        elif c == 2:
            return args,
        elif c == 3:
            return args,
        elif c == 4:
            return args,
        elif c == 254:
            return args,
        elif c == 255:
            return args,
        raise LookupError(f'invalid command: {c}')

    def register(self, name):  # TODO: add max connections
        hash_id = random.getrandbits(64).to_bytes(8, 'big')
        if hash_id in self.players:
            return
        snek = self.engine.create_snek(name=name)
        sneks, kinds = self.engine.all_objects()
        player = Server.Player(snek, sneks, kinds, time.time())
        self.players[hash_id] = player
        return hash_id

    def set_dir(self, hash_id, direction):  # add exception handling
        player = self.players[hash_id]
        player.snek.dir = direction
        return b'\x00'

    def engine_info(self):
        data = json.dumps(self.engine.info).encode('ascii')  # move to snekpi?
        data_len = len(data).to_bytes(2, 'big')
        return data_len + data

    def get_state_current(self, hash_id):
        player_snek = snekpi.BaseSnek()
        if hash_id:
            player_snek = self.players[hash_id].snek
        sneks, kinds = self.engine.all_objects
        res = b''

        res += snekpi.encode_whole_object(player_snek)
        res += (len(sneks) - 1 if player_snek in sneks else len(sneks)).to_bytes(4, 'big')  # ugly?
        for snek in sneks:
            if snek is not player_snek:
                res += snekpi.encode_whole_object(snek)

        for kind, elements in kinds.items():
            res += len(kind).to_bytes(4, 'big')
            for element in elements:
                res += snekpi.encode_whole_object(element)

        return res

    def get_state_updated(self, hash_id):
        player_snek = self.players[hash_id].snek
        sneks = self.players[hash_id].sneks
        kinds = self.players[hash_id].kinds
        res = b''

        res += snekpi.encode_partial_object(player_snek, sneks[player_snek][0], sneks[player_snek][1])
        res += (len(sneks) - 1).to_bytes(4, 'big')
        for snek, (news, olds) in sneks.items():
            if snek is not player_snek:
                res += snekpi.encode_partial_object(snek, news, olds)

        for kind, elements in kinds.items():
            res += len(kind).to_bytes(4, 'big')
            for element, (news, olds) in elements:
                res += snekpi.encode_partial_object(element, news, olds)

        return res

    def get_state_current_old(self, hash_id):
        alive = False
        if hash_id:
            alive = self.players[hash_id].snek.alive
        blocks = self.engine.all_blocks
        res = b''

        res += alive.to_bytes(1, 'big')
        res += snekpi.encode_blocks(blocks, [])

        return res

    def get_state_updated_old(self, hash_id):  # news and olds might contain repeated elements, is that a problem?
        player = self.players[hash_id]
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

    async def dispatch(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        c = (await reader.readexactly(1))[0]
        _args = await reader.read()  # is it safe to read any amount of bytes?

        args = self.decode(c, _args)
        answer = self.cases[c](*args)

        writer.write(answer)
        await writer.drain()

        # TODO: update staff abut player (e.g. last, ...)
        if c in (3, 4, 254, 255):
            pass
            # reset sneks, and kinds of the player; also maybe do this inside the functions themselves
        # set player last to time.time()

        writer.close()
        await writer.wait_closed()


def main():
    engine = PacManSnekEngine(width=20, height=20, max_food=2, game_tick=0.2)
    server = Server(address=('', 12345), engine=engine)
    server.run()


if __name__ == '__main__':
    main()
