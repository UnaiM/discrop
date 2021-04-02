import math

import obspython as obs

SLOTS = 20

# Discord call window measurements.
TITLE_BAR = 22
MARGIN_TOP = 64.5 # Half values since they fluctuate.
MARGIN_SIDES = 8.5
MARGIN_BTM = 71.5
CALLER_ASPECT = 16 / 9
CALLER_SPACING = 8
CALLER_BORDER = 3 # Inwards border when caller is talking.


def script_description():
    return '<p style="color: orange"><strong>CAUTION:</strong> picking a Discord source from the menu below will <strong>irreversibly</strong> modify all related items!</p>'


def script_properties():
    props = obs.obs_properties_create()

    grp = obs.obs_properties_create()
    p = obs.obs_properties_add_bool(grp, 'help', 'Help')
    obs.obs_property_set_enabled(p, False)
    obs.obs_property_set_long_description(p, '''<p>This script automatically maps Discord video calls into the scene’s layout.</p>
<h3>Discord instructions</h3>
<ol>
  <li>In the voice channel where the call is happening, go to the bottom-right corner and select <em>Pop Out.</em></li>
  <li>In the top-right corner, ensure you’re in <em>Grid</em> mode (no caller appears big while the rest are small).</li>
  <li>There too, under the three dots button, ensure <em>Show Non-Video Participants</em> is <strong>off.</strong></li>
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
  <li>Open the dropdown menu below, and pick the source that’s capturing the Discord call. <strong>CAUTION: this will irreversibly modify all items belonging to the source you pick!</strong></li>
  <li>Fill the text fields with the Discord server nicknames of everyone that could have their video on during your Discord call, <strong>even if they aren’t online right now.</strong> Follow the same order you used with your Discord items in the <em>Sources</em> panel. You can use slots further down for people who might join the call with video, but shouldn’t appear in OBS.</li>
  <li>Toggle the <em>Has video</em> checkboxes as people drop/rejoin!</li>
</ol>''')

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

    p = obs.obs_properties_add_bool(grp, 'full_screen', 'Full-screen')
    obs.obs_property_set_long_description(p, '<p>Whether the Discord call window is in <em>Full Screen</em> mode</p>')
    obs.obs_properties_add_group(props, 'general', 'General', obs.OBS_GROUP_NORMAL, grp)

    grp = obs.obs_properties_create()
    for i in range(SLOTS):
        p = obs.obs_properties_add_text(grp, f'nickname{i}', 'Nickname', obs.OBS_TEXT_DEFAULT)
        obs.obs_property_set_long_description(p, '<p>Discord server nickname of the participant at the ' + ordinal(i + 1) + ' capture item from the top of the scene</p>')
        p = obs.obs_properties_add_bool(grp, f'has_video{i}', 'Has video')
        obs.obs_property_set_long_description(p, '<p>Whether the above participant is online and with video</p>')
    obs.obs_properties_add_group(props, 'participants', 'Participants', obs.OBS_GROUP_NORMAL, grp)

    return props


def script_update(settings):

    # Get Discord call window size.
    source_name = obs.obs_data_get_string(settings, 'discord_source')
    source = obs.obs_get_source_by_name(source_name)
    # TODO: Why are these 0 when no nickname is filled up?
    source_width = obs.obs_source_get_width(source)
    source_height = obs.obs_source_get_height(source)
    obs.obs_source_release(source)

    # Get caller order differences between Discord and OBS.
    data = {}
    for i in range(SLOTS):
        name = obs.obs_data_get_string(settings, f'nickname{i}').lower()
        if name.rstrip() and obs.obs_data_get_bool(settings, f'has_video{i}'):
            # Discord sorts ‘ ’ before EOF, e.g. ‘foo bar’ > ‘foo’. Python doesn’t, but we can leverage the fact that ‘ ’ goes right before ‘!’.
            data[i] = name + '!'
    order = sorted(data, key=lambda x: data[x])

    margin_top = MARGIN_TOP
    if not obs.obs_data_get_bool(settings, 'full_screen'):
        margin_top = margin_top + TITLE_BAR

    # Get Discord call layout distribution and caller size.
    count = max(2, len(order)) # When there’s only one caller, Discord adds a call to action that occupies the same space as a second caller.
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
            last = None
            for r in range(1, count+1):
                c = math.ceil(count / r)
                # Valid row/column combinations are those where adding a row would remove columns or vice-versa, e.g. you could arrange 4 callers in 2 rows as 3+1, but what’s the point when you can do 2+2.
                if not last or c < last:
                    last = c
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
        j = 0
        for i in reversed(range(len(items))):
            item = items[i]
            source = obs.obs_sceneitem_get_source(item) # Shouldn’t be released.
            if obs.obs_source_get_name(source) == source_name:
                visible = False
                index = None
                for k, v in enumerate(order):
                    if j == v:
                        visible = True
                        index = k
                        break
                j += 1
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


def ordinal(n):
    # https://stackoverflow.com/a/20007730/5200147
    return "%d%s" % (n,"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])