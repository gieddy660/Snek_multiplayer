# Snek_multiplayer

**snek_multiplayer** is a framework for building multiplayer games. The name comes from the fact that it is particularly
apt for building snake-like games though it can be used to build many kinds of games.

---

## File Structure

This is an explanation of all the files contained in the repository

* ### [sneklib/](sneklib)
  This folder is the base folder for the sneklib package. It provides libraries for the **snek_multiplayer** framework,
  with functions for encoding and decoding messages, base types for implementing different game modes, and functions for
  making and serving requests.

    * #### [\_\_init\_\_.py](sneklib/__init__.py)
      Empty for now, might contain some infos about the package in the future.

    * #### [snekpi.py](sneklib/snekpi.py)
      The `snekpi` module contains the functions used to encode and decode messages between client and server.

    * #### [basetypes.py](sneklib/basetypes.py)
      This module contains 3 classes:
        * `Snek`
        * `SnekEngine`
        * `Server`

      These classes are the base classes used for defining custom snek classes and game logic (and to a lesser extent
      custom servers)

    * #### [servers.py](sneklib/servers.py)
      `servers.py` provides various implementations of servers. Right now it only contains `AsyncTCPServer` but it will
      be expanded in future to support UDP and other.

    * #### [aiosnek.py](sneklib/aiosnek.py)
      This module provides some functions used to make requests to the server. As of right now it only supports TCP
      with `asyncio`, but it will be expanded.

* ##### [server.py](server.py)
  An example implementation of the server. It creates 4 snek classes that are derived from `sneklib.basetypes.Snek`
  which than interact in 2 possible snek engines derived from `sneklib.basetypes.SnekEngine`. When the application gets
  started an instance of
  `sneklib.servers.AsyncTCPServer` gets created and run.

* ##### [client.py](client.py)
  An example implementation of the client. It uses `aiosnek` to make requests to the server. It uses two functions for
  updating the screen `draw_screen_whole` and
  `draw_screen_partial` for updating the screen and printing it to terminal. As of now it is still very underdeveloped
  and will be expanded in the future to have a complete GUI (probably using pygame).

* #### [README.md](README.md)
  This very file. It contains an explanation of the contents of the repository, explanations on how to build a server
  application through the **Snek BaseTypes** API, and definition of the **snek communication protocol**.

---

## Snek BaseTypes API

`basetypes.py` exposes three classes:

* `Snek`
* `SnekEngine`
* `Server`

These classes represent the basic elements that compose a snek_multiplayer game. These classes (except for `Server`, as
server implementations are already provided in `servers.py`) are expected to be subclassed in order to define custom
logic for one's own game.

Other two concepts are present inside the module:

* `Block`
* `Player`

`Block` is not actually a class and `Player` is a dataclass. These are *provided*
as is and are not expected to be subclassed.

### Block

A block is a tuple containing 2 (*unsigned*) integers. The first integer is the
**X** coordinate of the block, and the second integer is the **Y** coordinate of the block.

### Snek

A snek is any object that takes part to a game inside a snek engine. Therefore, players should have a corresponding snek
object, and (for example in the case of a snake-like game) so must walls, foods etc.

A snek is an object that provides the following attributes and method:

* `alive` a boolean representing whether the snek is alive or not.
* `whole` an *ordered* list of blocks representing the all the blocks
* `data` additional data about the snek (for example its name)
  that belong to the snek (should be json serializable)
* `kill()` sets sneks alive attribute to false.

Although not strictly necessary, other methods and attributes (even in the form of `@properties`) should be present and
are provided inside a snek:

* `head` it represents the head of a snek, should be the first element of `whole`
* `tail` it represents the tail of the snek, should be the last element of `whole`
* `body` everything that is not `head` or `tail`
* `future_head` what the head will be if the snek moves now
* `future_whole` what whole will be if the snek moves now
* `move()` method for actually moving the snek, should return a tuple containing new blocks as the first value and old
  blocks as the second value.

**note** that `head` `tail` and `future_head` should still be lists of one block and not a single block.

For user defined classes there should be no need to overload anything but `future_head`, `future_whole` and `move()` (
and optionally `data`). When overloading `move()`, in general only the return value should be calculated,
and `super().move()` should be called which sets `snek.whole` to `snek.future_whole`. Additional functionalities can
also be implemented in other *custom* methods.

### SnekEngine

The logic of the game is mostly defined within a snek engine. A snek engine consists of a collection of sneks of
different types, and the logic needed to make them interact.

A snek engine must provide the following attributes and methods:

* `infos` infos about the snek engine (es: size or game mode); should be json-serializable
* `all_blocks` a list of all the blocks contained inside the game_engine
* `all_objects` a tuple of all the objects contained inside the game_engine, which has a list of all the sneks that
  represent players as its first element, and a dictionary of all the other elements, where elements of the same type
  are contained inside the same list which has as key the type of the objects.
