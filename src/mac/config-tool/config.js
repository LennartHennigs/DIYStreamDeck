// ─── module-level state ─────────────────────────────────────────────────────

const buttonUndefinedColor = '#333';
const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;
const STRING_DELAY_DEFAULT = 0.05;
const BUTTON_COUNT = 16;
const GRID_COLS = 4;
const ARROW_MAP = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: GRID_COLS, ArrowUp: -GRID_COLS };
const KEY_MAP = { '1':0,'2':1,'3':2,'4':3,'5':4,'6':5,'7':6,'8':7,'9':8,'0':9,
                  'a':10,'b':11,'c':12,'d':13,'e':14,'f':15 };

let rawData = null;
let currentKeyConfig = {};
let applicationsArray = [];
let foldersArray = [];
let urlsArray = [];
let globalsData = null;
let activeButtonIndex = null;
let selectedButton = null;
let currentSection = null;

// DOM refs — assigned in DOMContentLoaded
let sidepane, colorPicker, colorHex, appsDropDown;
let folderField, keysField, applicationField, actionField, stringField;
let toggleColorPicker, toggleColorHex, pressedColorPicker, pressedColorHex;
let aliasRow, autocloseRow, ignoreCheck, aliasCheck, aliasInput, autocloseCheck, aliasInputRow, keypadEl;

// ─── DOMContentLoaded ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  // file modal
  document.getElementById('fileInput').addEventListener('change', handleFileSelected);

  // main UI refs
  sidepane       = document.getElementById('sidepane');
  colorPicker    = document.getElementById('colorPicker');
  colorHex       = document.getElementById('colorHex');
  appsDropDown   = document.getElementById('appsDropDown');
  folderField      = document.getElementById('folderField');
  keysField        = document.getElementById('keysField');
  applicationField = document.getElementById('applicationField');
  actionField      = document.getElementById('actionField');
  stringField      = document.getElementById('stringField');
  toggleColorPicker  = document.getElementById('toggleColorPicker');
  toggleColorHex     = document.getElementById('toggleColorHex');
  pressedColorPicker = document.getElementById('pressedColorPicker');
  pressedColorHex    = document.getElementById('pressedColorHex');

  // section settings refs
  aliasRow      = document.getElementById('aliasOfRow');
  autocloseRow  = document.getElementById('autocloseRow');
  ignoreCheck   = document.getElementById('ignoreDefaultCheck');
  aliasCheck    = document.getElementById('aliasOfCheck');
  aliasInput    = document.getElementById('aliasOfInput');
  autocloseCheck = document.getElementById('autocloseCheck');
  aliasInputRow = document.getElementById('aliasInputRow');
  keypadEl      = document.getElementById('keypad');

  for (let i = 0; i < BUTTON_COUNT; i++) keypadEl.appendChild(createKeypadButton(i));

  // keyboard shortcut
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeSidepanel(); return; }
    if (!rawData) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key in ARROW_MAP) {
      e.preventDefault();
      const current = activeButtonIndex !== null ? parseInt(activeButtonIndex) : -1;
      const next = current === -1 ? 0 : Math.max(0, Math.min(BUTTON_COUNT - 1, current + ARROW_MAP[e.key]));
      getKeyBtn(next)?.click();
      return;
    }

    if (sidepane.classList.contains('open')) return;
    const idx = KEY_MAP[e.key.toLowerCase()];
    if (idx === undefined) return;
    getKeyBtn(idx)?.click();
  });

  // header controls
  document.getElementById('cancelBtn').addEventListener('click', resetApp);
  document.getElementById('rotateSelect').addEventListener('change', function () {
    if (rawData) rawData.settings = rawData.settings || {};
    if (rawData) rawData.settings.rotate = this.value;
  });
  document.getElementById('saveBtn').addEventListener('click', saveJson);

  // dropdown
  appsDropDown.addEventListener('change', loadEntry);

  // color pickers
  colorHex.addEventListener('input', () => syncColorFromHex(colorHex, colorPicker, selectedButton));
  colorPicker.addEventListener('input', () => syncColorFromPicker(colorPicker, colorHex, selectedButton));
  toggleColorHex.addEventListener('input', () => syncColorFromHex(toggleColorHex, toggleColorPicker, null));
  toggleColorPicker.addEventListener('input', () => syncColorFromPicker(toggleColorPicker, toggleColorHex, null));
  pressedColorHex.addEventListener('input', () => syncColorFromHex(pressedColorHex, pressedColorPicker, null));
  pressedColorPicker.addEventListener('input', () => syncColorFromPicker(pressedColorPicker, pressedColorHex, null));
  document.getElementById('clearToggleColor').addEventListener('click', () => clearOptionalColor(toggleColorHex, toggleColorPicker));
  document.getElementById('clearPressedColor').addEventListener('click', () => clearOptionalColor(pressedColorHex, pressedColorPicker));

  // behaviour radio
  document.querySelectorAll('input[name="behaviour"]').forEach(r => {
    r.addEventListener('change', e => showBehaviourField(e.target.value));
  });

  // section settings
  document.getElementById('ignoreDefaultCheck').addEventListener('change', saveSectionSettings);
  document.getElementById('aliasOfCheck').addEventListener('change', onAliasCheckChange);
  document.getElementById('aliasOfInput').addEventListener('change', saveSectionSettings);
  document.getElementById('autocloseCheck').addEventListener('change', saveSectionSettings);

  // apply / clear / reload / close
  document.getElementById('applyBtn').addEventListener('click', applyChanges);
  document.getElementById('clearBtn').addEventListener('click', clearKey);
  document.getElementById('reloadBtn').addEventListener('click', reloadSidePanel);
  document.getElementById('closeBtn').addEventListener('click', closeSidepanel);
  document.getElementById('openFolderBtn').addEventListener('click', navigateToFolder);
  document.getElementById('openAliasBtn').addEventListener('click', navigateToAlias);

  // file modal: create new
  document.getElementById('createNewBtn').addEventListener('click', createNewFile);

  // add entry modal
  document.getElementById('addEntryBtn').addEventListener('click', openAddEntryModal);
  document.getElementById('addEntryCancelBtn').addEventListener('click', closeAddEntryModal);
  document.getElementById('addEntryConfirmBtn').addEventListener('click', confirmAddEntry);
  document.getElementById('addEntryName').addEventListener('keydown', e => {
    if (e.key === 'Enter') confirmAddEntry();
    if (e.key === 'Escape') closeAddEntryModal();
  });

  // entry actions
  document.getElementById('clearAllBtn').addEventListener('click', clearAllKeys);
  document.getElementById('deleteEntryBtn').addEventListener('click', deleteEntry);

  // close sidepanel on canvas click
  document.getElementById('app').addEventListener('click', e => {
    if (!sidepane.classList.contains('open')) return;
    if (sidepane.contains(e.target)) return;
    if (e.target.closest('.key')) return;
    closeSidepanel();
  });
});

