'''
VKeyboard
=========

.. image:: images/vkeyboard.jpg
    :align: right

.. versionadded:: 1.0.8

.. warning::

    This is experimental and subject to change as long as this warning notice is
    present.

VKeyboard is an onscreen keyboard for Kivy. Its operation is intended to be
transparent to the user. Using the widget directly is NOT recommended. Read the
section `Request keyboard`_ first.

Modes
-----

This virtual keyboard has a docked and free mode:

* docked mode (:data:`VKeyboard.docked` = True)
  Generally used when only one person is using the computer, like a tablet or
  personal computer etc.
* free mode: (:data:`VKeyboard.docked` = False)
  Mostly for multitouch surfaces. This mode allows multiple virtual
  keyboards to be used on the screen.

If the docked mode changes, you need to manually call
:meth:`VKeyboard.setup_mode` otherwise the change will have no impact.
During that call, the VKeyboard, implemented on top of a
:class:`~kivy.uix.scatter.Scatter`, will change the
behavior of the scatter and position the keyboard near the target (if target
and docked mode is set).


Layouts
-------

The virtual keyboard is able to load a custom layout. If you create a new
layout and put the JSON in :file:`<kivy_data_dir>/keyboards/<layoutid>.json`,
you can load it by setting :data:`VKeyboard.layout` to your layoutid.

The JSON must be structured like this::

    {
        "title": "Title of your layout",
        "description": "Description of your layout",
        "cols": 15,
        "rows": 5,

        ...
    }

Then, you need to describe the keys in each row, for either a "normal" mode or a
"shift" mode. Keys for this row data must be named `normal_<row>` and
`shift_<row>`. Replace `row` with the row number.
Inside each row, you will describe the key. A key is a 4 element list in the
format::

    [ <text displayed on the keyboard>, <text to put when the key is pressed>,
      <text that represents the keycode>, <size of cols> ]

Here are example keys::

    # f key
    ["f", "f", "f", 1]
    # capslock
    ["\u21B9", "\t", "tab", 1.5]

Finally, complete the JSON::

    {
        ...
        "normal_1": [
            ["`", "`", "`", 1],    ["1", "1", "1", 1],    ["2", "2", "2", 1],
            ["3", "3", "3", 1],    ["4", "4", "4", 1],    ["5", "5", "5", 1],
            ["6", "6", "6", 1],    ["7", "7", "7", 1],    ["8", "8", "8", 1],
            ["9", "9", "9", 1],    ["0", "0", "0", 1],    ["+", "+", "+", 1],
            ["=", "=", "=", 1],    ["\u232b", null, "backspace", 2]
        ],

        "shift_1": [ ... ],
        "normal_2": [ ... ],
        ...
    }


Request Keyboard
----------------

The instantiation of the virtual keyboard is controlled by the configuration.
Check `keyboard_mode` and `keyboard_layout` in the :doc:`api-kivy.config`.

If you intend to create a widget that requires a keyboard, do not use the
virtual keyboard directly, but prefer to use the best method available on
the platform. Check the :meth:`~kivy.core.window.WindowBase.request_keyboard`
method in the :doc:`api-kivy.core.window`.

If you want a specific layout when you request the keyboard, you should write
something like this (from 1.8.0, numeric.json can be in the same directory as
your main.py)::

    keyboard = Window.request_keyboard(
        self._keyboard_close, self)
    if keyboard.widget:
        vkeyboard = self._keyboard.widget
        vkeyboard.layout = 'numeric.json'

'''

__all__ = ('VKeyboard', )

from kivy.core.clipboard import Clipboard
from kivy.vector import Vector
from kivy.config import Config#, ConfigParser
from kivy.uix.scatter import Scatter
from kivy.uix.label import Label
from kivy.properties import ObjectProperty, NumericProperty, StringProperty, \
    BooleanProperty, DictProperty, OptionProperty, ListProperty
from kivy.logger import Logger
from kivy.graphics import Color, BorderImage, Canvas, Line
from kivy.core.image import Image
from kivy.resources import resource_find
from kivy.clock import Clock
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
#from kivy.uix.settings import Settings

from os.path import join, splitext, basename
from os import listdir
from json import loads

from math import exp

import trie

#default_layout_path = join(kivy_data_dir, 'keyboards')
default_layout_path = '.'

