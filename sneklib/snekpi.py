import json


def encode_json(serializable):
    """encodes a json serializable object"""
    data = json.dumps(serializable).encode('ascii')
    data_len = len(data).to_bytes(2, 'big')
    return data_len + data


def encode_snek_metadata(snek):
    """encodes alive and data attributes of a snek"""
    alive = int(snek.alive).to_bytes(1, 'big')
    data = encode_json(snek.data)
    return alive + data


def encode_blocks(new_blocks, old_blocks):
    """encodes new_blocks and old_blocks"""
    res = b''

    new_blocks_len = len(new_blocks).to_bytes(4, 'big')
    old_blocks_len = len(old_blocks).to_bytes(4, 'big')
    res += new_blocks_len + old_blocks_len

    for x, y in new_blocks:
        res += x.to_bytes(2, 'big') + y.to_bytes(2, 'big')
    for x, y in old_blocks:
        res += x.to_bytes(2, 'big') + y.to_bytes(2, 'big')

    return res


def encode_partial_snek(snek, new_blocks, old_blocks):
    """
    encodes a snek, using data and alive from the snek itself,
    but using new_blocks and old blocks from the arguments passed to the function
    """
    res = encode_snek_metadata(snek)
    res += encode_blocks(new_blocks, old_blocks)
    return res


def encode_whole_snek(snek):
    """encodes a snek"""
    return encode_partial_snek(snek, snek.whole, [])


def encode_partial_list(obj_news_olds):
    """
    Encodes a sequence of sneks using external new and old blocks.
    Parameter is a sequence, each element of which is a tuple containing
    1. snek, 2. new_blocks, 3. old_blocks.
    """
    res = b''
    obj_len = 0
    for snek_like_object, news, olds in obj_news_olds:
        res += encode_partial_snek(snek_like_object, news, olds)
        obj_len += 1
    return obj_len.to_bytes(4, 'big') + res


def encode_whole_list(objs):
    """encodes a list of sneks"""
    return encode_partial_list(((obj, obj.whole, []) for obj in objs))


def decode_json(message):
    """decodes a json message"""
    data_len = int.from_bytes(message[:2], 'big')
    data = json.loads(message[2:data_len + 2].decode('ascii'))
    return data, message[data_len + 2:]


def decode_blocks(message):
    """decodes old and new blocks"""
    new_blocks_len = int.from_bytes(message[:4], 'big')
    old_blocks_len = int.from_bytes(message[4:8], 'big')
    message = message[8:]

    new_blocks = []
    old_blocks = []

    for i in range(new_blocks_len):
        x = int.from_bytes(message[:2], 'big')
        y = int.from_bytes(message[2:4], 'big')
        message = message[4:]
        new_blocks.append((x, y))

    for i in range(old_blocks_len):
        x = int.from_bytes(message[:2], 'big')
        y = int.from_bytes(message[2:4], 'big')
        message = message[4:]
        old_blocks.append((x, y))

    return new_blocks, old_blocks, message


def decode_snek(message):
    """decodes a snek"""
    alive = bool(message[0])
    message = message[1:]

    data, message = decode_json(message)

    new_blocks, old_blocks, message = decode_blocks(message)

    return (alive, data, new_blocks, old_blocks), message


def decode_list(message):
    """decodes a list of sneks"""
    snek_like_object_len = int.from_bytes(message[:4], 'big')
    message = message[4:]

    snek_like_objects = []
    for i in range(snek_like_object_len):
        snek_like_object, message = decode_snek(message)
        snek_like_objects.append(snek_like_object)

    return snek_like_objects, message


def decode_message(message):
    """decodes a message"""
    player, message = decode_snek(message)

    sneks, message = decode_list(message)

    kinds = []
    while message:
        sneks_like_objects, message = decode_list(message)
        kinds.append(sneks_like_objects)

    return player, sneks, kinds
