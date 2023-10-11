from pathlib import Path
import os

from .style import CSS
from .collector import Collector


class CSSGenerator():
    def __init__(self, input_files, output_file):
        self.input_files = input_files
        self.output_file = Path(output_file).absolute()
        self.reset()

    def reset(self):
        self.selectors = set()
        self.init_collector()

    def init_collector(self):
        self.collector = Collector()
        for file in self.input_files:
            if isinstance(file, str):
                self.collector.add_file(file)
            elif isinstance(file, (tuple, list)):
                dir = file[0]
                for glob in file[1:]:
                    self.collector.add_glob(dir, glob)

    def generate(self, input_file=None):
        """
        如果input_file为空，则是一个全量生成css；
        如果input_file不为空，则是一个增量生成css，只生成input_file的css，
        此时注意，input_file中的**所有**样式都会重新生成一遍，附加到css
        文件最后，会有很多样式重复生成，这是故意为之，目的是防止样式顺序
        错误，因为样式的顺序决定了样式的优先级，同样优先级的selector下，
        后面的样式会覆盖前面的样式。
        """
        # 1. collect all utilities from configed files
        if input_file:
            collector = Collector()
            collector.add_file(input_file)
            incremental = True
        else:
            self.reset()
            collector = self.collector
            incremental = False

        collector.collect_attrs()

        # 2. generate and write css
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        preflight = os.path.join(os.path.dirname(__file__), 'preflight.css')
        with self.output_file.open('a' if incremental else 'w') as f:
            if not incremental:
                with open(preflight, 'r') as pf:
                    f.write(pf.read())
            csses = []
            for key, value in collector.all_attrs():
                css = CSS(key, value)
                if css.valid:
                    csses.append(css)
            for css in sorted(csses, key=lambda c: c.order):
                f.write(css.text())