// ─── file loading ────────────────────────────────────────────────────────────

function showApp()       { document.getElementById('fileModal').style.display = 'none'; document.getElementById('app').style.display = 'flex'; }
function showFileModal() { document.getElementById('app').style.display = 'none'; document.getElementById('fileModal').style.display = 'flex'; }

function resetApp() {
  rawData = null;
  currentKeyConfig = {};
  applicationsArray = [];
  foldersArray = [];
  urlsArray = [];
  globalsData = null;
  activeButtonIndex = null;
  selectedButton = null;
  currentSection = null;
  closeSidepanel();
  showFileModal();
  document.getElementById('fileInput').value = '';
  document.getElementById('fileError').textContent = '';
}

function createNewFile() {
  const skeleton = {
    settings: {},
    applications: { _default: {}, _otherwise: {} }
  };
  rawData = skeleton;
  initUI(skeleton);
  showApp();
}

function handleFileSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function (ev) {
    try {
      const data = JSON.parse(ev.target.result);
      rawData = data;
      initUI(data);
      showApp();
    } catch (err) {
      document.getElementById('fileError').textContent = 'Invalid JSON: ' + err.message;
    }
  };
  reader.readAsText(file);
}

function initUI(data) {
  const rotate = (data.settings || {}).rotate || '';
  document.getElementById('rotateSelect').value = rotate;

  appsDropDown.innerHTML = '';
  applicationsArray = [];
  foldersArray = [];
  urlsArray = [];
  globalsData = null;

  loadApplications(data);
  loadFolders(data);
  loadUrls(data);
  loadGlobals(data);
  loadCommandList();

  appsDropDown.selectedIndex = 0;
  appsDropDown.dispatchEvent(new Event('change'));
}

// ─── dropdown population ──────────────────────────────────────────────────────

