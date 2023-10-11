from collections import defaultdict
from pathlib import Path

class FileIter():
    def __init__(self, input_files=[]):
        self.path_globs = defaultdict(set)
        self.files = set()
        for file in input_files:
            if isinstance(file, str):
                self.add_file(file)
            elif isinstance(file, (tuple, list)):
                dir = file[0]
                for glob in file[1:]:
                    self.add_glob(dir, glob)

    def add_glob(self, path, glob):
        path = Path(path)
        try:
            path = path.absolute()
        except FileNotFoundError:
            return
        self.path_globs[path].add(glob)

    def add_file(self, file):
        path = Path(file)
        try:
            path = path.absolute()
        except FileNotFoundError:
            return
        self.files.add(path)

    def all_files(self):
        seen_files = set()
        for path, globs in self.path_globs.items():
            for glob in globs:
                for file in path.glob(glob):
                    if file in seen_files:
                        continue
                    seen_files.add(file)
                    yield file
        for file in self.files:
            if file in seen_files:
                continue
            seen_files.add(file)
            yield file
