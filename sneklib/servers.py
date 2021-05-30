import asyncio

from sneklib.basetypes import Server


class AsyncTCPServer(Server):
    """
    Server implementation using TCP and asyncio.
    If using this implementation address should be a tuple containing:
    a string with the IP address of the server as first element;
    a integer with the IP address if the server as second element.
    """

    async def server_loop(self):
        server = await asyncio.start_server(self.dispatch, self.address[0], self.address[1],
                                            backlog=self.max_connections)
        async with server:
            await server.serve_forever()

    async def dispatch(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        c = (await reader.readexactly(1))[0]
        _args = await reader.read()  # is it safe to read any amount of bytes?

        answer = self.deal_with_request(c, _args)

        writer.write(answer)
        await writer.drain()

        writer.close()
        await writer.wait_closed()
