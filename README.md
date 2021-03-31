RPC test
========

**WARNING: Completely different tree to `main` branch!**

This is as far as I got using the app credentials from the [StreamKit Overlay](https://streamkit.discord.com/overlay). We would also need the `rpc.api` scope to check for video, but this app isn’t whitelisted for that, and using our own app is off-bounds as the [RPC side of the API](https://discord.com/developers/docs/topics/rpc) is in public beta and not allowing new developers to enter it, so our app isn’t whitelisted for any of it.


Requirements
------------

* [Python](https://www.python.org/) ≥ 3.8
* [Requests](https://github.com/psf/requests)
* [Websockets](https://github.com/aaugustin/websockets)