function addOptgroup(label) {
  const g = document.createElement('optgroup');
  g.label = label;
  appsDropDown.appendChild(g);
  return g;
}

function loadApplications(data) {
  if (!data.applications) return;
  applicationsArray = Object.entries(data.applications);
  applicationsArray.sort(([a], [b]) => {
    const specialA = a === '_default' ? 0 : a === '_otherwise' ? 1 : 2;
    const specialB = b === '_default' ? 0 : b === '_otherwise' ? 1 : 2;
    if (specialA !== specialB) return specialA - specialB;
    return a.localeCompare(b);
  });

  const apps    = applicationsArray.filter(([, val]) => !val || !val.alias_of);
  const aliases = applicationsArray.filter(([, val]) => val && val.alias_of);

  const gApps = addOptgroup('Applications');
  apps.forEach(([key]) => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.text = key === '_default' ? '_default (merged into all)'
             : key === '_otherwise' ? '_otherwise (fallback)'
             : key;
    gApps.appendChild(opt);
  });

  if (aliases.length) {
    const gAliases = addOptgroup('Aliases');
    aliases.forEach(([key]) => {
      const opt = document.createElement('option');
      opt.value = key;
      opt.text = key;
      opt.style.fontStyle = 'italic';
      gAliases.appendChild(opt);
    });
  }
}

function loadFolders(data) {
  if (!data.folders) return;
  foldersArray = Object.entries(data.folders);
  foldersArray.sort(([a], [b]) => a.localeCompare(b));
  const g = addOptgroup('Folders');
  foldersArray.forEach(([key]) => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.text = key;
    g.appendChild(opt);
  });
}

function loadUrls(data) {
  if (!data.urls) return;
  urlsArray = Object.entries(data.urls);
  urlsArray.sort(([a], [b]) => a.localeCompare(b));
  const g = addOptgroup('URLs');
  urlsArray.forEach(([key]) => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.text = key;
    g.appendChild(opt);
  });
}

function loadGlobals(data) {
  if (!data.global) return;
  globalsData = data.global;
  const g = addOptgroup('Global');
  const opt = document.createElement('option');
  opt.value = 'global';
  opt.text = 'global';
  g.appendChild(opt);
}

function loadCommandList() {
  fetch('command_list.md')
    .then(r => r.text())
    .then(text => {
      const datalist = document.getElementById('actionList');
      datalist.innerHTML = '';
      text.split('\n').forEach(line => {
        const cmd = line.match(/^-\s+(.+)/);
        if (cmd) {
          const opt = document.createElement('option');
          opt.value = cmd[1].trim();
          datalist.appendChild(opt);
        }
      });
    })
    .catch(() => {});
}

// ─── entry loading ────────────────────────────────────────────────────────────

function loadEntry() {
  if (sidepane.classList.contains('open')) closeSidepanel();
  keypadEl.style.display = 'grid';

  const selectedOption = appsDropDown.options[appsDropDown.selectedIndex];
  const groupLabel = selectedOption.parentNode.label;
  const value = selectedOption.value;

  if (groupLabel === 'Applications' || groupLabel === 'Aliases') {
    currentSection = { type: 'Applications', name: value };
    currentKeyConfig = buildKeyConfig(applicationsArray, value);
  } else if (groupLabel === 'Folders') {
    currentSection = { type: 'Folders', name: value };
    currentKeyConfig = buildKeyConfig(foldersArray, value);
  } else if (groupLabel === 'URLs') {
    currentSection = { type: 'URLs', name: value };
    currentKeyConfig = buildKeyConfig(urlsArray, value);
  } else if (groupLabel === 'Global') {
    currentSection = { type: 'Global', name: 'global' };
    currentKeyConfig = globalsData || {};
  }

  updateSectionSettingsBar();
  colorizeKeypad();
}

function buildKeyConfig(dataArray, selectedValue) {
  const entry = dataArray.find(([k]) => k === selectedValue);
  if (!entry) return {};
  const result = {};
  Object.entries(entry[1]).forEach(([k, v]) => {
    if (!isNaN(parseInt(k))) result[k] = v;
  });
  return result;
}

// ─── section settings bar ────────────────────────────────────────────────────

