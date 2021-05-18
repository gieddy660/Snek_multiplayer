import asyncio
import sys

import keyboard

import aiosnek

DIRECTION = {'u': b'\x01', 'l': b'\x02', 'd': b'\x03', 'r': b'\x04', 'lol': b'\x05'}

A_MESSAGE_SIZE = 1
N_MESSAGE_SIZE = D_MESSAGE_SIZE = 2
X_MESSAGE_SIZE = Y_MESSAGE_SIZE = 2

direction: str


async def gather_keyboard():
    global direction
    direction = 'u'
    while True:
        if keyboard.is_pressed('w') and direction != 'd':
            direction = 'u'
        if keyboard.is_pressed('a') and direction != 'r':
            direction = 'l'
        if keyboard.is_pressed('s') and direction != 'u':
            direction = 'd'
        if keyboard.is_pressed('d') and direction != 'l':
            direction = 'r'
        if keyboard.is_pressed('u'):
            direction = 'lol'
        await asyncio.sleep(0.003)


def draw_screen_whole(blocks):  # TODO: improve
    global grid
    grid = [[' ' for x in range(20)] for y in range(20)]
    for x, y in blocks:
        grid[y][x] = 1

    for row in grid:
        for cell in row:
            print('{} '.format(cell), end='')
        print()


def draw_screen_partial(news, olds):  # TODO: improve
    global grid
    for x, y in olds:
        grid[y][x] = ' '
    for x, y in news:
        grid[y][x] = 1

    for row in grid:
        for cell in row:
            print('{} '.format(cell), end='')
        print()


async def handle_connection(host, port):
    hash_id = await aiosnek.register(host, port)
    await asyncio.sleep(0.01)

    while 1:
        await aiosnek.set_dir(host, port, hash_id, DIRECTION[direction])
        await asyncio.sleep(0.01)

        alive, new_blocks, old_blocks = await aiosnek.get_current_blocks(host, port, hash_id)

        if not alive:
            sys.exit()

        draw_screen_whole(new_blocks)


async def main():
    host = 'localhost'
    port = 12345
    print(host, port)
    await asyncio.gather(handle_connection(host, port), gather_keyboard())

if __name__ == '__main__':
    grid = [[' ' for x in range(20)] for y in range(20)]
    asyncio.run(main())
