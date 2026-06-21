from .lexer import Token, TokenType
from .ast_nodes import (
    Program, GateDecl, CircuitDecl, SimulationCall,
    NodeDecl, TransistorStmt, WireDecl, InstanceStmt,
    SingleOutput, NamedOutputs, PortBinding,
    PortDecl, IndexLit, IndexName, SignalRef, GenerateStmt,
    NameRef, LitRef,
    LitExpr, NameExpr, NotExpr, AndExpr, OrExpr,
    SimArgBinding, VectorLit, ParamDecl,
)
from .errors import ParseError


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _peek_type(self) -> TokenType:
        return self._tokens[self._pos].type

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.type != TokenType.EOF:
            self._pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._peek_type() in types

    def _expect(self, tt: TokenType, expected_msg: str) -> Token:
        tok = self._peek()
        if tok.type != tt:
            raise ParseError(tok.line, tok.column, expected_msg, tok.lexeme)
        return self._advance()

    # ------------------------------------------------------------------
    # Port declarations
    # ------------------------------------------------------------------

    def parse_port_decl(self) -> PortDecl:
        tok = self._expect(TokenType.IDENT, "port name")
        size = None
        if self._check(TokenType.LBRACKET):
            self._advance()
            size_tok = self._peek()
            if size_tok.type == TokenType.INT_LIT:
                size = int(self._advance().lexeme)
            elif size_tok.type == TokenType.IDENT:
                size = self._advance().lexeme   # param name; resolved by elaborator
            else:
                raise ParseError(size_tok.line, size_tok.column,
                                 "integer literal or param name inside port size brackets",
                                 size_tok.lexeme)
            self._expect(TokenType.RBRACKET, "']' after port size")
        return PortDecl(name=tok.lexeme, size=size, line=tok.line, column=tok.column)

    def parse_port_decl_list(self) -> list:
        ports = [self.parse_port_decl()]
        while self._check(TokenType.COMMA):
            self._advance()
            ports.append(self.parse_port_decl())
        return ports

    # ------------------------------------------------------------------
    # Signal references and index expressions
    # ------------------------------------------------------------------

    def parse_index_expression(self):
        tok = self._peek()
        if tok.type == TokenType.INT_LIT:
            self._advance()
            return IndexLit(value=int(tok.lexeme))
        elif tok.type == TokenType.IDENT:
            self._advance()
            return IndexName(name=tok.lexeme)
        else:
            raise ParseError(tok.line, tok.column,
                             "integer literal or identifier as index expression",
                             tok.lexeme)

    def parse_range_bound_expr(self):
        """Parse a compile-time range bound: integer, param name, or param±offset."""
        tok = self._peek()
        if tok.type == TokenType.INT_LIT:
            self._advance()
            return int(tok.lexeme)
        elif tok.type == TokenType.IDENT:
            name = self._advance().lexeme
            if self._check(TokenType.OP_MINUS):
                self._advance()
                lit = self._expect(TokenType.INT_LIT, "integer after '-' in range bound")
                return f"{name}-{lit.lexeme}"
            elif self._check(TokenType.OP_PLUS):
                self._advance()
                lit = self._expect(TokenType.INT_LIT, "integer after '+' in range bound")
                return f"{name}+{lit.lexeme}"
            return name
        else:
            raise ParseError(tok.line, tok.column,
                             "integer literal or param name as range bound", tok.lexeme)

    def parse_signal_reference(self) -> SignalRef:
        tok = self._expect(TokenType.IDENT, "signal name")
        indices = []
        while self._check(TokenType.LBRACKET):
            self._advance()
            idx = self.parse_index_expression()
            self._expect(TokenType.RBRACKET, "']' after index expression")
            indices.append(idx)
        return SignalRef(name=tok.lexeme, indices=indices, line=tok.line, column=tok.column)

    # ------------------------------------------------------------------
    # Program
    # ------------------------------------------------------------------

    def parse_program(self) -> Program:
        items = []
        while not self._check(TokenType.EOF):
            items.append(self.parse_top_level_item())
        return Program(items=items)

    def parse_top_level_item(self):
        tok = self._peek()
        if tok.type == TokenType.KW_GATE:
            return self.parse_gate_decl()
        elif tok.type == TokenType.KW_CIRCUIT:
            return self.parse_circuit_decl()
        elif tok.type == TokenType.KW_SIMULATE:
            return self.parse_simulate_call()
        elif tok.type == TokenType.KW_PARAM:
            return self.parse_param_decl()
        elif tok.type == TokenType.IDENT:
            from .errors import TGateError
            raise TGateError(
                f"Syntax error at line {tok.line}, column {tok.column}: "
                f"unexpected identifier '{tok.lexeme}' at top level; "
                f"did you mean 'simulate {tok.lexeme}(...)' for a simulation call?"
            )
        else:
            raise ParseError(tok.line, tok.column,
                             "'gate', 'circuit', 'simulate', or 'param'", tok.lexeme)

    # ------------------------------------------------------------------
    # Gate declaration
    # ------------------------------------------------------------------

    def _expect_component_name(self, context: str) -> Token:
        """Accept IDENT, or KW_VDD/KW_GND so the semantic analyzer can reject them."""
        tok = self._peek()
        if tok.type in (TokenType.KW_VDD, TokenType.KW_GND):
            return self._advance()
        return self._expect(TokenType.IDENT, context)

    def parse_gate_decl(self) -> GateDecl:
        kw = self._advance()  # consume 'gate'
        name_tok = self._expect_component_name("gate name after 'gate'")
        self._expect(TokenType.LPAREN, "'(' after gate name")
        inputs, output = self.parse_gate_port_spec()
        self._expect(TokenType.RPAREN, "')' after gate port spec")
        self._expect(TokenType.LBRACE, "'{' to open gate body")
        body = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            body.append(self.parse_gate_body_item())
        self._expect(TokenType.RBRACE, "'}' to close gate body")
        return GateDecl(name=name_tok.lexeme, inputs=inputs, output=output,
                        body=body, line=kw.line, column=kw.column)

    def parse_gate_port_spec(self):
        self._expect(TokenType.KW_IN, "'in' to start port spec")
        inputs = self.parse_port_decl_list()
        tok = self._peek()
        if tok.type == TokenType.KW_OUT:
            raise ParseError(tok.line, tok.column,
                             "';' between input and output port sections", tok.lexeme)
        self._expect(TokenType.SEMICOLON, "';' between input and output port sections")
        self._expect(TokenType.KW_OUT, "'out' before output port name")
        output = self.parse_port_decl()
        if self._check(TokenType.COMMA):
            bad = self._peek()
            raise ParseError(bad.line, bad.column,
                             "')' after single output port (gate declarations have exactly one output)",
                             ",")
        return inputs, output

    # ------------------------------------------------------------------
    # Gate body items
    # ------------------------------------------------------------------

    def parse_gate_body_item(self):
        tok = self._peek()
        if tok.type == TokenType.KW_NODE:
            return self.parse_node_decl()
        elif tok.type in (TokenType.KW_PMOS, TokenType.KW_NMOS):
            return self.parse_transistor_stmt()
        elif tok.type == TokenType.KW_GENERATE:
            return self.parse_gate_generate_statement()
        elif tok.type == TokenType.KW_WIRE:
            raise ParseError(tok.line, tok.column,
                             "node declaration or transistor statement "
                             "('wire' is not allowed inside a gate body)",
                             tok.lexeme)
        else:
            raise ParseError(tok.line, tok.column,
                             "'node', 'pmos', or 'nmos'", tok.lexeme)

    def _parse_generate_statement(self, context: str, parse_body_item) -> GenerateStmt:
        kw = self._advance()  # consume 'generate'
        if self._check(TokenType.LPAREN):
            raise ParseError(kw.line, kw.column,
                "old generate syntax 'generate(i in 0..3)' is no longer supported; "
                "use: generate i from 0 to N { ... }")
        var_tok = self._expect(TokenType.IDENT, "generate variable name after 'generate'")
        self._expect(TokenType.KW_FROM, "'from' after generate variable")
        start = self.parse_range_bound_expr()
        self._expect(TokenType.KW_TO, "'to' after generate start bound")
        end = self.parse_range_bound_expr()
        self._expect(TokenType.LBRACE, "'{' to open generate body")
        body = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            body.append(parse_body_item())
        self._expect(TokenType.RBRACE, "'}' to close generate body")
        return GenerateStmt(var_name=var_tok.lexeme, start=start, end=end,
                            body=body, context=context,
                            line=kw.line, column=kw.column)

    def parse_gate_generate_statement(self) -> GenerateStmt:
        return self._parse_generate_statement("gate", self.parse_gate_generate_body_statement)

    def parse_gate_generate_body_statement(self):
        tok = self._peek()
        if tok.type == TokenType.KW_NODE:
            return self.parse_node_decl()
        elif tok.type in (TokenType.KW_PMOS, TokenType.KW_NMOS):
            return self.parse_transistor_stmt()
        elif tok.type == TokenType.KW_GENERATE:
            return self.parse_gate_generate_statement()
        elif tok.type == TokenType.IDENT:
            raise ParseError(tok.line, tok.column,
                             "gate generate body expects node declaration, "
                             "transistor statement, or nested generate "
                             "(component instance is not allowed inside gate generate)",
                             tok.lexeme)
        else:
            raise ParseError(tok.line, tok.column,
                             "gate generate body expects node declaration, "
                             "transistor statement, or nested generate",
                             tok.lexeme)

    def parse_node_decl(self) -> NodeDecl:
        kw = self._advance()  # consume 'node'
        names = [self._expect(TokenType.IDENT, "node name after 'node'").lexeme]
        while self._check(TokenType.COMMA):
            self._advance()
            names.append(self._expect(TokenType.IDENT, "node name").lexeme)
        self._expect(TokenType.SEMICOLON, "';' after node declaration")
        return NodeDecl(names=names, line=kw.line, column=kw.column)

    def parse_transistor_stmt(self) -> TransistorStmt:
        kw = self._advance()  # consume 'pmos' or 'nmos'
        kind = kw.lexeme

        # drain = <net>
        tok = self._peek()
        if tok.type != TokenType.KW_DRAIN:
            raise ParseError(tok.line, tok.column,
                             f"'drain' as first terminal "
                             f"(terminals must be in order: drain, gate, source)",
                             tok.lexeme)
        self._advance()  # drain
        self._expect(TokenType.ASSIGN, "'=' after 'drain'")
        drain = self.parse_net_ref()

        # comma after drain
        tok = self._peek()
        if tok.type != TokenType.COMMA:
            raise ParseError(tok.line, tok.column,
                             "',' after drain net reference", tok.lexeme)
        self._advance()

        # gate = <net>  (KW_GATE doubles as the terminal label here)
        tok = self._peek()
        if tok.type != TokenType.KW_GATE:
            raise ParseError(tok.line, tok.column,
                             "'gate' as second terminal "
                             "(terminals must be in order: drain, gate, source)",
                             tok.lexeme)
        self._advance()  # gate
        self._expect(TokenType.ASSIGN, "'=' after 'gate'")
        gate_net = self.parse_net_ref()

        # comma after gate
        tok = self._peek()
        if tok.type != TokenType.COMMA:
            raise ParseError(tok.line, tok.column,
                             "',' after gate net reference", tok.lexeme)
        self._advance()

        # source = <net>
        tok = self._peek()
        if tok.type != TokenType.KW_SOURCE:
            raise ParseError(tok.line, tok.column,
                             "'source' as third terminal", tok.lexeme)
        self._advance()  # source
        self._expect(TokenType.ASSIGN, "'=' after 'source'")
        source = self.parse_net_ref()

        self._expect(TokenType.SEMICOLON, "';' after transistor statement")
        return TransistorStmt(kind=kind, drain=drain, gate=gate_net,
                              source=source, line=kw.line, column=kw.column)

    # ------------------------------------------------------------------
    # Circuit declaration
    # ------------------------------------------------------------------

    def parse_circuit_decl(self) -> CircuitDecl:
        kw = self._advance()  # consume 'circuit'
        name_tok = self._expect_component_name("circuit name after 'circuit'")
        self._expect(TokenType.LPAREN, "'(' after circuit name")
        inputs, outputs = self.parse_circuit_port_spec()
        self._expect(TokenType.RPAREN, "')' after circuit port spec")
        self._expect(TokenType.LBRACE, "'{' to open circuit body")
        body = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            body.append(self.parse_circuit_body_item())
        self._expect(TokenType.RBRACE, "'}' to close circuit body")
        return CircuitDecl(name=name_tok.lexeme, inputs=inputs, outputs=outputs,
                           body=body, line=kw.line, column=kw.column)

    def parse_circuit_port_spec(self):
        self._expect(TokenType.KW_IN, "'in' to start port spec")
        inputs = self.parse_port_decl_list()
        tok = self._peek()
        if tok.type == TokenType.KW_OUT:
            raise ParseError(tok.line, tok.column,
                             "';' between input and output port sections", tok.lexeme)
        self._expect(TokenType.SEMICOLON, "';' between input and output port sections")
        self._expect(TokenType.KW_OUT, "'out' before output port names")
        outputs = self.parse_port_decl_list()
        return inputs, outputs

    # ------------------------------------------------------------------
    # Circuit body items
    # ------------------------------------------------------------------

    def parse_circuit_body_item(self):
        tok = self._peek()
        if tok.type == TokenType.KW_WIRE:
            return self.parse_wire_decl()
        elif tok.type == TokenType.KW_GENERATE:
            return self.parse_circuit_generate_statement()
        elif tok.type == TokenType.IDENT:
            return self.parse_instance_stmt()
        elif tok.type == TokenType.KW_NODE:
            raise ParseError(tok.line, tok.column,
                             "wire declaration or component instance "
                             "('node' is not allowed inside a circuit body)",
                             tok.lexeme)
        else:
            raise ParseError(tok.line, tok.column,
                             "'wire', 'generate', or component instance identifier",
                             tok.lexeme)

    def parse_circuit_generate_statement(self) -> GenerateStmt:
        return self._parse_generate_statement("circuit", self.parse_circuit_generate_body_statement)

    def parse_circuit_generate_body_statement(self):
        tok = self._peek()
        if tok.type == TokenType.KW_WIRE:
            return self.parse_wire_decl()
        elif tok.type == TokenType.KW_GENERATE:
            return self.parse_circuit_generate_statement()
        elif tok.type == TokenType.IDENT:
            return self.parse_instance_stmt()
        elif tok.type in (TokenType.KW_PMOS, TokenType.KW_NMOS):
            raise ParseError(tok.line, tok.column,
                             "circuit generate body expects wire declaration, "
                             "component instance, or nested generate "
                             "(transistor statement is not allowed inside circuit generate)",
                             tok.lexeme)
        else:
            raise ParseError(tok.line, tok.column,
                             "circuit generate body expects wire declaration, "
                             "component instance, or nested generate",
                             tok.lexeme)

    def parse_wire_decl(self) -> WireDecl:
        kw = self._advance()  # consume 'wire'
        ports = self.parse_port_decl_list()
        self._expect(TokenType.SEMICOLON, "';' after wire declaration")
        return WireDecl(ports=ports, line=kw.line, column=kw.column)

    def parse_instance_stmt(self) -> InstanceStmt:
        ref_tok = self._advance()  # component type name (e.g. NAND2)
        label_tok = self._expect(TokenType.IDENT, "instance label after component name")
        self._expect(TokenType.LPAREN, "'(' after instance label")
        args = []
        if not self._check(TokenType.RPAREN):
            args = self.parse_arg_list()
        self._expect(TokenType.RPAREN, "')' after instance argument list")
        tok = self._peek()
        if tok.type != TokenType.ARROW:
            raise ParseError(tok.line, tok.column,
                             "'->' after instance argument list", tok.lexeme)
        self._advance()  # ->
        binding = self.parse_output_binding()
        self._expect(TokenType.SEMICOLON, "';' after instance statement")
        return InstanceStmt(ref_name=ref_tok.lexeme, label=label_tok.lexeme,
                            args=args, binding=binding,
                            line=ref_tok.line, column=ref_tok.column)

    def parse_output_binding(self):
        if self._check(TokenType.LBRACE):
            self._advance()
            bindings = [self.parse_port_binding()]
            while self._check(TokenType.COMMA):
                self._advance()
                bindings.append(self.parse_port_binding())
            self._expect(TokenType.RBRACE, "'}' to close named output binding")
            return NamedOutputs(bindings=bindings)
        else:
            sig = self.parse_signal_reference()
            return SingleOutput(net=sig)

    def parse_port_binding(self) -> PortBinding:
        name_tok = self._expect(TokenType.IDENT, "port name in output binding")
        self._expect(TokenType.ASSIGN, "'=' after port name in output binding")
        sig = self.parse_signal_reference()
        return PortBinding(port_name=name_tok.lexeme, net=sig,
                           line=name_tok.line, column=name_tok.column)

    def parse_arg_list(self) -> list:
        args = [self.parse_signal_reference()]
        while self._check(TokenType.COMMA):
            self._advance()
            args.append(self.parse_signal_reference())
        return args

    # ------------------------------------------------------------------
    # Net references  (structural — identifiers, integers, VDD, GND)
    # ------------------------------------------------------------------

    def parse_net_ref(self):
        tok = self._peek()
        if tok.type == TokenType.IDENT:
            return self.parse_signal_reference()
        elif tok.type == TokenType.KW_VDD:
            self._advance()
            return NameRef(name='VDD')
        elif tok.type == TokenType.KW_GND:
            self._advance()
            return NameRef(name='GND')
        else:
            raise ParseError(tok.line, tok.column,
                             "signal reference, VDD, or GND",
                             tok.lexeme)

    # ------------------------------------------------------------------
    # Simulation call  (top-level only)
    # ------------------------------------------------------------------

    def parse_simulate_call(self) -> SimulationCall:
        kw = self._advance()  # consume 'simulate'
        ref_tok = self._expect(TokenType.IDENT, "component name after 'simulate'")
        self._expect(TokenType.LPAREN, "'(' after component name in simulate call")
        args = []
        if not self._check(TokenType.RPAREN):
            args = self.parse_sim_named_arg_list()
        self._expect(TokenType.RPAREN, "')' after simulate arguments")
        self._expect(TokenType.SEMICOLON, "';' after simulate call")
        return SimulationCall(ref_name=ref_tok.lexeme, args=args,
                              line=kw.line, column=kw.column)

    def parse_sim_named_arg_list(self) -> list:
        args = [self.parse_sim_named_arg()]
        while self._check(TokenType.COMMA):
            self._advance()
            args.append(self.parse_sim_named_arg())
        return args

    def parse_sim_named_arg(self):
        name_tok = self._expect(TokenType.IDENT, "argument name in simulate call")
        self._expect(TokenType.ASSIGN, "'=' after argument name")
        if self._check(TokenType.LBRACKET):
            value = self.parse_vector_literal()
        else:
            value = self.parse_logic_expr()
        return SimArgBinding(name=name_tok.lexeme, value=value,
                             line=name_tok.line, column=name_tok.column)

    def parse_vector_literal(self):
        lbr = self._advance()  # consume '['
        bits = []
        if not self._check(TokenType.RBRACKET):
            tok = self._peek()
            if tok.type != TokenType.INT_LIT or tok.lexeme not in ('0', '1'):
                raise ParseError(tok.line, tok.column,
                                 "0 or 1 inside vector literal", tok.lexeme)
            bits.append(int(self._advance().lexeme))
            while self._check(TokenType.COMMA):
                self._advance()
                tok = self._peek()
                if tok.type != TokenType.INT_LIT or tok.lexeme not in ('0', '1'):
                    raise ParseError(tok.line, tok.column,
                                     "0 or 1 inside vector literal", tok.lexeme)
                bits.append(int(self._advance().lexeme))
        self._expect(TokenType.RBRACKET, "']' to close vector literal")
        return VectorLit(bits=bits, line=lbr.line, column=lbr.column)

    def parse_param_decl(self):
        kw = self._advance()  # consume 'param'
        name_tok = self._expect(TokenType.IDENT, "param name after 'param'")
        self._expect(TokenType.ASSIGN, "'=' after param name")
        val_tok = self._expect(TokenType.INT_LIT, "integer value after '='")
        self._expect(TokenType.SEMICOLON, "';' after param declaration")
        return ParamDecl(name=name_tok.lexeme, value=int(val_tok.lexeme),
                         line=kw.line, column=kw.column)

    # ------------------------------------------------------------------
    # Logic expressions  (simulation arguments only)
    # Precedence: ! (highest) > & > | (lowest)
    # ------------------------------------------------------------------

    def parse_logic_expr(self):
        return self.parse_or_expr()

    def parse_or_expr(self):
        left = self.parse_and_expr()
        while self._check(TokenType.OP_OR):
            self._advance()
            right = self.parse_and_expr()
            left = OrExpr(left=left, right=right)
        if self._check(TokenType.OP_PLUS):
            tok = self._peek()
            from .errors import TGateError
            raise TGateError(
                f"Syntax error at line {tok.line}, column {tok.column}: "
                f"'+' is not a valid logic operator; use '|' for logical OR"
            )
        return left

    def parse_and_expr(self):
        left = self.parse_not_expr()
        while self._check(TokenType.OP_AND):
            self._advance()
            right = self.parse_not_expr()
            left = AndExpr(left=left, right=right)
        return left

    def parse_not_expr(self):
        if self._check(TokenType.OP_NOT):
            self._advance()
            operand = self.parse_not_expr()
            return NotExpr(operand=operand)
        return self.parse_primary()

    def parse_primary(self):
        tok = self._peek()
        if tok.type == TokenType.INT_LIT:
            if tok.lexeme not in ('0', '1'):
                raise ParseError(tok.line, tok.column,
                                 "logic literal '0' or '1'",
                                 tok.lexeme)
            self._advance()
            return LitExpr(value=int(tok.lexeme))
        elif tok.type == TokenType.LPAREN:
            self._advance()
            expr = self.parse_logic_expr()
            self._expect(TokenType.RPAREN, "')' to close parenthesised expression")
            return expr
        else:
            raise ParseError(tok.line, tok.column,
                             "logic literal '0' or '1', or '(' in logic expression",
                             tok.lexeme)