function updateSectionSettingsBar() {
  if (!currentSection) return;
  const type = currentSection.type;

  const isUnderscored = currentSection.name.startsWith('_');
  const isAliasTarget = applicationsArray.some(([, val]) => val && val.alias_of === currentSection.name);
  aliasRow.style.display    = type === 'Applications' ? '' : 'none';
  aliasRow.style.visibility = (type === 'Applications' && !isUnderscored && !isAliasTarget) ? 'visible' : 'hidden';
  autocloseRow.style.display = type === 'Folders' ? '' : 'none';
  ignoreCheck.closest('label').style.visibility = isUnderscored ? 'hidden' : 'visible';

  const canDelete = type !== 'Global';
  document.getElementById('deleteEntryBtn').style.display = canDelete ? '' : 'none';

  const srcEntry = getSourceEntry();
  if (!srcEntry) { ignoreCheck.checked = false; return; }
  const raw = srcEntry[1];

  ignoreCheck.checked = !!raw.ignore_default;

  if (type === 'Applications') {
    const hasAlias = !!raw.alias_of;
    aliasCheck.checked = hasAlias;
    aliasInput.value = raw.alias_of || '';
    aliasInputRow.style.display = hasAlias ? 'flex' : 'none';
    keypadEl.style.display = hasAlias ? 'none' : 'grid';
  }

  if (type === 'Folders') autocloseCheck.checked = raw.autoclose !== false;
}

function onAliasCheckChange() {
  const checked = aliasCheck.checked;
  aliasInputRow.style.display = checked ? 'flex' : 'none';
  keypadEl.style.display = checked ? 'none' : 'grid';
  if (!checked) aliasInput.value = '';
  saveSectionSettings();
}

function saveSectionSettings() {
  const srcEntry = getSourceEntry();
  if (!srcEntry) return;
  const raw = srcEntry[1];

  raw.ignore_default = ignoreCheck.checked || undefined;
  if (currentSection.type === 'Applications') {
    const v = aliasCheck.checked ? aliasInput.value.trim() : '';
    raw.alias_of = v || undefined;
  }
  if (currentSection.type === 'Folders') {
    raw.autoclose = autocloseCheck.checked;
  }
  Object.keys(raw).forEach(k => raw[k] === undefined && delete raw[k]);
}

function getSourceEntry() {
  if (!currentSection) return null;
  const { type, name } = currentSection;
  if (type === 'Applications') return applicationsArray.find(([k]) => k === name);
  if (type === 'Folders')      return foldersArray.find(([k]) => k === name);
  if (type === 'URLs')         return urlsArray.find(([k]) => k === name);
  return null;
}

// ─── keypad ───────────────────────────────────────────────────────────────────

function getKeyBtn(index) {
  return document.querySelector(`.key[data-index="${index}"]`);
}

function createKeypadButton(index) {
  const btn = document.createElement('button');
  btn.className = 'key';
  btn.setAttribute('data-index', String(index));
  btn.addEventListener('click', showButtonDetails);
  btn.addEventListener('mouseenter', showTooltip);
  btn.addEventListener('mouseleave', hideTooltip);
  return btn;
}

function colorizeKeypad() {
  document.querySelectorAll('.key').forEach(btn => {
    const index = btn.getAttribute('data-index');
    const cfg = currentKeyConfig[index];
    btn.style.backgroundColor = cfg ? (cfg.color || buttonUndefinedColor) : buttonUndefinedColor;
  });
}

// ─── tooltip ──────────────────────────────────────────────────────────────────

let tooltipEl = null;

function showTooltip(e) {
  const btn = e.currentTarget;
  const index = btn.getAttribute('data-index');
  const cfg = currentKeyConfig[index];
  if (!cfg) return;

  const lines = [];
  if (cfg.description) lines.push(`<strong>${cfg.description}</strong>`);
  if (cfg.key_sequence) {
    const seq = Array.isArray(cfg.key_sequence) ? cfg.key_sequence.join(' → ') : cfg.key_sequence;
    lines.push(`Keys: ${seq}`);
  }
  if (cfg.folder)      lines.push(`Folder: ${cfg.folder}`);
  if (cfg.application) lines.push(`App: ${cfg.application}`);
  if (cfg.action)      lines.push(`Action: ${cfg.action}`);
  if (cfg.string)      lines.push(`String: "${cfg.string}"`);
  if (cfg.pressedUntilReleased) lines.push('Hold until released');
  if (cfg.toggleColor) lines.push(`Toggle color: ${cfg.toggleColor}`);
  if (cfg.pressedColor) lines.push(`Pressed color: ${cfg.pressedColor}`);
  if (!lines.length) return;

  if (!tooltipEl) {
    tooltipEl = document.createElement('div');
    tooltipEl.id = 'keyTooltip';
    document.body.appendChild(tooltipEl);
  }
  tooltipEl.innerHTML = lines.join('<br>');
  tooltipEl.style.display = 'block';
  positionTooltip(e);
}

