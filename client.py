import asyncio
import keyboard
import sys
import random

DIRECTION = {'u': b'\x01', 'l': b'\x02', 'd': b'\x03', 'r': b'\x04', 'lol': b'\x05'}


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


def draw_screen(news, olds):  # TODO: imporove
    global grid
    for x, y in olds:
        grid[y][x] = ' '
    for x, y in news:
        grid[y][x] = 1

    for row in grid:
        for cell in row:
            print('{} '.format(cell), end='')
        print()


async def handle_connection(id_hash, host, port):
    while 1:
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(id_hash)
        writer.write(DIRECTION[direction])
        await writer.drain()

        a_ = await reader.read(1)  # DEBUG: readexactly? -- even for following rows
        n_ = await reader.read(2)
        d_ = await reader.read(2)

        a = True if a_ == b'\x01' else False
        n = (n_[0] << 8) + n_[1]
        d = (d_[0] << 8) + d_[1]
        if not a:
            sys.exit()

        news = []
        for _ in range(n):
            x_ = await reader.read(2)
            y_ = await reader.read(2)
            x = (x_[0] << 8) + x_[1]
            y = (y_[0] << 8) + y_[1]
            news.append((x, y))

        olds = []
        for _ in range(d):
            x_ = await reader.read(2)
            y_ = await reader.read(2)
            x = (x_[0] << 8) + x_[1]
            y = (y_[0] << 8) + y_[1]
            olds.append((x, y))

        draw_screen(news, olds)
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.1)


async def main():
    id_hash = (random.getrandbits(64)).to_bytes(8, 'big')
    host = 'localhost'
    port = 12345
    print(id_hash, host, port)
    await asyncio.gather(handle_connection(id_hash, host, port), gather_keyboard())

if __name__ == '__main__':
    grid = [[' ' for x in range(20)] for y in range(20)]
    asyncio.run(main())
