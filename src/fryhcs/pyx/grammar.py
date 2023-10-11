from parsimonious import Grammar
from pathlib import Path

def load_grammar():
    grammar_file = Path(__file__).parent / 'pyx.ppeg'
    with grammar_file.open('r') as gf:
        grammar_text = gf.read()
    return Grammar(grammar_text)

grammar = load_grammar()
