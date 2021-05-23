import asyncio
import math
import os.path
import sys
import time
import threading
import webbrowser

import obspython as obs

script_path_ = os.path.dirname(__file__) # script_path is part of the OBS script interface.
sys.path.append(os.path.join(script_path_, 'lib', 'site-packages'))
import discord

SLOTS = 10 # Seems to be the maximum people allowed.

# Discord call window measurements.
TITLE_BAR = 22
MARGIN_TOP = 64.5 # Half values since they fluctuate.
MARGIN_SIDES = 8.25 # Don’t ask why, but .25 here seems to be even more accurate.
MARGIN_BTM = 71.25 # Don’t ask why, but .25 here seems to be even more accurate.
CALLER_ASPECT = 16 / 9
CALLER_SPACING = 8
CALLER_BORDER = 3 # Inwards border when caller is talking.

client = None
thread = None
settings = obs.obs_data_create()
discord_source = None


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


def script_load(_settings): # OBS script interface.
    global client
    global thread
    global settings
    settings = _settings

    if asyncio.get_event_loop().is_closed():
        asyncio.set_event_loop(asyncio.new_event_loop())

    client = Client()
    with open(os.path.join(script_path_, '.bot_token')) as f: # script_path() is part of the OBS script interface.
        thread = threading.Thread(target=client.run, args=(f.read().rstrip(),))
        thread.start()


def script_update(_settings): # OBS script interface.
    global settings
    settings = _settings

    while not client.is_ready():
        time.sleep(0.1)
    try:
        client.channel = int(obs.obs_data_get_string(settings, 'voice_channel'))
    except ValueError:
        pass


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
  <li>Clicking on <em>Bot invite link</em> will take to a Discord webpage where you can invite your bot to any of your servers with the right permissions, or you can copy the URL and share it with someone who owns another server too.</li>
  <li>Open the dropdown menu below, and pick the voice channel you’re in.</strong></li>
  <li>Tick the <em>Full Screen</li> and <em>Show Non-Video Participants</em> checkboxes according to the state of your Discord call (on Discord, <em>Show Non-Video Participants</em> is located under the three dots button at the top right of the call window).</li>
  <li>Open the next dropdown menu, and pick the source that’s capturing the Discord call. <strong>CAUTION: this will irreversibly modify all items belonging to the source you pick! Moreover, the script knows which items to modify based on their source’s name alone, so please avoid changing your sources’ names to prevent unexpected behaviour.</strong></li>
  <li>If <em>Show Non-Video Participants</em> is off, you can tick <em>Show/hide item right below for audio-only.</em> This requires an item right below each Discord item, which the script will show when the participant has no video, and hide otherwise.</li>
  <li>Pick yourself in the <em>Myself</em> list, so that you appear un-mirrored to the rest of the world while your video is on.</li>
  <li>Choose every participant you want to appear in your scene. Follow the same order you used with your Discord items in the <em>Sources</em> panel.</li>
  <li><strong>If you’re in <em>Studio Mode,</em> click on the gear icon between both views, and make sure <em>Duplicate Scene</em> is OFF!</strong></li>
