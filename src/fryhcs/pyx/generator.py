from parsimonious import NodeVisitor, BadGrammar
import sys
import re
import hashlib
from fryhcs.pyx.grammar import grammar
from fryhcs.spec import is_valid_html_attribute
from fryhcs.css.style import CSS

def escape(s):
    return s.replace('"', '\\"')


class BaseGenerator(NodeVisitor):
    def __init__(self):
        self.client_embed_count = 0

    def inc_client_embed(self):
        count = self.client_embed_count
        self.client_embed_count = count + 1
        return count 

    def reset_client_embed(self):
        self.client_embed_count = 0

    def get_uuid(self, node):
        sha1 = hashlib.sha1()
        sha1.update(node.text.encode('utf-8'))
        return sha1.hexdigest()


#client_embed_attr_name = 'data-fryembed'
children_attr_name = 'children'
call_client_script_attr_name = 'call-client-script'

no_attr = 'no_attr'                   # ('no_attr', ...)
spread_attr = 'spread_attr'           # ('spread_attr', script): {script}
literal_attr = 'literal_attr'         # ('literal_attr', name, value): name="literal_value"
novalue_attr = 'novalue_attr'         # ('novalue_attr', name): name
py_attr = 'py_attr'                   # ('py_attr', name, pyscript): name={pyscript}
js_attr = 'js_attr'                   # ('js_attr', name, jscount): name=(jsscript)
jsop_attr = 'jsop_attr'               # ('jsop_attr', name, pyscript): name=({pyscript})
element_attr = 'element_attr'         # ('element_attr', name, element): name=<element></element>
pyjs_attr = 'pyjs_attr'               # ('pyjs_attr', name, pyscript, jscount): name={pyscript}(jsscript)
pyjsop_attr = 'pyjsop_attr'           # ('pyjsop_attr', name, pyscript, pyscript): name={pyscript1}({pyscript2})
literaljs_attr = 'literaljs_attr'     # ('literaljs_attr', name, value, jscount): name=[value](jsscript)
literaljsop_attr = 'literaljsop_attr' # ('literaljsop_attr', name, value, value): name=[value]({pyscript})
children_attr = 'children_attr'       # ('children_attr', [children])
jstext_attr = 'jstext_attr'           # ('jstext_attr', jscount)
jsoptext_attr = 'jsoptext_attr'       # ('jsoptext_attr', value)
call_client_attr = 'call_client_attr' # ('call_client_attr', uuid, args)

def concat_kv(attrs):
    ats = []
    for attr in attrs:
        if isinstance(attr, (list, tuple)):
            atype = attr[0]
            if atype == spread_attr:
                ats.append(attr[1])
            elif atype == literal_attr:
                _, name, value = attr
                ats.append(f'"{name}": {value}')
            elif atype == novalue_attr:
                ats.append(f'"{attr[1]}": ""')
            elif atype == py_attr:
                _, name, value = attr
                ats.append(f'"{name}": {value}')
            elif atype == js_attr:
                _, jscount = attr
                ats.append(f'"{name}": Element.ClientEmbed({jscount})')
            elif atype == jsop_attr:
                _, value = attr
                ats.append(f'"{name}": {value}')
            elif atype == element_attr:
                _, name, value = attr
                ats.append(f'"{name}": {value}')
            elif atype == pyjs_attr:
                _, name, value, jscount = attr
                ats.append(f'"{name}": {value}')
                ats.append(f'"${name}": Element.ClientEmbed({jscount})')
            elif atype == pyjsop_attr:
                _, name, value, jsvalue = attr
                ats.append(f'"{name}": {value}')
                ats.append(f'"${name}": {jsvalue}')
            elif atype == literaljs_attr:
                _, name, value, jscount = attr
                ats.append(f'"{name}": {value}')
                ats.append(f'"${name}": Element.ClientEmbed({jscount})')
            elif atype == literaljsop_attr:
                _, name, value, jsvalue = attr
                ats.append(f'"{name}": {value}')
                ats.append(f'"${name}": {jsvalue}')
            elif atype == children_attr:
                ats.append(f'"{children_attr_name}": [{", ".join(attr[1])}]')
            elif atype == jstext_attr:
                _, jscount = attr
                ats.append(f'"*": Element.ClientEmbed({jscount})')
            elif atype == jsoptext_attr:
                _, jsvalue = attr
                ats.append(f'"*": {jsvalue}')
            elif atype == call_client_attr:
                _, uuid, args = attr
                args = ', '.join(f'("{k}", {v})' for k,v in args)
                ats.append(f'"{call_client_script_attr_name}": ["{uuid}", [{args}]]')
            elif atype == no_attr:
                pass
            else:
                raise BadGrammar(f"Invalid attribute: {attr}")
        else:
            raise BadGrammar(f"Invalid attr: {attr}")
    return ats

