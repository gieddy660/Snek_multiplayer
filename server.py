import asyncio
import random
import time
from dataclasses import make_dataclass
from functools import partial

# pacman effect -> snek wraps to the other side when it exits


class Snek:
    MOVEMENT = {'u': (0, -1), 'l': (-1, 0), 'd': (0, 1), 'r': (1, 0), 'lol': (0, -3)}

    def __init__(self,  dir='u', pos=(0, 0)):
        ''' snek spawns vertical, facing up, 3 blocks high '''
        self.dir = dir
        self.whole = [(pos[0], pos[1] + b) for b in range(3)]
        self.alive = True

    @property
    def head(self):
        return self.whole[:1]

    @head.setter
    def head(self, value):
        self.whole[:1] = value

    @property
    def body(self):
        return self.whole[1: -1]

    @property
    def tail(self):
        return self.whole[-1:]

    @property
    def future(self):
        zip_ = zip(self.head[0], type(self).MOVEMENT[self.dir])
        t = [tuple(a + b for a, b in zip_)]
        return t

    def kill(self):
        self.alive = False

    def move(self, grow=False):
        if grow:
            res = (set(self.future), set())
            self.whole = self.future + self.whole
        else:
            res = (set(self.future), set(self.tail))
            self.whole = self.future + self.head + self.body
        return res

    def __and__(self, other):
        if other is self:
            return self.future[0] in (other.head + other.body)
        return self.future[0] in (other.future + other.head + other.body)

    def __len__(self):
        return len(self.whole)


class PacManSnek(Snek):
    def __init__(self, dimensions, dir='u', pos=(0, 0)):
        super().__init__(dir, pos)
        self.dimensions = dimensions

    @property
    def future(self):
        zip_ = zip(self.head[0], type(self).MOVEMENT[self.dir], self.dimensions)
        t = [tuple((a + b) % c for a, b, c in zip_)]
        return t


class Food(Snek):
    def __init__(self, pos=(0, 0)):
        self.whole = [pos]
        self.alive = True

    @property
    def future(self):
        return self.head

    def move(self, grow=False):
        pass


class SnekEngine:
    _snek_factory = Snek

    def __init__(self, width, height, max_food, game_tick, sneks=(), foods=()):
        self.width = width
        self.height = height
        self.sneks = list(sneks)
        self.target_food = max_food
        self.foods = list(foods)
        self.game_tick = game_tick

    def snek_within(self, snek):
        return 0 <= snek.future[0][0] < self.width and 0 <= snek.future[0][1] < self.height

    @property
    def all_blocks(self):
        res = set()
        for snek in self.sneks:
            res |= set(snek.whole)
        for food in self.foods:
            res |= set(food.whole)
        return res

    def move(self):
        res = [set(), set()]

        # kill sneks
        new_sneks = []
        for s1 in self.sneks:
            if not self.snek_within(s1) or any([s1 & s2 for s2 in self.sneks]) or not s1.alive:
                s1.kill()
                res[1] |= set(s1.whole)
            else:
                new_sneks.append(s1)
        self.sneks = new_sneks

        # eat food
        new_foods = []
        temp = set()
        for food in self.foods:
            for s1 in self.sneks:
                if food & s1:
                    food.kill()
                    res[1] |= set(food.whole)
                    temp.add(s1)
                    break
            else:
                new_foods.append(food)
        self.foods = new_foods

        # move sneks
        for snek in self.sneks:
            new, old = snek.move(snek in temp)  # IDEA: might be better to add a flag to snek
            res[0] |= new
            res[1] |= old

        # create food
        if len(self.foods) < self.target_food:
            t = self.create_food()
            if t is not None:
                res[0] |= set(t.head)

        t = res[0] & res[1]
        res[0] -= t
        res[1] -= t
        return res

    def create_snek(self):
        t = []
        for y in range(3, self.height-3):
            for x in range(self.width):
                if (x, y) not in self.all_blocks:
                    t.append((x, y))

        if t:
            res = self._snek_factory(pos=random.choice(t))
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

    def __init__(self, width, height, max_food, game_tick, sneks=(), foods=()):
        super().__init__(width, height, max_food, game_tick, sneks, foods)
        self._snek_factory = partial(self._snek_factory, dimensions=(width, height))  # ugly?


