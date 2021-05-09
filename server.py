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
        res = (self.future_head, ()) if self.will_grow else (self.future_head, self.tail)
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
        # sneks = {}
        # foods = {}
        # for snek in self.sneks:
        #     sneks[snek] = snek.whole
        # for food in self.foods:
        #     foods[food] = food.whole  # maybe we could use something other than a dict
        return self.sneks, (self.foods,)

    def move(self):
        new_foods = []
        new_blocks = {}
        old_blocks = {}

        # kill sneks
        keep_sneks = []
        for s1 in self.sneks:
            if not self.snek_within(s1) or any((s1 >> s2 for s2 in self.sneks)) or not s1.alive:
                s1.kill()
                old_blocks[s1] = s1.whole
            else:
                keep_sneks.append(s1)
        self.sneks = keep_sneks

        # eat food
        keep_foods = []
        for food in self.foods:
            for s1 in self.sneks:
                if s1 >> food:
                    food.kill()
                    s1.will_grow = True
                    old_blocks[food] = food.whole
                    break
            else:
                keep_foods.append(food)
        self.foods = keep_foods

        # move sneks
        for snek in self.sneks:
            new, old = snek.move()
            new_blocks[snek] = new
            old_blocks[snek] = old

        # create food
        if len(self.foods) < self.target_food:
            food = self.create_food()
            if food is not None:
                new_foods.append(food)
                new_blocks[food] = food.whole

        return new_foods, new_blocks, old_blocks

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
    KICK_TIME = 10

    Player = make_dataclass('Player', [('snek', snekpi.BaseSnek), ('last', float)])

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
            async for news, olds in self.engine.loop():  # TODO: restructure completely
                new_players = {}
                for hash_id, player in self.players.items():
                    player.news |= news
                    player.olds |= olds
                    player.news -= olds
                    player.olds -= news
                    if time.time() - player.last > Server.KICK_TIME:
                        player.snek.kill()
                    else:
                        new_players[hash_id] = player

    @classmethod
    def decode(cls, c, args):  # TODO: add exception handling
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

    def register(self, name):  # TODO: rework for new self.player
        hash_id = random.getrandbits(64).to_bytes(8, 'big')
        if hash_id in self.players:
            return
        snek = self.engine.create_snek(name=name)
        player = Server.Player(snek, time.time())
        self.players[hash_id] = player
        return hash_id

    def set_dir(self, hash_id, direction):  # add exception handling
        player = self.players[hash_id]
        player.dir = direction
        return b'\x00'

    def engine_info(self):
        data = json.dumps(self.engine.info).encode('ascii')  # move to snekpi?
        data_len = len(data).to_bytes(2, 'big')
        return data_len + data

    def get_state_current(self, hash_id):
        player_snek = snekpi.BaseSnek
        if hash_id in self.players:
            player_snek = self.players[hash_id].snek
        sneks, stuff = self.engine.all_objects
        res = b''

        res += snekpi.encode_whole_object(player_snek)
        res += (len(sneks) - 1 if player_snek in sneks else len(sneks)).to_bytes(4, 'big')  # ugly?\
        for snek in sneks:
            if snek is not player_snek:
                res += snekpi.encode_whole_object(snek)

        for kind in stuff:
            res += len(kind).to_bytes(4, 'big')
            for snek_object in kind:
                res += snekpi.encode_whole_object(snek_object)

        return res

    def get_state_updated(self, hash_id):
        raise NotImplementedError

    def get_state_current_old(self, hash_id):
        raise NotImplementedError

    def get_state_updated_old(self, hash_id):
        raise NotImplementedError

    async def dispatch(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        c = (await reader.readexactly(1))[0]
        _args = await reader.read()  # is it safe to read any amount of bytes?

        args = self.decode(c, _args)
        answer = self.cases[c](*args)

        writer.write(answer)
        await writer.drain()

        # update staff abut player (e.g. last, ...)

        writer.close()
        await writer.wait_closed()


def main():
    engine = PacManSnekEngine(width=20, height=20, max_food=2, game_tick=0.2)
    server = Server(address=('', 12345), engine=engine)
    server.run()


if __name__ == '__main__':
    main()
