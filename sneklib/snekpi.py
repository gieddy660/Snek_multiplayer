import json


def encode_json(serializable):
    data = json.dumps(serializable).encode('ascii')
    data_len = len(data).to_bytes(2, 'big')
    return data_len + data


def encode_object_metadata(snek_like_object):
    alive = int(snek_like_object.alive).to_bytes(1, 'big')
    data = encode_json(snek_like_object.data)
    return alive + data


def encode_blocks(new_blocks, old_blocks):
    res = b''

    new_blocks_len = len(new_blocks).to_bytes(4, 'big')
    old_blocks_len = len(old_blocks).to_bytes(4, 'big')
    res += new_blocks_len + old_blocks_len

    for x, y in new_blocks:
        res += x.to_bytes(2, 'big') + y.to_bytes(2, 'big')
    for x, y in old_blocks:
        res += x.to_bytes(2, 'big') + y.to_bytes(2, 'big')

    return res


def encode_partial_object(snek_like_object, new_blocks, old_blocks):
    res = encode_object_metadata(snek_like_object)
    res += encode_blocks(new_blocks, old_blocks)
    return res


def encode_whole_object(snek_like_object):
    return encode_partial_object(snek_like_object, snek_like_object.whole, [])


def encode_partial_list(obj_news_olds):
    res = b''
    obj_len = 0
    for snek_like_object, news, olds in obj_news_olds:
        res += encode_partial_object(snek_like_object, news, olds)
        obj_len += 1
    return obj_len.to_bytes(4, 'big') + res


def encode_whole_list(objs):
    return encode_partial_list(((obj, obj.whole, []) for obj in objs))


def decode_json(message):
    data_len = int.from_bytes(message[:2], 'big')
    data = json.loads(message[2:data_len + 2].decode('ascii'))
    return data, message[data_len + 2:]


def decode_blocks(message):
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


def decode_object(message):
    alive = bool(message[0])
    message = message[1:]

    data, message = decode_json(message)

    new_blocks, old_blocks, message = decode_blocks(message)

    return (alive, data, new_blocks, old_blocks), message


def decode_list(message):
    snek_like_object_len = int.from_bytes(message[:4], 'big')
    message = message[4:]

    snek_like_objects = []
    for i in range(snek_like_object_len):
        snek_like_object, message = decode_object(message)
        snek_like_objects.append(snek_like_object)

    return snek_like_objects, message


def decode_message(message):
    player, message = decode_object(message)

    sneks, message = decode_list(message)

    kinds = []
    while message:
        sneks_like_objects, message = decode_list(message)
        kinds.append(sneks_like_objects)

    return player, sneks, kinds
