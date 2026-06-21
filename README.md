# TGate (TransistorGate) — Parts 1 & 2

TGate is a domain-specific language for describing CMOS-style digital logic circuits at the transistor level. A `.tg` file contains gate declarations (primitive transistor-level building blocks), circuit declarations (structural compositions), optional `param` constants, and top-level `simulate` calls.

---

## Quick Start

```
python main.py tg_parser/tests/valid/valid1_inv.tg --run
```
Output:
```
INV(a=0) -> y=1
INV(a=1) -> y=0
```

```
python main.py tg_parser/tests/valid/valid3_half_adder.tg --truth-table HalfAdder
```
Output:
```
HalfAdder truth table:
a b | sum carry
0 0 | 0 0
0 1 | 1 0
1 0 | 1 0
1 1 | 0 1
```

---

## Requirements

- Python 3.10 or later
- No third-party packages — standard library only

---

## Project Structure

```
TGate/                         <- project root — run all commands from here
  main.py                      <- entry point
  tg_parser/
    __init__.py
    errors.py                  <- TGateError, LexError, ParseError, ...
    lexer.py                   <- TokenType, Token, Lexer
    ast_nodes.py               <- all AST dataclasses + dump()
    parser.py                  <- recursive-descent Parser
    elaborator.py              <- generate expansion + param resolution
    semantics.py               <- two-pass name resolution
    type_checker.py            <- logic / logic[N] type system
    interpreter.py             <- simulation engine + truth table
    main.py                    <- CLI (argparse)
    README.md                  <- this file
    tests/
      valid/
      invalid/
      edge_cases/
      semantic/
      type_errors/
      runtime_errors/
      simulation/
```

---

## CLI Flags

| Flag | Description |
|------|-------------|
| *(none)* | Parse only — print "Parse successful." |
| `--tokens` | Dump the token stream and exit |
| `--dump-ast` | Print the AST after parsing |
| `--run` | Elaborate, type-check, simulate all `simulate` calls |
| `--truth-table COMP` | Print truth table for the named component |

---

## Language Reference

### param declarations

Compile-time integer constants, used in port sizes and generate ranges:

```
param N = 4;

gate INV_ARRAY(in a[N]; out y[N]) {
    generate i from 0 to N-1 {
        pmos drain=y[i], gate=a[i], source=VDD;
        nmos drain=y[i], gate=a[i], source=GND;
    }
}
```

- `param` declarations are top-level only and must appear before they are used.
- Port widths may reference param names: `logic[N]`.
- Generate bounds may be integer literals, param names, `PARAM-INT`, or `PARAM+INT`.

### Logic operators

| Operator | Meaning | Precedence |
|----------|---------|------------|
| `!` | NOT (unary) | highest |
| `&` | AND | middle |
| `\|` | OR | lowest |

```
simulate NAND2(a=!0, b=1 & 0 | 1);
```

> **Note:** The `+` operator is **not** valid for logical OR. Using `+` in a logic expression is a syntax error with a helpful message.

### simulate calls with named arguments

Every simulation call must use the `simulate` keyword and name its arguments:

```
simulate INV(a=0);
simulate NAND2(a=0, b=1);
simulate HalfAdder(a=1, b=0);
```

Arguments can be logic expressions (`0`, `1`, `!0`, `1 & 0 | 1`, etc.) for scalar ports.

### Vector literals for array ports

Array ports use vector literals — a comma-separated list of bits in brackets:

```
simulate INV_ARRAY(a=[0, 1, 0, 1]);
simulate NAND_ARRAY(a=[0, 0, 0, 1], b=[1, 0, 1, 1]);
```

The vector length must match the declared port width exactly. Each bit must be `0` or `1`.

### generate syntax

Generate blocks replicate hardware structure at compile time. The range is inclusive on both ends:

```
generate i from 0 to N-1 {
    NAND2 g_i(a[i], b[i]) -> y[i];
}
```

`generate i from 0 to 3` produces indices 0, 1, 2, 3 (four iterations).

**Gate generate** (inside gate bodies): may contain node declarations, transistor statements, and nested gate generates.

**Circuit generate** (inside circuit bodies): may contain wire declarations, component instance statements, and nested circuit generates.

---

## Simulation Examples

### INV gate

```
python main.py tg_parser/tests/valid/valid1_inv.tg --run
```
```
INV(a=0) -> y=1
INV(a=1) -> y=0
```

### NAND2 gate

```
python main.py tg_parser/tests/valid/valid2_nand2.tg --run
```
```
NAND2(a=0, b=0) -> y=1
NAND2(a=0, b=1) -> y=1
NAND2(a=1, b=1) -> y=0
```

