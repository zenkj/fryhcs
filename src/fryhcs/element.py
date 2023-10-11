import inspect
from fryhcs.utils import static_url, component_name
from fryhcs.config import fryconfig
from fryhcs.pyx.generator import call_client_script_attr_name

def escape(s):
    return s.replace('"', '\\"')


class RenderException(Exception):
    pass


def render_children(children, page):
    chs = []
    for ch in children:
        if isinstance(ch, (list, tuple)):
            chs += render_children(ch, page)
        elif isinstance(ch, Element):
            chs.append(ch.render(page))
        else:
            chs.append(ch)
    return chs


class ClientEmbed(object):
    def __init__(self, embed_id):
        self.embed_id = embed_id
        self.component = 0

    def hook(self, component):
        if self.component == 0:
            self.component = component

    def __str__(self):
        if self.component == 0:
            return str(self.embed_id)
        else:
            return f'{self.component}/{self.embed_id}'


class Element(object):
    component_attr_name = 'data-fryclass'
    component_id_attr_name = 'data-fryid'
    client_embed_attr_name = 'data-fryembed'

    def __init__(self, name, props={}, rendered=False):
        self.name = name
        self.props = props
        self.rendered = rendered

    def is_component(self):
        if self.rendered:
            return self.component_attr_name in self.props
        else:
            return inspect.isfunction(self.name) #or inspect.isclass(self.name)

    def hook_client_embed(self, component):
        def hook(v):
            if isinstance(v, ClientEmbed):
                v.hook(component)
            elif isinstance(v, (list, tuple)):
                for lv in v:
                    hook(lv)
            elif isinstance(v, dict):
                for lv in v.values():
                    hook(lv)
            elif isinstance(v, Element):
                hook(v.props)
        hook(self.props)

    def collect_client_embed(self, component):
        def collect(e):
            children = e.props.get('children', [])
            for ch in children:
                if isinstance(ch, Element):
                    collect(ch)
            embeds = e.props.get(self.client_embed_attr_name, [])
            for key in list(e.props.keys()):
                if key in (self.client_embed_attr_name, 'children'):
                    continue
                value = e.props.get(key)
                if isinstance(value, ClientEmbed) and value.component == component:
                    if e.name == 'script':
                        value.embed_id = f'{value.embed_id}-object-{key}'
                    elif key[0] == '@':
                        value.embed_id = f'{value.embed_id}-event-{key[1:]}'
                    elif key[0] == '$':
                        value.embed_id = f'{value.embed_id}-attr-{key[1:]}'
                    elif key == '*':
                        value.embed_id = f'{value.embed_id}-text'
                    else:
                        raise RenderException
                    embeds.append(value)
                    e.props.pop(key)
            if embeds:
                e.props[self.client_embed_attr_name] = embeds
        collect(self)

    def render(self, page):
        """
        返回渲染后的元素。
        所有组件元素被渲染为基础元素（HTML元素），子元素列表中的子元素列表被摊平，属性值中不应再有元素
        """
        if self.rendered:
            return self

        if inspect.isfunction(self.name):
            # function component
            # 1. 执行组件函数，返回未渲染的原始组件元素树
            #    元素树中的js嵌入值以ClientEmbed对象表示，元素树中
            #    的ClientEmbed对象有两类，一类是从组件函数参数中传进来
            #    的父组件js嵌入值，一类是新生成的本组件js嵌入值。
            #    父组件js嵌入值中有父组件实例唯一编号，本组件js嵌入值
            #    中(暂时)不带组件实例唯一编号。
            #    其中：
            #    * 元素树中html元素属性和文本中的js嵌入值都被移到
            #      所在元素的data-fryembed属性值列表中；
            #    * 元素树中子组件元素属性中的js嵌入值，将被当做
            #      props值传入子组件函数中
            result = self.name(self.props)

            # 2. 生成页面内组件实例唯一编号
            #    组件函数每执行一次，返回该组件的一个实例。页面中
            #    每个组件实例都有一个页面内唯一编号。
            cnumber = page.add_component()

            # 3. 将组件实例唯一编号挂载到组件元素树的所有本组件生成的
            #    js嵌入值上，使每个js嵌入值具有页面内唯一标识，
            #    标识格式为：组件实例唯一编号/js嵌入值在组件内唯一编号
            result.hook_client_embed(cnumber)

            # 4. 从原始组件元素树根元素的属性中取出calljs属性值
            calljs = result.props.pop(call_client_script_attr_name, False)

            # 5. 原始组件元素树渲染为最终的html元素树，
            element = result.render(page)

            # 6. 此时已hook到组件实例的js嵌入值已挂载到html元素树上的合适
            #    位置，将这些js嵌入值收集到`self.client_embed_attr_name('data-fryembed')`属性上
            element.collect_client_embed(cnumber)
            
            # 7. 将组件名和组件实例ID附加到html元素树的树根元素上
            inner = element.props.get(self.component_attr_name, '')
            inner_id = element.props.get(self.component_id_attr_name, '')
            cname = component_name(self.name)
            element.props[self.component_attr_name] = f'{cname} {inner}' if inner else cname
            element.props[self.component_id_attr_name] = f'{cnumber} {inner_id}' if inner_id else str(cnumber)

            # 8. 如果当前组件存在js代码，将script脚本元素添加为树根元素的第一个子元素
            if calljs:
                uuid, args = calljs
                scriptprops = {
                    'src': static_url(fryconfig.js_url) + uuid + '.js',
                    #'defer': True,
                    self.component_id_attr_name: cnumber,
                    'children': [],
                }
                for k,v in args:
                    # 父组件实例传过来的js嵌入值
                    if isinstance(v, ClientEmbed):
                        scriptprops[k] = v
                    else:
                        scriptprops[f'data-{k}'] = v
                children = element.props['children']
                children.insert(0, Element('script', scriptprops, True))
        elif isinstance(self.name, str):
            props = {}
            for k, v in self.props.items():
                if k == 'children':
                    props[k] = render_children(v, page)
                elif isinstance(v, Element):
                    props[k] = v.render(page)
                else:
                    props[k] = v
            element = Element(self.name, props, True)
        else:
            raise RenderException(f"invalid element name '{self.name}'")

        return element


    def __str__(self):
        if not self.rendered:
            return '<Element(not rendered)>'

        children = self.props.pop('children', None)
        attrs = []
        for k, v in self.props.items():
            if isinstance(v, dict):
                values = []
                for k1, v1 in v.items():
                    values.append(f"{k1}: {v1};")
                value = ' '.join(values)
            elif isinstance(v, (list, tuple)):
                value = ' '.join(str(x) for x in v)
            elif v is True:
                value = ''
            elif v is False:
                continue
            else:
                value = str(v)
            if value:
                attrs.append(f'{k}="{escape(value)}"')
            else:
                attrs.append(k)
        if attrs:
            attrs = ' ' + ' '.join(attrs)
        else:
            attrs = ''
        if children is None:
            return f'<{self.name}{attrs} />'
        else:
            children = ''.join(str(ch) for ch in children)
            return f'<{self.name}{attrs}>{children}</{self.name}>'


Element.ClientEmbed = ClientEmbed