# 检查并预处理html基本元素的属性
#
#   html基本元素是符合html规范的元素，支持无属性值属性、有属性值属性、事件处理器属性，属性有如下几种：
#   * `name`                               : 无值属性，如果是符合html规范的属性，正常传给浏览器引擎，否则放到class中
#                                            服务端：class中的值，或无值属性
#                                            浏览器：class中的值，或无值属性
#   * `name="literal_value"`               : 符合html规范的属性在客户端传给浏览器引擎，否则放到css中
#                                            服务端：class中的值，或正常html元素属性
#                                            浏览器：class中的值，或正常html元素属性
#   * `name='literal_value'`               : 符合html规范的属性在客户端传给浏览器引擎，否则放到css中
#                                            服务端：class中的值，或正常html元素属性
#                                            浏览器：class中的值，或正常html元素属性
#   * `@event=(js_handler)`                : 本组件的js事件处理函数
#   * `@event=({jsop_handler})`            : 父组件的js事件处理函数
#                                            服务端：ClientEmbed对象
#                                            浏览器：data-fry-script一项
#   * `@event={py_value}`                  : ClientEmbed类型的python值，父组件的事件处理函数
#                                            服务端：data-fry-script一项
#                                            浏览器：data-fry-script一项
#   * `name={py_value}`                    : python值在服务端渲染为常量传给浏览器引擎，不可以为ClientEmbed
#                                            服务端：`name=py_value`，python数据值
#                                            浏览器：`name="py_value"`，字符串值，如果是ClientEmbed时生成data-fry-script一项
#   * `name={py_value}(js_value)`          : python值，客户端js修改
#   * `name={py_value}({jsop_value})`      : python值，客户端父组件js修改
#                                            服务端：`name=py_value`，python数据值
#                                            浏览器：`name="py_value"`，字符串值，同时新增data-fry-script一项
#   * `name=[literal_value](js_value)`     : 常量字符串，客户端js修改
#   * `name=[literal_value]({jsop_value})` : 常量字符串，客户端父组件js修改
#                                            服务端：`name=literal_value`，python数据值
#                                            浏览器：`name="literal_value"`，字符串值，同时新增data-fry-script一项
#   * `{*python_list}`                     : python列表值，服务端渲染为常量传给浏览器引擎
#   * `{**python_dict}`                    : python字典值，服务端渲染为常量传给浏览器引擎
def check_html_element(name, attrs):
    classes = []
    class_attr = None
    for attr in attrs:
        atype = attr[0]
        if atype not in (novalue_attr, literal_attr, js_attr, py_attr, pyjs_attr, literaljs_attr, spread_attr):
            raise BadGrammar(f"Invalid attribute type '{atype}' in html element '{name}'")
        if attr[1][0] == '@' and atype not in (js_attr, py_attr):
            raise BadGrammar(f"Invalid attribute type '{atype}' for event handler '{attr[1]}' in html element '{name}'")
        if atype == js_attr:
            if attr[1][0] != '@':
                raise BadGrammar(f"js_attr type can only be specified for event handler, not '{attr[1]}'")
            attr[0] = py_attr
            attr[2] = f'Element.ClientEmbed({attr[2]})'
        if atype == novalue_attr:
            key = attr[1]
            value = ''
        elif atype == literal_attr:
            _, key, value = attr
            if value[0] in '\'"':
                value = value[1:-1]
        else:
            continue
        if key == 'class' and atype == literal_attr:
            class_attr = attr
            continue
        if is_valid_html_attribute(name, key):
            continue
        values = value.split()
        if not values:
            values = ['']
        classes.extend(CSS(key, value).to_class() for value in values) 
        attr[0] = no_attr
    if classes:
        classes = ' '.join(classes)
        if not class_attr:
            class_attr = [literal_attr, 'class', '""']
            attrs.append(class_attr)
        value = class_attr[2]
        if value[0] in '\'"':
            value = value[1:-1]
        if value:
            class_attr[2] = '"{value} {classes}"'
        else:
            class_attr[2] = f'"{classes}"'


