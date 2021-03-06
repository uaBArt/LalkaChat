# Copyright (C) 2016   CzT/Vladislav Ivanov
from modules.interface.controls import KeyListBox, MainMenuToolBar

import modules.interface.functions

try:
    from cefpython3.wx import chromectrl as browser
    HAS_CHROME = True
except ImportError:
    from wx import html2 as browser
    HAS_CHROME = False

from collections import OrderedDict
import threading
import os
import logging
import webbrowser
import wx
from modules.helper.system import MODULE_KEY, translate_key
from modules.helper.parser import return_type
from modules.helper.module import BaseModule
# ToDO: Support customization of borders/spacings

log = logging.getLogger('chat_gui')
INFORMATION_TAG = 'gui_information'
SECTION_GUI_TAG = '__gui'
SKIP_TAGS = [INFORMATION_TAG]
SKIP_TXT_CONTROLS = ['list_input', 'list_input2']
SKIP_BUTTONS = ['list_add', 'list_remove', 'apply_button', 'cancel_button', 'ok_button']
ITEM_SPACING_VERT = 6
ITEM_SPACING_HORZ = 30


def check_duplicate(item, window):
    items = window.GetItems()
    if item in items:
        return True
    return False


def create_categories(loaded_modules):
    cat_dict = OrderedDict()
    for module_name, module_config in loaded_modules.items():
        if 'config' not in module_config:
            continue

        config = module_config.get('config')
        if INFORMATION_TAG in config:
            tag = config[INFORMATION_TAG].get('category', 'undefined')
            if tag not in cat_dict:
                cat_dict[tag] = OrderedDict()
            cat_dict[tag][module_name] = module_config
    return cat_dict


def hide_sizer_items(page_sizer):
    for index, child in enumerate(page_sizer.GetChildren()):
        page_sizer.Hide(index)


class SettingsKeyError(Exception):
    pass


class CategoryKeyError(Exception):
    pass


class ModuleKeyError(Exception):
    pass


