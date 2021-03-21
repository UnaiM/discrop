local obs = obslua

local SOURCE_NAME = 'Discord'
local SLOTS = 20

-- Discord call window measurements.
local TITLE_BAR = 22
local MARGIN_TOP = 64.5 -- Half values since they fluctuate.
local MARGIN_SIDES = 8.5
local MARGIN_BTM = 71.5
local CALLER_ASPECT = 16 / 9
local CALLER_SPACING = 8
local CALLER_BORDER = 3 -- Inwards border when caller is talking.

local source_width
local source_height

function script_description()
  return '<p>Levers: <strong>offline – no video – video</strong></p>'
end

function script_properties()
  local props = obs.obs_properties_create()

  local file = io.open(script_path()..'discrop_help.html')
  if file then
    local help = file:read('*a'):gsub('{SOURCE_NAME}', SOURCE_NAME)
    file:close()
    local p = obs.obs_properties_add_bool(props, 'help', 'Hover for help')
    obs.obs_property_set_enabled(p, false)
    obs.obs_property_set_long_description(p, help)
  end
  obs.obs_properties_add_bool(props, 'fullscreen', 'Call window is full-screen')

  for i=1, SLOTS do
    obs.obs_properties_add_text(props, 'name'..i, '', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int_slider(props, 'status'..i, '', 0, 2, 1)
  end

  return props
end

function script_defaults(settings)
  obs.obs_data_set_default_bool(settings, 'fullscreen', true)
  for i=1, SLOTS do
    obs.obs_data_set_default_int(settings, 'status'..i, 2)
  end
end

function script_load(settings)

  -- Get Discord call window size.
  local sources = obs.obs_enum_sources()
  for _,src in ipairs(sources) do
    if obs.obs_source_get_name(src) == SOURCE_NAME then
      source_width = obs.obs_source_get_width(src)
      source_height = obs.obs_source_get_height(src)

      local err
      if not source_width or not source_height then
        err = 'not found or invalid'
      elseif source_width <= 0 or source_height <= 0 then
        err = 'not pointing to any existing/valid window'
      end
      if err then
        error('ERROR: ‘Discord’ source '..err..'!')
        error('Please read the script help and reload it once you’re set up.')
      end
      break
    end
  end
  obs.source_list_release(sources)
end

function script_update(settings)

  -- Get caller order differences between Discord and OBS.
  local data = {}
  for i=1, SLOTS do
    local name = obs.obs_data_get_string(settings, 'name'..i):lower()
    if not name:match('^%s*$') then
      local status = obs.obs_data_get_int(settings, 'status'..i)
      if status ~= 0 then
        -- Discord sorts ‘ ’ before EOF, e.g. ‘foo bar’ > ‘foo’. Lua doesn’t,
        -- but we can leverage the fact that ‘ ’ goes right before ‘!’.
        table.insert(data, {i, name..'!', status})
      end
    end
  end
  table.sort(data, function(a, b)
    if a[3] < b[3] then
      return false
    elseif a[3] > b[3] then
      return true
    end
    return a[2] < b[2]
  end)
  local order = {}
  for _,x in ipairs(data) do
    table.insert(order, x[1])
  end

  local margin_top = MARGIN_TOP
  if not obs.obs_data_get_bool(settings, 'fullscreen') then
    margin_top = margin_top + TITLE_BAR
  end

  -- Get Discord call layout distribution and caller size.
  local count = #order
  if count < 2 then
    -- When there’s only one caller, Discord adds a call to action
    -- that occupies the same space as a second caller.
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
        -- Valid row/column combinations are those where adding a row would
        -- remove columns or vice-versa, e.g. you could arrange 4 callers in
        -- 2 rows as 3+1, but what’s the point when you can do 2+2.
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

      -- If the window is wider or taller than the callers fit in,
      -- Discord will center them as a whole.
      local inner_width = (width * cols + CALLER_SPACING * (cols - 1))
      if wide then -- Wider than needed, therefore center horizontally.
        offsetx = (totalw - inner_width) / 2
      else -- Taller than needed, therefore center vertically.
        -- We compared using widths only before, so height needs to be adjusted.
        height = width / CALLER_ASPECT
        offsety = (totalh - (height * rows + CALLER_SPACING * (rows - 1))) / 2
      end

      -- If last row contains fewer callers than columns, Discord will center it.
      offset_last = count % cols
      if offset_last > 0 then
        offset_last = (inner_width
          - (width * offset_last + CALLER_SPACING * (offset_last - 1))) / 2
      end

    end
  end

  -- Apply necessary changes to relevant scene items.
  local scene_sources = obs.obs_frontend_get_scenes()
  for _,scene_src in ipairs(scene_sources) do
    local scene = obs.obs_scene_from_source(scene_src) -- Shouldn’t be released.
    local items = obs.obs_scene_enum_items(scene)
    local j = 0
    for i=#items, 1, -1 do
      local item = items[i]
      local source = obs.obs_sceneitem_get_source(item) -- Shouldn’t be released.
      if obs.obs_source_get_name(source) == SOURCE_NAME then
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
          -- obs.OBS_ALIGN_CENTER doesn’t seem to be implemented, so we use 0.
          obs.obs_sceneitem_set_bounds_alignment(item, 0)
          if rows then

            -- Get top left corner of this caller.
            local r = math.ceil(index / cols)
            local c = (index - 1) % cols + 1
            local x = MARGIN_SIDES + offsetx + (width + CALLER_SPACING) * (c - 1)
            if r == rows then
              x = x + offset_last
            end
            local y = margin_top + offsety + (height + CALLER_SPACING) * (r - 1)

            local crop = obs.obs_sceneitem_crop()
            crop.left = math.ceil(x + CALLER_BORDER)
            crop.top = math.ceil(y + CALLER_BORDER)
            crop.right = source_width - math.floor(x + width - CALLER_BORDER)
            crop.bottom = source_height - math.floor(y + height - CALLER_BORDER)
            obs.obs_sceneitem_set_crop(item, crop)
          end
        end
      end
    end
    obs.sceneitem_list_release(items)
  end
  obs.source_list_release(scene_sources)
end