### HalfAdder circuit

```
python main.py tg_parser/tests/valid/valid3_half_adder.tg --run
```
```
HalfAdder(a=0, b=0) -> sum=0, carry=0
HalfAdder(a=0, b=1) -> sum=1, carry=0
HalfAdder(a=1, b=1) -> sum=0, carry=1
```

### 4-bit inverter array

```
python main.py tg_parser/tests/simulation/d3_program2_inv_array.tg --run
```
```
INV_ARRAY(a=[0, 1, 0, 1]) -> y[0]=1, y[1]=0, y[2]=1, y[3]=0
```

### 4-wide NAND array

```
python main.py tg_parser/tests/simulation/d3_program3_nand_array.tg --run
```
```
NAND_ARRAY(a=[0, 0, 0, 1], b=[1, 0, 1, 1]) -> y[0]=1, y[1]=1, y[2]=1, y[3]=0
```

---

## Truth Table

`--truth-table COMPONENT` enumerates all input combinations and prints the result. Array input ports are expanded into individual bit columns, so a `logic[4]` port produces 4 columns (`a[0] a[1] a[2] a[3]`).

```
python main.py tg_parser/tests/valid/valid2_nand2.tg --truth-table NAND2
```
```
NAND2 truth table:
a b | y
0 0 | 1
0 1 | 1
1 0 | 1
1 1 | 0
```

```
python main.py tg_parser/tests/simulation/d3_program2_inv_array.tg --truth-table INV_ARRAY
```
```
INV_ARRAY truth table:
a[0] a[1] a[2] a[3] | y[0] y[1] y[2] y[3]
0 0 0 0 | 1 1 1 1
0 0 0 1 | 1 1 1 0
...
1 1 1 1 | 0 0 0 0
```

---

## Type Errors Caught Before Execution

| Error | Message |
|-------|---------|
| Duplicate simulate argument | `duplicate argument 'a' in simulate 'INV'` |
| Unknown simulate argument | `unknown argument 'x' for 'INV'; valid input ports: 'a'` |
| Missing simulate argument | `missing argument 'b' in simulate 'NAND2'` |
| Vector for scalar port | `argument 'a' is a vector literal but port 'a' is scalar logic` |
| Scalar for array port | `argument 'a' is a scalar expression but port expects logic[4]` |
| Wrong vector length | `argument 'a' has 2 bits but port expects logic[4]` |
| Index out of range | `index 5 out of range for 'a' of size 4` |
| Undefined param | `undefined param 'N' used in port size` |

---

## Formal EBNF Grammar

