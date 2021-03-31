import asyncio
import contextlib
import json
import os.path
import pprint
import types
import uuid

import requests
import websockets

CLIENT_ID = '207646673902501888' # StreamKit Overlay

token_file = os.path.join(os.path.dirname(__file__), '.access_token')
nonce = str(uuid.uuid4())
connected = False
channel_id = None
callers = set()


async def main():
    await asyncio.gather(*(task(port) for port in range(6463, 6473)))
    if not connected:
        raise RuntimeError('Couldn’t connect to Discord. Is it running?')


async def task(port):
    global connected

    current = asyncio.current_task()
    current.set_name(f'port{port}')
    try:
        async with websockets.connect(f'ws://127.0.0.1:{port}/?v=1&client_id={CLIENT_ID}&encoding=json', origin='https://discord.com') as socket:
            connected = True

            for t in asyncio.all_tasks():
                if t != current and t.get_name().startswith('port'):
                    t.cancel()

            async with exchange(socket) as msg:
                pass

            access_token = None
            if os.path.isfile(token_file):
                with open(token_file) as f:
                    access_token = f.read().rstrip()

            async with exchange(socket, 'AUTHENTICATE', access_token=access_token) if access_token else contextlib.AsyncExitStack() as msg: # AsyncExitStack = null context.
                if not access_token or msg.evt == 'ERROR' and msg.data.code == 4009: # Invalid token.
                    msg._skip = True # No need for extra error handling.

                    async with exchange(socket, 'AUTHORIZE', client_id=CLIENT_ID, scope='rpc') as msg:
                        code = msg.data.code

                    req = requests.post('https://streamkit.discord.com/overlay/token', data=json.dumps({'code': code}))
                    if req.status_code != requests.codes.ok:
                        raise RuntimeError('No access token:\n' + req.content)
                    access_token = req.json()['access_token']

                    with open(token_file, 'w') as f:
                        f.write(access_token + '\n')

                    async with exchange(socket, 'AUTHENTICATE', access_token=access_token):
                        pass

            async with exchange(socket, 'SUBSCRIBE', 'VOICE_CHANNEL_SELECT') as msg:
                pass
            await change_channel(socket)

            async for msg in listen(socket, use_nonce=False):
                if msg.cmd == 'DISPATCH':
                    if msg.evt == 'VOICE_CHANNEL_SELECT':
                        await change_channel(socket)
                    elif msg.evt == 'VOICE_STATE_CREATE':
                        callers.add(msg.data.nick)
                        print('User joined:', msg.data.nick)
                    elif msg.evt == 'VOICE_STATE_DELETE':
                        callers.discard(msg.data.nick)
                        print('User left:', msg.data.nick)

    except (ConnectionRefusedError, asyncio.CancelledError):
        pass


@contextlib.asynccontextmanager
async def exchange(socket, cmd=None, evt=None, **args):
    if cmd:
        msg = {'cmd': cmd, 'args': args, 'nonce': nonce}
        if evt:
            msg['evt'] = evt
        await socket.send(json.dumps(msg))
    async for msg in listen(socket, use_nonce=cmd):
        if cmd and msg.cmd == cmd and getattr(msg.data, 'evt', None) == evt or msg.cmd == 'DISPATCH' and msg.evt == 'READY':
            yield msg
            break


async def listen(socket, use_nonce=True):
    async for msg in socket:
        msg = json.loads(msg, object_hook=lambda x: types.SimpleNamespace(**x))
        if use_nonce and msg.nonce == nonce or not use_nonce:
            try:
                yield msg
            finally:
                if msg.evt == 'ERROR' and not getattr(msg, '_skip', None):
                    raise RuntimeError(msg.cmd + ' command failed:\n' + pprint.pformat(msg.data))


async def change_channel(socket):
    global channel_id

    if channel_id:
        async with exchange(socket, 'UNSUBSCRIBE', 'VOICE_STATE_CREATE', channel_id=channel_id) as msg:
            pass
        async with exchange(socket, 'UNSUBSCRIBE', 'VOICE_STATE_DELETE', channel_id=channel_id) as msg:
            pass
    async with exchange(socket, 'GET_SELECTED_VOICE_CHANNEL') as msg:
        callers.clear()
        if msg.data:
            channel_id = msg.data.id
            for c in msg.data.voice_states:
                callers.add(c.nick)
            async with exchange(socket, 'SUBSCRIBE', 'VOICE_STATE_CREATE', channel_id=channel_id) as msg:
                pass
            async with exchange(socket, 'SUBSCRIBE', 'VOICE_STATE_DELETE', channel_id=channel_id) as msg:
                pass
        else:
            channel_id = None
    print('CHANNEL SWITCHED.', ('Participants: ' + ', '.join(sorted(callers, key=lambda x: x.lower()))) if callers else 'No participants')


asyncio.run(main())