# 检查并预处理组件元素的属性
#
#   组件元素以大写字母开头的名字作为元素名，元素名代表一个组件函数。
#   组件元素的属性作为python参数列表传给组件函数，所以组件元素只支持如下几种格式的属性：
#   * `name="literal_value"`: 常量字符串在服务端传给子组件
#                             服务端：常量字符串
#                             浏览器：不可见
#   * `name='literal_value'`: 常量字符串在服务端传给子组件
#                             服务端：常量字符串
#                             浏览器：不可见
#   * `name=<tagname a="b">xxx</tagname>`:
#                             元素值转化为Element实例传给子组件
#                             服务端：Element实例
#                             浏览器：不可见
#   * `name={py_value}`     : python值在服务端运行时传给子组件，可以是各种类型数据，不包括ClientEmbed
#                             服务端：python数据
#                             浏览器：不可见
#   * `name=(js_value)`     : 本组件js值在客户端运行时传给子组件
#   * `name=({jsop_value})` : 父组件js值在客户端运行时传给子组件
#                             服务端：ClientEmbed对象
#                             浏览器：不可见
#   * `{**python_dict}`     : python字典值
#                             服务端：传递给python组件函数的props参数的一部分
#                             浏览器：不可见
def check_component_element(name, attrs):
    for attr in attrs:
        atype = attr[0]
        if atype not in (spread_attr, literal_attr, element_attr, py_attr, js_attr):
            raise BadGrammar(f"Invalid attr '{atype}': Component element can only have spread_attr, literal_attr, element_attr, py_attr, js_attr")
        if atype != spread_attr and attr[1][0] == '@':
            raise BadGrammar(f"Can't set event handler '{attr[1]}' on Component element '{name}'")
        if atype == js_attr:
            attr[0] = py_attr
            attr[2] = f'Element.ClientEmbed({attr[2]})'

