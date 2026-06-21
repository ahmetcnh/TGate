from dataclasses import dataclass
from enum import Enum, auto
from .errors import LexError


# ---------------------------------------------------------------------------
# ASCII character classification helpers
# These replace Python's built-in is* methods which accept Unicode codepoints.
# The TGate grammar defines IDENT and INT_LIT in terms of ASCII only.
# ---------------------------------------------------------------------------

def _is_ascii_letter(c: str) -> bool:
    return ('a' <= c <= 'z') or ('A' <= c <= 'Z')

def _is_ascii_digit(c: str) -> bool:
    return '0' <= c <= '9'

def _is_ident_start(c: str) -> bool:
    return _is_ascii_letter(c)

def _is_ident_part(c: str) -> bool:
    return _is_ascii_letter(c) or _is_ascii_digit(c) or c == '_'


class TokenType(Enum):
    # Keywords
    KW_GATE    = auto()
    KW_CIRCUIT = auto()
    KW_NODE    = auto()
    KW_WIRE    = auto()
    KW_PMOS    = auto()
    KW_NMOS    = auto()
    KW_IN      = auto()
    KW_OUT     = auto()
    KW_DRAIN   = auto()
    KW_SOURCE  = auto()
    KW_VDD     = auto()
    KW_GND     = auto()
    KW_GENERATE  = auto()
    KW_SIMULATE  = auto()
    KW_PARAM     = auto()
    KW_FROM      = auto()
    KW_TO        = auto()
    # Identifiers and literals
    IDENT      = auto()
    INT_LIT    = auto()
    # Operators / punctuation
    OP_NOT     = auto()   # !
    OP_AND     = auto()   # &
    OP_OR      = auto()   # |
    OP_PLUS    = auto()   # + (new — produces helpful error in parser when used in logic context)
    OP_MINUS   = auto()   # - (new — for param expressions like N-1)
    ARROW      = auto()   # ->
    ASSIGN     = auto()   # =
    COMMA      = auto()   # ,
    SEMICOLON  = auto()   # ;
    LPAREN     = auto()   # (
    RPAREN     = auto()   # )
    LBRACE     = auto()   # {
    RBRACE     = auto()   # }
    LBRACKET   = auto()   # [
    RBRACKET   = auto()   # ]
    RANGE      = auto()   # ..
    EOF        = auto()


KEYWORDS: dict[str, TokenType] = {
    'gate':    TokenType.KW_GATE,
    'circuit': TokenType.KW_CIRCUIT,
    'node':    TokenType.KW_NODE,
    'wire':    TokenType.KW_WIRE,
    'pmos':    TokenType.KW_PMOS,
    'nmos':    TokenType.KW_NMOS,
    'in':      TokenType.KW_IN,
    'out':     TokenType.KW_OUT,
    'drain':   TokenType.KW_DRAIN,
    'source':  TokenType.KW_SOURCE,
    'VDD':     TokenType.KW_VDD,
    'GND':     TokenType.KW_GND,
    'generate': TokenType.KW_GENERATE,
    'simulate': TokenType.KW_SIMULATE,
    'param':    TokenType.KW_PARAM,
    'from':     TokenType.KW_FROM,
    'to':       TokenType.KW_TO,
}


@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.lexeme!r}, {self.line}:{self.column})"


class Lexer:
    def __init__(self, source: str):
        self._src = source
        self._pos = 0
        self._line = 1
        self._col = 1

    def _peek(self) -> str:
        return self._src[self._pos] if self._pos < len(self._src) else ''

    def _peek2(self) -> str:
        return self._src[self._pos + 1] if self._pos + 1 < len(self._src) else ''

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == '\n':
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _skip_whitespace_and_comments(self) -> None:
        while self._pos < len(self._src):
            ch = self._peek()
            if ch in ' \t\r':
                self._advance()
            elif ch == '\n':
                self._advance()
            elif ch == '/' and self._peek2() == '/':
                while self._pos < len(self._src) and self._peek() != '\n':
                    self._advance()
            elif ch == '/' and self._peek2() == '*':
                start_line, start_col = self._line, self._col
                self._advance()  # /
                self._advance()  # *
                closed = False
                while self._pos < len(self._src):
                    if self._peek() == '*' and self._peek2() == '/':
                        self._advance()  # *
                        self._advance()  # /
                        closed = True
                        break
                    self._advance()
                if not closed:
                    raise LexError(start_line, start_col,
                                   message="unterminated block comment")
            else:
                break

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_whitespace_and_comments()
            if self._pos >= len(self._src):
                tokens.append(Token(TokenType.EOF, '', self._line, self._col))
                break

            line, col = self._line, self._col
            ch = self._peek()

            if ch == '-' and self._peek2() == '>':
                self._advance(); self._advance()
                tokens.append(Token(TokenType.ARROW, '->', line, col))
            elif ch == '-':
                self._advance()
                tokens.append(Token(TokenType.OP_MINUS, '-', line, col))
            elif ch == '!':
                self._advance()
                tokens.append(Token(TokenType.OP_NOT, '!', line, col))
            elif ch == '&':
                self._advance()
                tokens.append(Token(TokenType.OP_AND, '&', line, col))
            elif ch == '+':
                self._advance()
                tokens.append(Token(TokenType.OP_PLUS, '+', line, col))
            elif ch == '|':
                self._advance()
                tokens.append(Token(TokenType.OP_OR, '|', line, col))
            elif ch == '=':
                self._advance()
                tokens.append(Token(TokenType.ASSIGN, '=', line, col))
            elif ch == ',':
                self._advance()
                tokens.append(Token(TokenType.COMMA, ',', line, col))
            elif ch == ';':
                self._advance()
                tokens.append(Token(TokenType.SEMICOLON, ';', line, col))
            elif ch == '(':
                self._advance()
                tokens.append(Token(TokenType.LPAREN, '(', line, col))
            elif ch == ')':
                self._advance()
                tokens.append(Token(TokenType.RPAREN, ')', line, col))
            elif ch == '{':
                self._advance()
                tokens.append(Token(TokenType.LBRACE, '{', line, col))
            elif ch == '}':
                self._advance()
                tokens.append(Token(TokenType.RBRACE, '}', line, col))
            elif ch == '[':
                self._advance()
                tokens.append(Token(TokenType.LBRACKET, '[', line, col))
            elif ch == ']':
                self._advance()
                tokens.append(Token(TokenType.RBRACKET, ']', line, col))
            elif ch == '.' and self._peek2() == '.':
                self._advance(); self._advance()
                tokens.append(Token(TokenType.RANGE, '..', line, col))
            elif ch == '.':
                self._advance()
                raise LexError(line, col, '.', message="unexpected '.'; did you mean '..'?")
            elif _is_ascii_digit(ch):
                buf = ''
                while _is_ascii_digit(self._peek()):
                    buf += self._advance()
                tokens.append(Token(TokenType.INT_LIT, buf, line, col))
            elif _is_ident_start(ch):
                buf = ''
                while _is_ident_part(self._peek()):
                    buf += self._advance()
                tt = KEYWORDS.get(buf, TokenType.IDENT)
                tokens.append(Token(tt, buf, line, col))
            else:
                self._advance()
                raise LexError(line, col, ch)

        return tokens
