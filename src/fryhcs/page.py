from fryhcs.element import Element
from fryhcs.utils import static_url
from fryhcs.config import fryconfig

class Page(object):
    def __init__(self):
        self.component_count = 0

    def add_component(self):
        self.component_count += 1
        return self.component_count


def html(content='', title='', lang='en', rootclass='', charset='utf-8', viewport="width=device-width, initial-scale=1.0", metas={}, properties={}, equivs={}):
    sep = '\n    '

    if isinstance(content, Element):
        page = Page()
        content = content.render(page)
    elif callable(content) and getattr(content, '__name__', 'anonym')[0].isupper():
        page = Page()
        content = Element(content).render(page)

    metas = sep.join(f'<meta name="{name}" content="{value}">'
                       for name, value in metas.items())
    properties = sep.join(f'<meta property="{property}" content="{value}">'
                            for property, value in properties.items())
    equivs = sep.join(f'<meta http-equiv="{equiv}" content="{value}">'
                            for equiv, value in equivs.items())
    importmap = f'''
    <script type="importmap">
      {{
        "imports": {{
          "fryhcs": "{static_url('js/fryhcs.js')}",
          "components/": "{static_url(fryconfig.js_url)}",
          "@/": "{static_url('/')}"
        }}
      }}
    </script>
    '''

    if fryconfig.debug:
        script = """
  <script type="module">
    let serverId = undefined
    async function checkAutoReload() {
        let reload = false
        try {
            let resp = await fetch("{{autoReloadPath}}")
            let data = await resp.json()
            if (serverId === undefined) {
                serverId = data.serverId
            } else if (serverId !== data.serverId) {
                reload = true
                location.reload()
            }
        } catch(err) { }
        if (!reload) {
            setTimeout(checkAutoReload, 1000)
        }
    }
    checkAutoReload()
  </script>
"""
        autoreload = script.replace('{{autoReloadPath}}', fryconfig.check_reload_url)
    else:
        autoreload = ''

    if rootclass:
        rootclass = f' class="{rootclass}"'
    else:
        rootclass = ''

    return f'''\
<!DOCTYPE html>
<html lang={lang}{rootclass}>
  <head>
    <meta charset="{charset}">
    <title>{title}</title>
    <meta name="viewport" content="{viewport}">
    {metas}
    {properties}
    {equivs}
    <link rel="stylesheet" href="{static_url(fryconfig.css_url)}">
    {importmap}
  </head>
  <body>
    {content}
    <script>
      (async function () {{
        if ('fryfunctions$$' in window) {{
          for (const [script, fn] of window.fryfunctions$$) {{
            await fn(script);
          }}
        }}
      }})();
    </script>
    {autoreload}
  </body>
</html>
'''
