import random
from functools import partial
from itertools import chain

from sneklib import basetypes, servers


# pacman effect -> snek wraps to the other side when it exits


class Snek(basetypes.Snek):
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
    def future_whole(self):
        if self.will_grow:
            return self.future_head + self.whole
        else:
            return self.future_head + self.head + self.body

    def move(self):
        res = (self.future_head, []) if self.will_grow else (self.future_head, self.tail)
        super().move()
        self.will_grow = False
        return res

    def __rshift__(self, other):
        if other is self:
            return self.future_head[0] in (other.head + other.body)
        return self.future_head[0] in (other.future_head + other.head + other.body)


class PacManSnek(Snek):
    def __init__(self, dimensions, direction='u', pos=(0, 0), name=''):
        super().__init__(direction, pos, name)
        self.dimensions = dimensions

    @property
    def future_head(self):
        zip_ = zip(self.head[0], type(self).MOVEMENT[self.dir], self.dimensions)
        t = [tuple((a + b) % c for a, b, c in zip_)]
        return t


class Food(basetypes.Snek):
    def __init__(self, pos=(0, 0)):
        whole = [pos]
        super().__init__(whole=whole)


class Wall(basetypes.Snek):
    def __init__(self, pos):
        whole = [pos]
        super().__init__(whole=whole)


class SnekEngine(basetypes.SnekEngine):
    _snek_factory = Snek
    mode = 'Snek'

    def __init__(self, width, height, max_food, game_tick, sneks=(), foods=(), walls=()):
        self.width = width
        self.height = height
        self.target_food = max_food
        super().__init__(sneks, {Food: foods, Wall: walls}, game_tick)

    @property
    def infos(self):
        return {'mode': self.mode, 'width': self.width, 'height': self.height}

    @property
    def foods(self):
        return self.other_objects[Food]

    @foods.setter
    def foods(self, value):
        self.other_objects[Food] = value

    @property
    def walls(self):
        return self.other_objects[Wall]

    @walls.setter
    def walls(self, value):
        self.other_objects[Wall] = value

    def snek_within(self, snek):
        return 0 <= snek.future_head[0][0] < self.width and 0 <= snek.future_head[0][1] < self.height

    def create_snek(self, *args, **kwargs):
        t = []
        for x in range(self.width):
            for y in range(3, self.height-3):
                if all((x, y + b) not in self.all_blocks for b in range(3)):
                    t.append((x, y))

        if t:
            return super().create_snek(pos=random.choice(t), *args, **kwargs)
        return None  # IDEA: maybe raise instead

    def create_food(self):
        t = []
        for x in range(self.width):
            for y in range(self.height-3):
                if (x, y) not in self.all_blocks:
                    t.append((x, y))

        if t:
            res = Food(pos=random.choice(t))
            self.foods.append(res)
            return res
        return None  # IDEA: maybe raise instead

    def move(self):
        # 0: news, 1: olds
        sneks = {}
        foods = {}
        new_foods = {}

        # kill sneks
        keep_sneks = []
        for s1 in self.sneks:
            sneks[s1] = [[], []]
            if not self.snek_within(s1) or any((s1 >> s2 for s2 in chain(self.sneks, self.walls))) or not s1.alive:
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
            if food:
                new_foods[food] = [food.whole, []]

        return sneks, {}, {Food: foods}, {Food: new_foods}


class PacManSnekEngine(SnekEngine):
    _snek_factory = PacManSnek
    mode = 'PacManSnek/LoopingSnek'

    def __init__(self, width, height, max_food, game_tick, sneks=(), foods=(), walls=()):
        super().__init__(width, height, max_food, game_tick, sneks, foods, walls)
        self._snek_factory = partial(self._snek_factory, dimensions=(width, height))  # ugly?


def main():
    wall_list = [Wall(pos=(10, y)) for y in range(21)] + [Wall(pos=(x, 10)) for x in range(21) if x != 10]
    engine = PacManSnekEngine(width=21, height=21, max_food=2, game_tick=0.1, walls=wall_list)
    server = servers.AsyncTCPServer(address=('', 12345), engine=engine)
    server.DIRECTION = {b'\x01': 'u', b'\x02': 'l', b'\x03': 'd', b'\x04': 'r', b'\x05': 'lol'}
    server.run()


if __name__ == '__main__':
    main()