```
<program>                  ::= { <top_level_item> }

<top_level_item>           ::= <param_declaration>
                             | <gate_declaration>
                             | <circuit_declaration>
                             | <simulate_call> ";"

<param_declaration>        ::= "param" <identifier> "=" <integer_literal> ";"

<gate_declaration>         ::= "gate" <identifier>
                               "(" <gate_port_section> ")" <gate_body>

<circuit_declaration>      ::= "circuit" <identifier>
                               "(" <circuit_port_section> ")" <circuit_body>

<gate_port_section>        ::= <input_section> ";" "out" <port_decl>

<circuit_port_section>     ::= <input_section> ";" "out" <port_decl_list>

<input_section>            ::= "in" <port_decl_list>

<port_decl_list>           ::= <port_decl> { "," <port_decl> }

<port_decl>                ::= <identifier>
                             | <identifier> "[" <size_expr> "]"

<size_expr>                ::= <integer_literal>
                             | <identifier>

<gate_body>                ::= "{" { <gate_statement> } "}"

<gate_statement>           ::= <node_declaration> ";"
                             | <transistor_statement> ";"
                             | <gate_generate_statement>

<node_declaration>         ::= "node" <identifier_list>

<transistor_statement>     ::= <transistor_type>
                               "drain"  "=" <net_reference> ","
                               "gate"   "=" <net_reference> ","
                               "source" "=" <net_reference>

<transistor_type>          ::= "pmos" | "nmos"

<net_reference>            ::= <signal_reference>
                             | "VDD"
                             | "GND"

<circuit_body>             ::= "{" { <circuit_statement> } "}"

<circuit_statement>        ::= <wire_declaration> ";"
                             | <component_instance_statement> ";"
                             | <circuit_generate_statement>

<wire_declaration>         ::= "wire" <port_decl_list>

<component_instance_statement>
                           ::= <identifier> <instance_name>
                               "(" [ <signal_list> ] ")"
                               "->" <output_binding>

<instance_name>            ::= <identifier>

<signal_list>              ::= <signal_reference> { "," <signal_reference> }

<signal_reference>         ::= <identifier> { "[" <index_expression> "]" }

<output_binding>           ::= <signal_reference>
                             | "{" <named_binding>
                                   { "," <named_binding> } "}"

<named_binding>            ::= <identifier> "=" <signal_reference>

<gate_generate_statement>  ::= "generate" <identifier> "from" <range_bound>
                               "to" <range_bound>
                               "{" { <gate_generate_body_statement> } "}"

<gate_generate_body_statement>
                           ::= <node_declaration> ";"
                             | <transistor_statement> ";"
                             | <gate_generate_statement>

<circuit_generate_statement>
                           ::= "generate" <identifier> "from" <range_bound>
                               "to" <range_bound>
                               "{" { <circuit_generate_body_statement> } "}"

<circuit_generate_body_statement>
                           ::= <wire_declaration> ";"
                             | <component_instance_statement> ";"
                             | <circuit_generate_statement>

<range_bound>              ::= <integer_literal>
                             | <identifier>
                             | <identifier> "-" <integer_literal>
                             | <identifier> "+" <integer_literal>

<simulate_call>            ::= "simulate" <identifier> "(" [ <sim_arg_list> ] ")"

<sim_arg_list>             ::= <sim_arg> { "," <sim_arg> }

<sim_arg>                  ::= <identifier> "=" <logic_expression>
                             | <identifier> "=" <vector_literal>

<vector_literal>           ::= "[" <logic_literal> { "," <logic_literal> } "]"

<logic_expression>         ::= <logic_term> { "|" <logic_term> }

<logic_term>               ::= <logic_factor> { "&" <logic_factor> }

<logic_factor>             ::= "!" <logic_factor>
                             | "(" <logic_expression> ")"
                             | <logic_literal>

<logic_literal>            ::= "0" | "1"

<index_expression>         ::= <integer_literal>
                             | <identifier>

<identifier_list>          ::= <identifier> { "," <identifier> }

<identifier>               ::= LETTER { LETTER | DIGIT | "_" }

<integer_literal>          ::= DIGIT { DIGIT }
```

### Grammar Notes

- `generate i from A to B` is **inclusive** on both ends: `from 0 to 3` gives i = 0, 1, 2, 3.
- `param` names in `<size_expr>` and `<range_bound>` are resolved by the elaborator.
- `simulate` calls use **named arguments** only; positional calls are a syntax error.
- `+` in logic expressions is a syntax error with the message: `'+' is not a valid logic operator; use '|' for logical OR`.
- Bare identifiers at top level (without `simulate`) produce: `unexpected identifier 'X' at top level; did you mean 'simulate X(...)'?`

---

## Running Tests

```
python -m pytest tg_parser/tests/ -v
```

Currently 38 tests passing.

---

## Error Reference

### Syntax errors

| Cause | Sample message |
|-------|----------------|
| `+` used as OR | `'+' is not a valid logic operator; use '\|' for logical OR` |
| Bare identifier at top level | `unexpected identifier 'NAND2' at top level; did you mean 'simulate NAND2(...)'?` |
| Bad logic literal | `expected logic literal '0' or '1', found '2'` |
| `generate` missing `from` | Syntax error |
| `generate` missing `to` | Syntax error |
| Missing `->` in instance | `expected '->' after instance argument list` |
| Unclosed gate body | `expected '}' to close gate body, found EOF` |

### Semantic errors

| Cause | Sample message |
|-------|----------------|
| Undefined component | `undefined component 'UnknownGate'` |
| Duplicate component | `component 'INV' already defined at line N` |
| Undefined net/wire | `undefined wire or port 'ghost'` |
| Undefined param | `undefined param 'N' used in port size` |

### Type errors

| Cause | Sample message |
|-------|----------------|
| Duplicate sim argument | `duplicate argument 'a' in simulate 'INV'` |
| Unknown sim argument | `unknown argument 'x' for 'INV'; valid input ports: 'a'` |
| Missing sim argument | `missing argument 'b' in simulate 'NAND2'` |
| Vector for scalar port | `argument 'a' is a vector literal but port 'a' is scalar logic` |
| Wrong vector length | `argument 'a' has 2 bits but port expects logic[4]` |
| Index out of range | `index 5 out of range for 'a' of size 4` |

### Simulation errors

| Cause | Sample message |
|-------|----------------|
| Floating output | `floating output 'y' in gate 'INV'` |
| Short circuit | `short-circuit conflict at output 'y' in gate 'INV'` |
