# Development moves to [frybox/fryhcs](https://github.com/frybox/fryhcs)
# fryhcs
A python library to generate HTML, Javascript and CSS, based on pyx file.

## Features
* Support pyx extension to normal py file, similar to jsx, html tags can be written directly in py files.
* Provide a pyx file loader for python import machanism, pyx files can be loaded and executed by CPython directly.
* Provide a utility first css framework, similar to TailwindCSS, support attributify mode similar to WindiCSS
* Can be used with django/flask framework.
* Provide a command line tool `fry` based on flask. 
* Provide development server which support server auto reload and browser auto reload when file saved.

All features are implemented in python, no node ecosystem is required.