function positionTooltip(e) {
  if (!tooltipEl) return;
  tooltipEl.style.left = (e.clientX + 12) + 'px';
  tooltipEl.style.top  = (e.clientY + 12) + 'px';
}

function hideTooltip() {
  if (tooltipEl) tooltipEl.style.display = 'none';
}

// ─── side panel ───────────────────────────────────────────────────────────────

function showButtonDetails(e) {
  hideTooltip();
  unsetActiveButton();

  const btn = e.currentTarget;
  const index = btn.getAttribute('data-index');
  activeButtonIndex = index;
  selectedButton = btn;
  btn.classList.add('active');

  const cfg = currentKeyConfig[index];
  if (cfg) {
    populateSidePanel(cfg);
  } else {
    resetSidePanel();
  }
  sidepane.classList.add('open');
}

function populateSidePanel(cfg) {
  const color = cfg.color || '#000000';
  colorPicker.value = color;
  colorPicker.style.backgroundColor = color;
  colorHex.value = color;

  document.getElementById('description').value = cfg.description || '';

  resetBehaviourFields();
  if (cfg.folder) {
    setRadio('folder');
    document.getElementById('folderInput').value = cfg.folder;
    showBehaviourField('folder');
  } else if (cfg.application) {
    setRadio('application');
    document.getElementById('applicationInput').value = cfg.application;
    showBehaviourField('application');
  } else if (cfg.action) {
    setRadio('action');
    document.getElementById('actionInput').value = cfg.action;
    showBehaviourField('action');
  } else if (cfg.string) {
    setRadio('string');
    document.getElementById('stringInput').value = cfg.string;
    document.getElementById('stringDelayInput').value = cfg.string_delay !== undefined ? cfg.string_delay : STRING_DELAY_DEFAULT;
    showBehaviourField('string');
  } else if (cfg.key_sequence) {
    setRadio('keys');
    const seq = cfg.key_sequence;
    document.getElementById('keysInput').value = Array.isArray(seq) ? seq.join(', ') : seq;
    document.getElementById('pressedUntilReleasedCheck').checked = !!cfg.pressedUntilReleased;
    showBehaviourField('keys');
  } else {
    setRadio('nothing');
    showBehaviourField('nothing');
  }

  setOptionalColor(cfg.toggleColor, toggleColorHex, toggleColorPicker);
  setOptionalColor(cfg.pressedColor, pressedColorHex, pressedColorPicker);
}

function resetSidePanel() {
  colorPicker.value = '#000000';
  colorPicker.style.backgroundColor = buttonUndefinedColor;
  colorHex.value = '';
  document.getElementById('description').value = '';
  resetBehaviourFields();
  setRadio('nothing');
  showBehaviourField('nothing');
  clearOptionalColor(toggleColorHex, toggleColorPicker);
  clearOptionalColor(pressedColorHex, pressedColorPicker);
}

function resetBehaviourFields() {
  document.getElementById('keysInput').value = '';
  document.getElementById('pressedUntilReleasedCheck').checked = false;
  document.getElementById('folderInput').value = '';
  document.getElementById('applicationInput').value = '';
  document.getElementById('actionInput').value = '';
  document.getElementById('stringInput').value = '';
  document.getElementById('stringDelayInput').value = STRING_DELAY_DEFAULT;
}

function showBehaviourField(value) {
  [keysField, folderField, applicationField, actionField, stringField].forEach(f => {
    f.style.display = 'none';
  });
  const map = { keys: keysField, folder: folderField, application: applicationField, action: actionField, string: stringField };
  if (map[value]) map[value].style.display = 'block';
}

function setRadio(value) {
  const r = document.querySelector(`input[name="behaviour"][value="${value}"]`);
  if (r) r.checked = true;
}

function getRadioValue() {
  const r = document.querySelector('input[name="behaviour"]:checked');
  return r ? r.value : 'keys';
}

// ─── optional color helpers ───────────────────────────────────────────────────

