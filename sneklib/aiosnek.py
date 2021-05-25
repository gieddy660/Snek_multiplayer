import asyncio

from sneklib import snekpi


# TODO: improve exceptions

async def send_command(host, port, c, *args):
    """Function for sending a generic command"""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(c)
        await writer.drain()
        for arg in args:
            writer.write(arg)
            await writer.drain()
        writer.write_eof()
        await writer.drain()

        res = await reader.read()

        return res
    finally:
        writer.close()
        await writer.wait_closed()


async def register(host, port, name=''):
    """0 -> Registers a snek to the server"""
    hash_id = await send_command(host, port, b'\x00', name.encode('utf-8'))
    if not hash_id:
        raise ConnectionError('No hash_id received')
    return hash_id


async def set_dir(host, port, hash_id, direction):
    """1 -> Sets the direction of the snek"""
    ack = await send_command(host, port, b'\x01', hash_id, direction)
    if ack != b'\x00':
        raise ConnectionError('Error setting direction')


async def get_infos(host, port):
    """2 -> Request game general infos (e.g. game type, size, ...)"""
    _res = await send_command(host, port, b'\x02')

    data, _ = snekpi.decode_json(_res)

    return data


async def get_current_state(host, port, hash_id=b''):
    """3 -> Gets current state of the game from the server"""
    _res = await send_command(host, port, b'\x03', hash_id)

    return snekpi.decode_message(_res)


async def get_updated_state(host, port, hash_id):
    """4 -> gets updated state of the game since last request"""
    _res = await send_command(host, port, b'\x04', hash_id)

    return snekpi.decode_message(_res)


async def get_current_blocks(host, port, hash_id=b''):
    """254 -> requests current blocks in the game"""
    _res = await send_command(host, port, b'\xfe', hash_id)

    alive = bool(_res[0])
    news, olds, _ = snekpi.decode_blocks(_res[1:])

    return alive, news, olds


async def get_updated_blocks(host, port, hash_id):
    """255 -> requests updated blocks state in the server
    (new blocks and blocks to be deleted)"""
    _res = await send_command(host, port, b'\xff', hash_id)

    alive = bool(_res[0])
    news, olds, _ = snekpi.decode_blocks(_res[1:])

    return alive, news, olds