class PyGenerator(BaseGenerator):
    def generate(self, tree):
        self.web_component_script = False
        self.client_script_args = {}
        self.reset_client_embed()
        return self.visit(tree)

    def generic_visit(self, node, children):
        return children or node

    def visit_script(self, node, children):
        return ''.join(str(ch) for ch in children)

    def visit_inner_script(self, node, children):
        return ''.join(str(ch) for ch in children)

    def visit_script_item(self, node, children):
        return children[0]

    def visit_inner_script_item(self, node, children):
        item = children[0]
        if isinstance(item, tuple):
            if item[0] == 'element':
                return item[1]
            else:
                raise BadGrammar
        return item 

    def visit_comment(self, node, children):
        return node.text

    def visit_brace(self, node, children):
        _, script, _ = children
        # brace是正常的python脚本，需要原样输出
        return '{' + script + '}'

    def visit_embed(self, node, children):
        _, script, _ = children
        # embed都是赋值表达式，可以直接加上小括号
        return '(' + script + ')'

    def visit_triple_single_quote(self, node, children):
        return node.text

    def visit_triple_double_quote(self, node, children):
        return node.text

    def visit_single_quote(self, node, children):
        return node.text

    def visit_double_quote(self, node, children):
        return node.text

    def visit_simple_quote(self, node, children):
        return children[0]

    def visit_less_than_char(self, node, children):
        return '<'

    def visit_normal_code(self, node, children):
        return node.text

    def visit_inner_normal_code(self, node, children):
        return node.text

    def visit_pyx_root_element(self, node, children):
        name, attrs = children[0]
        if name == 'script':
            raise BadGrammar("'script' can't be used as the root element name") 
        if self.web_component_script:
            uuid = self.get_uuid(node)
            args = [(k,v) for k,v in self.client_script_args.items()]
            attrs.insert(0, [call_client_attr, uuid, args])
        self.web_component_script = False
        self.client_script_args = {}
        self.reset_client_embed()
        attrs = concat_kv(attrs)
        return f'Element({name}, {{{", ".join(attrs)}}})'

    def visit_pyx_element(self, node, children):
        name, attrs = children[0]
        if name == 'script':
            raise BadGrammar(f"Something is wrong in script: {node.text}") 
        attrs = concat_kv(attrs)
        return ('element', f'Element({name}, {{{", ".join(attrs)}}})')

    def visit_pyx_fragment(self, node, children):
        _, pyx_children, _ = children
        return ('"div"', [[children_attr, pyx_children]])

    def visit_pyx_self_closing_element(self, node, children):
        _, name, attrs, _, _ = children
        if not name:
            raise BadGrammar
        if name[0].islower():
            check_html_element(name, attrs)
            name = f'"{name}"'
        else:
            check_component_element(name, attrs)
        attrs.append([children_attr,[]])
        return (name, attrs)

    def visit_pyx_paired_element(self, node, children):
        start, pyx_children, end = children
        start_name, attrs = start
        end_name = end
        if start_name != end_name:
            raise BadGrammar(f'start_name "{start_name}" is not the same with end_name "{end_name}"')
        name = start_name
        if not name:
            raise BadGrammar
        elif name[0].islower():
            check_html_element(name, attrs)
            name = f'"{name}"'
        else:
            check_component_element(name, attrs)

        attrs.append([children_attr, pyx_children])

        return (name, attrs)

    def visit_pyx_start_tag(self, node, children):
        _, start_name, attrs, _, _ = children
        return start_name, attrs

    def visit_pyx_end_tag(self, node, children):
        _, name, _, _ = children
        return name

    def visit_pyx_element_name(self, node, children):
        return node.text

    def visit_space(self, node, children):
        return node.text

    def visit_maybe_space(self, node, children):
        return node.text

    def visit_pyx_attributes(self, node, children):
        return children

    def visit_pyx_spaced_attribute(self, node, children):
        _, attr = children
        return attr

    def visit_pyx_attribute(self, node, children):
        return children[0]

    def visit_pyx_embed_spread_attribute(self, node, children):
        _lbrace, _, stars, _, script, _rbrace, _, _css_literal = children
        if stars.text == '*':
            return [spread_attr, "**{ key: True for key in (" + script + ")}"]
        return [spread_attr, '**(' + script + ')']

    #def visit_pyx_client_embed_attribute(self, node, children):
    #    value, _, _css_literal = children
    #    _name, literal, client_embed = value
    #    kvs = [(name, '""') for name in literal.split()]
    #    count = self.inc_client_embed()
    #    return (client_embed_attr_name, kvs, str(count))

    #def visit_pyx_event_attribute(self, node, children):
    #    _at, _identifier, _, _equal, _, _client_embed = children
    #    count = self.inc_client_embed()
    #    return (client_embed_attr_name, [], str(count))

    def visit_pyx_kv_attribute(self, node, children):
        name, _, _, _, value = children
        if isinstance(value, str):
            return [literal_attr, name, value]
        elif isinstance(value, tuple):
            if value[0] == 'client_embed_value':
                _, literal, client_embed = value
                if client_embed[0] == 'js_client_embed':
                    count = self.inc_client_embed()
                    return [literaljs_attr, name, f'"{literal}"', str(count)]
                elif client_embed[0] == 'jsop_client_embed':
                    return [literaljsop_attr, name, f'"{literal}"', client_embed[1]]
                else:
                    raise BadGrammar
            elif value[0] == 'embed_value':
                _, embed, client_embed = value
                if client_embed:
                    if client_embed[0] == 'js_client_embed':
                        count = self.inc_client_embed()
                        return [pyjs_attr, name, embed, str(count)]
                    elif client_embed[0] == 'jsop_client_embed':
                        return [pyjsop_attr, name, embed, client_embed[1]]
                    else:
                        raise BadGrammar
                else:
                    return [py_attr, name, embed]
            elif value[0] == 'js_client_embed':
                count = self.inc_client_embed()
                return [js_attr, name, str(count)]
            elif value[0] == 'jsop_client_embed':
                return [jsop_attr, name, value[1]]
            elif value[0] == 'element':
                return [element_attr, name, value[1]]
            else:
                raise BadGrammar(f'Invalid attribute value: {value[0]}')
        else:
            raise BadGrammar(f'Invalid attribute value: {value}')

    def visit_pyx_novalue_attribute(self, node, children):
        name, _ = children
        return [novalue_attr, name]

    def visit_pyx_attribute_name(self, node, children):
        return node.text

    def visit_pyx_attribute_value(self, node, children):
        return children[0]

    def visit_pyx_attr_value_embed(self, node, children):
        embed, _, client_embed, _, _css_literal = children
        return ('embed_value', embed, client_embed)

    def visit_pyx_attr_value_client_embed(self, node, children):
        value, _, _css_literal = children
        return value #('client_embed', literal, client_embed)

    def visit_pyx_css_literal(self, node, children):
        _colon, _, value = children
        return value

    def visit_maybe_css_literal(self, node, children):
        if not children:
            return ''
        return children[0]

    def visit_pyx_children(self, node, children):
        return [ch for ch in children if ch]

    def visit_pyx_child(self, node, children):
        pyxchild = children[0]
        if isinstance(pyxchild, str):
            return pyxchild
        elif isinstance(pyxchild, tuple):
            if pyxchild[0] == 'embed_value':
                _, embed, client_embed = pyxchild
                if not client_embed:
                    return embed
                if client_embed[0] == 'js_client_embed':
                    attr = jstext_attr
                    value = str(self.inc_client_embed())
                elif client_embed[0] == 'jsop_client_embed':
                    attr = jsoptext_attr
                    value = client_embed[1]
                else:
                    raise BadGrammar
                attrs = [[attr, value],
                         [children_attr, [embed]]]
                attrs = concat_kv(attrs)
                return f'Element("span", {{{", ".join(attrs)}}})'
            elif pyxchild[0] == 'client_embed_value':
                _, literal, client_embed = pyxchild
                if client_embed[0] == 'js_client_embed':
                    attr = jstext_attr
                    value = str(self.inc_client_embed())
                elif client_embed[0] == 'jsop_client_embed':
                    attr = jsoptext_attr
                    value = client_embed[1]
                else:
                    raise BadGrammar
                attrs = [[attr, value],
                         [children_attr, [f'"{literal}"']]]
                attrs = concat_kv(attrs)
                return f'Element("span", {{{", ".join(attrs)}}})'
            elif pyxchild[0] == 'element':
                return pyxchild[1]
        else:
            raise BadGrammar(f'Invalid pyx_child "{pyxchild}"')

    def visit_embed_value(self, node, children):
        embed, _, client_embed = children
        return ('embed_value', embed, client_embed)

    def visit_client_embed_value(self, node, children):
        _l, literal, _r, _, client_embed = children
        return ('client_embed_value', literal.text, client_embed)

    def visit_pyx_text(self, node, children):
        value = re.sub(r'(\s+)', lambda m: ' ', node.text).strip()
        if not value or value == ' ':
            return ''
        return f'"{escape(value)}"'

    def visit_no_embed_char(self, node, children):
        return node.text

    # 脚本元素的元素名为script，代表了一个组件对应的js脚本，一个组件最多有一个脚本元素。
    # 脚本元素的属性作为js参数列表传给脚本代码，并且脚本代码需要在编译期生成，属性名需要在编译期可见，
    # 不能依赖python运行期的信息，所以脚本元素只支持如下几种格式的属性：
    # * `name="literal_value"`: 常量字符串在客户端传给js脚本
    #                           服务端：`data-name="literal_value"`
    #                           浏览器：`data-name="literal_value"`
    # * `name='literal_value'`: 常量字符串在客户端传给js脚本
    #                           服务端：`data-name='literal_value'`
    #                           浏览器：`data-name="literal_value"`
    # * `name={py_value}`     : python值作为字符串在客户端运行时传给js脚本，在客户端是一个常量字符串
    #                           服务端：`data-name=py_value`，python数据值
    #                           浏览器：`data-name="py_value"`，字符串值。
    # * `name=({py_value})`   : ClientEmbed值在客户端运行时传给本组件js脚本，是父组件的js值
    #                           服务端：`data-fryembed=[ClientEmbed]`，ClientEmbed值
    #                           浏览器：`data-fryembed="4/3-object-foo"`，父组件js值
    # name不能以'fry'开头
    def visit_web_component_script(self, node, children):
        self.web_component_script = True
        _begin, attributes, _, _lessthan, _script, _end = children
        for attr in attributes:
            if attr[0] not in (literal_attr, py_attr, jsop_attr):
                raise BadGrammar("script attributes can only be literal_attr, py_attr or jsop_attr")
            if attr[1][0] == '@':
                raise BadGrammar(f"can't set event handler {attr[1]} on script element")
            atype, k, v = attr
            if k.startswith('fry'):
                raise BadGrammar(f"<script> attribute name can't be started with 'fry'")
            self.client_script_args[k] = v
        return ''

    def visit_html_comment(self, node, children):
        return ''

    def visit_client_embed(self, node, children):
        self.web_component_script = True
        return children[0]

    def visit_js_client_embed(self, node, children):
        return ('js_client_embed', node.text)

    def visit_jsop_client_embed(self, node, children):
        _l, script, _r = children
        return ('jsop_client_embed', script)

    def visit_maybe_client_embed(self, node, children):
        if children:
            return children[0]
        else:
            return ''


def pyx_to_py(source):
    """
    pyx文件内容转成py文件内容
    """
    tree = grammar.parse(source)
    generator = PyGenerator()
    return generator.generate(tree)
