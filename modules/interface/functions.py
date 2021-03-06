import os
import wx
import wx.grid

from modules.helper.system import MODULE_KEY, translate_key, log, PYTHON_FOLDER
from modules.interface.controls import GuiCreationError, CustomColourPickerCtrl, KeyListBox, KeyCheckListBox, KeyChoice, \
    id_renew


def create_textctrl(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')

    item_sizer = wx.BoxSizer(wx.HORIZONTAL)
    item_name = MODULE_KEY.join(key)
    item_box = wx.TextCtrl(panel, id=id_renew(item_name, update=True),
                           value=unicode(value))
    item_box.Bind(wx.EVT_TEXT, bind)
    item_text = wx.StaticText(panel, label=translate_key(item_name))
    item_sizer.Add(item_text, 0, wx.ALIGN_CENTER)
    item_sizer.Add(item_box)
    return {'item': item_sizer, 'text_size': item_text.GetSize()[0], 'text_ctrl': item_text}


def create_button(source_class=None, panel=None, key=None, value=None,
                  bind=None, enabled=True, multiple=None, **kwargs):
    item_sizer = wx.BoxSizer(wx.VERTICAL)
    item_name = MODULE_KEY.join(key)
    button_id = id_renew(item_name, update=True, multiple=multiple)
    c_button = wx.Button(panel, id=button_id, label=translate_key(item_name))
    if not enabled:
        c_button.Disable()

    if item_name in source_class.buttons:
        source_class.buttons[item_name].append(c_button)
    else:
        source_class.buttons[item_name] = [c_button]

    if value:
        c_button.Bind(wx.EVT_BUTTON, value, id=button_id)
    else:
        c_button.Bind(wx.EVT_BUTTON, bind, id=button_id)

    item_sizer.Add(c_button)
    return {'item': item_sizer}


def create_static_box(source_class, panel=None, value=None,
                      gui=None, key=None, show_hidden=None, **kwargs):
    item_value = value

    static_box = wx.StaticBox(panel, label=translate_key(MODULE_KEY.join(key)))
    static_sizer = wx.StaticBoxSizer(static_box, wx.VERTICAL)
    instatic_sizer = wx.BoxSizer(wx.VERTICAL)
    spacer_size = 7

    max_text_size = 0
    text_ctrls = []
    log.debug("Working on {0}".format(MODULE_KEY.join(key)))
    spacer = False
    hidden_items = gui.get('hidden', [])

    for item, value in item_value.items():
        if item in hidden_items and not show_hidden:
            continue
        view = gui.get(item, {}).get('view', type(value))
        if view in source_class.controls.keys():
            bind_fn = source_class.controls[view]
        elif callable(value):
            bind_fn = source_class.controls['button']
        else:
            raise GuiCreationError('Unable to create item, bad value map')
        item_dict = bind_fn['function'](source_class=source_class, panel=static_box, item=item,
                                        value=value, key=key + [item],
                                        bind=bind_fn['bind'], gui=gui.get(item, {}),
                                        from_sb=True)
        if 'text_size' in item_dict:
            if max_text_size < item_dict.get('text_size'):
                max_text_size = item_dict['text_size']

            text_ctrls.append(item_dict['text_ctrl'])
        spacer = True if not spacer else instatic_sizer.AddSpacer(spacer_size)
        instatic_sizer.Add(item_dict['item'], 0, wx.EXPAND, 5)

    if max_text_size:
        for ctrl in text_ctrls:
            ctrl.SetMinSize((max_text_size + 50, ctrl.GetSize()[1]))

    item_count = instatic_sizer.GetItemCount()
    if not item_count:
        static_sizer.Destroy()
        return wx.BoxSizer(wx.VERTICAL)

    static_sizer.Add(instatic_sizer, 0, wx.EXPAND | wx.ALL, 5)
    return static_sizer


def create_spin(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')
    gui = kwargs.get('gui')

    item_sizer = wx.BoxSizer(wx.HORIZONTAL)
    item_name = MODULE_KEY.join(key)
    style = wx.ALIGN_LEFT
    item_box = wx.SpinCtrl(panel, id=id_renew(item_name, update=True), min=gui['min'], max=gui['max'],
                           initial=int(value), style=style)
    item_text = wx.StaticText(panel, label=translate_key(item_name))
    item_box.Bind(wx.EVT_SPINCTRL, bind)
    item_box.Bind(wx.EVT_TEXT, bind)
    item_sizer.Add(item_text, 0, wx.ALIGN_CENTER)
    item_sizer.Add(item_box)
    return {'item': item_sizer, 'text_size': item_text.GetSize()[0], 'text_ctrl': item_text}


def create_list(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')
    gui = kwargs.get('gui')
    from_sb = kwargs.get('from_sb')

    view = gui.get('view')
    is_dual = True if 'dual' in view else False
    style = wx.ALIGN_CENTER_VERTICAL
    border_sizer = wx.BoxSizer(wx.VERTICAL)
    item_sizer = wx.BoxSizer(wx.VERTICAL)

    static_label = MODULE_KEY.join(key)
    static_text = wx.StaticText(panel, label=u'{}:'.format(translate_key(static_label)), style=wx.ALIGN_RIGHT)
    item_sizer.Add(static_text)

    addable_sizer = wx.BoxSizer(wx.HORIZONTAL) if gui.get('addable') else None
    if addable_sizer:
        item_input_key = MODULE_KEY.join(key + ['list_input'])
        addable_sizer.Add(wx.TextCtrl(panel, id=id_renew(item_input_key, update=True)), 0, style)
        if is_dual:
            item_input2_key = MODULE_KEY.join(key + ['list_input2'])
            addable_sizer.Add(wx.TextCtrl(panel, id=id_renew(item_input2_key, update=True)), 0, style)

        item_apply_key = MODULE_KEY.join(key + ['list_add'])
        item_apply_id = id_renew(item_apply_key, update=True)
        item_apply = wx.Button(panel, id=item_apply_id, label=translate_key(item_apply_key))
        addable_sizer.Add(item_apply, 0, style)
        item_apply.Bind(wx.EVT_BUTTON, bind['add'], id=item_apply_id)

        item_remove_key = MODULE_KEY.join(key + ['list_remove'])
        item_remove_id = id_renew(item_remove_key, update=True)
        item_remove = wx.Button(panel, id=item_remove_id, label=translate_key(item_remove_key))
        addable_sizer.Add(item_remove, 0, style)
        item_remove.Bind(wx.EVT_BUTTON, bind['remove'], id=item_remove_id)

        item_sizer.Add(addable_sizer, 0, wx.EXPAND)

    list_box = wx.grid.Grid(panel, id=id_renew(MODULE_KEY.join(key + ['list_box']), update=True))
    list_box.CreateGrid(0, 2 if is_dual else 1)
    list_box.DisableDragColSize()
    list_box.DisableDragRowSize()
    list_box.Bind(wx.grid.EVT_GRID_SELECT_CELL, bind['select'])

    if is_dual:
        for index, (item, item_value) in enumerate(value.items()):
            list_box.AppendRows(1)
            list_box.SetCellValue(index, 0, item)
            list_box.SetCellValue(index, 1, item_value)
    else:
        for index, item in enumerate(value):
            list_box.AppendRows(1)
            list_box.SetCellValue(index, 0, item)

    list_box.SetColLabelSize(1)
    list_box.SetRowLabelSize(1)

    if addable_sizer:
        col_size = addable_sizer.GetMinSize()[0] - 2
        if is_dual:
            first_col_size = list_box.GetColSize(0)
            second_col_size = col_size - first_col_size if first_col_size < col_size else -1
            list_box.SetColSize(1, second_col_size)
        else:
            list_box.SetDefaultColSize(col_size, resizeExistingCols=True)
    else:
        list_box.AutoSize()

    item_sizer.Add(list_box)

    border_sizer.Add(item_sizer, 0, wx.EXPAND | wx.ALL, 5)
    if from_sb:
        return {'item': border_sizer}
    else:
        return border_sizer


def create_colour_picker(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')

    item_sizer = wx.BoxSizer(wx.HORIZONTAL)

    item_name = MODULE_KEY.join(key)
    colour_picker = CustomColourPickerCtrl()
    item_box = colour_picker.create(panel, value=value, event=bind, key=key)

    item_text = wx.StaticText(panel, label=translate_key(item_name))
    item_sizer.Add(item_text, 0, wx.ALIGN_CENTER)
    item_sizer.Add(item_box, 1, wx.EXPAND)
    return {'item': item_sizer, 'text_size': item_text.GetSize()[0], 'text_ctrl': item_text}


def create_choose(**kwargs):
    panel = kwargs.get('panel')
    item_list = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')
    gui = kwargs.get('gui')

    view = gui.get('view')
    is_single = True if 'single' in view else False
    description = gui.get('description', False)
    style = wx.LB_SINGLE if is_single else wx.LB_EXTENDED
    border_sizer = wx.BoxSizer(wx.VERTICAL)
    item_sizer = wx.BoxSizer(wx.VERTICAL)
    list_items = []
    translated_items = []

    static_label = MODULE_KEY.join(key)
    static_text = wx.StaticText(panel, label=u'{}:'.format(translate_key(static_label)), style=wx.ALIGN_RIGHT)
    item_sizer.Add(static_text)

    if gui['check_type'] in ['dir', 'folder', 'files']:
        check_type = gui['check_type']
        keep_extension = gui['file_extension'] if 'file_extension' in gui else False
        for item_in_list in os.listdir(os.path.join(PYTHON_FOLDER, gui['check'])):
            item_path = os.path.join(PYTHON_FOLDER, gui['check'], item_in_list)
            if check_type in ['dir', 'folder'] and os.path.isdir(item_path):
                list_items.append(item_in_list)
            elif check_type == 'files' and os.path.isfile(item_path):
                if not keep_extension:
                    item_in_list = ''.join(os.path.basename(item_path).split('.')[:-1])
                if '__init__' not in item_in_list:
                    if item_in_list not in list_items:
                        list_items.append(item_in_list)
                        translated_items.append(translate_key(item_in_list))

    item_key = MODULE_KEY.join(key + ['list_box'])
    label_text = translate_key(item_key)
    if label_text:
        item_sizer.Add(wx.StaticText(panel, label=label_text, style=wx.ALIGN_RIGHT))
    if is_single:
        item_list_box = KeyListBox(panel, id=id_renew(item_key, update=True), keys=list_items,
                                   choices=translated_items if translated_items else list_items, style=style)
    else:
        item_list_box = KeyCheckListBox(panel, id=id_renew(item_key, update=True), keys=list_items,
                                        choices=translated_items if translated_items else list_items)
        item_list_box.Bind(wx.EVT_CHECKLISTBOX, bind['check_change'])
    item_list_box.Bind(wx.EVT_LISTBOX, bind['change'])

    section_for = item_list if not is_single else {item_list: None}
    if is_single:
        item, value = section_for.items()[0]
        if item not in item_list_box.GetItems():
            if item_list_box.GetItems():
                item_list_box.SetSelection(0)
        else:
            item_list_box.SetSelection(list_items.index(item))
    else:
        check_items = [list_items.index(item) for item in section_for]
        item_list_box.SetChecked(check_items)

    if description:
        adv_sizer = wx.BoxSizer(wx.HORIZONTAL)
        adv_sizer.Add(item_list_box, 0, wx.EXPAND)

        descr_key = MODULE_KEY.join(key + ['descr_explain'])
        descr_text = wx.StaticText(panel, id=id_renew(descr_key, update=True),
                                   label=translate_key(descr_key), style=wx.ST_NO_AUTORESIZE)
        adv_sizer.Add(descr_text, 0, wx.EXPAND | wx.LEFT, 10)

        sizes = descr_text.GetSize()
        sizes[0] -= 20
        descr_text.SetMinSize(sizes)
        descr_text.Fit()
        item_sizer.Add(adv_sizer)
    else:
        item_sizer.Add(item_list_box)
    border_sizer.Add(item_sizer, 0, wx.EXPAND | wx.ALL, 5)
    return border_sizer


def create_dropdown(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')
    gui = kwargs.get('gui')

    item_sizer = wx.BoxSizer(wx.HORIZONTAL)
    choices = gui.get('choices', [])
    item_name = MODULE_KEY.join(key)
    item_text = wx.StaticText(panel, label=translate_key(item_name))
    item_box = KeyChoice(panel, id=id_renew(item_name, update=True),
                         keys=choices, choices=choices)
    item_box.Bind(wx.EVT_CHOICE, bind)
    item_box.SetSelection(choices.index(value))
    item_sizer.Add(item_text, 0, wx.ALIGN_CENTER)
    item_sizer.Add(item_box)
    return {'item': item_sizer, 'text_size': item_text.GetSize()[0], 'text_ctrl': item_text}


def create_slider(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')
    gui = kwargs.get('gui')

    item_sizer = wx.BoxSizer(wx.HORIZONTAL)
    item_name = MODULE_KEY.join(key)
    style = wx.SL_VALUE_LABEL | wx.SL_AUTOTICKS
    item_box = wx.Slider(panel, id=id_renew(item_name, update=True),
                         minValue=gui['min'], maxValue=gui['max'],
                         value=int(value), style=style)
    freq = (gui['max'] - gui['min'])/5
    item_box.SetTickFreq(freq)
    item_box.SetLineSize(4)
    item_box.Bind(wx.EVT_SCROLL, bind)
    item_text = wx.StaticText(panel, label=translate_key(item_name))
    item_sizer.Add(item_text, 0, wx.ALIGN_CENTER)
    item_sizer.Add(item_box, 1, wx.EXPAND)
    return {'item': item_sizer, 'text_size': item_text.GetSize()[0], 'text_ctrl': item_text}


def create_checkbox(**kwargs):
    panel = kwargs.get('panel')
    value = kwargs.get('value')
    key = kwargs.get('key')
    bind = kwargs.get('bind')

    item_sizer = wx.BoxSizer(wx.HORIZONTAL)
    style = wx.ALIGN_CENTER_VERTICAL
    item_key = MODULE_KEY.join(key)
    item_box = wx.CheckBox(panel, id=id_renew(item_key, update=True),
                           label=translate_key(item_key), style=style)
    item_box.SetValue(value)
    item_box.Bind(wx.EVT_CHECKBOX, bind)
    item_sizer.Add(item_box, 0, wx.ALIGN_LEFT)
    return {'item': item_sizer}
