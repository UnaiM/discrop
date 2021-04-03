discrop
=======

**Dynamic [Discord](https://discord.com) video call mapping for [OBS](https://obsproject.com)**

Ever tried laying out your calls nicely for your stream, cropping each participant, adding fancy frames and overlays, and suddenly someone’s video or connection drops, and nothing matches in OBS anymore? **This script solves that.**


Installation
------------

### Getting the right Python

We have to satisfy [OBS’s Python requirements](https://obsproject.com/docs/scripting.html). This script was tested on Windows 10 and OBS 26, with [WinPython x64 3.6.8](https://sourceforge.net/projects/winpython/files/WinPython_3.6/3.6.8.0/WinPython64-3.6.8.0Zero.exe).

In OBS’s main menu, go to _Tools > Scripts_ and in the _Python Settings_ tab, browse to the folder where the `python` program is located.

### Getting this script’s requirements

This script only requires the [discord.py package](https://pypi.org/project/discord.py) and its dependencies, and it’s prepared to run without any modifications as part of a [virtual environment](https://docs.python.org/3/tutorial/venv.html):

1. Clone or download this repository.
2. In a command line, run `path/to/python -m venv path/to/repo`, replacing `path/to/python` (pointing to the program itself) and `path/to/repo` accordingly.
3. Run `path\to\repo\Scripts\activate` (Windows) or `source path/to/repo/bin/activate` (everywhere else).
4. Run `pip install discord.py`.

### Setting up the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Go to the application’s _Bot_ section, and create a bot for it.
3. Copy its token into a file named `.bot_token`, sitting alongside `discrop.py`.
4. Under _Privileged Gateway Intents,_ enable the _Server Members Intent._
5. Go to the application’s _OAuth2_ section, and under _Scopes_, select `bot`.
6. _Bot Permissions_ should have appeared. There, under _Voice Permissions_, select _Connect._
7. Go to the auto-generated link that appears at the bottom of the _Scopes_ box, and invite your bot to a server.


Usage
-----

After loading `discrop.py` in OBS’s _Scripts_ window, you should see a _Help_ text and icon. Hover over it to get extensive instructions on how to use the script.
