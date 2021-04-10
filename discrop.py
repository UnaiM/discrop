import asyncio
import math
import os.path
import sys
import time
import threading

import obspython as obs

script_path_ = os.path.dirname(__file__) # script_path is part of the OBS script interface.
sys.path.append(os.path.join(script_path_, 'lib', 'site-packages'))
import discord

SLOTS = 10 # Seems to be the maximum people allowed.

# Discord call window measurements.
TITLE_BAR = 22
MARGIN_TOP = 64.5 # Half values since they fluctuate.
MARGIN_SIDES = 8.25 # Don’t ask why, but .25 here seems to be even more acurate.
MARGIN_BTM = 71.25 # Don’t ask why, but .25 here seems to be even more acurate.
CALLER_ASPECT = 16 / 9
CALLER_SPACING = 8
CALLER_BORDER = 3 # Inwards border when caller is talking.

client = None
thread = None
channels = []
full_screen = False
show_nonvideo_participants = False
discord_source = None
participants = ()


class Client(discord.Client):

    def __init__(self):
        super().__init__(intents=discord.Intents(guilds=True, members=True, voice_states=True))
        self.audio = []
        self.video = []
        self._audio = {}
        self._video = {}
        self._channel = None

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, channel):
        if (channel and not self._channel) or (self.channel and channel != self._channel.id):
            self._audio.clear()
            self._video.clear()
            self._channel = self.get_channel(channel)
            if self._channel:
                for member in self._channel.members:
                    if member.voice.self_video:
                        self._video[member.id] = member.display_name
                    else:
                        self._audio[member.id] = member.display_name
            else:
                self._channel = None
            self.sort()

    async def on_ready(self):
        for guild in sorted(self.guilds, key=lambda x: x.name.lower()):
            for channel in sorted(guild.channels, key=lambda x: x.position):
                if isinstance(channel, discord.VoiceChannel):
                    channels.append((guild.name + ' -> ' + channel.name, channel.id))

    async def on_member_update(self, before, after):
        if not self.channel:
            return
        if before.display_name != after.display_name and (before.voice and before.voice.channel == self.channel) or (after.voice and after.voice.channel == self.channel):
            # before.id == after.id (duh), so it doesn’t matter which one we use.
            if before.id in self._audio:
                self._audio[after.id] = after.display_name
            elif before.id in self._video:
                self._video[after.id] = after.display_name
            self.sort()

    async def on_voice_state_update(self, member, before, after):
        if not self.channel:
            return
        if before.channel == self.channel and after.channel == self.channel:
            if before.self_video and not after.self_video:
                self._video.pop(member.id, None)
                self._audio[member.id] = member.display_name
            if not before.self_video and after.self_video:
                self._audio.pop(member.id, None)
                self._video[member.id] = member.display_name
        elif before.channel == self.channel:
            self._audio.pop(member.id, None)
            self._video.pop(member.id, None)
        elif after.channel == self.channel:
            if after.self_video:
                self._video[member.id] = member.display_name
            else:
                self._audio[member.id] = member.display_name
        else:
            return
        self.sort()

    def sort(self):
        # Discord sorts ‘ ’ before EOF, e.g. ‘foo bar’ > ‘foo’. Python doesn’t, but we can leverage the fact that ‘ ’ goes right before ‘!’.
        self.audio = sorted(self._audio, key=lambda x: self._audio[x].lower() + '!')
        self.video = sorted(self._video, key=lambda x: self._video[x].lower() + '!')


def script_description(): # OBS script interface.
    return '<p style="color: orange"><strong>CAUTION:</strong> picking a Discord source from the menu below will <strong>irreversibly</strong> modify all related items!</p>'


def script_load(settings): # OBS script interface.
    global client
    global thread

    if asyncio.get_event_loop().is_closed():
        asyncio.set_event_loop(asyncio.new_event_loop())

    client = Client()
    with open(os.path.join(script_path_, '.bot_token')) as f: # script_path() is part of the OBS script interface.
        thread = threading.Thread(target=client.run, args=(f.read().rstrip(),))
        thread.start()


def script_update(settings): # OBS script interface.
    global full_screen
    global show_nonvideo_participants
    global discord_source
    global participants

    while not client.is_ready():
        time.sleep(0.1)
    client.channel = obs.obs_data_get_int(settings, 'voice_channel')
    full_screen = obs.obs_data_get_bool(settings, 'full_screen')
    show_nonvideo_participants = obs.obs_data_get_bool(settings, 'show_nonvideo_participants')
    obs.obs_source_release(discord_source) # Doesn’t error even if discord_source == None.
    discord_source = obs.obs_get_source_by_name(obs.obs_data_get_string(settings, 'discord_source'))
    participants = tuple(obs.obs_data_get_int(settings, f'participant{i}') for i in range(SLOTS))