class VKeyboard(Scatter):
    '''
    VKeyboard is an onscreen keyboard with multitouch support.
    Its layout is entirely customizable and you can switch between available
    layouts using a button in the bottom right of the widget.

    :Events:
        `on_key_down`: keycode, internal, modifiers
            Fired when the keyboard received a key down event (key press).
        `on_key_up`: keycode, internal, modifiers
            Fired when the keyboard received a key up event (key release).
    '''

    target = ObjectProperty(None, allownone=True)
    '''Target widget associated with the VKeyboard. If set, it will be used to
    send keyboard events. If the VKeyboard mode is "free", it will also be used
    to set the initial position.

    :data:`target` is an :class:`~kivy.properties.ObjectProperty` instance and
    defaults to None.
    '''

    callback = ObjectProperty(None, allownone=True)
    '''Callback can be set to a function that will be called if the VKeyboard is
    closed by the user.

    :data:`target` is an :class:`~kivy.properties.ObjectProperty` instance and
    defaults to None.
    '''

    layout = StringProperty(None)
    '''Layout to use for the VKeyboard. By default, it will be the layout set in
    the configuration, according to the `keyboard_layout` in `[kivy]` section.

    .. versionchanged:: 1.8.0

        If layout is a .json filename, it will loaded and added to the
        available_layouts.

    :data:`layout` is a :class:`~kivy.properties.StringProperty` and defaults
    to None.
    '''

    layout_path = StringProperty(default_layout_path)
    '''Path from which layouts are read.

    :data:`layout` is a :class:`~kivy.properties.StringProperty` and defaults to
    :file:`<kivy_data_dir>/keyboards/`
    '''

    available_layouts = DictProperty({})
    '''Dictionary of all available layouts. Keys are the layout ID, and the
    value is the JSON (translated into a Python object).

    :data:`available_layouts` is a :class:`~kivy.properties.DictProperty` and
    defaults to {}.
    '''

    docked = BooleanProperty(False)
    '''Indicate whether the VKeyboard is docked on the screen or not. If you
    change it, you must manually call :meth:`setup_mode` otherwise it will have
    no impact. If the VKeyboard is created by the Window, the docked mode will
    be automatically set by the configuration, using the `keyboard_mode` token
    in `[kivy]` section.

    :data:`docked` is a :class:`~kivy.properties.BooleanProperty` and defaults
    to False.
    '''

    margin_hint = ListProperty([.05, .06, .05, .06])
    '''Margin hint, used as spacing between keyboard background and keys
    content. The margin is composed of four values, between 0 and 1::

        margin_hint = [top, right, bottom, left]

    The margin hints will be multiplied by width and height, according to their
    position.

    :data:`margin_hint` is a :class:`~kivy.properties.ListProperty` and defaults
    to [.05, .06, .05, .06]
    '''

    key_margin = ListProperty([2, 2, 2, 2])
    '''Key margin, used to create space between keys. The margin is composed of
    four values, in pixels::

        key_margin = [top, right, bottom, left]

    :data:`key_margin` is a :class:`~kivy.properties.ListProperty` and defaults
    to [2, 2, 2, 2]
    '''

    background_color = ListProperty([1, 1, 1, 1])
    '''Background color, in the format (r, g, b, a). If a background is set, the
    color will be combined with the background texture.

    :data:`background_color` is a :class:`~kivy.properties.ListProperty` and
    defaults to [1, 1, 1, 1].
    '''

    background = StringProperty(
        'atlas://./defaulttheme/vkeyboard_background')
    '''Filename of the background image.

    :data:`background` a :class:`~kivy.properties.StringProperty` and defaults to
    :file:`atlas://./defaulttheme/vkeyboard_background`.
    '''

    background_disabled = StringProperty(
        'atlas://./defaulttheme/vkeyboard_disabled_background')
    '''Filename of the background image when vkeyboard is disabled.

    .. versionadded:: 1.8.0

    :data:`background_disabled` is a
    :class:`~kivy.properties.StringProperty` and defaults to
    :file:`atlas://./defaulttheme/vkeyboard__disabled_background`.

    '''

    key_background_color = ListProperty([1, 1, 1, 1])
    '''Key background color, in the format (r, g, b, a). If a key background is
    set, the color will be combined with the key background texture.

    :data:`key_background_color` is a :class:`~kivy.properties.ListProperty`
    and defaults to [1, 1, 1, 1].
    '''

    key_background_normal = StringProperty(
            'atlas://./defaulttheme/vkeyboard_key_normal')
    '''Filename of the key background image for use when no touches are active
    on the widget.

    :data:`key_background_normal` a :class:`~kivy.properties.StringProperty`
    and defaults to
    :file:`atlas://./defaulttheme/vkeyboard_key_normal`.
    '''

    key_disabled_background_normal = StringProperty(
            'atlas://./defaulttheme/vkeyboard_key_normal')
    '''Filename of the key background image for use when no touches are active
    on the widget and vkeyboard is disabled.

    ..versionadded:: 1.8.0

    :data:`key_disabled_background_normal` a
    :class:`~kivy.properties.StringProperty` and defaults to
    :file:`atlas://./defaulttheme/vkeyboard_disabled_key_normal`.

    '''

    key_background_down = StringProperty(
        'atlas://./defaulttheme/vkeyboard_key_down')
    '''Filename of the key background image for use when a touch is active
    on the widget.

    :data:`key_background_down` a :class:`~kivy.properties.StringProperty`
    and defaults to
    :file:`atlas://./defaulttheme/vkeyboard_key_down`.
    '''

    background_border = ListProperty([16, 16, 16, 16])
    '''Background image border. Used for controlling the
    :data:`~kivy.graphics.vertex_instructions.BorderImage.border` property of
    the background.

    :data:`background_border` is a :class:`~kivy.properties.ListProperty` and
    defaults to [16, 16, 16, 16]
    '''

    key_border = ListProperty([8, 8, 8, 8])
    '''Key image border. Used for controlling the
    :data:`~kivy.graphics.vertex_instructions.BorderImage.border` property of
    the key.

    :data:`key_border` is a :class:`~kivy.properties.ListProperty` and
    defaults to [16, 16, 16, 16]
    '''

    # XXX internal variables
    layout_mode = OptionProperty('normal', options=('normal', 'shift', 'capslock'))
    layout_geometry = DictProperty({})
    have_capslock = BooleanProperty(False)
    have_shift = BooleanProperty(False)
    active_keys = DictProperty({})
    font_size = NumericProperty('20dp')
    font_name = StringProperty('./DejaVuSans.ttf')

    __events__ = ('on_key_down', 'on_key_up')

    def __init__(self, **kwargs):
        # XXX move to style.kv
        kwargs.setdefault('size_hint', (None, None))
        kwargs.setdefault('scale_min', .4)
        kwargs.setdefault('scale_max', 1.6)
        kwargs.setdefault('size', (700, 200))
        kwargs.setdefault('docked', False)
        self._trigger_update_layout_mode = Clock.create_trigger(
            self._update_layout_mode)
        self._trigger_load_layouts = Clock.create_trigger(
            self._load_layouts)
        self._trigger_load_layout = Clock.create_trigger(
            self._load_layout)
        self.bind(
            docked=self.setup_mode,
            have_shift=self._trigger_update_layout_mode,
            have_capslock=self._trigger_update_layout_mode,
            layout_path=self._trigger_load_layouts,
            layout=self._trigger_load_layout)
        super(VKeyboard, self).__init__(**kwargs)
        
        # load all the layouts found in the layout_path directory
        self._load_layouts()

        # ensure we have default layouts
        available_layouts = self.available_layouts
        if not available_layouts:
            Logger.critical('VKeyboard: unable to load default layouts')

        # load the default layout from configuration
        if self.layout is None:
            self.layout = Config.get('kivy', 'keyboard_layout')
        else:
            # ensure the current layout is found on the available layout
            self._trigger_load_layout()

        # update layout mode (shift or normal)
        self._trigger_update_layout_mode()

        # create a top layer to draw active keys on
        with self.canvas:
            self.background_key_layer = Canvas()
            self.active_keys_layer = Canvas()

        # prepare layout widget
        self.refresh_keys_hint()
        self.refresh_keys()
        
        self.key_width, self.key_height = self.layout_geometry['LINE_3'][1][1]
        
        layout = self.available_layouts[self.layout]
        self.key_centers = {}
        for r in xrange(1, layout['rows'] + 1):
            row = layout['%s_%d' % (self.layout_mode, r)]
            row_geom = self.layout_geometry['LINE_%d' % r]
            for c, ((x, y), (w, h)) in zip(row, row_geom):
                if c[0].isalpha():
                    self.key_centers[c[0]] = (x + w * 0.5, y + h * 0.5)
        
        self.words = trie.Trie()
        
        with open('0grams') as nograms:
            total = float(nograms.read())
        
        with open('1grams') as unigrams:
            for line in unigrams:
                w, c = line[:-1].split('\t', 1)
                if w.isalpha():
                    self.words[w.lower()] = self.val_dist(tuple(map(self.key_centers.__getitem__, w.lower()))) + (float(c) / total,)
        
        self.labels = []
        
        #self.config = ConfigParser()
        #self.config.read('settings.ini')
        
        self.user_nograms = 1
        self.user_unigrams = {'the':1}
        self.user_bigrams = {}
        self.user_paths = {}
        
        '''import random
        for word in random.sample(self.words.keys(), 10):
            print word
        
        print '======'
        
        count = 0
        ranks = []
            candidates = self.candidate_matches(self.word_sample_n(word, 50))
            if candidates[0][0] != word:
                print word
                count += 1
                for i, e in enumerate(candidates):
                    if e[0] == word:
                        ranks += [i]
            else:
                ranks += [0]
        print len([r for r in ranks if r <= 5]) / float(len(ranks))
        print sum(ranks) / float(len(ranks))
        print 1 - count / 10000.'''
    
    def reload_layout(self):
        layout = self.available_layouts[self.layout]
        self.key_centers = {}
        for r in xrange(1, layout['rows'] + 1):
            row = layout['%s_%d' % (self.layout_mode, r)]
            row_geom = self.layout_geometry['LINE_%d' % r]
            for c, ((x, y), (w, h)) in zip(row, row_geom):
                if c[0].isalpha():
                    self.key_centers[c[0]] = (x + w * 0.5, y + h * 0.5)
    
        words = trie.Trie()
        for word in self.words:
            words[word] = self.val_dist(tuple(map(self.key_centers.__getitem__, word))) + (self.words[word][-1],)
        self.words = words
    
    def get_text_area(self):
        return self.get_parent_window().children[1].children[0]
    
    def val_dist(self, path):
        tot = 0.0
        for i in xrange(1, len(path)):
            tot += ((path[i][0]-path[i-1][0])**2 + (path[i][1]-path[i-1][1])**2)**0.5
        return (path, tot)
    
    def get_ngram_probability(self, word, prev_word):
        nogram = self.user_nograms
        bigram = self.user_bigrams.get((prev_word, word), 0)
        unigram1 = self.user_unigrams.get(prev_word, 0)
        unigram2 = self.user_unigrams.get(word, 0)
        p = 0.4 * (bigram + 1) / (unigram1 + len(self.user_unigrams)) + 0.1 * (unigram2 + 1) / (nogram + len(self.user_unigrams))
        p = p + 0.5 * self.words[word][2]
        return p
        
    def candidate_matches(self, gesture):
        candidates = []
        #g0 = self.get_key_at_pos(*gesture[0])[0][2]
        #g1 = self.get_key_at_pos(*gesture[-1])[0][2]
        gest_length = self.val_dist(gesture)[1]
        prev_word = self.get_previous_word()
        for word in self.words:
            #if word[0] != g0 or word[-1] != g1:
            #    continue
            path = self.words[word]
            if abs(path[0][0][0] - gesture[0][0]) > self.key_width or abs(path[0][0][1] - gesture[0][1]) > self.key_height:
                continue
            if abs(path[0][-1][0] - gesture[-1][0]) > self.key_width or abs(path[0][-1][1] - gesture[-1][1]) > self.key_height:
                continue
            if not 0.8*path[1] <= gest_length <= 1.4*path[1]:
                continue
            p = exp(-self.gesture_distance(gesture, word)/2) * self.get_ngram_probability(word, prev_word)
            candidates.append((word, p))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def candidate_predictions(self, word):
        prev_word = self.get_previous_word()
        candidates = [(w, 0.001**d * self.get_ngram_probability(w, prev_word)) for (w, d) in self.words.search_prediction(word, 2)]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def candidate_corrections(self, word):
        prev_word = self.get_previous_word()
        candidates = [(w, 0.001**d * self.get_ngram_probability(w, prev_word)) for (w, d) in self.words.search_correction(word, 2)]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates
    
    def candidate_guesses(self):
        prev_word = self.get_previous_word()
        candidates = [(w, self.get_ngram_probability(w, prev_word)) for w in self.words]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates
        
    def word_sample_n(self, word, n):
        path = self.words[word][0]
        cum_length = [0.0]
        for i in xrange(1, len(path)):
            cum_length.append(cum_length[-1] + ((path[i][0]-path[i-1][0])**2 + (path[i][1]-path[i-1][1])**2)**0.5)
        import bisect
        points = []
        for k in range(n):
            L = min(k * cum_length[-1] / (n - 1), cum_length[-1])
            i = bisect.bisect_left(cum_length[1:], L)
            if i >= len(path) - 1:
                i -= 1
            p = 0 if cum_length[i+1] == cum_length[i] else (L - cum_length[i]) / (cum_length[i+1] - cum_length[i])
            x, y = path[i][0] + p * (path[i+1][0] - path[i][0]), path[i][1] + p * (path[i+1][1] - path[i][1])
            points.append((x, y))
        return points
    
    def gesture_distance(self, gesture, word):
        n = len(gesture)
        template = self.word_sample_n(word, n)
        return sum(((x1-x2)**2 + (y1-y2)**2)**0.5 for ((x1, y1), (x2, y2)) in zip(gesture, template)) / n

    def on_disabled(self, intance, value):
        self.refresh_keys()

    def _update_layout_mode(self, *l):
        # update mode according to capslock and shift key
        mode = self.have_capslock != self.have_shift
        if not mode:
            mode = 'normal'
        else:
            mode = 'shift' if self.have_shift else 'capslock'
        if mode != self.layout_mode:
            self.layout_mode = mode
            self.refresh(False)

    def _load_layout(self, *largs):
        # ensure new layouts are loaded first
        if self._trigger_load_layouts.is_triggered:
            self._load_layouts()
            self._trigger_load_layouts.cancel()

        value = self.layout
        available_layouts = self.available_layouts

        # it's a filename, try to load it directly
        if self.layout[-5:] == '.json':
            if value not in available_layouts:
                fn = resource_find(self.layout)
                self._load_layout_fn(fn, self.layout)

        if not available_layouts:
            return
        if value not in available_layouts and value != 'qwerty':
            Logger.error(
                'Vkeyboard: <%s> keyboard layout mentioned in '
                'conf file was not found, fallback on qwerty' %
                value)
            self.layout = 'qwerty'
        self.refresh(True)

    def _load_layouts(self, *largs):
        # first load available layouts from json files
        # XXX fix to be able to reload layout when path is changing
        value = self.layout_path
        for fn in listdir(value):
            self._load_layout_fn(join(value, fn),
                    basename(splitext(fn)[0]))

    def _load_layout_fn(self, fn, name):
        available_layouts = self.available_layouts
        if fn[-5:] != '.json':
            return
        with open(fn, 'r') as fd:
            json_content = fd.read()
            layout = loads(json_content)
        available_layouts[name] = layout

    def setup_mode(self, *largs):
        '''Call this method when you want to readjust the keyboard according to
        options: :data:`docked` or not, with attached :data:`target` or not:

        * If :data:`docked` is True, it will call :meth:`setup_mode_dock`
        * If :data:`docked` is False, it will call :meth:`setup_mode_free`

        Feel free to overload these methods to create new
        positioning behavior.
        '''
        if self.docked:
            self.setup_mode_dock()
        else:
            self.setup_mode_free()

    def setup_mode_dock(self, *largs):
        '''Setup the keyboard in docked mode.

        Dock mode will reset the rotation, disable translation, rotation and
        scale. Scale and position will be automatically adjusted to attach the
        keyboard to the bottom of the screen.

        .. note::
            Don't call this method directly, use :meth:`setup_mode` instead.
        '''
        self.do_translation = False
        self.do_rotation = False
        self.do_scale = False
        self.rotation = 0
        win = self.get_parent_window()
        scale = win.width / float(self.width)
        self.scale = scale
        self.pos = 0, 0
        win.bind(on_resize=self._update_dock_mode)

    def _update_dock_mode(self, win, *largs):
        scale = win.width / float(self.width)
        self.scale = scale
        self.pos = 0, 0

    def setup_mode_free(self):
        '''Setup the keyboard in free mode.

        Free mode is designed to let the user control the position and
        orientation of the keyboard. The only real usage is for a multiuser
        environment, but you might found other ways to use it.
        If a :data:`target` is set, it will place the vkeyboard under the
        target.

        .. note::
            Don't call this method directly, use :meth:`setup_mode` instead.
        '''
        self.do_translation = True
        self.do_rotation = True
        self.do_scale = True
        target = self.target
        if not target:
            return

        # NOTE all math will be done in window point of view
        # determine rotation of the target
        a = Vector(1, 0)
        b = Vector(target.to_window(0, 0))
        c = Vector(target.to_window(1, 0)) - b
        self.rotation = -a.angle(c)

        # determine the position of center/top of the keyboard
        dpos = Vector(self.to_window(self.width / 2., self.height))

        # determine the position of center/bottom of the target
        cpos = Vector(target.to_window(target.center_x, target.y))

        # the goal now is to map both point, calculate the diff between them
        diff = dpos - cpos

        # we still have an issue, self.pos represent the bounding box, not the
        # 0,0 coordinate of the scatter. we need to apply also the diff between
        # them (inside and outside coordinate matrix). It's hard to explain, but
        # do a scheme on a paper, wrote all the vector i'm calculating, and
        # you'll understand. :)
        diff2 = Vector(self.x + self.width / 2., self.y + self.height) - \
                Vector(self.to_parent(self.width / 2., self.height))
        diff -= diff2

        # now we have a good "diff", set it as a pos.
        self.pos = -diff

    def refresh(self, force=False):
        '''(internal) Recreate the entire widget and graphics according to the
        selected layout.
        '''
        self.clear_widgets()
        if force:
            self.refresh_keys_hint()
        self.refresh_keys()
        self.refresh_active_keys_layer()

    def refresh_active_keys_layer(self):
        self.active_keys_layer.clear()

        active_keys = self.active_keys
        layout_geometry = self.layout_geometry
        background = resource_find(self.key_background_down)
        texture = Image(background, mipmap=True).texture

        with self.active_keys_layer:
            Color(1, 1, 1)
            for line_nb, index in active_keys.values():
                pos, size = layout_geometry['LINE_%d' % line_nb][index]
                BorderImage(texture=texture, pos=pos, size=size,
                        border=self.key_border)

    def refresh_keys_hint(self):
        layout = self.available_layouts[self.layout]
        layout_cols = layout['cols']
        layout_rows = layout['rows']
        layout_geometry = self.layout_geometry
        mtop, mright, mbottom, mleft = self.margin_hint

        # get relative EFFICIENT surface of the layout without external margins
        el_hint = 1. - mleft - mright
        eh_hint = 1. - mtop - mbottom
        ex_hint = 0 + mleft
        ey_hint = 0 + mbottom

        # get relative unit surface
        uw_hint = (1. / layout_cols) * el_hint
        uh_hint = (1. / layout_rows) * eh_hint
        layout_geometry['U_HINT'] = (uw_hint, uh_hint)

        # calculate individual key RELATIVE surface and pos (without key margin)
        current_y_hint = ey_hint + eh_hint
        for line_nb in range(1, layout_rows + 1):
            current_y_hint -= uh_hint
            # get line_name
            line_name = '%s_%d' % (self.layout_mode, line_nb)
            line_hint = 'LINE_HINT_%d' % line_nb
            layout_geometry[line_hint] = []
            current_x_hint = ex_hint
            # go through the list of keys (tuples of 4)
            for key in layout[line_name]:
                # calculate relative pos, size
                layout_geometry[line_hint].append([
                    (current_x_hint, current_y_hint),
                    (key[3] * uw_hint, uh_hint)])
                current_x_hint += key[3] * uw_hint

        self.layout_geometry = layout_geometry

    def refresh_keys(self):
        layout = self.available_layouts[self.layout]
        layout_rows = layout['rows']
        layout_geometry = self.layout_geometry
        w, h = self.size
        kmtop, kmright, kmbottom, kmleft = self.key_margin
        uw_hint, uh_hint = layout_geometry['U_HINT']

        for line_nb in range(1, layout_rows + 1):
            llg = layout_geometry['LINE_%d' % line_nb] = []
            llg_append = llg.append
            for key in layout_geometry['LINE_HINT_%d' % line_nb]:
                x_hint, y_hint = key[0]
                w_hint, h_hint = key[1]
                kx = x_hint * w
                ky = y_hint * h
                kw = w_hint * w
                kh = h_hint * h

                # now adjust, considering the key margin
                kx = int(kx + kmleft)
                ky = int(ky + kmbottom)
                kw = int(kw - kmleft - kmright)
                kh = int(kh - kmbottom - kmtop)

                pos = (kx, ky)
                size = (kw, kh)
                llg_append((pos, size))

        self.layout_geometry = layout_geometry
        self.draw_keys()

    def draw_keys(self):
        layout = self.available_layouts[self.layout]
        layout_rows = layout['rows']
        layout_geometry = self.layout_geometry
        layout_mode = self.layout_mode

        # draw background
        w, h = self.size

        background = resource_find(self.background)
        texture = Image(background, mipmap=True).texture
        self.background_key_layer.clear()
        with self.background_key_layer:
            Color(*self.background_color)
            BorderImage(texture=texture, size=self.size,
                    border=self.background_border)

        # XXX seperate drawing the keys and the fonts to avoid
        # XXX reloading the texture each time

        # first draw keys without the font
        key_normal = resource_find(self.key_background_normal)
        texture = Image(key_normal, mipmap=True).texture
        with self.background_key_layer:
            for line_nb in range(1, layout_rows + 1):
                for pos, size in layout_geometry['LINE_%d' % line_nb]:
                        BorderImage(texture=texture, pos=pos, size=size,
                                border=self.key_border)

        self.labels = []
        font_size = int(w) / 60
        key_nb = 0
        for pos, size in layout_geometry['LINE_1']:
            # retrieve the relative text
            text = layout[layout_mode + '_1'][key_nb][0]
            l = Label(text=text, font_size=font_size, pos=pos, size=size,
                    font_name=self.font_name)
            self.add_widget(l)
            self.labels.append(l)
            key_nb += 1
        # then draw the text
        # calculate font_size
        font_size = int(w) / 46
        # draw
        for line_nb in range(2, layout_rows + 1):
            key_nb = 0
            for pos, size in layout_geometry['LINE_%d' % line_nb]:
                # retrieve the relative text
                text = layout[layout_mode + '_' + str(line_nb)][key_nb][0]
                l = Label(text=text, font_size=font_size, pos=pos, size=size,
                        font_name=self.font_name)
                self.add_widget(l)
                key_nb += 1

    def on_key_down(self, *largs):
        pass

    def on_key_up(self, *largs):
        pass

    def get_key_at_pos(self, x, y):
        w, h = self.size
        x_hint = x / w
        # focus on the surface without margins
        layout_geometry = self.layout_geometry
        layout = self.available_layouts[self.layout]
        layout_rows = layout['rows']
        mtop, mright, mbottom, mleft = self.margin_hint

        # get the line of the layout
        e_height = h - (mbottom + mtop) * h  # efficient height in pixels
        line_height = e_height / layout_rows  # line height in px
        y = y - mbottom * h
        line_nb = layout_rows - int(y / line_height)

        if line_nb > layout_rows:
            line_nb = layout_rows
        if line_nb < 1:
            line_nb = 1

        # get the key within the line
        key_index = ''
        current_key_index = 0
        for key in layout_geometry['LINE_HINT_%d' % line_nb]:
            if x_hint >= key[0][0] and x_hint < key[0][0] + key[1][0]:
                key_index = current_key_index
                break
            else:
                current_key_index += 1
        if key_index == '':
            return None

        # get the full character
        key = layout['%s_%d' % (self.layout_mode, line_nb)][key_index]

        return [key, (line_nb, key_index)]

    def collide_margin(self, x, y):
        '''Do a collision test, and return True if the (x, y) is inside the
        vkeyboard margin.
        '''
        mtop, mright, mbottom, mleft = self.margin_hint
        x_hint = x / self.width
        y_hint = y / self.height
        if x_hint > mleft and x_hint < 1. - mright \
            and y_hint > mbottom and y_hint < 1. - mtop:
            return False
        return True

    def process_key_on(self, touch):
        x, y = self.to_local(*touch.pos)
        key = self.get_key_at_pos(x, y)
        if not key:
            return

        key_data = key[0]
        displayed_char, internal, special_char, size = key_data
        line_nb, key_index = key[1]

        # save pressed key on the touch
        ud = touch.ud[self.uid] = {}
        ud['key'] = key

        # for caps lock or shift only:
        uid = touch.uid
        if special_char is not None:
            if special_char == 'capslock':
                self.have_capslock = not self.have_capslock
                uid = -1
            elif special_char == 'shift':
                self.have_shift = True

        # save key as an active key for drawing
        self.active_keys[uid] = key[1]
        self.refresh_active_keys_layer()

    def process_key_up(self, touch):
        uid = touch.uid
        if self.uid not in touch.ud:
            return

        # save pressed key on the touch
        key_data, key = touch.ud[self.uid]['key']
        displayed_char, internal, special_char, size = key_data

        # send info to the bus
        b_keycode = special_char
        b_modifiers = self._get_modifiers()
        self.dispatch('on_key_up', b_keycode, internal, b_modifiers)

        if special_char == 'capslock':
            uid = -1

        if uid in self.active_keys:
            self.active_keys.pop(uid, None)
            if special_char == 'shift':
                self.have_shift = False
            if special_char == 'capslock' and self.have_capslock:
                self.active_keys[-1] = key
            self.refresh_active_keys_layer()

    def _get_modifiers(self):
        ret = []
        if self.have_shift:
            ret.append('shift')
        if self.have_capslock:
            ret.append('capslock')
        return ret

    def on_touch_down(self, touch):
        if touch.ud is None:
            return
        x, y = touch.pos
        if not self.collide_point(x, y):
            return

        x, y = self.to_local(x, y)
        
        touch.ud['key'] = self.get_key_at_pos(x, y)
        if touch.ud['key'] is None:
            del touch.ud['key']
            return
        
        if len(touch.ud['key'][0][2]) == 1 and touch.ud['key'][0][2].isalpha():
            with self.canvas:
                Color(0.5, 0.6, 1)
                touch.ud['line'] = Line(points=[x, y], width=2)
        elif touch.ud['key'][0][2] == u'ctrl':
            touch.ud['ctrl'] = None
            with self.canvas:
                Color(0.5, 0.6, 1)
                touch.ud['line'] = Line(points=[x, y], width=2)
        
        if not self.collide_margin(x, y):
            self.process_key_on(touch)
            touch.grab(self, exclusive=True)
        else:
            super(VKeyboard, self).on_touch_down(touch)
        return True
    
    def get_current_word(self):
        textarea = self.get_text_area()
        i = textarea.cursor_index()
        T = textarea.text[:i]
        for j in xrange(i-1, -1, -1):
            if not T[j].isalpha():
                break
        else:
            return T
        return T[j + 1:i]

    def get_previous_word(self):
        textarea = self.get_text_area()
        len_cur = len(self.get_current_word())
        i = max(textarea.cursor_index() - len_cur - 1, 0)
        T = textarea.text[:i]
        while len(T) > 0 and not T[-1].isalpha():
            T = T[:-1]
        i = len(T)
        for j in xrange(i-1, -1, -1):
            if not T[j].isalpha():
                break
        else:
            return T
        return T[j + 1:i]
    
    def on_touch_move(self, touch):
        if touch.ud is None:
            return
        x, y = self.to_local(*touch.pos)
        if 'line' in touch.ud:
            touch.ud['line'].points += [x, y]
        if 'key' in touch.ud and touch.ud['key'] != self.get_key_at_pos(x, y):
            touch.ud['key'] = None

    def on_touch_up(self, touch):
        if touch.ud is None:
            return
        x, y = self.to_local(*touch.pos)
        if 'key' in touch.ud and touch.ud['key'] == self.get_key_at_pos(x, y) and self.get_key_at_pos(x, y) is not None:
            displayed_char, internal, special_char, size = touch.ud['key'][0]
            b_keycode = special_char
            b_modifiers = self._get_modifiers()
            if special_char.startswith('sug'):
                if internal is not None and internal != '':
                    word = self.get_current_word()
                    textarea = self.get_text_area()
                    textarea.select_text(textarea.cursor_index() - len(word), textarea.cursor_index())
                    textarea.delete_selection()
            if internal is not None and len(internal) == 1 and not (len(special_char) == 1 and special_char.isalpha()):
                prev_word = str(self.get_previous_word())
                cur_word = str(self.get_current_word())
                if cur_word != '':
                    self.user_nograms += 1
                    if cur_word not in self.words:
                        self.words[cur_word.lower()] = self.val_dist(tuple(map(self.key_centers.__getitem__, cur_word.lower()))) + (0.0,)
                    self.user_unigrams[cur_word] = self.user_unigrams.get(cur_word, 0) + 1
                    if prev_word != '':
                        self.user_bigrams[(prev_word, cur_word)] = self.user_bigrams.get((prev_word, cur_word), 0) + 1
                    self.dispatch('on_key_down', b_keycode, internal, b_modifiers)
                    matches = self.candidate_guesses()[:6]
                    self.update_candidates(matches)
                else:
                    self.dispatch('on_key_down', b_keycode, internal, b_modifiers)
            else:
                self.dispatch('on_key_down', b_keycode, internal, b_modifiers)
            if (len(special_char) == 1 and special_char.isalpha()) or special_char == 'backspace':
                word = self.get_current_word()
                if len(word) >= 4:
                    matches = self.candidate_predictions(word)[:6]
                else:
                    matches = []
                self.update_candidates(matches)
        elif 'ctrl' in touch.ud and self.get_key_at_pos(x, y) is not None:
            displayed_char, internal, special_char, size = self.get_key_at_pos(x, y)[0]
            k = special_char
            if k == 'c':
                textarea = self.get_text_area()
                Clipboard.put(textarea.selection_text, 'STRING')
                textarea.cancel_selection()
            elif k == 'v':
                textarea = self.get_text_area()
                textarea.delete_selection()
                textarea.insert_text(Clipboard.get('STRING'))
            elif k == 'a':
                textarea = self.get_text_area()
                textarea.select_all()
            elif k == 'x':
                textarea = self.get_text_area()
                Clipboard.put(textarea.selection_text, 'STRING')
                textarea.delete_selection()
            elif k == 'z':
                textarea = self.get_text_area()
                textarea.do_undo()
            elif k == 'y':
                textarea = self.get_text_area()
                textarea.do_redo()
            elif k == 'l':
                available_layouts = self.available_layouts.keys()
                self.layout = available_layouts[(available_layouts.index(self.layout) + 1) % len(self.available_layouts)]
                self.reload_layout()
            #elif k == 's':
            #    window = self.get_parent_window()
            #    textarea = self.get_text_area()
            #    def _on_close(self):
            #        window.children[0].remove_widget(settings)
            #        textarea.focus = True
            #    settings = Settings(on_close=_on_close)
            #    settings.add_json_panel('VKeyboard Settings', self.config, 'settings.json')
            #    window.children[1].add_widget(settings)
            #    window.release_keyboard(self)
                
        elif 'line' in touch.ud:
            gesture = touch.ud['line'].points
            gesture = [(gesture[i], gesture[i+1]) for i in xrange(0, len(gesture), 2)]
            matches = self.candidate_matches(gesture)[:6]
            self.update_candidates(matches)
            b_modifiers = self._get_modifiers()
            if 'shift' in b_modifiers and 'capslock' not in b_modifiers:
                matches = [(w[0].upper() + w[1:], p) for w, p in matches]
            elif 'capslock' in b_modifiers and 'shift' not in b_modifiers:
                matches = [(w.upper(), p) for w, p in matches]
            if len(matches) > 0:
                textarea = self.get_text_area()
                textarea.delete_selection()
                textarea.insert_text(matches[0][0])
        if touch.grab_current is self:
            self.process_key_up(touch)
        if 'line' in touch.ud:
            self.canvas.remove(touch.ud['line'])
        return super(VKeyboard, self).on_touch_up(touch)
    
    def update_candidates(self, matches):
        layout = self.available_layouts[self.layout]
        i = -1
        for i, (w, p) in enumerate(matches):
            layout['normal_1'][i] = [unicode(w), unicode(w), u'sug%d' % i, 2.5]
            layout['shift_1'][i] = [unicode(w[0].upper() + w[1:]), unicode(w[0].upper() + w[1:]), u'sug%d' % i, 2.5]
            layout['capslock_1'][i] = [unicode(w.upper()), unicode(w.upper()), u'sug%d' % i, 2.5]
            b_modifiers = self._get_modifiers()
            if ('shift' in b_modifiers) == ('capslock' in b_modifiers):
                self.labels[i].text = unicode(w)
            elif 'shift' in b_modifiers:
                self.labels[i].text = unicode(w[0].upper() + w[1:])
            else:
                self.labels[i].text = unicode(w.upper())
        for j in xrange(i + 1, 6):
            layout['normal_1'][j] = [u'', u'', u'sug%d' % j, 2.5]
            layout['shift_1'][j] = [u'', u'', u'sug%d' % j, 2.5]
            layout['capslock_1'][j] = [u'', u'', u'sug%d' % j, 2.5]
            self.labels[j].text = u''