class SettingsWindow(wx.Frame):
    main_grid = None
    page_list = []
    selected_cell = None

    def __init__(self, *args, **kwargs):
        self.spacer_size = (0, 10)
        self.main_class = kwargs.pop('main_class')  # type: ChatGui
        self.categories = kwargs.pop('categories')  # type: dict

        wx.Frame.__init__(self, *args, **kwargs)

        self.settings_saved = True
        self.tree_ctrl = None
        self.tree_ctrl_image_dict = {}
        self.content_page = None
        self.sizer_dict = {}
        self.changes = {}
        self.buttons = {}
        self.groups = {
            dict: {
                'function': modules.interface.functions.create_static_box,
                'bind': None
            },
            OrderedDict: {
                'function': modules.interface.functions.create_static_box,
                'bind': None
            },
            'list_dual': {
                'function': modules.interface.functions.create_list,
                'bind': {
                    'add': self.button_clicked,
                    'remove': self.button_clicked,
                    'select': self.select_cell
                }
            },
            'list': {
                'function': modules.interface.functions.create_list,
                'bind': {
                    'add': self.button_clicked,
                    'remove': self.button_clicked,
                    'select': self.select_cell
                }
            },
            'choose_multiple': {
                'function': modules.interface.functions.create_choose,
                'bind': {
                    'change': self.on_listbox_change,
                    'check_change': self.on_checklist_box_change
                }
            },
            'choose_single': {
                'function': modules.interface.functions.create_choose,
                'bind': {
                    'change': self.on_listbox_change,
                    'check_change': self.on_checklist_box_change
                }
            }
        }
        self.controls = {
            type(None): {
                'function': modules.interface.functions.create_button,
                'bind': self.button_clicked
            },
            bool: {
                'function': modules.interface.functions.create_checkbox,
                'bind': self.on_check_change
            },
            str: {
                'function': modules.interface.functions.create_textctrl,
                'bind': self.on_textctrl
            },
            unicode: {
                'function': modules.interface.functions.create_textctrl,
                'bind': self.on_textctrl
            },
            int: {
                'function': modules.interface.functions.create_textctrl,
                'bind': self.on_textctrl
            },
            'spin': {
                'function': modules.interface.functions.create_spin,
                'bind': self.on_spinctrl
            },
            'dropdown': {
                'function': modules.interface.functions.create_dropdown,
                'bind': self.on_dropdown
            },
            'slider': {
                'function': modules.interface.functions.create_slider,
                'bind': self.on_sliderctrl
            },
            'colour_picker': {
                'function': modules.interface.functions.create_colour_picker,
                'bind': self.on_color_picker
            },
            'list': {
                'function': modules.interface.functions.create_list,
                'bind': {
                    'add': self.button_clicked,
                    'remove': self.button_clicked,
                    'select': self.select_cell
                }
            },
            'button': {
                'function': modules.interface.functions.create_button,
                'bind': self.button_clicked
            }
        }
        self.list_map = {}
        self.redraw_map = {}
        self.show_icons = self.main_class.main_config['config']['gui']['show_icons']

        # Setting up the window
        self.SetBackgroundColour('cream')
        self.show_hidden = self.main_class.gui_settings.get('show_hidden')

        # Setting up events
        self.Bind(wx.EVT_CLOSE, self.on_close)

        styles = wx.DEFAULT_FRAME_STYLE
        if wx.STAY_ON_TOP & self.main_class.GetWindowStyle() == wx.STAY_ON_TOP:
            styles = styles | wx.STAY_ON_TOP
        self.SetWindowStyle(styles)

        self.create_layout()
        self.Show(True)

    def on_exit(self, event):
        log.debug(event)
        self.Destroy()

    def on_close(self, event):
        self.on_exit(event)

    def on_listbox_change(self, event):
        item_object = event.EventObject
        selection = item_object.get_key_from_index(item_object.GetSelection())
        description = translate_key(MODULE_KEY.join([selection, 'description']))

        item_key = modules.interface.controls.IDS[event.GetId()].split(MODULE_KEY)
        show_description = self.main_class.loaded_modules[item_key[0]]['gui'][item_key[1]].get('description', False)

        if isinstance(item_object, KeyListBox):
            self.on_change(modules.interface.controls.IDS[event.GetId()], selection, item_type='listbox', section=True)

        if show_description:
            item_id_key = MODULE_KEY.join(item_key[:-1])
            descr_static_text = wx.FindWindowById(
                modules.interface.controls.get_id_from_name(MODULE_KEY.join([item_id_key, 'descr_explain']))
            )
            descr_static_text.SetLabel(description)
            descr_static_text.Wrap(descr_static_text.GetSize()[0])

    def on_checklist_box_change(self, event):
        window = event.EventObject
        item_ids = window.GetChecked()
        items_values = [window.get_key_from_index(item_id) for item_id in item_ids]
        self.on_change(modules.interface.controls.IDS[event.GetId()], items_values, item_type='listbox_check', section=True)

    def on_change(self, key, value, item_type=None, section=False):
        def enable_button():
            for button in self.buttons[MODULE_KEY.join(['settings', 'apply_button'])]:
                button.Enable()

        def disable_button():
            for button in self.buttons[MODULE_KEY.join(['settings', 'apply_button'])]:
                button.Disable()

        def compare_2d_lists(list1, list2):
            return not set(map(tuple, list1)) ^ set(map(tuple, list2))

        def apply_changes():
            self.changes[key] = {'value': value, 'type': item_type}
            enable_button()

        def clear_changes(remote_change=None):
            if key in self.changes:
                self.changes.pop(key)
            if remote_change:
                for change in self.changes.keys():
                    if remote_change in change:
                        self.changes.pop(change)
            if not self.changes:
                disable_button()

        split_keys = key.split(MODULE_KEY)
        module_name = split_keys[0]
        config_section_name = split_keys[1]
        if module_name in self.redraw_map:
            for section, section_config in self.redraw_map[module_name].items():
                if config_section_name in section_config['redraw_trigger']:
                    redraw_key = MODULE_KEY.join(section_config['key'])
                    self.redraw_item(section_config, value)
                    clear_changes(redraw_key)
                    enable_button()

        config = self.main_class.loaded_modules[module_name]['config']
        change_item = config_section_name
        if section:
            if isinstance(value, list):
                if set(config[change_item]) != set(value):
                    apply_changes()
                else:
                    clear_changes()
            else:
                if config[change_item] != return_type(value):
                    apply_changes()
                else:
                    clear_changes()
        elif item_type == 'gridbox':
            main_tuple = config[change_item]

            if compare_2d_lists(value, main_tuple):
                clear_changes()
            else:
                apply_changes()
        else:
            if isinstance(value, bool):
                if config[change_item][split_keys[2]] != value:
                    apply_changes()
                else:
                    clear_changes()
            else:
                if config[change_item][split_keys[2]] != return_type(value):
                    apply_changes()
                else:
                    clear_changes()

    def on_tree_ctrl_changed(self, event):
        self.settings_saved = False
        tree_ctrl = event.EventObject  # type: wx.TreeCtrl
        selection = tree_ctrl.GetFocusedItem()
        selection_text = tree_ctrl.GetItemData(selection).GetData()
        key_list = selection_text.split(MODULE_KEY)

        # Drawing page
        self.fill_page_with_content(self.content_page, key_list)

        event.Skip()

    def on_textctrl(self, event):
        text_ctrl = event.EventObject
        self.on_change(modules.interface.controls.IDS[event.GetId()], text_ctrl.GetValue().encode('utf-8'), item_type='textctrl')
        event.Skip()

    def on_spinctrl(self, event):
        spin_ctrl = event.EventObject
        self.on_change(modules.interface.controls.IDS[event.GetId()], spin_ctrl.GetValue(), item_type='spinctrl')
        event.Skip()

    def on_sliderctrl(self, event):
        ctrl = event.EventObject
        self.on_change(modules.interface.controls.IDS[event.GetId()], ctrl.GetValue(), item_type='sliderctrl')
        event.Skip()

    def on_dropdown(self, event):
        drop_ctrl = event.EventObject
        self.on_change(modules.interface.controls.IDS[event.GetId()], drop_ctrl.GetString(drop_ctrl.GetCurrentSelection()),
                       item_type='dropctrl')
        event.Skip()

    def on_check_change(self, event):
        check_ctrl = event.EventObject
        self.on_change(modules.interface.controls.IDS[event.GetId()], check_ctrl.IsChecked(), item_type='checkbox')
        event.Skip()

    def on_list_operation(self, key, action):
        list_box = wx.FindWindowById(modules.interface.controls.get_id_from_name(MODULE_KEY.join([key, 'list_box'])))
        if action == 'list_add':
            list_input_value = wx.FindWindowById(
                modules.interface.controls.get_id_from_name(MODULE_KEY.join([key, 'list_input']))).GetValue().strip()

            row_count = list_box.GetNumberRows()
            row_values = [list_box.GetCellValue(f_row, 0).lower() for f_row in range(0, row_count)]
            if list_input_value.lower() not in row_values:
                list_box.AppendRows(1)
                list_box.SetCellValue(row_count, 0, list_input_value)

            list_input2_id = modules.interface.controls.get_id_from_name(MODULE_KEY.join([key, 'list_input2']))
            if list_input2_id:
                list_input2_value = wx.FindWindowById(list_input2_id).GetValue().strip()
                row_values = [list_box.GetCellValue(f_row, 1).lower() for f_row in range(0, row_count)]
                if list_input2_value.lower() not in row_values:
                    list_box.SetCellValue(row_count, 1, list_input2_value)

        elif action == 'list_remove':
            top = list_box.GetSelectionBlockTopLeft()
            bot = list_box.GetSelectionBlockBottomRight()
            if top and bot:
                top = top[0][0]
                bot = bot[0][0] + 1
                del_rows = range(top, bot) if top < bot else range(bot, top)
            else:
                del_rows = [self.selected_cell[0]]

            if list_box.GetNumberRows():
                ids_deleted = 0
                for select in del_rows:
                    list_box.DeleteRows(select - ids_deleted)
                    ids_deleted += 1
        rows = list_box.GetNumberRows()
        cols = list_box.GetNumberCols()
        if cols > 1:
            list_box_item = [[list_box.GetCellValue(row, col).strip()
                              for col in range(cols)]
                             for row in range(rows)]
            grid_elements = {}
            for (item, value) in list_box_item:
                grid_elements[item] = value

        else:
            grid_elements = list(set([list_box.GetCellValue(row, 0) for row in range(rows)]))

        max_rows = 7
        if rows <= max_rows:
            list_box.SetMinSize((-1, -1))
            self.content_page.GetSizer().Layout()
        else:
            scroll_size = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
            max_size = self.list_map[key]
            list_box.SetMinSize((max_size[0] + scroll_size, max_size[1]))
            list_box.SetSize((max_size[0] + scroll_size, max_size[1]))
        if rows == max_rows:
            self.list_map[key] = list_box.GetBestSize()
        self.on_change(key, grid_elements, item_type='gridbox')

    def on_color_picker(self, event):
        self.on_change(MODULE_KEY.join(event['key']), event['hex'])

    def create_layout(self):
        self.main_grid = wx.BoxSizer(wx.HORIZONTAL)
        style = wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_TWIST_BUTTONS | wx.TR_NO_LINES
        # style = wx.TR_HAS_BUTTONS | wx.TR_SINGLE | wx.TR_HIDE_ROOT

        image_list = wx.ImageList(16, 16)

        tree_ctrl_id = modules.interface.functions.id_renew('settings.tree', update=True)
        tree_ctrl = wx.TreeCtrl(self, id=tree_ctrl_id, style=style)
        root_key = MODULE_KEY.join(['settings', 'tree', 'root'])
        root_node = tree_ctrl.AddRoot(translate_key(root_key))
        for cat_name, category in self.categories.iteritems():
            item_key = MODULE_KEY.join(['settings', cat_name])
            item_data = wx.TreeItemData()
            item_data.SetData(item_key)

            item_node = tree_ctrl.AppendItem(root_node, translate_key(item_key), data=item_data)
            for module_name, module_settings in category.iteritems():
                if not module_name == cat_name:
                    if module_settings.get('gui', {}).get('icon'):
                        icon = wx.Bitmap(module_settings['gui']['icon'])
                        self.tree_ctrl_image_dict[module_name] = image_list.GetImageCount()
                        image_list.Add(icon)
                    else:
                        self.tree_ctrl_image_dict[module_name] = -1

                    f_item_key = MODULE_KEY.join([item_key, module_name])
                    f_item_data = wx.TreeItemData()
                    f_item_data.SetData(f_item_key)
                    tree_ctrl.AppendItem(item_node, translate_key(module_name),
                                         image=self.tree_ctrl_image_dict[module_name],
                                         data=f_item_data)
        if self.show_icons:
            tree_ctrl.AssignImageList(image_list)
        tree_ctrl.ExpandAll()

        self.tree_ctrl = tree_ctrl
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_ctrl_changed, id=tree_ctrl_id)

        self.main_grid.Add(tree_ctrl, 7, wx.EXPAND | wx.ALL, 7)

        content_page_id = modules.interface.functions.id_renew(MODULE_KEY.join(['settings', 'content']))
        self.content_page = wx.Panel(self, id=content_page_id)
        self.main_grid.Add(self.content_page, 15, wx.EXPAND)

        self.main_grid.Layout()
        self.SetSizer(self.main_grid)
        tree_ctrl.SelectItem(tree_ctrl.GetFirstChild(root_node)[0])

    def fill_page_with_content(self, panel, keys):

        if keys[0] != 'settings':
            raise SettingsKeyError("Key is not for settings GUI")

        if keys[1] not in self.categories:
            raise CategoryKeyError("Key not found in categories")

        category = keys[1]
        module_id = keys[1] if not MODULE_KEY.join(keys[2:]) else MODULE_KEY.join(keys[2:])

        if module_id not in self.categories[category]:
            raise ModuleKeyError("Key not found in modules")

        module_data = self.categories[category][module_id]
        custom_renderer = module_data['custom_renderer']
        module_config = module_data.get('config', {})
        module_gui_config = module_data.get('gui', {})

        if module_id not in self.sizer_dict:
            module_sizer = wx.BoxSizer(wx.VERTICAL)
            if custom_renderer:
                module_data['class'].render(sizer=module_sizer, panel=panel)
            else:
                self.create_page(sizer=module_sizer, panel=panel, config=module_config, gui=module_gui_config,
                                 key=module_id.split(MODULE_KEY))
            hide_sizer_items(module_sizer)
            self.sizer_dict[module_id] = module_sizer

        page_sizer = panel.GetSizer()  # type: wx.Sizer
        if not page_sizer:
            page_sizer = wx.BoxSizer(wx.VERTICAL)
            page_sizer.Add(self.sizer_dict[module_id], 1, wx.EXPAND)
            page_sizer.Show(0)
            panel.SetSizer(page_sizer)
        else:
            hide_sizer_items(page_sizer)
            found = False
            index = 0
            for index, child in enumerate(page_sizer.GetChildren()):
                if self.sizer_dict[module_id] == child.GetSizer():
                    page_sizer.Show(index)
                    found = True
                    break
            if not found:
                page_sizer.Add(self.sizer_dict[module_id], 1, wx.EXPAND)
                page_sizer.Show(index + 1)

        page_sizer.Layout()
        panel.Layout()

    def create_page(self, sizer, panel, config, gui, key):
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page_subitem_sizer = wx.BoxSizer(wx.VERTICAL)
        self.create_page_items(page_subitem_sizer, panel, config, gui, key)
        page_sizer.Add(page_subitem_sizer, 1, wx.EXPAND)
        sizer.Add(page_sizer, 1, wx.EXPAND)
        self.create_page_buttons(sizer=page_sizer, panel=panel)

    def create_page_items(self, page_sizer, panel, config, gui, key):
        page_sc_window = wx.ScrolledWindow(panel, id=modules.interface.functions.id_renew(gui), style=wx.VSCROLL)
        page_sc_window.SetScrollbars(5, 5, 10, 10)
        sizer = wx.BoxSizer(wx.VERTICAL)
        joined_keys = MODULE_KEY.join(key)
        if 'redraw' in gui:
            for redraw_target, redraw_settings in gui['redraw'].items():
                if joined_keys not in self.redraw_map:
                    self.redraw_map[joined_keys] = {}
                self.redraw_map[joined_keys][redraw_target] = {
                    'key': None,
                    'item': None,
                    'redraw_type': None,
                    'redraw_trigger': redraw_settings['redraw_trigger'],
                    'redraw_target': redraw_target,
                    'get_config': redraw_settings['get_config'],
                    'get_gui': redraw_settings['get_gui'],
                    'sizer_parent': sizer,
                    'panel_parent': page_sc_window,
                    'all_settings': redraw_settings
                }
        for section_key, section_items in config.items():
            if section_key in SKIP_TAGS:
                continue

            view = gui.get(section_key, {}).get('view', type(section_items))
            if view in self.groups.keys():
                data = self.groups[view]
                gui_settings = gui.get(section_key, {}).copy()
                item_keys = key + [section_key]
                sizer_item = data['function'](
                    source_class=self, panel=page_sc_window, item=section_key,
                    value=section_items, bind=data['bind'],
                    gui=gui_settings, key=item_keys, from_sb=False)
                if joined_keys in self.redraw_map.keys():
                    if section_key in self.redraw_map[joined_keys]:
                        self.redraw_map[joined_keys][section_key].update({
                            'bind_item': data,
                            'item': sizer_item,
                            'redraw_type': view,
                            'key': item_keys,
                        })

                sizer.Add(sizer_item, 0, wx.EXPAND)

        page_sc_window.SetSizer(sizer)
        page_sizer.Add(page_sc_window, 1, wx.EXPAND)

    def create_page_buttons(self, sizer, panel):
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(
            modules.interface.functions.create_button(
                self, panel=panel, key=['settings', 'ok_button'],
                bind=self.button_clicked, multiple=True)['item'],
            0, wx.ALIGN_RIGHT)
        button_sizer.Add(
            modules.interface.functions.create_button(
                self, panel=panel, key=['settings', 'apply_button'],
                bind=self.button_clicked, enabled=False, multiple=True)['item'],
            0, wx.ALIGN_RIGHT)
        button_sizer.Add(
            modules.interface.functions.create_button(
                self, panel=panel, key=['settings', 'cancel_button'],
                bind=self.button_clicked, multiple=True)['item'],
            0, wx.ALIGN_RIGHT)
        sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

    def redraw_item(self, redraw_keys, redraw_value):
        sizer = redraw_keys['item']
        sizer_parent = redraw_keys['sizer_parent']
        config = redraw_keys['get_config'](redraw_value, keys=redraw_keys)
        config_gui = redraw_keys['get_gui'](redraw_value)
        panel = redraw_keys['panel_parent']
        fnc = redraw_keys['bind_item']['function']
        bind = redraw_keys['bind_item']['bind']
        key = redraw_keys['key']
        static_box = None

        if isinstance(sizer, wx.StaticBoxSizer):
            static_box = sizer.GetStaticBox()

        item_index = 0
        self.detach_all_children(sizer)
        for index, item_sizer in enumerate(sizer_parent.GetChildren()):
            if item_sizer.GetSizer() == sizer:
                item_index = index
                sizer_parent.Detach(index)
        if static_box:
            static_box.Destroy()
        sizer.Destroy()
        new_sizer = fnc(panel=panel, item=redraw_keys['redraw_target'],
                        value=config, bind=bind, gui=config_gui, key=key)
        sizer_parent.Insert(item_index, new_sizer, 0, wx.EXPAND)

        self.redraw_map[key[0]][key[1]]['item'] = new_sizer

        self.main_grid.Layout()

    def detach_all_children(self, sizer):
        if not sizer:
            return
        for index, child in reversed(list(enumerate(sizer.GetChildren()))):
            child_item = child.GetSizer()
            if not child_item:
                continue
            elif child_item.GetChildren():
                self.detach_all_children(child_item)
            sizer.Remove(index)

    def button_clicked(self, event):
        log.debug("[Settings] Button clicked: {0}".format(modules.interface.controls.IDS[event.GetId()]))
        button_id = event.GetId()
        keys = modules.interface.controls.IDS[button_id].split(MODULE_KEY)
        last_key = keys[-1]
        if last_key in ['list_add', 'list_remove']:
            self.on_list_operation(MODULE_KEY.join(keys[:-1]), action=last_key)
        elif last_key in ['ok_button', 'apply_button']:
            if self.save_settings():
                log.debug('Got non-dynamic changes')
                dialog = wx.MessageDialog(self,
                                          message=translate_key(MODULE_KEY.join(['main', 'save', 'non_dynamic'])),
                                          caption="Caption",
                                          style=wx.OK_DEFAULT,
                                          pos=wx.DefaultPosition)
                dialog.ShowModal()
            if last_key == 'ok_button':
                self.on_exit(event)
            self.settings_saved = True
        elif last_key == 'cancel_button':
            self.on_close(event)
        event.Skip()

    def save_settings(self):
        dynamic_check = False
        for module_name in self.main_class.loaded_modules.keys():
            change_list = {}
            for item, change in self.changes.iteritems():
                if module_name == item.split(MODULE_KEY)[0]:
                    change_list[item] = change
            for key in change_list.keys():
                self.changes.pop(key)

            if self.save_module(module_name, change_list):
                dynamic_check = True
        for button in self.buttons[MODULE_KEY.join(['settings', 'apply_button'])]:
            button.Disable()
        return dynamic_check

    def save_module(self, module_name, changed_items):
        non_dynamic_check = False
        if changed_items:
            module_settings = self.main_class.loaded_modules.get(module_name, {})
            non_dynamic = module_settings.get('gui', {}).get('non_dynamic', [])
            module_config = module_settings.get('config')

            for item, change in changed_items.iteritems():
                item_split = item.split(MODULE_KEY)
                section, item_name = item_split[1:] if len(item_split) > 2 else (item_split[1], None)
                for d_item in non_dynamic:
                    if section in d_item:
                        if MODULE_KEY.join([section, '*']) in d_item:
                            non_dynamic_check = True
                            break
                        elif MODULE_KEY.join([section, item_name]) in d_item:
                            non_dynamic_check = True
                            break
                if item_split[-1] in ['list_box']:
                    del item_split[-1]
                if len(item_split) == 2:
                    module_config[section] = change['value']
                else:
                    value = change['value']
                    if item == MODULE_KEY.join(['main', 'gui', 'show_hidden']):
                        self.show_hidden = value
                    module_config[section][item_name] = value
            if 'class' in module_settings:
                module_settings['class'].apply_settings()
        return non_dynamic_check

    def select_cell(self, event):
        self.selected_cell = (event.GetRow(), event.GetCol())
        event.Skip()