</ol>''')

    p = obs.obs_properties_add_button(grp, 'bot_invite_link', 'Bot invite link', bot_invite)
    obs.obs_property_set_long_description(p, '<p>Go to a Discord webpage that lets you invite your bot into any of your servers with the right permissions. You can share this URL with the owner of another server so they invite it for you.</p>')

    p = obs.obs_properties_add_list(grp, 'voice_channel', 'Voice channel', obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_property_set_modified_callback(p, populate_participants)
    obs.obs_property_set_long_description(p, '<p>Discord server and voice/video channel where the call is happening.</p>')
    p = obs.obs_properties_add_button(grp, 'refresh_channels', 'Refresh channels', populate_channels)
    obs.obs_property_set_long_description(p, '<p>Rebuild the list of channels above. Useful for when you’ve just invited the bot to a server, or a new channel has been created in one of the servers it’s invited to. Don’t worry— it won’t reset your choice, unless it’s no longer available.</p>')

    p = obs.obs_properties_add_bool(grp, 'full_screen', 'Full-screen')
    obs.obs_property_set_long_description(p, '<p>Whether the Discord call window is in <em>Full Screen</em> mode</p>')
    p = obs.obs_properties_add_bool(grp, 'show_nonvideo_participants', 'Show Non-Video Participants')
    obs.obs_property_set_modified_callback(p, show_nonvideo_participants_callback)
    obs.obs_property_set_long_description(p, '<p>Whether the Discord call window has <em>Show Non-video Participants</em> on (under the three dots button at the top right corner)</p>')

    p = obs.obs_properties_add_list(grp, 'discord_source', 'Discord source', obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_property_set_long_description(p, '<p>Source that is capturing the Discord call. <strong>CAUTION: this will irreversibly modify all items belonging to the source you pick!</strong></p>')
    p = obs.obs_properties_add_button(grp, 'refresh_sources', 'Refresh sources', populate_sources)
    obs.obs_property_set_long_description(p, '<p>Rebuild the list of sources above. Useful for when you’ve made major changes to your scenes. This won’t reset your choice, unless it’s no longer available.</p>')
    p = obs.obs_properties_add_bool(grp, 'item_right_below', 'Show/hide item right below for audio-only')
    obs.obs_property_set_long_description(p, '<p>Requires an item right below each Discord item, which the script will show when the participant has no video, and hide otherwise</p>')

    obs.obs_properties_add_group(props, 'general', 'General', obs.OBS_GROUP_NORMAL, grp)

    grp = obs.obs_properties_create()
    p = obs.obs_properties_add_list(grp, 'myself', 'Myself', obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_property_set_long_description(p, '<p>Participant whose video should be un-mirrored (yourself).</p>')
    p = obs.obs_properties_add_button(grp, 'refresh_names', 'Refresh names', populate_participants)
    obs.obs_property_set_long_description(p, '<p>Rebuild the participant lists. Useful when there have been nickname changes, or someone has joined the server. Don’t worry— it won’t reset each choice, unless a selected participant left the server.</p>')
    for i in range(SLOTS):
        p = obs.obs_properties_add_list(grp, f'participant{i}', None, obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_property_set_long_description(p, '<p>Participant to appear at the ' + ordinal(i + 1) + ' capture item from the top of the scene</p>')
    obs.obs_properties_add_group(props, 'participant_layout', 'Participant layout', obs.OBS_GROUP_NORMAL, grp)

    populate_sources(props)
    while not client.is_ready():
        time.sleep(0.1)
    populate_channels(props)
    populate_participants(props)

    obs.obs_properties_apply_settings(props, settings)
    return props


def script_tick(seconds): # OBS script interface.
    global discord_source

    source_name = obs.obs_data_get_string(settings, 'discord_source')
    if source_name != obs.obs_source_get_name(discord_source):
        obs.obs_source_release(discord_source) # Doesn’t error even if discord_source == None.
        discord_source = obs.obs_get_source_by_name(source_name)

    if not client:
        return

    # NOTE: These are 0 when the source isn’t visible at all in the current scene. Not that it matters, but I was just weirded out by it until I got it.
    source_width = obs.obs_source_get_width(discord_source)
    source_height = obs.obs_source_get_height(discord_source)

    margin_top = MARGIN_TOP
    if not obs.obs_data_get_bool(settings, 'full_screen'):
        margin_top = margin_top + TITLE_BAR

    # Get Discord call layout distribution and caller size.
    people = [x for x in client.video] # Mutability and shiz.
    nonvideo = obs.obs_data_get_bool(settings, 'show_nonvideo_participants')
    if nonvideo:
        people += client.audio
    count = len(people)
    if count == 1 and (not client.audio or not client.video and nonvideo):
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
        next_vis = None
        for item in reversed(items):
            _next_vis = None
            if obs.obs_sceneitem_get_source(item) == discord_source: # Shouldn’t be released.
                uid = int(obs.obs_data_get_string(settings, f'participant{i}') or -1)
                visible = True
                try:
                    index = people.index(uid)
                except (IndexError, ValueError):
                    visible = False
                i += 1
                obs.obs_sceneitem_set_visible(item, visible)
                if visible and rows:
                    crop = obs.obs_sceneitem_crop()
                    obs.obs_sceneitem_get_crop(item, crop)
                    scale = obs.vec2()
                    obs.obs_sceneitem_get_scale(item, scale)
                    bounds = obs.vec2()
                    obs.obs_sceneitem_get_bounds(item, bounds)

                    # If item was set to not use a bounding box policy, calculate it from its other transform properties.
                    if obs.obs_sceneitem_get_bounds_type(item) == obs.OBS_BOUNDS_NONE:
                        obs.vec2_set(bounds, scale.x * (source_width - crop.right - crop.left), scale.y * (source_height - crop.bottom - crop.top))
                        obs.obs_sceneitem_set_bounds(item, bounds)

                    obs.obs_sceneitem_set_bounds_type(item, obs.OBS_BOUNDS_SCALE_OUTER)
                    obs.obs_sceneitem_set_bounds_alignment(item, 0) # obs.OBS_ALIGN_CENTER doesn’t seem to be implemented.

                    # Get top left corner of this caller.
                    r = math.ceil((index + 1) / cols)
                    c = index % cols + 1
                    x = MARGIN_SIDES + offsetx + (width + CALLER_SPACING) * (c - 1)
                    if r == rows:
                        x = x + offset_last
                    y = margin_top + offsety + (height + CALLER_SPACING) * (r - 1)

                    # Make sure the crop doesn’t overflow the item bounds.
                    aspect = bounds.x / bounds.y
                    clipx = 0
                    clipy = 0
                    if aspect > CALLER_ASPECT:
                        clipy = (height - width / aspect) / 2
                    else:
                        clipx = (width - height * aspect) / 2

                    crop.left = math.ceil(x + CALLER_BORDER + clipx)
                    crop.top = math.ceil(y + CALLER_BORDER + clipy)
                    crop.right = source_width - int(x + width - CALLER_BORDER - clipx)
                    crop.bottom = source_height - int(y + height - CALLER_BORDER - clipy)
                    obs.obs_sceneitem_set_crop(item, crop)

                    sx = abs(scale.x)
                    if uid == int(obs.obs_data_get_string(settings, 'myself') or -1) and uid in client.video:
                        sx = -sx
                    sy = scale.y
                    obs.vec2_set(scale, sx, sy)
                    obs.obs_sceneitem_set_scale(item, scale)
                if not nonvideo and obs.obs_data_get_bool(settings, 'item_right_below'):
                    _next_vis = uid in client.audio
            elif next_vis is not None:
                obs.obs_sceneitem_set_visible(item, next_vis)
            next_vis = _next_vis
        obs.sceneitem_list_release(items)
    obs.source_list_release(scene_sources)


def script_unload(): # OBS script interface.
    client.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(client.close()))
    thread.join()


def show_nonvideo_participants_callback(props, p, _settings):
    obs.obs_property_set_enabled(obs.obs_properties_get(props, 'item_right_below'), not obs.obs_data_get_bool(_settings, 'show_nonvideo_participants'))
    return True


def bot_invite(props, p=None, _settings=None):
    while not client.is_ready():
        time.sleep(0.1)
    webbrowser.open_new_tab(discord.utils.oauth_url(client.user.id, discord.Permissions(connect=True)))


def populate_channels(props, p=None, _settings=None):
    p = obs.obs_properties_get(props, 'voice_channel')
    obs.obs_property_list_clear(p)
    for guild in sorted(client.guilds, key=lambda x: x.name.lower()):
        for channel in sorted(guild.channels, key=lambda x: x.position):
            if isinstance(channel, discord.VoiceChannel):
                obs.obs_property_list_add_string(p, guild.name + ' -> ' + channel.name, str(channel.id))
    return True


def populate_sources(props, p=None, _settings=None):
    p = obs.obs_properties_get(props, 'discord_source')
    obs.obs_property_list_clear(p)
    obs.obs_property_list_add_string(p, '(none)', '')
    sources = obs.obs_enum_sources()
    labels = {}
    for src in sources:
        n = obs.obs_source_get_name(src)
        labels[n] = n + ' (' + obs.obs_source_get_display_name(obs.obs_source_get_id(src)) + ')'
    obs.source_list_release(sources)
    for n in sorted(labels, key=lambda x: x.lower()):
        obs.obs_property_list_add_string(p, labels[n], n)
    return True


def populate_participants(props, p=None, _settings=None):
    if not client.channel:
        return False
    values = []
    for nick, name, disc, uid in ((x.nick, x.name, x.discriminator, x.id) for x in sorted(client.channel.guild.members, key=lambda x: x.display_name.lower() + '!') if x != client.user):
        label = (nick or name) + ' ('
        if nick:
            label += name + ' '
        label += f'#{disc})'
        values.append((label, uid))
    for name in ['myself'] + [f'participant{i}' for i in range(SLOTS)]:
        p = obs.obs_properties_get(props, name)
        obs.obs_property_list_clear(p)
        obs.obs_property_list_add_string(p, '(none)', '')
        for label, uid in values:
            obs.obs_property_list_add_string(p, label, str(uid))
    return True


def ordinal(n):
    # https://stackoverflow.com/a/20007730/5200147
    return "%d%s" % (n,"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])
