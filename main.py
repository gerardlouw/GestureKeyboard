from vkeyboard import VKeyboard

import kivy
kivy.require('1.0.8')

from kivy.core.window import Window
from kivy.uix.textinput import TextInput
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatter import Scatter
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.config import Config
#from kivy.base import runTouchApp
from kivy.app import App
#from kivy.uix.settings import Settings

class VKeyboardApp(App):
    def _keyboard_close(self):
        pass
    
    def build(self):
        Config.set('kivy', 'keyboard_mode', 'dock')
        Window.set_vkeyboard_class(VKeyboard)
        Window.configure_keyboards()
        
        root = FloatLayout()
        root.add_widget(TextInput())
        
        kb = Window.request_keyboard(self._keyboard_close, self)
        
        return root

if __name__ == '__main__':
    VKeyboardApp().run()