class StatusFrame(wx.Panel):
    def __init__(self, parent, **kwargs):
        self.chat_modules = kwargs.get('chat_modules')
        wx.Panel.__init__(self, parent, size=wx.Size(-1, 24))
        self.SetBackgroundColour('cream')

        self.chats = {}
        self.border_sizer = self._create_sizer()

        for chat_name, chat_settings in self.chat_modules.items():
            if chat_name == 'chat':
                continue
            if chat_settings['class'].get_queue('status_frame'):
                for item in chat_settings['class'].get_queue('status_frame'):
                    if item['action'] == 'add':
                        self.set_chat_online(chat_name, item['channel'])

                for item in chat_settings['class'].get_queue('status_frame'):
                    if item['action'] == 'set_online':
                        self.set_online(chat_name, item['channel'])

        self.Fit()
        self.Layout()
        self.Show(True)

    def _create_sizer(self):
        border_sizer = wx.BoxSizer(wx.HORIZONTAL)
        border_sizer.AddSpacer(2)
        item_sizer = wx.FlexGridSizer(0, 0, 10, 10)
        border_sizer.Add(item_sizer, 0, wx.EXPAND)
        border_sizer.AddSpacer(2)
        self.SetSizer(border_sizer)
        return item_sizer

    def _create_item(self, channel, icon, multiple):
        item_sizer = wx.BoxSizer(wx.VERTICAL)
        module_sizer = wx.FlexGridSizer(0, 0, 5, 3)

        bitmap = wx.StaticBitmap(self, wx.ID_ANY,
                                 wx.Bitmap(icon),
                                 size=wx.Size(16, 16))
        module_sizer.Add(bitmap, 0, wx.EXPAND)

        channel_name = '{}: '.format(channel) if multiple else ''
        channel_text = wx.StaticText(self, id=wx.ID_ANY, label=channel_name)
        module_sizer.Add(channel_text, 0, wx.EXPAND)

        label = wx.StaticText(self, id=wx.ID_ANY, label='N/A')
        module_sizer.Add(label, 1, wx.EXPAND)
        module_sizer.AddSpacer(2)

        item_sizer.Add(module_sizer, 0, wx.EXPAND)

        status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        status_item = wx.Panel(self, size=wx.Size(-1, 5))
        status_item.SetBackgroundColour('gray')

        status_sizer.Add(status_item, 1, wx.EXPAND)

        item_sizer.AddSpacer(3)
        item_sizer.Add(status_sizer, 1, wx.EXPAND)
        item_sizer.AddSpacer(2)

        self.border_sizer.Add(item_sizer, 0, wx.EXPAND)
        return {'item': item_sizer, 'label': label,
                'status': status_item, 'name': channel_text, 'channel': channel}

    def set_online(self, module_name, channel):
        if module_name in self.chats:
            if channel.lower() in self.chats[module_name]:
                self.chats[module_name][channel.lower()]['status'].SetBackgroundColour(wx.Colour(0, 128, 0))
        self.Layout()
        self.Refresh()

    def set_chat_online(self, module_name, channel):
        if module_name not in self.chats:
            self.chats[module_name] = {}
        if channel.lower() not in self.chats[module_name]:
            config = self.chat_modules.get(module_name)['class'].conf_params()
            icon = config['gui']['icon']
            multiple = config['config']['config']['show_channel_names']
            self.chats[module_name][channel.lower()] = self._create_item(channel, icon, multiple)
        self.Layout()
        self.Refresh()

    def set_chat_offline(self, module_name, channel):
        channel = channel.lower()
        if module_name not in self.chats:
            return
        if channel not in self.chats[module_name]:
            return

        chat = self.chats[module_name][channel]
        self.border_sizer.Detach(chat['item'])
        chat['item'].Clear(True)
        del self.chats[module_name][channel]
        self.Layout()
        self.Refresh()

    def set_offline(self, module_name, channel):
        if module_name in self.chats:
            if channel in self.chats[module_name]:
                self.chats[module_name][channel.lower()]['status'].SetBackgroundColour('red')
        self.Refresh()

    def refresh_labels(self, module_name):
        if module_name not in self.chats:
            return
        show_names = self.chat_modules[module_name]['config']['config']['show_channel_names']
        for name, settings in self.chats[module_name].items():
            channel = '{}: '.format(settings['channel']) if show_names else ''
            settings['name'].SetLabel(channel)
        self.Layout()
        self.Refresh()

    def set_viewers(self, module_name, channel, viewers):
        if not viewers:
            return
        if isinstance(viewers, int):
            viewers = str(viewers)
        if len(viewers) >= 5:
            viewers = '{0}k'.format(viewers[:-3])
        if module_name in self.chats:
            if channel.lower() in self.chats[module_name]:
                self.chats[module_name][channel.lower()]['label'].SetLabel(str(viewers))
        self.Layout()