function setOptionalColor(hexValue, hexInput, picker) {
  if (hexValue && HEX_COLOR_RE.test(hexValue)) {
    hexInput.value = hexValue;
    picker.value = hexValue;
  } else {
    hexInput.value = '';
    picker.value = '#000000';
  }
}

function clearOptionalColor(hexInput, picker) {
  hexInput.value = '';
  picker.value = '#000000';
}

function syncColorFromHex(hexInput, picker, button) {
  const v = hexInput.value;
  if (HEX_COLOR_RE.test(v)) {
    picker.value = v;
    picker.style.backgroundColor = v;
    if (button) button.style.backgroundColor = v;
  }
}

function syncColorFromPicker(picker, hexInput, button) {
  hexInput.value = picker.value;
  picker.style.backgroundColor = picker.value;
  if (button) button.style.backgroundColor = picker.value;
}

// ─── apply / clear ────────────────────────────────────────────────────────────

function applyChanges() {
  if (activeButtonIndex === null || !selectedButton) return;

  const behaviour = getRadioValue();
  const color = colorHex.value || colorPicker.value || '#000000';
  const description = document.getElementById('description').value.trim();

  const cfg = { color, description };

  switch (behaviour) {
    case 'nothing':
      break;
    case 'keys': {
      const raw = document.getElementById('keysInput').value.trim();
      const parts = raw.split(',').map(s => s.trim()).filter(Boolean);
      cfg.key_sequence = parts.length === 1 ? parts[0] : parts;
      if (document.getElementById('pressedUntilReleasedCheck').checked) cfg.pressedUntilReleased = true;
      break;
    }
    case 'folder':
      cfg.folder = document.getElementById('folderInput').value.trim();
      break;
    case 'application':
      cfg.application = document.getElementById('applicationInput').value.trim();
      break;
    case 'action':
      cfg.action = document.getElementById('actionInput').value.trim();
      break;
    case 'string':
      cfg.string = document.getElementById('stringInput').value;
      const delay = parseFloat(document.getElementById('stringDelayInput').value);
      if (!isNaN(delay) && delay !== STRING_DELAY_DEFAULT) cfg.string_delay = delay;
      break;
  }

  const tc = toggleColorHex.value.trim();
  if (HEX_COLOR_RE.test(tc)) cfg.toggleColor = tc;

  const pc = pressedColorHex.value.trim();
  if (HEX_COLOR_RE.test(pc)) cfg.pressedColor = pc;

  currentKeyConfig[activeButtonIndex] = cfg;
  writeBackKey(activeButtonIndex, cfg);

  selectedButton.style.backgroundColor = color;
  closeSidepanel();
}

function clearKey() {
  if (activeButtonIndex === null) return;
  delete currentKeyConfig[activeButtonIndex];
  writeBackKey(activeButtonIndex, null);
  if (selectedButton) selectedButton.style.backgroundColor = buttonUndefinedColor;
  resetSidePanel();
  closeSidepanel();
}

function writeBackKey(index, cfg) {
  const entry = getSourceEntry();
  if (!entry) return;
  const raw = entry[1];
  if (cfg === null) {
    delete raw[index];
  } else {
    raw[index] = cfg;
  }
}

// ─── panel open/close ─────────────────────────────────────────────────────────

function unsetActiveButton() {
  if (activeButtonIndex === null) return;
  const btn = getKeyBtn(activeButtonIndex);
  if (btn) { btn.classList.remove('active'); btn.blur(); }
  activeButtonIndex = null;
  selectedButton = null;
}

function closeSidepanel() {
  if (selectedButton && activeButtonIndex !== null) {
    const cfg = currentKeyConfig[activeButtonIndex];
    selectedButton.style.backgroundColor = cfg ? (cfg.color || buttonUndefinedColor) : buttonUndefinedColor;
  }
  unsetActiveButton();
  sidepane.classList.remove('open');
}

function reloadSidePanel() {
  if (activeButtonIndex === null) return;
  const cfg = currentKeyConfig[activeButtonIndex];
  if (cfg) {
    populateSidePanel(cfg);
    if (selectedButton) selectedButton.style.backgroundColor = cfg.color || buttonUndefinedColor;
  } else {
    resetSidePanel();
    if (selectedButton) selectedButton.style.backgroundColor = buttonUndefinedColor;
  }
}

