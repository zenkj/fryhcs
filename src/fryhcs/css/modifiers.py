import re

# css: wrapper1{wrapper2{selector{styles}}}
# wrapper: @xxx aaa and (ccc: ddd)
# selector: parent-modifier1 selector[attr=value]:modifier2
# styles: key1:value1;key2:value2;
append_template = '{selector}:{modifier}'
append_template2 = '{selector}::{modifier}'
selector_modifier_templates = {
    # pseudo classes
    'hover':             append_template,              # &:hover
    'focus':             append_template,              # &:focus
    'focus-within':      append_template,              # &:focus-within
    'focus-visible':     append_template,              # &:focus-visible
    'active':            append_template,              # &:active
    'visited':           append_template,              # &:visited
    'target':            append_template,              # &:target
    'first':             '{selector}:first-child',     # &:first-child
    'last':              '{selector}:last-child',      # &:last-child
    'only':              '{selector}:only-child',      # &:only-child
    'odd':               '{selector}:nth-child(odd)',  # &:nth-child(odd)
    'even':              '{selector}:nth-child(even)', # &:nth-child(even)
    'first-of-type':     append_template,              # &:first-of-type
    'last-of-type':      append_template,              # &:last-of-type
    'only-of-type':      append_template,              # &:only-of-type
    'empty':             append_template,              # &:empty
    'disabled':          append_template,              # &:disabled
    'enabled':           append_template,              # &:enabled
    'checked':           append_template,              # &:checked
    'indeterminate':     append_template,              # &:indeterminate
    'default':           append_template,              # &:default
    'required':          append_template,              # &:required
    'valid':             append_template,              # &:valid
    'invalid':           append_template,              # &:invalid
    'in-range':          append_template,              # &:in-range
    'out-of-range':      append_template,              # &:out-of-range
    'placeholder-shown': append_template,              # &:placeholder-shown
    'autofill':          append_template,              # &:autofill
    'read-only':         append_template,              # &:read-only

    'before':            append_template2,             # &::before
    'after':             append_template2,             # &::after
    'first-letter':      append_template2,             # &::first-letter
    'first-line':        append_template2,             # &::first-line
    'marker':            append_template2,             # &::marker
    'selection':         append_template2,             # &::selection
    'file':              append_template2,             # &::file-selector-button
    'backdrop':          append_template2,             # &::backdrop
    'placeholder':       append_template2,             # &::placeholder


    # aria
    'aria-checked':      '{selector}[aria-checked="true"]',  # &[aria-checked="true"]
    'aria-disabled':     '{selector}[aria-disabled="true"]', # &[aria-disabled="true"]
    'aria-expanded':     '{selector}[aria-expanded="true"]', # &[aria-expanded="true"]
    'aria-hidden':       '{selector}[aria-hidden="true"]',   # &[aria-hidden="true"]
    'aria-pressed':      '{selector}[aria-pressed="true"]',  # &[aria-pressed="true"]
    'aria-readonly':     '{selector}[aria-readonly="true"]', # &[aria-readonly="true"]
    'aria-required':     '{selector}[aria-required="true"]', # &[aria-required="true"]
    'aria-selected':     '{selector}[aria-selected="true"]', # &[aria-selected="true"]

    'rtl':                '[dir="rtl"] {selector}',          # [dir="rtl"] &
    'ltr':                '[dir="ltr"] {selector}',          # [dir="ltr"] &

    'open':               '{selector}[open]',                # &[open]

    # dark mode
    'dark':               '.dark {selector}, [dark=""] {selector}', # .dark & 
}

selector_modifiers = set(selector_modifier_templates.keys())

# 原先modifier是有中括号的，所以命名为re_brackets，现在把中括号去掉了。
#另外，为防止将utility误判为modifier，像"max-w-sm"之类的utility不使用re_brackets
#最后，发现很多正则没那么多共同点，不需要定义一个公共的正则了，去掉
#re_brackets = '(.+)'
re_selector_modifier_templates = {
    f'aria-(.+)':          r'{selector}[aria-{group1}]',       # &[aria-xxx]
    f'data-(.+)':          r'{selector}[data-{group1}]',       # &[data-xxx]
    f'group-([^@]+)':      r'.group:{group1} {selector}, [group=""]:{group1} {selector}',
    f'group-([^@]+)@(.+)': r'.group\@{group2}:{group1} {selector}, [group\@{group2}=""]:{group1} {selector}',
    f'peer-([^@]+)':       r'.peer:{group1} ~ {selector}, [peer=""]:{group1} ~ {selector}',
    f'peer-([^@]+)@(.+)':  r'.peer\@{group2}:{group1} + {selector}, [peer\@{group2}=""]:{group1} ~ {selector}',
}
re_selector_modifiers = set(re_selector_modifier_templates.keys())