def script_properties(): # OBS script interface.
    props = obs.obs_properties_create()

    grp = obs.obs_properties_create()
    p = obs.obs_properties_add_bool(grp, 'help', 'Help')
    obs.obs_property_set_enabled(p, False)
    obs.obs_property_set_long_description(p, '''<p>This script automatically maps Discord video calls into the scene’s layout.</p>
<h3>Discord instructions</h3>
<ol>
  <li>In the voice channel where the call is happening, go to the bottom-right corner and select <em>Pop Out.</em></li>
  <li>In the top-right corner, ensure you’re in <em>Grid</em> mode (no caller appears big while the rest are small).</li>
</ol>

<h3>OBS capture source and scene set-up</h3>
<ol>
  <li>Create a <em>Window Capture</em> source and set it to capture your Discord call.</li>
  <li>Move and crop it until it’s the size and position you want a single caller’s video to be in the scene— don’t pay any attention to which area of the Discord call it shows, as that’s what this script does for you.</li>
  <li>Duplicate it <strong>(always as reference)</strong> and tweak it for every other caller, across scenes, etc.</li>
  <li>Make sure the order of all Discord items in the <em>Sources</em> panel matches across your scenes, with the order in which you want the participants to show up (see next section).</li>
</ol>

<h3>Using this script</h3>
<ol>
  <li>Open the dropdown menu below, and pick the voice channel you’re in.</strong></li>
  <li>Tick the <em>Full Screen</li> and <em>Show Non-Video Participants</em> checkboxes according to the state of your Discord call (on Discord, <em>Show Non-Video Participants</em> is located under the three dots button at the top right of the call window).</li>
  <li>Open the next dropdown menu, and pick the source that’s capturing the Discord call. <strong>CAUTION: this will irreversibly modify all items belonging to the source you pick!</strong></li>
  <li>Choose every participant you want to appear in your scene. Follow the same order you used with your Discord items in the <em>Sources</em> panel.</li>
</ol>''')

    p = obs.obs_properties_add_list(grp, 'voice_channel', 'Voice channel', obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_INT)
    obs.obs_property_set_modified_callback(p, populate_participants)
    obs.obs_property_set_long_description(p, '<p>Discord server and voice/video channel where the call is happening.</p>')
    while not client.is_ready():
        time.sleep(0.1)
    for label, cid in channels:
        obs.obs_property_list_add_int(p, label, cid)

    p = obs.obs_properties_add_bool(grp, 'full_screen', 'Full-screen')
    obs.obs_property_set_long_description(p, '<p>Whether the Discord call window is in <em>Full Screen</em> mode</p>')
    p = obs.obs_properties_add_bool(grp, 'show_nonvideo_participants', 'Show Non-Video Participants')
    obs.obs_property_set_long_description(p, '<p>Whether the Discord call window has <em>Show Non-video Participants</em> on (under the three dots button at the top right corner)</p>')

    p = obs.obs_properties_add_list(grp, 'discord_source', 'Discord source', obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_property_set_long_description(p, '<p>Source that is capturing the Discord call. <strong>CAUTION: this will irreversibly modify all items belonging to the source you pick!</strong></p>')
    obs.obs_property_list_add_string(p, '(none)', None)
    sources = obs.obs_enum_sources()
    labels = {}
    for src in sources:
        n = obs.obs_source_get_name(src)
        labels[n] = n + ' (' + obs.obs_source_get_display_name(obs.obs_source_get_id(src)) + ')'
    obs.source_list_release(sources)
    for n in sorted(labels, key=lambda x: x.lower()):
        obs.obs_property_list_add_string(p, labels[n], n)

    obs.obs_properties_add_group(props, 'general', 'General', obs.OBS_GROUP_NORMAL, grp)

    grp = obs.obs_properties_create()
    p = obs.obs_properties_add_button(grp, 'refresh_names', 'Refresh names', populate_participants)
    obs.obs_property_set_long_description(p, '<p>Rebuild the participant lists below. Useful when there have been nickname changes, or someone has joined the server. Don’t worry— it won’t reset each choice, unless a selected participant left the server.</p>')
    for i in range(SLOTS):
        p = obs.obs_properties_add_list(grp, f'participant{i}', None, obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_INT)
        obs.obs_property_set_long_description(p, '<p>Participant to appear at the ' + ordinal(i + 1) + ' capture item from the top of the scene</p>')
    obs.obs_properties_add_group(props, 'participant_layout', 'Participant layout', obs.OBS_GROUP_NORMAL, grp)

    populate_participants(props)

    return props


def script_tick(seconds): # OBS script interface.

    if not client:
        return

    # NOTE: These are 0 when the source isn’t visible at all in the current scene. Not that it matters, but I was just weirded out by it until I got it.
    source_width = obs.obs_source_get_width(discord_source)
    source_height = obs.obs_source_get_height(discord_source)

    margin_top = MARGIN_TOP
    if not full_screen:
        margin_top = margin_top + TITLE_BAR

    # Get Discord call layout distribution and caller size.
    people = [x for x in client.video] # Mutability and shiz.
    if show_nonvideo_participants:
        people += client.audio
    count = len(people)
    if count == 1 and (not client.audio or not client.video and show_nonvideo_participants):
        count = 2 # Discord adds a call to action that occupies the same space as a second caller.
    rows = None
    cols = None
    width = 0
    height = None
    offsetx = 0
    offsety = 0
    offset_last = None
    if source_width and source_height:
        totalw = source_width - MARGIN_SIDES * 2
        totalh = source_height - margin_top - MARGIN_BTM
        if totalw > 0 and totalh > 0:
            wide = None
            # Discord packs the callers in as many columns as possible, unless their videos appear bigger with fewer columns.
            for c in reversed(range(1, count+1)):
                r = math.ceil(count / c)
                w = (totalw - CALLER_SPACING * (c - 1)) / c
                h = (totalh - CALLER_SPACING * (r - 1)) / r
                wi = w / h > CALLER_ASPECT
                if wi:
                    w = h * CALLER_ASPECT
                if w > width:
                    rows = r
                    cols = c
                    width = w
                    height = h
                    wide = wi
            if rows:
                # If the window is wider or taller than the callers fit in, Discord will center them as a whole.
                inner_width = (width * cols + CALLER_SPACING * (cols - 1))
                if wide: # Wider than needed, therefore center horizontally.
                    offsetx = (totalw - inner_width) / 2
                else: # Taller than needed, therefore center vertically.
                    height = width / CALLER_ASPECT # We compared using widths only before, so height needs to be adjusted.
                    offsety = (totalh - (height * rows + CALLER_SPACING * (rows - 1))) / 2

                # If last row contains fewer callers than columns, Discord will center it.
                offset_last = count % cols
                if offset_last > 0:
                    offset_last = (inner_width - (width * offset_last + CALLER_SPACING * (offset_last - 1))) / 2

    # Apply necessary changes to relevant scene items.
    scene_sources = obs.obs_frontend_get_scenes()
    for scene_src in scene_sources:
        scene = obs.obs_scene_from_source(scene_src) # Shouldn’t be released.
        items = obs.obs_scene_enum_items(scene)
        i = 0
        for item in reversed(items):
            if obs.obs_sceneitem_get_source(item) == discord_source: # Shouldn’t be released.
                visible = True
                try:
                    index = people.index(participants[i])
                except (IndexError, ValueError):
                    visible = False
                i += 1
                obs.obs_sceneitem_set_visible(item, visible)
                if visible:
                    obs.obs_sceneitem_set_bounds_type(item, obs.OBS_BOUNDS_SCALE_OUTER)
                    obs.obs_sceneitem_set_bounds_alignment(item, 0) # obs.OBS_ALIGN_CENTER doesn’t seem to be implemented.
                    if rows:

                        # Get top left corner of this caller.
                        r = math.ceil((index + 1) / cols)
                        c = index % cols + 1
                        x = MARGIN_SIDES + offsetx + (width + CALLER_SPACING) * (c - 1)
                        if r == rows:
                            x = x + offset_last
                        y = margin_top + offsety + (height + CALLER_SPACING) * (r - 1)

                        # Make sure the crop doesn’t overflow the item bounds.
                        bounds = obs.vec2()
                        obs.obs_sceneitem_get_bounds(item, bounds)
                        aspect = bounds.x / bounds.y
                        clipx = 0
                        clipy = 0
                        if aspect > CALLER_ASPECT:
                            clipy = (height - width / aspect) / 2
                        else:
                            clipx = (width - height * aspect) / 2

                        crop = obs.obs_sceneitem_crop()
                        crop.left = math.ceil(x + CALLER_BORDER + clipx)
                        crop.top = math.ceil(y + CALLER_BORDER + clipy)
                        crop.right = source_width - int(x + width - CALLER_BORDER - clipx)
                        crop.bottom = source_height - int(y + height - CALLER_BORDER - clipy)
                        obs.obs_sceneitem_set_crop(item, crop)
        obs.sceneitem_list_release(items)
    obs.source_list_release(scene_sources)


def script_unload(): # OBS script interface.
    client.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(client.close()))
    thread.join()


def populate_participants(props, p=None, settings=None):
    if not client.channel:
        return False
    for i in range(SLOTS):
        p = obs.obs_properties_get(props, f'participant{i}')
        obs.obs_property_list_clear(p)
        obs.obs_property_list_add_int(p, '(none)', -1)
        for nick, name, disc, uid in ((x.nick, x.name, x.discriminator, x.id) for x in sorted(client.channel.guild.members, key=lambda x: x.display_name.lower() + '!') if x != client.user):
            label = (nick or name) + ' ('
            if nick:
                label += name + ' '
            label += f'#{disc})'
            obs.obs_property_list_add_int(p, label, uid)
    return True


def ordinal(n):
    # https://stackoverflow.com/a/20007730/5200147
    return "%d%s" % (n,"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])
