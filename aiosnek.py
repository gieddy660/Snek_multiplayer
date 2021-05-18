import asyncio
import json

import snekpi


# TODO: exceptions

def send_command(host, port, c, *args):
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(c)
    for arg in args:
        writer.write(arg)
    writer.write_eof()
    await writer.drain()

    res = await reader.read()

    writer.close()
    await writer.wait_closed()

    return res


async def register(host, port, name=''):
    hash_id = send_command(host, port, b'\x00', name.encode('utf-8'))

    return hash_id


async def set_dir(host, port, hash_id, direction):
    ack = send_command(host, port, b'\x01', hash_id, direction)


async def get_infos(host, port):
    _res = send_command(host, port, b'\x02')

    data_len = int.from_bytes(_res[:2], 'big')
    data = json.loads(_res[2:data_len + 2].decode('ascii'))

    return data


async def get_current_state(host, port, hash_id=b''):
    _res = send_command(host, port, b'\x03', hash_id)

    return snekpi.decode_message(_res)


async def get_updated_state(host, port, hash_id):
    _res = send_command(host, port, b'\x04', hash_id)

    return snekpi.decode_message(_res)


async def get_current_blocks(host, port, hash_id=b''):
    _res = send_command(host, port, b'\xfe', hash_id)

    alive = bool(_res[0])
    news, olds, _ = snekpi.decode_blocks(_res[1:])

    return alive, news, olds


async def get_updated_blocks(host, port, hash_id):
    _res = send_command(host, port, b'\xff', hash_id)

    alive = bool(_res[0])
    news, olds, _ = snekpi.decode_blocks(_res[1:])

    return alive, news, olds
