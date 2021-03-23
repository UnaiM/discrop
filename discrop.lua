local obs = obslua

local SLOTS = 20

-- Discord call window measurements.
local TITLE_BAR = 22
local MARGIN_TOP = 64.5 -- Half values since they fluctuate.
local MARGIN_SIDES = 8.5
local MARGIN_BTM = 71.5
local CALLER_ASPECT = 16 / 9
local CALLER_SPACING = 8
local CALLER_BORDER = 3 -- Inwards border when caller is talking.

function script_description()
  return '<p style="color: orange"><strong>CAUTION:</strong> picking a Discord source from the menu below will <strong>irreversibly</strong> modify all related items!</p>'
end

function script_properties()
  local props = obs.obs_properties_create()

  local grp = obs.obs_properties_create()
  local p = obs.obs_properties_add_bool(grp, 'help', 'Help')
  obs.obs_property_set_enabled(p, false)
  obs.obs_property_set_long_description(p, [[<p>This script automatically maps Discord video calls into the scene’s layout.</p>
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
</ol>]])

  p = obs.obs_properties_add_list(grp, 'discord_source', 'Discord source', obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
  obs.obs_property_set_long_description(p, '<p>Source that is capturing the Discord call. <strong>CAUTION: this will irreversibly modify all items belonging to the source you pick!</strong></p>')
  obs.obs_property_list_add_string(p, '(none)', nil)
  local sources = obs.obs_enum_sources()
  local labels = {}
  local names = {}
  for _,src in pairs(sources) do
    local n = obs.obs_source_get_name(src)
    labels[n] = n..' ('..obs.obs_source_get_display_name(obs.obs_source_get_id(src))..')'
    table.insert(names, n)
  end
  obs.source_list_release(sources)
  table.sort(names, function(a, b)
    return a:lower() < b:lower()
  end)
  for _,n in ipairs(names) do
    obs.obs_property_list_add_string(p, labels[n], n)
  end

  p = obs.obs_properties_add_bool(grp, 'full_screen', 'Full-screen')
  obs.obs_property_set_long_description(p, '<p>Whether the Discord call window is in <em>Full Screen</em> mode</p>')
  obs.obs_properties_add_group(props, 'general', 'General', obs.OBS_GROUP_NORMAL, grp)

  grp = obs.obs_properties_create()
  for i=1, SLOTS do
    p = obs.obs_properties_add_text(grp, 'nickname'..i, 'Nickname', obs.OBS_TEXT_DEFAULT)
    obs.obs_property_set_long_description(p, '<p>Discord server nickname of the participant at the '..ordinal(i)..' capture item from the top of the scene</p>')
    p = obs.obs_properties_add_bool(grp, 'has_video'..i, 'Has video')
    obs.obs_property_set_long_description(p, '<p>Whether the above participant is online and with video</p>')
  end
  obs.obs_properties_add_group(props, 'participants', 'Participants', obs.OBS_GROUP_NORMAL, grp)

  return props
end

function script_update(settings)

  -- Get Discord call window size.
  local source_name = obs.obs_data_get_string(settings, 'discord_source')
  local source = obs.obs_get_source_by_name(source_name)
  -- TODO: Why are these 0 when no nickname is filled up?
  local source_width = obs.obs_source_get_width(source)
  local source_height = obs.obs_source_get_height(source)
  obs.obs_source_release(source)

  -- Get caller order differences between Discord and OBS.
  local data = {}
  for i=1, SLOTS do
    local name = obs.obs_data_get_string(settings, 'nickname'..i):lower()
    if not name:match('^%s*$') then
      if obs.obs_data_get_bool(settings, 'has_video'..i) then
        -- Discord sorts ‘ ’ before EOF, e.g. ‘foo bar’ > ‘foo’. Lua doesn’t, but we can leverage the fact that ‘ ’ goes right before ‘!’.
        table.insert(data, {i, name..'!'})
      end
    end
  end
  table.sort(data, function(a, b)
    return a[2] < b[2]
  end)
  local order = {}
  for _,x in ipairs(data) do
    table.insert(order, x[1])
  end

  local margin_top = MARGIN_TOP
  if not obs.obs_data_get_bool(settings, 'full_screen') then
    margin_top = margin_top + TITLE_BAR
  end

  -- Get Discord call layout distribution and caller size.
  local count = #order
  if count < 2 then
    -- When there’s only one caller, Discord adds a call to action that occupies the same space as a second caller.
    count = 2
  end
  local rows
  local cols
  local width = 0
  local height
  local offsetx = 0
  local offsety = 0
  local offset_last
  if source_width and source_height then
    local totalw = source_width - MARGIN_SIDES * 2
    local totalh = source_height - margin_top - MARGIN_BTM
    if totalw > 0 and totalh > 0 then
      local wide
      local last
      for r=1, count do
        local c = math.ceil(count / r)
        -- Valid row/column combinations are those where adding a row would remove columns or vice-versa, e.g. you could arrange 4 callers in 2 rows as 3+1, but what’s the point when you can do 2+2.
        if not last or c < last then
          last = c
          local w = (totalw - CALLER_SPACING * (c - 1)) / c
          local h = (totalh - CALLER_SPACING * (r - 1)) / r
          local wi = w / h > CALLER_ASPECT
          if wi then
            w = h * CALLER_ASPECT
          end
          if w > width then
            rows = r
            cols = c
            width = w
            height = h
            wide = wi
          end
        end
      end

      -- If the window is wider or taller than the callers fit in, Discord will center them as a whole.
      local inner_width = (width * cols + CALLER_SPACING * (cols - 1))
      if wide then -- Wider than needed, therefore center horizontally.
        offsetx = (totalw - inner_width) / 2
      else -- Taller than needed, therefore center vertically.
        height = width / CALLER_ASPECT -- We compared using widths only before, so height needs to be adjusted.
        offsety = (totalh - (height * rows + CALLER_SPACING * (rows - 1))) / 2
      end

      -- If last row contains fewer callers than columns, Discord will center it.
      offset_last = count % cols
      if offset_last > 0 then
        offset_last = (inner_width - (width * offset_last + CALLER_SPACING * (offset_last - 1))) / 2
      end

    end
  end

  -- Apply necessary changes to relevant scene items.
  local scene_sources = obs.obs_frontend_get_scenes()
  for _,scene_src in pairs(scene_sources) do
    local scene = obs.obs_scene_from_source(scene_src) -- Shouldn’t be released.
    local items = obs.obs_scene_enum_items(scene)
    local j = 0
    for i=#items, 1, -1 do
      local item = items[i]
      local source = obs.obs_sceneitem_get_source(item) -- Shouldn’t be released.
      if obs.obs_source_get_name(source) == source_name then
        j = j + 1
        local visible = false
        local index
        for k,v in ipairs(order) do
          if j == v then
            visible = true
            index = k
            break
          end
        end
        obs.obs_sceneitem_set_visible(item, visible)
        if visible then
          obs.obs_sceneitem_set_bounds_type(item, obs.OBS_BOUNDS_SCALE_OUTER)
          obs.obs_sceneitem_set_bounds_alignment(item, 0) -- obs.OBS_ALIGN_CENTER doesn’t seem to be implemented.
          if rows then

            -- Get top left corner of this caller.
            local r = math.ceil(index / cols)
            local c = (index - 1) % cols + 1
            local x = MARGIN_SIDES + offsetx + (width + CALLER_SPACING) * (c - 1)
            if r == rows then
              x = x + offset_last
            end
            local y = margin_top + offsety + (height + CALLER_SPACING) * (r - 1)

            -- Make sure the crop doesn’t overflow the item bounds.
            local bounds = obs.vec2()
            obs.obs_sceneitem_get_bounds(item, bounds)
            local aspect = bounds.x / bounds.y
            local clipx = 0
            local clipy = 0
            if aspect > CALLER_ASPECT then
              clipy = (height - width / aspect) / 2
            else
              clipx = (width - height * aspect) / 2
            end

            local crop = obs.obs_sceneitem_crop()
            crop.left = math.ceil(x + CALLER_BORDER + clipx)
            crop.top = math.ceil(y + CALLER_BORDER + clipy)
            crop.right = source_width - math.floor(x + width - CALLER_BORDER - clipx)
            crop.bottom = source_height - math.floor(y + height - CALLER_BORDER - clipy)
            obs.obs_sceneitem_set_crop(item, crop)
          end
        end
      end
    end
    obs.sceneitem_list_release(items)
  end
  obs.source_list_release(scene_sources)
end

function ordinal(n)
  if string.sub(n, -2, -2) ~= '1' then
    local last = string.sub(n, -1)
    if last == '1' then
      do return n..'st' end
    elseif last == '2' then
      do return n..'nd' end
    elseif last == '3' then
      do return n..'rd' end
    end
  end
  return n..'th'
end
