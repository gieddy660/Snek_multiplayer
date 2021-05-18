# Snek_multiplayer
Multiplayer snake game written in python

###Communication between server and client

Each player is represented by: <br>
**hash_id** (8 bytes) <br>
note: **hash_id** must be unique

####Flow of the game:
1. player registers to the server
2. player sends commands and queries to the server to get status and set data about itself
3. player dies

####Commands:
    0 -> register to server
    1 -> set direction
    2 -> get game info
    3 -> get current state
    4 -> get updated state
    254 -> get current state (old mode)
    255 -> get updated state (old mode)


####Client message format:
    0 -> 
        | 0 (| name as UTF-8 string )|
    
    1 ->
        | 1 | player hash_id | direction |
    
    2 ->
        | 2 |
    
    3 ->
        | 3 (| player hash_id )|  (see note 2)
    
    4 ->
        | 4 | player hash_id |
    
    254 ->
        |254(| player hash_id )|  (see note 2)
    
    255 ->
        |255| player hash_id |



####Server answer format:
    0 -> register player to server:
        player hash_id (8 bytes)
    
    
    1 -> sets direction for player with given hash:
        - ack (1 byte)
    
    
    2 -> sends to the player game settings info:
        - length of json_string (2 bytes)
        - data (json) (ascii) (up to 65535 bytes) (see note 5)
            (es: mode, length)
    
    
    3 -> sends to player game state info:
        player:
            - alive (1 byte)
            data:
                - length of json_string (2 bytes)
                - data (json) (ascii) (up to 65535 bytes) (see note 5)
                    (es: name, length)
            - number of blocks (4 bytes)
            - 0 (4 bytes)
            for each block:
               - x coordinate (2 bytes)
               - y coordinate (2 bytes)
    
        - number of sneks (4 bytes) (see note (3))
        for each snek (both deleted and new):
            - 1 (1 byte)
            data:
                - length of json_string (2 bytes)
                - data (json) (ascii) (up to 65535 bytes) (see note 5)
                    (es: name, length)
            - number of blocks in order (4 bytes)
            - 0 (4 bytes)
            for each block:
               - x coordinate (2 bytes)
               - y coordinate (2 bytes)
    
        for each type of snek like object (food, walls, ecc)
            - number of snek like objects (4 bytes) (see note (3))
            for each snek like object (both deleted and new)
                - 1 (1 byte)
                data:
                    - length of json_string (2 bytes)
                    - data (json) (ascii) (up to 65535 bytes) (see note 5)
                        (es: name, length)
                - number of new blocks (4 bytes)
                - 0 (4 bytes)
                for each block:
                   - x coordinate (2 bytes)
                   - y coordinate (2 bytes)
        (it's sent like this so that it can be treated as a snek)
    
    
    4 -> sends to player updates to the state of the game since last request:
        player:
            - alive (1 byte)
            data:
                - length of json_string (2 bytes)
                - data (json) (ascii) (up to 65535 bytes) (see note 5)
                    (es: name, length)
            - number of new blocks (4 bytes)
            - number of old blocks (4 bytes)
            for each block:
                - x coordinate (2 bytes)
                - y coordinate (2 bytes)
    
        - number of sneks (4 bytes) (both dead or alive, old and new, see note (4))
        for each snek (both deleted and new):
            - alive (1 byte)
            data:
                - length of json_string (2 bytes)
                - data (json) (ascii) (up to 65535 bytes) (see note 5)
                    (es: name, length)
            - number of new blocks in order (4 bytes)
            - number of old blocks in order (4 bytes)
            for each block:
                - x coordinate (2 bytes)
                - y coordinate (2 bytes)
    
        for each type of snek like object (food, walls, ecc)
            - number of snek like objects (4 bytes) (both dead or alive, old and new, see note (4))
            for each snek like object (both deleted and new)
                - alive (1 byte)
                data:
                    - length of json_string (2 bytes)
                    - data (json) (ascii) (up to 65535 bytes) (see note 5)
                        (es: name, length)- data (json) (variable length)
                - number of new blocks (4 bytes)
                - number of old blocks (4 bytes)
                for each block:
                    - x coordinate (2 bytes)
                    - y coordinate (2 bytes)
        (it's sent like this so that it can be treated as a snek)
    
    
    254 -> sends current state in old mode, meaning it only sends blocks and if the player is alive:
        - alive (1 byte)
    
        - number of blocks (4 bytes)
        - 0 (4 bytes)
        for each block:
            - x coordinate (2 bytes)
            - y coordinate (2 bytes)
    
    
    255 -> sends updated state in of the game in old mode, meaning it only sends old and new blocks and if the player is alive:
        - alive (1 byte)
    
        - number of new blocks (4 bytes)
        - number of old blocks (4 bytes)
        - for each block
            - x coordinate (2 bytes)
            - y coordinate (2 bytes)

######Notes:
1.  All numbers are **unsigned integers**, sent as **big endian**.

2.  For commands *3* and *254* **hash_id** of a player is optional. If not given, the server sends a dummy player
    that should be ignored.

3.  Differently to command *4* the only objects to be sent are the ones alive right now, so if an object
    dies between two adjacent messages the server doesn't communicate it directly. Therefore, the client
    should discard current state of the game every time it uses this command. <br>
    es:

        message 1: A B C
        meanwhile B dies and D joins
        message 2: A C D

    (note that the server doesn't directly communicate identity of an object, so the client can't effectively
    know that the second object sent is now C rather than B)

4.  Objects of each type are sent in order, so that the first object sent in two following messages is
    the same object, and the same applies for the second, third, and so on. If an object is to be deleted
    the server will still send it in the following message marking it as dead. It will not be sent in
    subsequent messages. Objects that are to be added will be added at the bottom of the list. <br>
    es:

        message 1: A B C
        message 2: A B C D
        message 3: A B.dead C D
        message 4: A C D

5.  While data is sent as ascii, the strings it contains may contain unicode. Unicode characters are escaped
    with \x \u or \U  (see Python's <code>ascii</code> builtin function or <code>json.dump</code> function).