class ChatGui(wx.Frame):
    def __init__(self, parent, title, url, **kwargs):
        # Setting the settings
        self.main_config = kwargs.get('main_config')
        self.gui_settings = kwargs.get('gui_settings')
        self.loaded_modules = kwargs.get('loaded_modules')
        self.queue = kwargs.get('queue')
        self.settings_window = None
        self.status_frame = None
        self.browser = None

        wx.Frame.__init__(self, parent, title=title,
                          size=self.gui_settings.get('size'),
                          pos=self.gui_settings.get('position'))
        # Set window style
        if self.gui_settings.get('transparency') < 100:
            log.info("Application is transparent")
            self.SetTransparent(self.gui_settings['transparency'] * 2.55)
        if self.gui_settings.get('borderless', False):
            log.info("Application is in borderless mode")
            styles = wx.CLIP_CHILDREN | wx.BORDER_NONE | wx.FRAME_SHAPED
        else:
            styles = wx.DEFAULT_FRAME_STYLE
        if self.gui_settings.get('on_top', False):
            log.info("Application is on top")
            styles = styles | wx.STAY_ON_TOP
        self.SetFocus()
        self.SetWindowStyle(styles)

        # Creating categories for gui
        log.debug("Sorting modules to categories")
        self.sorted_categories = create_categories(self.loaded_modules)

        # Creating main gui window
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.toolbar = MainMenuToolBar(self, main_class=self)

        vbox.Add(self.toolbar, 0, wx.EXPAND)
        if self.main_config['config']['gui']['show_counters']:
            self.status_frame = StatusFrame(self, chat_modules=self.sorted_categories['chat'])
            vbox.Add(self.status_frame, 0, wx.EXPAND)
        if self.gui_settings['show_browser']:
            if HAS_CHROME:
                browser_settings = {
                    'application_cache_disabled': True
                }
                self.browser = browser.ChromeCtrl(self, useTimer=False, url=str(url), hasNavBar=False,
                                                  browserSettings=browser_settings)
                if self.main_config['config']['system']['testing_mode']:
                    self.browser2 = browser.ChromeCtrl(self, useTimer=False, url=str(url).replace('/gui', ''),
                                                       hasNavBar=False, browserSettings=browser_settings)
                    vbox.Add(self.browser2, 1, wx.EXPAND)

            else:
                self.browser = browser.WebView.New(parent=self, url=url, name='LalkaWebViewGui')
            vbox.Add(self.browser, 1, wx.EXPAND)

        # Set events
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Show window after creation
        self.SetSizer(vbox)

        if not self.gui_settings['show_browser']:
            self.Layout()
            self.Fit()

        self.Show(True)

        # Show update dialog if new version found
        if self.main_config['update']:
            dialog = wx.MessageDialog(self, message="There is new version, do you want to update?",
                                      caption="New Update Available",
                                      style=wx.YES_NO | wx.YES_DEFAULT,
                                      pos=wx.DefaultPosition)
            response = dialog.ShowModal()
            if response == wx.ID_YES:
                webbrowser.open(self.main_config['update_url'])

    def on_close(self, event):
        log.info("Exiting...")
        log.debug(event)

        # Saving last window size
        config = self.loaded_modules['main']['config']['gui_information']

        size = self.Size
        config['width'] = size[0]
        config['height'] = size[1]
        config['pos_x'] = self.Position.x
        config['pos_y'] = self.Position.y

        for module_name, module_dict in self.loaded_modules.iteritems():
            module_dict['class'].apply_settings(system_exit=True)

        self.Destroy()

    @staticmethod
    def on_right_down(event):
        log.info(event)
        event.Skip()

    def on_settings(self, event):
        log.debug("Got event from {0}".format(modules.interface.controls.IDS[event.GetId()]))
        module_groups = modules.interface.controls.IDS[event.GetId()].split(MODULE_KEY)
        settings_category = MODULE_KEY.join(module_groups[1:-1])
        settings_menu_id = modules.interface.functions.id_renew(settings_category, update=True)
        if self.settings_window:
            self.settings_window.SetFocus()
        else:
            self.settings_window = SettingsWindow(self,
                                                  id=settings_menu_id,
                                                  title=translate_key('settings'),
                                                  size=(700, 400),
                                                  main_class=self,
                                                  categories=self.sorted_categories)

    @staticmethod
    def button_clicked(event):
        button_id = event.GetId()
        keys = modules.interface.controls.IDS[event.GetId()].split(MODULE_KEY)
        log.debug("[ChatGui] Button clicked: {0}, {1}".format(keys, button_id))
        event.Skip()

    def on_toolbar_button(self, event):
        button_id = event.GetId()
        list_keys = modules.interface.controls.IDS[event.GetId()].split(MODULE_KEY)
        log.debug("[ChatGui] Toolbar clicked: {0}, {1}".format(list_keys, button_id))
        if list_keys[0] in self.loaded_modules:
            self.loaded_modules[list_keys[0]]['class'].gui_button_press(self, event, list_keys)
        else:
            for module_name, settings in self.loaded_modules.items():
                if 'class' in settings:
                    settings['class'].gui_button_press(self, event, list_keys)
        event.Skip()


class GuiThread(threading.Thread, BaseModule):
    title = 'LalkaChat'
    url = 'http://localhost'
    port = '8080'

    def __init__(self, **kwargs):
        threading.Thread.__init__(self)
        BaseModule.__init__(self, **kwargs)
        self.daemon = True
        self.gui = None
        self.kwargs = kwargs
        if 'webchat' in self.kwargs.get('loaded_modules'):
            self.port = self.kwargs['loaded_modules']['webchat']['port']

    def run(self):
        if HAS_CHROME:
            browser.Initialize()
        url = ':'.join([self.url, str(self.port)])
        url += '/gui'
        app = wx.App(False)  # Create a new app, don't redirect stdout/stderr to a window.
        self.gui = ChatGui(None, "LalkaChat", url, **self.kwargs)  # A Frame is a top-level window.
        app.MainLoop()
        self.quit()

    def apply_settings(self, **kwargs):
        pass

    def quit(self):
        try:
            self.gui.on_close('event')
        except wx.PyDeadObjectError:
            pass
        os._exit(0)
