# Snek_multiplayer
Multiplayer snake game written in python

### Communication between server and client

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

the client first send *s* message to the server to request to signal its direction.
The server answers with *r*, *ns* and *ds* messages to signal how to update the status of the client.
The messages get sent as raw integer, big endian over tcp sockets. 