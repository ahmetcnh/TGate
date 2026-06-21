class TGateError(Exception):
    pass


class LexError(TGateError):
    def __init__(self, line: int, column: int, char: str = '', *, message: str = ''):
        if message:
            msg = f"Lexical error at line {line}, column {column}: {message}"
        else:
            msg = f"Lexical error at line {line}, column {column}: unexpected character '{char}'"
        super().__init__(msg)
        self.line = line
        self.column = column


class ParseError(TGateError):
    def __init__(self, line: int, column: int, expected: str, found: str):
        # Show EOF explicitly rather than empty string so unclosed-brace errors are clear.
        found_display = 'EOF' if found == '' else f"'{found}'"
        super().__init__(
            f"Syntax error at line {line}, column {column}: expected {expected}, found {found_display}"
        )
        self.line = line
        self.column = column


class SemanticError(TGateError):
    def __init__(self, line: int, column: int, message: str):
        super().__init__(
            f"Semantic error at line {line}, column {column}: {message}"
        )
        self.line = line
        self.column = column


class TypeCheckError(TGateError):
    def __init__(self, line: int, column: int, message: str):
        super().__init__(
            f"Type error at line {line}, column {column}: {message}"
        )
        self.line = line
        self.column = column


class SimulationError(TGateError):
    def __init__(self, message: str):
        super().__init__(f"Simulation error: {message}")