class Server:
    PLAYER_HASH_SIZE = 8
    DIR_MESSAGE_SIZE = 1
    DEAD, ALIVE = b'\x00', b'\x01'
    DIRECTION = {b'\x01': 'u', b'\x02': 'l', b'\x03': 'd', b'\x04': 'r', b'\x05': 'lol'}
    KICK_TIME = 10

    Player = make_dataclass('Player', [('snek', Snek), ('news', set), ('olds', set), ('last', float)])

    def __init__(self, address, engine, max_connections=5):
        self.address = address
        self.engine = engine
        self.max_connections = max_connections
        self.players = {}

    def run(self):
        asyncio.run(self.loop())

    async def loop(self):
        server = await asyncio.start_server(self.dispatch, self.address[0], self.address[1],
                                            backlog=self.max_connections)
        async with server:
            await server.start_serving()  # DEBUG: seems like it's working, but keep under control

            async for news, olds in self.engine.loop():
                print(news, olds)

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
                self.players = new_players

    async def dispatch(self, reader, writer):
        '''
              | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
        s  =  [           play_id_hash        |
              | d ]
        r  =  [ a |   n   |   d   ]
        ns =  [   x   |   y   ]*
        ds =  [   x   |   y   ]*

        s = client message ................. (9 bytes)
        r = server response message ........ (5 bytes)
        ns = new blocks (to be drawn) ...... (4 bytes * n)
        ds = old blocks (to be cleared) .... (4 bytes * d)

        play_id_hash = hash that represents each player ... (8 bytes)
        d = new direction ................................. (1 byte)
        a = still alive or dead ........................... (1 byte)
        n = number of new blocks .......................... (2 bytes)
        d = number of deleted blocks ...................... (2 bytes)
        x = x coordinate of the block ..................... (2 bytes)
        y = y coordinate of the block ..................... (2 bytes)
        '''
        try:
            player_hash = await reader.readexactly(Server.PLAYER_HASH_SIZE)
            new_dir = await reader.readexactly(Server.DIR_MESSAGE_SIZE)
            if player_hash not in self.players:
                if len(self.players) >= self.max_connections:
                    raise ConnectionError
                snek = self.engine.create_snek()
                if snek is None:
                    raise ValueError
                news = set(self.engine.all_blocks)
                olds = set()
                last = time.time()
                self.players[player_hash] = Server.Player(snek, news, olds, last)
                for player in self.players.values():
                    player.news |= set(snek.whole)
        except (asyncio.IncompleteReadError, ConnectionError, ValueError) as err:
            writer.close()
            if isinstance(err, asyncio.IncompleteReadError):
                print('failed connection attempt')
            elif isinstance(err, ConnectionError):
                print('full server')
            elif isinstance(err, ValueError):
                print("can't generate any snek")
            await writer.wait_closed()
            return

        player = self.players[player_hash]
        player.snek.dir = Server.DIRECTION[new_dir]

        a = Server.ALIVE if player.snek.alive else Server.DEAD
        n = bytes([len(player.news) & 0xff00, len(player.news) & 0xff])
        d = bytes([len(player.olds) & 0xff00, len(player.olds) & 0xff])
        writer.write(a)
        writer.write(n)
        writer.write(d)
        for block in player.news:
            x = bytes([block[0] & 0xff00, block[0] & 0xff])
            y = bytes([block[1] & 0xff00, block[1] & 0xff])
            writer.write(x)
            writer.write(y)
        for block in player.olds:
            x = bytes([block[0] & 0xff00, block[0] & 0xff])
            y = bytes([block[1] & 0xff00, block[1] & 0xff])
            writer.write(x)
            writer.write(y)
        await writer.drain()

        player.news = set()
        player.olds = set()
        player.last = time.time()
        writer.close()
        await writer.wait_closed()


if __name__ == '__main__':
    engine = PacManSnekEngine(width=20, height=20, max_food=2, game_tick=0.2)
    server = Server(address=('', 12345), engine=engine)
    server.run()
