from parsimonious import NodeVisitor, VisitationError
from collections import defaultdict

import re

from fryhcs.fileiter import FileIter
from fryhcs.pyx.grammar import grammar

class BaseCollector():
    ignored_tags = ('head', 'title', 'meta', 'style', 'link', 'script', 'template')

    def __init__(self):
        self.fileiter = FileIter()
        self.attrs = defaultdict(set)
        self.classes = set()

    def add_glob(self, path, glob):
        self.fileiter.add_glob(path, glob)

    def add_file(self, file):
        self.fileiter.add_file(file)

    def collect_attrs(self):
        for file in self.fileiter.all_files():
            with file.open('r') as f:
                self.collect_from_content(f.read())

    def collect_from_content(self, data):
        pass

    def collect_kv(self, k, v):
        if not v: v = ""
        if len(v) > 1 and v[0] in "\"'":
            v = v[1:-1]
        vs = v.split()
        if not k or k == 'class':
            self.classes.update(vs)
        else:
            self.attrs[k].update(vs)

    def all_attrs(self):
        for cls in self.classes:
            yield '', cls
        for k, vs in self.attrs.items():
            if not vs:
                vs.add('')
            for v in vs:
                yield k, v


class RegexCollector(BaseCollector):
    tagname = r'([a-zA-Z0-9]+)'
    attrname = r"""[^\s"'>/=]+"""
    attrvalue = r"""'[^']*'|"[^"]*"|[^\s"'=><`]+"""
    attr = r"""[^"'>]*|"[^"]*"|'[^']*'"""

    #(?:xxx)表示不取值的group
    starttag_re = re.compile(f"<{tagname}((?:{attr})*)/?>")
    attr_re = re.compile(f"({attrname})(?:\s*=\s*({attrvalue}))?")

    def collect_from_content(self, data):
        for starttag in self.starttag_re.finditer(data):
            name = starttag.group(1)
            attrs = starttag.group(2)
            if name in self.ignored_tags:
                continue
            if not attrs:
                continue
            for attr in self.attr_re.finditer(attrs):
                self.collect_kv(attr.group(1), attr.group(2))


class CssVisitor(NodeVisitor):
    def __init__(self, collect_kv):
        self.collect_kv = collect_kv

    def collect_literal(self, css_literal):
        if css_literal:
            for css in css_literal.split():
                eq = css.find('=')
                if eq >= 0:
                    key = css[:eq]
                    value = css[eq+1:]
                else:
                    key = css
                    value = ''
                self.collect_kv(key, value)

    def generic_visit(self, node, children):
        return None

    def visit_single_quote(self, node, children):
        return node.text

    def visit_double_quote(self, node, children):
        return node.text

    def visit_simple_quote(self, node, children):
        return children[0]

    def visit_pyx_self_closing_element(self, node, children):
        _, name, attrs, _, _ = children
        if not name[0].islower():
            return
        for attr in attrs:
            if isinstance(attr, str):
                self.collect_literal(attr)
            elif isinstance(attr, tuple):
                self.collect_kv(attr[0], attr[1])

    def visit_pyx_start_tag(self, node, children):
        _, start_name, attrs, _, _ = children
        if not start_name[0].islower():
            return
        for attr in attrs:
            if isinstance(attr, str):
                self.collect_literal(attr)
            elif isinstance(attr, tuple):
                self.collect_kv(attr[0], attr[1])

    def visit_pyx_element_name(self, node, children):
        return node.text

    def visit_pyx_attributes(self, node, children):
        return children

    def visit_pyx_spaced_attribute(self, node, children):
        _, attr = children
        return attr

    def visit_pyx_attribute(self, node, children):
        return children[0]

    def visit_pyx_embed_spread_attribute(self, node, children):
        _lbrace, _, _stars, _, _script, _rbrace, _, css_literal = children
        return css_literal

    #def visit_pyx_client_embed_attribute(self, node, children):
    #    _value, _, css_literal = children
    #    return css_literal

    def visit_pyx_kv_attribute(self, node, children):
        name, _, _, _, value = children
        if isinstance(value, str):
            return (name, value)

    def visit_pyx_novalue_attribute(self, node, children):
        name, _ = children
        return (name, '')

    def visit_pyx_attribute_name(self, node, children):
        return node.text

    def visit_pyx_attribute_value(self, node, children):
        return children[0]

    def visit_pyx_attr_value_embed(self, node, children):
        _embed, _, _client_embed, _, css_literal = children
        return css_literal

    def visit_pyx_attr_value_client_embed(self, node, children):
        value, _, css_literal = children
        _name, literal, _client_embed = value
        if isinstance(css_literal, str):
            if len(css_literal) > 0 and css_literal[0] in '"\'':
                css_literal = css_literal[1:-1]
            value = literal + ' ' + css_literal
        else:
            value = literal
        return value

    def visit_pyx_css_literal(self, node, children):
        _colon, _, value = children
        return value

    def visit_maybe_css_literal(self, node, children):
        if not children:
            return None
        return children[0]

    def visit_client_embed_value(self, node, children):
        _l, literal, _r, _, client_embed = children
        return ('client_embed', literal, client_embed)

    def visit_client_embed(self, node, children):
        return '' 

    def visit_maybe_client_embed(self, node, children):
        return ''


class ParserCollector(BaseCollector):
    def collect_from_content(self, data):
        tree = grammar.parse(data)
        visitor = CssVisitor(self.collect_kv)
        visitor.visit(tree)

Collector = ParserCollector


if __name__ == '__main__':
    collector = Collector()
    collector.add_glob('test', '**/*.html')
    collector.collect_attrs()
    print("classes:")
    for cls in collector.classes:
        print("", cls)

    print("attrs:")
    for k,v in collector.attrs.items():
        print("", k, "\t\t", v)