function navigateDropdownTo(value, groups, closePanel) {
  if (!value) return;
  for (let i = 0; i < appsDropDown.options.length; i++) {
    const opt = appsDropDown.options[i];
    if (opt.value === value && groups.includes(opt.parentNode.label)) {
      appsDropDown.selectedIndex = i;
      appsDropDown.dispatchEvent(new Event('change'));
      if (closePanel) closeSidepanel();
      return;
    }
  }
}

function navigateToFolder() {
  navigateDropdownTo(document.getElementById('folderInput').value.trim(), ['Folders'], true);
}

function navigateToAlias() {
  navigateDropdownTo(document.getElementById('aliasOfInput').value.trim(), ['Applications', 'Aliases'], false);
}

// ─── add entry modal ──────────────────────────────────────────────────────────

function openAddEntryModal() {
  document.getElementById('addEntryName').value = '';
  document.getElementById('addEntryError').textContent = '';
  document.getElementById('addEntryModal').style.display = 'flex';
  document.getElementById('addEntryName').focus();
}

function closeAddEntryModal() {
  document.getElementById('addEntryModal').style.display = 'none';
}

function confirmAddEntry() {
  const type = document.getElementById('addEntryType').value;
  const name = document.getElementById('addEntryName').value.trim();
  const errorEl = document.getElementById('addEntryError');
  if (!name) { errorEl.textContent = 'Name is required.'; return; }

  const typeMap = {
    application: { array: applicationsArray, dataKey: 'applications', label: 'Applications' },
    folder:      { array: foldersArray,      dataKey: 'folders',      label: 'Folders' },
    url:         { array: urlsArray,         dataKey: 'urls',         label: 'URLs' },
  };
  const { array, dataKey, label } = typeMap[type];

  if (array.some(([k]) => k === name)) {
    errorEl.textContent = `A ${type === 'url' ? 'URL entry' : type} with that name already exists.`;
    return;
  }

  if (!rawData[dataKey]) rawData[dataKey] = {};
  rawData[dataKey][name] = {};
  array.push([name, rawData[dataKey][name]]);

  const optgroups = Array.from(appsDropDown.querySelectorAll('optgroup'));
  let g = optgroups.find(g => g.label === label);
  if (!g) g = addOptgroup(label);
  const opt = document.createElement('option');
  opt.value = name; opt.text = name;
  g.appendChild(opt);
  appsDropDown.value = name;

  closeAddEntryModal();
  appsDropDown.dispatchEvent(new Event('change'));
}

// ─── entry actions ────────────────────────────────────────────────────────────

function clearAllKeys() {
  if (!currentSection) return;
  const entry = getSourceEntry();
  for (let i = 0; i < BUTTON_COUNT; i++) {
    const key = String(i);
    if (currentKeyConfig[key] !== undefined) {
      delete currentKeyConfig[key];
      if (entry) delete entry[1][key];
    }
  }
  colorizeKeypad();
  if (sidepane.classList.contains('open')) closeSidepanel();
}

function deleteEntry() {
  if (!currentSection) return;
  const { type, name } = currentSection;

  const typeMap = {
    Applications: { array: applicationsArray, dataKey: 'applications' },
    Folders:      { array: foldersArray,      dataKey: 'folders' },
    URLs:         { array: urlsArray,         dataKey: 'urls' },
  };
  const mapping = typeMap[type];
  if (!mapping) return;

  const { array, dataKey } = mapping;
  const idx = array.findIndex(([k]) => k === name);
  if (idx === -1) return;
  array.splice(idx, 1);
  if (rawData[dataKey]) delete rawData[dataKey][name];

  appsDropDown.querySelector(`option[value="${name}"]`)?.remove();

  if (appsDropDown.options.length > 0) {
    appsDropDown.selectedIndex = 0;
    appsDropDown.dispatchEvent(new Event('change'));
  }
}

// ─── save ─────────────────────────────────────────────────────────────────────

function arrayToObj(arr) {
  return Object.fromEntries(arr);
}

function saveJson() {
  if (!rawData) return;

  const apps    = arrayToObj(applicationsArray);
  const folders = arrayToObj(foldersArray);
  const urls    = arrayToObj(urlsArray);

  const out = { settings: rawData.settings || {} };
  if (Object.keys(apps).length)    out.applications = apps;
  if (Object.keys(folders).length) out.folders = folders;
  if (Object.keys(urls).length)    out.urls = urls;
  if (globalsData)                 out.global = globalsData;

  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'key_def.json';
  a.click();
  URL.revokeObjectURL(a.href);
}