wrapper_modifier_templates = {
    # responsive design
    'sm':            ('@media (min-width: 640px)', 640),                # @media (min-width: 640px)  { ... }
    'md':            ('@media (min-width: 768px)', 768),                # @media (min-width: 768px)  { ... }
    'lg':            ('@media (min-width: 1024px)', 1024),              # @media (min-width: 1024px) { ... }
    'xl':            ('@media (min-width: 1280px)', 1280),              # @media (min-width: 1280px) { ... }
    '2xl':           ('@media (min-width: 1536px)', 1536),              # @media (min-width: 1536px) { ... }
    'max-sm':        ('@media not all and (min-width: 640px)', -640),   # @media not all and (min-width: 640px) { ... }
    'max-md':        ('@media not all and (min-width: 768px)', -768),   # @media not all and (min-width: 768px) { ... }
    'max-lg':        ('@media not all and (min-width: 1024px)', -1024), # @media not all and (min-width: 1024px) { ... }
    'max-xl':        ('@media not all and (min-width: 1280px)', -1280), # @media not all and (min-width: 1280px) { ... }
    'max-2xl':       ('@media not all and (min-width: 1536px)', -1536), # @media not all and (min-width: 1536px) { ... }

    #'dark':          '@media (perfers-color-scheme: dark)',             # @media (perfers-color-scheme: dark) { ... }

    'portrait':      '@media (orientation: portrait)',                  # @media (orientation: portrait) { ... }
    'landscape':     '@media (orientation: landscape)',                 # @media (orientation: landscape) { ... }
    'motion-safe':   '@media (prefers-reduced-motion: no-preference)',  # @media (prefers-reduced-motion: no-preference) { ... }
    'motion-reduce': '@media (prefers-reduced-motion: reduce)',         # @media (prefers-reduced-motion: reduce) { ... }
    'contrast-more': '@media (prefers-contrast: more)',                 # @media (prefers-contrast: more) { ... }
    'contrast-less': '@media (prefers-contrast: less)',                 # @media (prefers-contrast: less) { ... }
    'print':         '@media print',                                    # @media print { ... }
}
wrapper_modifiers = set(wrapper_modifier_templates.keys())

re_wrapper_modifier_templates = {
    f'min-([0-9]+)px':         ('@media (min-width: {group1}px)', '{group1}'),    # @media (min-width: xxx) { ... }
    f'max-([0-9]+)px':         ('@media (max-width: {group1}px)', '-{group1}'),   # @media (max-width: xxx) { ... }
    f'supports-(.+)': '@supports ({group1})',                            # @supports (xxx) { ... }
}
re_wrapper_modifiers = set(re_wrapper_modifier_templates.keys())

all_modifiers = set(selector_modifiers)
all_modifiers.update(wrapper_modifiers)

re_all_modifiers = set(re_selector_modifiers)
re_all_modifiers.update(re_wrapper_modifiers)

def is_modifier(value):
    return (value in all_modifiers or
            any(re.fullmatch(pattern, value) for pattern in re_all_modifiers))


def is_modifiers(value):
    return value and all(is_modifier(v) for v in value.split(':'))


def add_modifier(css, modifier):
    css.order = css.DEFAULT_MODIFIER_ORDER

    def convert_template(template):
        if isinstance(template, tuple):
            template, order = template
            if order > css.order:
                css.order = order
        return template

    def convert_re_template(template, group1, group2):
        if isinstance(template, tuple):
            template, order = template
            order = int(order.format(group1=group1, group2=group2))
            if order > css.order:
                css.order = order
        return template

    if modifier in selector_modifiers:
        template = convert_template(selector_modifier_templates[modifier])
        css.selector = template.format(selector=css.selector, modifier=modifier)
        return True
    elif modifier in wrapper_modifiers:
        template = convert_template(wrapper_modifier_templates[modifier])
        css.wrappers.append(template)
        return True
    else:
        for pattern in re_selector_modifiers:
            match = re.fullmatch(pattern, modifier)
            if match:
                group1 = group2 = None
                ngroup = len(match.groups())
                if ngroup > 0:
                    group1 = css.quote(match.group(1))
                if ngroup > 1:
                    group2 = css.quote(match.group(2))
                template = convert_re_template(re_selector_modifier_templates[pattern], group1, group2)
                css.selector = template.format(selector=css.selector, group1=group1, group2=group2)
                return True

        for pattern in re_wrapper_modifiers:
            match = re.fullmatch(pattern, modifier)
            if match:
                group1 = group2 = None
                ngroup = len(match.groups())
                if ngroup > 0:
                    group1 = css.quote(match.group(1))
                if ngroup > 1:
                    group2 = css.quote(match.group(2))
                template = convert_re_template(re_wrapper_modifier_templates[pattern], group1, group2)
                css.wrappers.append(template.format(group1=group1, group2=group2))
                return True
        return False