* `create_snek(*args, **kwargs)` method used for adding new player-sneks to the engine.
* `loop()` asynchronous `loop` generator method that keeps the server running. It should yield a tuple of the following
  format `(sneks, new_sneks, kinds, new_of_kinds)` with
    1. `sneks` is a dictionary of the non-new player-sneks in the server, which associates to each snek a tuple
       containing new_blocks as its first element, old_blocks as uts second element
    2. `new_sneks` is a dictionary formatted like `sneks`, but which only contains new sneks
    3. `kinds` is a dictionary which associates types of sneks as keys to dictionary each formatted like `sneks` which
       contains non-new sneks of a that type
    4. `new_of_kinds` like kinds but only for newly created sneks.

the `SnekEngine` class inside `basetypes.py` in addition to the previous attributes and methods additionally provides:

* `_snek_factory` a callable that creates a new snek of some type which should represent a player; it receives the
  arguments that are passed to `create_snek`
* `sneks` list of player-sneks inside the game engine
* `other_sneks` dictionary of other sneks inside the game engine (sneks of the same type are inside the same list which
  has the type of the sneks as key)
* `game_tick` number of seconds that each tick should last
* `move()` method which actually contains the logic of the game. It gets periodically called inside `loop()` and in fact
  it is this function which actually returns the yield value of loop

**NOTE**: it is very important that all the lists which contain sneks mentioned above
**keep element in the same relative order** (meaning that it must hold true that snek A comes before snek B if this was
previously true). This is necessary because sneks are identified in the client by the order in these lists.

User defined classes should extend `create_snek` and overload `move` (and optionally `_snek_factory`), to actually
implement the logic of the game. Additional features may be added via other methods and attributes.

### Player

A player is a dataclass, which represents a player who has registered to the server. It has four attributes:

* `snek` the snek of the player
* `sneks` a dictionary which has the sneks of the other players as keys, and new and old blocks of each snek as value
  for a snek
* `kinds` a dictionary which contains all the other objects of the game; It is composed of dictionaries that are
  individually built like the `sneks` dictionary, but whose values are the type of the object they contain
* `last` a float with the time of the last command from the player

### Server

The server is the object that directly communicates with the client. It serves as a bridge between the engine (and
therefore also the sneks that it contains) and therefore contains methods for generating and providing answers to the
client requests. These methods are *private* (meaning their names start with two underscores) and shouldn't be accessed
or modified. For most users there should be no need to subclass from Server, as server implementations are provided
inside the `servers.py` module.

Servers have the following attributes and methods:

* `address` it contains the address of the server; tha kind of value passed vary depending on the server implementation
  used.
* `engine` the game engine for the server
* `max_connections` max number of player that can simultaneously connect to the server
* `players` a dictionary which has hash_id and Player of each player as keys and values.
* `run()` method called to start the server
* `loop()` asynchronous method with the purpose of starting the three following loops
* `user_interface_loop()` asynchronous *loop* method that draws UI for the server
* `game_loop()` asynchronous *loop* method that *bridges* between the snek engine and the server itself, updating
  players accordingly
* `server_loop()` asynchronous *loop* method that is actually responsible for starting the server; must be implemented
  in the subclasses
* `deal_with_request(c, _args)` function that should be called to deal with an incoming message from a player The server
  should read the incoming message in its entirety and forward it to this function, which will than modify the state of
  the server accordingly and return an answer that should be relayed back to the player. The 2 arguments `c` amd `_args`
  are the incoming message from the player: `c` is the first byte of the message and `_args` contains all the following
  bytes.

---

## Snek Communication Protocol

In this section it is explained the protocol for the communication between client and server

#### player representation

Each player is represented by: <br>
**hash_id** (8 bytes) <br>
note: **hash_id** must be unique

#### Flow of the game:

1. player registers to the server
2. player sends commands and queries to the server to get status and set data about itself
3. player dies

#### Commands:

    0 -> register to server
    1 -> set direction
    2 -> get game info
    3 -> get current state
    4 -> get updated state
    254 -> get current state (old mode)
    255 -> get updated state (old mode)

#### Client message format:

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

#### Server answer format:

    0 -> register player to server:
        - player hash_id (8 bytes)
    
    
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

###### Notes:

1. All numbers are **unsigned integers**, sent as **big endian**.

2. For commands *3* and *254* **hash_id** of a player is optional. If not given, the server sends a dummy player that
   should be ignored.

3. Differently to command *4* the only objects to be sent are the ones alive right now, so if an object dies between two
   adjacent messages the server doesn't communicate it directly. Therefore, the client should discard current state of
   the game every time it uses this command. <br>
   es:

       message 1: A B C
       meanwhile B dies and D joins
       message 2: A C D

   (note that the server doesn't directly communicate identity of an object, so the client can't effectively know that
   the second object sent is now C rather than B)

4. Objects of each type are sent in order, so that the first object sent in two following messages is the same object,
   and the same applies for the second, third, and so on. If an object is to be deleted the server will still send it in
   the following message marking it as dead. It will not be sent in subsequent messages. Objects that are to be added
   will be added at the bottom of the list. <br>
   es:

       message 1: A B C
       message 2: A B C D
       message 3: A B.dead C D
       message 4: A C D

5. While data is sent as ascii, the strings it contains may contain unicode. Unicode characters are escaped with \x \u
   or \U  (see Python's `ascii` builtin function or `json.dump` function).
   
