-- penmentor sends this plugin's shortcut when you ask a question; the plugin exports the current page as a PNG
-- (from memory, so unsaved strokes count) to penmentor's cache as page.png, plus "page pages" in page.txt.
-- The cache: ~/.cache/penmentor on Linux, %LOCALAPPDATA%\penmentor\cache on Windows (XDG_CACHE_HOME wins on both).

function initUi()
  app.registerUi({menu = "penmentor: share the current page", callback = "penmentorSharePage", accelerator = "<Control><Alt><Shift>F12"})
end

local windows = package.config:sub(1, 1) == "\\"

local function cacheDir()
  local xdg = os.getenv("XDG_CACHE_HOME")
  if xdg then
    return xdg .. "/penmentor"
  end
  if windows then
    local base = os.getenv("LOCALAPPDATA") or ((os.getenv("USERPROFILE") or "") .. "\\AppData\\Local")
    return base .. "\\penmentor\\cache"
  end
  return (os.getenv("HOME") or "") .. "/.cache/penmentor"
end

local function replace(from, to)  -- os.rename won't overwrite on Windows
  os.remove(to)
  os.rename(from, to)
end

function penmentorSharePage()
  local dir = cacheDir()
  local doc = app.getDocumentStructure()
  app.export({outputFile = dir .. "/page.tmp.png", range = tostring(doc.currentPage), background = "all", pngDpi = 150})
  local f = io.open(dir .. "/page.tmp.txt", "w")
  if f then
    f:write(doc.currentPage, " ", #doc.pages)
    f:close()
    replace(dir .. "/page.tmp.txt", dir .. "/page.txt")
  end
  replace(dir .. "/page.tmp.png", dir .. "/page.png")  -- last: penmentor waits for this file
end
