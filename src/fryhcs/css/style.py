import re

from .modifiers import is_modifier, add_modifier
from .utilities import Utility


def quote_selector(value):
    invalid_chars = r"([~!@$%^&*()+=,./';:\"?><[\]\\{}|`#])"
    fun = lambda m: '\\'+m.group(1)
    return re.sub(invalid_chars, fun, value)


class CSS():
    DEFAULT_ORDER          = -100000
    DEFAULT_MODIFIER_ORDER = -10000
    def __init__(self, key='', value='', toclass=True):
        self.key = key
        self.value = value
        self.toclass = toclass
        self.parse()
        self.generate()

    @classmethod
    def union(cls, csses):
        # TODO
        pass

    def to_class(self):
        modifiers = ':'.join(self.modifiers)
        utility = '-'.join(self.utility_args)
        if modifiers:
            if utility:
                return modifiers + ':' + utility
            else:
                return modifiers
        else:
            return utility

    def clean_args(self, args):
        # border="~ cyan-100"将被匹配为border和border-cyan-100
        # 而非border-~和border-cyan-100
        if len(args) > 1 and args[-1] == '~':
            return args[:-1]
        return args

    def parse(self):
        """
        for class, key = '';
        for no-value attribute, value = ''
        generate:
          selector: css selector based on the value of key and value
          modifiers: all modifiers
          utility_args: utility and its args
        如果utility中的大小为负值，则utility_args[0]以'-'开头
        """
        key = self.key
        value = self.value

        if not key:
            # class的css匹配方式: .classname
            selector = '.' + quote_selector(value)
        elif not value:
            # 只有属性名没有值的匹配方式：[key=""]，不能用[key]，
            # [key]匹配的是存在属性key，此时key的值可以是任意值；
            # 也不能用[key ~= ""]，这个无法匹配只有属性名的情况。
            selector = '[' + quote_selector(key) + ' = ""]'
        else:
            # 既有属性又有值的情况，与类的情况类似，值中使用空格分开
            # 的每一个"子值"，都是用[key ~= subvalue]进行匹配
            selector = '[' + quote_selector(key) + ' ~= "' + value + '"]'

        keys = key.split(':') if key else []
        values = value.split(':') if value else []
        negative = False
        if keys and not is_modifier(keys[-1]):
            modifiers = keys[:-1]
            utility = keys[-1]
            if utility and utility[0] == '-':
                utility = utility[1:]
                negative = not negative
            if utility:
                utility_args = utility.split('-')
            else:
                utility_args = []
        else:
            modifiers = keys[:]
            utility_args = []
        if values:
            modifiers += values[:-1]
            utility = values[-1]
            if utility and utility[0] == '-':
                utility = utility[1:]
                negative = not negative
            if utility:
                utility_args += utility.split('-')
        if negative and utility_args:
            utility_args[0] = '-' + utility_args[0]

        self.modifiers = modifiers
        self.utility_args = self.clean_args(utility_args)
        self.selector = selector
        if self.toclass:
            self.selector = '.' + quote_selector(self.to_class())

    def generate(self):
        self.wrappers = []
        self.styles = []
        self.addons = []
        self.order = self.DEFAULT_ORDER
        self.valid = True
        for modifier in self.modifiers:
            if not add_modifier(self, modifier):
                self.valid = False
                return
        self.utility = Utility(self)
        self.valid = self.utility()
    
    def new_addon(self):
        addon = CSS()
        self.addons.append(addon)
        return addon

    def quote(self, value):
        return quote_selector(value)

    def lines(self, new_selector=''):
        if not self.valid:
            return []
        twospace = '  '
        indent = ''
        lines = []
        for wrapper in self.wrappers:
            lines.append(indent + wrapper + ' {')
            indent += twospace
        selector = self.selector or new_selector
        lines.append(indent + selector + ' {')
        indent += twospace
        for style in self.styles:
            lines.append(indent + style)
        indent = indent[:-2]
        lines.append(indent + '}')
        for addon in self.addons:
            lines.append('')
            for line in addon.lines(selector):
                lines.append(indent + line)
        while len(indent) > 0:
            indent = indent[:-2]
            lines.append(indent + '}')
        return lines

    def text(self):
        return '\n'.join(self.lines()) + '\n\n'
