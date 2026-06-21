import argparse
import sys
from .lexer import Lexer
from .parser import Parser
from .errors import TGateError


def main() -> None:
    ap = argparse.ArgumentParser(
        prog='tgate',
        description='TGate DSL — parser, type checker, and simulator')
    ap.add_argument('file', help='Path to a .tg source file')
    ap.add_argument('--dump-ast', action='store_true',
                    help='Print the AST after a successful parse (parse-only mode)')
    ap.add_argument('--tokens', action='store_true',
                    help='Print the token stream and exit')
    ap.add_argument('--run', action='store_true',
                    help='Elaborate, type-check, and simulate')
    ap.add_argument('--truth-table', metavar='COMPONENT',
                    help='Print truth table for a scalar-input component')
    args = ap.parse_args()

    try:
        source = open(args.file, encoding='utf-8').read()
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        tokens = Lexer(source).tokenize()
    except TGateError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if args.tokens:
        for tok in tokens:
            print(tok)
        sys.exit(0)

    try:
        program = Parser(tokens).parse_program()
    except TGateError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if not args.run and not args.truth_table:
        print("Parse successful.")
        if args.dump_ast:
            print(program.dump())
        sys.exit(0)

    # Full pipeline: elaborate -> semantic analysis -> type check -> simulate/table
    from .elaborator import Elaborator
    from .semantics import SemanticAnalyzer
    from .type_checker import TypeChecker
    from .interpreter import run_simulation, print_truth_table

    try:
        elaborated = Elaborator(program).elaborate()
        analyzer = SemanticAnalyzer(elaborated)
        analyzer.analyze()
        TypeChecker(elaborated, analyzer.components).check()
        if args.run:
            run_simulation(elaborated, analyzer.components)
        if args.truth_table:
            print_truth_table(args.truth_table, analyzer.components)
    except TGateError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
