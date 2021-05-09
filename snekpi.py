import json


class BaseSnek:
    def __init__(self, whole=None, data=()):
        self.alive = True
        if whole is None:
            whole = []
        self.whole = whole
        self.data = data

    @property
    def head(self):
        return self.whole[:1]

    @property
    def body(self):
        return self.whole[1:-1]

    @property
    def tail(self):
        return self.whole[-1:]

    @property
    def future_head(self):
        return self.head

    @property
    def future_whole(self):
        return self.whole

    def move(self):
        res = ((), ())
        self.whole = self.future_whole
        return res

    def kill(self):
        self.alive = False


def get_object_metadata(snek_like_object):
    alive = int(snek_like_object.alive).to_bytes(1, 'big')
    data = json.dumps(snek_like_object.data).encode('ascii')
    data_len = len(data).to_bytes(2, 'big')
    return alive + data_len + data


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


def encode_whole_object(snek_like_object):
    res = get_object_metadata(snek_like_object)
    res += encode_blocks(snek_like_object.whole, [])
    return res


def encode_partial_object(snek_like_object, new_blocks, old_blocks):
    res = get_object_metadata(snek_like_object)
    res += encode_blocks(new_blocks, old_blocks)
    return bytes()


def decode_blocks(message, length):
    res = []
    for i in range(length):
        x = int.from_bytes(message[:2], 'big')
        y = int.from_bytes(message[2:4], 'big')
        message = message[4:]
        res.append((x, y))
    return res


def decode_object(message):
    alive = bool(message[0])
    message = message[1:]

    data_len = int.from_bytes(message[:2], 'big')
    data = json.loads(message[2:data_len + 2].decode('ascii'))
    message = message[data_len + 2:]

    new_blocks_len = int.from_bytes(message[:4], 'big')
    old_blocks_len = int.from_bytes(message[4:8], 'big')
    message = message[8:]

    message_n = message[:new_blocks_len * 4]
    message_o = message[new_blocks_len * 4:]
    new_blocks = decode_blocks(message_n, new_blocks_len)
    old_blocks = decode_blocks(message_o, old_blocks_len)

    return alive, data, new_blocks, old_blocks
