#/usr/bin/python



#######################################################################
#
# SYMBOLS SECTION - Can be edited. Changes will be preserved.
#
#######################################################################



import collections
from functools import partial
import os
import sys
from typing import Tuple, List, Set, Union, Any, Optional, Callable, cast

try:
    scriptdir = os.path.dirname(os.path.realpath(__file__))
except NameError:
    scriptdir = ''
if scriptdir and scriptdir not in sys.path: sys.path.append(scriptdir)

try:
    from DHParser import versionnumber
except (ImportError, ModuleNotFoundError):
    i = scriptdir.rfind("/DHParser/")
    if i >= 0:
        dhparserdir = scriptdir[:i + 10]  # 10 = len("/DHParser/")
        if dhparserdir not in sys.path:  sys.path.insert(0, dhparserdir)

from DHParser.compile import Compiler, compile_source, full_compile
from DHParser.configuration import set_config_value, add_config_values, get_config_value, \
    access_thread_locals, access_presets, finalize_presets, set_preset_value, \
    get_preset_value, read_local_config, CONFIG_PRESET, NEVER_MATCH_PATTERN, ALLOWED_PRESET_VALUES
from DHParser import dsl
from DHParser.dsl import recompile_grammar
from DHParser.ebnf import grammar_changed
from DHParser.error import ErrorCode, Error, canonical_error_strings, has_errors, NOTICE, \
    WARNING, ERROR, FATAL
from DHParser.log import start_logging, suspend_logging, resume_logging
from DHParser.nodetree import Node, WHITESPACE_PTYPE, TOKEN_PTYPE, RootNode, Path, ZOMBIE_TAG
from DHParser.parse import Grammar, PreprocessorToken, Whitespace, Drop, DropFrom, AnyChar, Parser, \
    Lookbehind, Lookahead, Alternative, Pop, Text, Synonym, Counted, Interleave, INFINITE, ERR, \
    Option, NegativeLookbehind, OneOrMore, RegExp, SmartRE, Retrieve, Series, Capture, TreeReduction, \
    ZeroOrMore, Ref, Forward, NegativeLookahead, Required, CombinedParser, Custom, IgnoreCase, \
    LateBindingUnary, mixin_comment, last_value, matching_bracket, optional_last_value, \
    PARSER_PLACEHOLDER, RX_NEVER_MATCH, UninitializedError
from DHParser.pipeline import end_points, full_pipeline, create_parser_junction, \
    create_preprocess_junction, create_junction, Junction, PseudoJunction, PipelineResult
from DHParser.preprocess import nil_preprocessor, PreprocessorFunc, PreprocessorResult, \
    gen_find_include_func, preprocess_includes, make_preprocessor, chain_preprocessors
from DHParser.stringview import StringView
from DHParser.toolkit import is_filename, load_if_file, cpu_count, get_piped_data, \
    ThreadLocalSingletonFactory, expand_table, static, CancelQuery, re
from DHParser.trace import set_tracer, resume_notices_on, trace_history
from DHParser.transform import is_empty, remove_if, TransformationDict, TransformerFunc, \
    transformation_factory, remove_children_if, move_fringes, normalize_whitespace, \
    is_anonymous, name_matches, reduce_single_child, replace_by_single_child, replace_or_reduce, \
    remove_whitespace, replace_by_children, remove_empty, remove_tokens, flatten, all_of, \
    any_of, transformer, merge_adjacent, collapse, collapse_children_if, transform_result, \
    remove_children, remove_content, remove_brackets, change_name, remove_anonymous_tokens, \
    keep_children, is_one_of, not_one_of, content_matches, apply_if, peek, \
    remove_anonymous_empty, keep_nodes, traverse_locally, strip, lstrip, rstrip, \
    replace_content_with, forbid, assert_content, remove_infix_operator, add_error, error_on, \
    left_associative, lean_left, node_maker, has_descendant, neg, has_ancestor, insert, \
    positions_of, replace_child_names, add_attributes, delimit_children, merge_connected, \
    has_attr, has_parent, has_children, has_child, apply_unless, apply_ifelse, traverse
from DHParser import parse as parse_namespace__


import DHParser.versionnumber
if DHParser.versionnumber.__version_info__ < (1, 9, 6):
    print(f'DHParser version {DHParser.versionnumber.__version__} is lower than the DHParser '
          f'version 1.9.6, {os.path.basename(__file__)} has first been generated with. '
          f'Please install a more recent version of DHParser to avoid unexpected errors!')


if sys.version_info >= (3, 14, 0):
    CONFIG_PRESET['multicore_pool'] = 'InterpreterPool'
read_local_config(os.path.join(scriptdir, 'FreeholdConfig.ini'))



#######################################################################
#
# PREPROCESSOR SECTION - Can be edited. Changes will be preserved.
#
#######################################################################




# To capture includes, replace the NEVER_MATCH_PATTERN
# by a pattern with group "name" here, e.g. r'\input{(?P<name>.*)}'
RE_INCLUDE = NEVER_MATCH_PATTERN
RE_COMMENT = '--[^\\n]*(?:\\n|$)|/\\*(?:.|\\n)*?\\*/'  # THIS MUST ALWAYS BE THE SAME AS FreeholdGrammar.COMMENT__ !!!


def FreeholdTokenizer(original_text) -> Tuple[str, List[Error]]:
    # Here, a function body can be filled in that adds preprocessor tokens
    # to the source code and returns the modified source.
    return original_text, []

preprocessing: PseudoJunction = create_preprocess_junction(
    FreeholdTokenizer, RE_INCLUDE, RE_COMMENT)



#######################################################################
#
# CUSTOM PARSER Section - Can be edited. Changes will be preserved.
#
#######################################################################



# Examples for custom parsers. Use these as role models for your own
# Python-implemented parsing-functions

# 1. Plain parsing function (denoted as "@pCustom(parse_word)" is the grammar)

def parse_word(s: StringView) -> Optional[Node]:
    m = s.match(r'\w+')
    if m:
        return Node('word', s[:m.end()])
    return None

# 2. Simple parser generator: like plain parser function, but looks
#    in the grammar, i.e. "@parse_word()"






#######################################################################
#
# PARSER SECTION - Don't edit! CHANGES WILL BE OVERWRITTEN!
#
#######################################################################


class FreeholdGrammar(Grammar):
    r"""Parser for a Freehold document.

    Instantiate this class and then call the instance with the source
    code as the single argument in order to use the parser, e.g.:
        parser = Freehold()
        syntax_tree = parser(source_code)
    """
    arg_list = Forward()
    expr = Forward()
    named_arg_list = Forward()
    postfix_expr = Forward()
    result_payload_type = Forward()
    stmt = Forward()
    type_ref = Forward()
    unary = Forward()
    source_hash__ = "65dc7333c1d1a76259849e8cb9acd846"
    disposable__ = re.compile('$.')
    static_analysis_pending__ = []  # type: List[bool]
    parser_initialization__ = ["upon instantiation"]
    COMMENT__ = r'--[^\n]*(?:\n|$)|/\*(?:.|\n)*?\*/'
    comment_rx__ = re.compile(COMMENT__)
    WHITESPACE__ = r'\s*'
    WSP_RE__ = mixin_comment(whitespace=WHITESPACE__, comment=COMMENT__)
    wsp__ = Whitespace(WSP_RE__)
    type_arg_list = Series(Series(Text("<"), wsp__), type_ref, ZeroOrMore(Series(Series(Text(","), wsp__), type_ref)), Series(Text(">"), wsp__))
    STRING_LITERAL = Series(RegExp('"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"'), wsp__)
    FIELD_PATH = Series(RegExp('(?!module\\b|import\\b|exposing\\b|type\\b|is\\b|record\\b|error\\b|function\\b'
       '|procedure\\b|service\\b|rpc\\b|proto\\b|returns\\b|requires\\b|aborts\\b|ensure'
       's\\b|let\\b|return\\b|abort\\b|ok\\b|if\\b|then\\b|else\\b|end\\b|while\\b|invar'
       'iant\\b|variant\\b|do\\b|case\\b|when\\b|default\\b|call\\b|check\\b|and\\b|or'
       '\\b|not\\b|async\\b|await\\b|scope\\b|spawn\\b|join\\b|true\\b|false\\b|success\\b'
       '|failure\\b|value\\b)[A-Za-z_][A-Za-z0-9_]*(?:\\.[A-Za-z_][A-Za-z0-9_]*)+'), wsp__)
    IDENT = Series(RegExp('(?!module\\b|import\\b|exposing\\b|type\\b|is\\b|record\\b|error\\b|function\\b'
       '|procedure\\b|service\\b|rpc\\b|proto\\b|returns\\b|requires\\b|aborts\\b|ensure'
       's\\b|let\\b|return\\b|abort\\b|ok\\b|if\\b|then\\b|else\\b|end\\b|while\\b|invar'
       'iant\\b|variant\\b|do\\b|case\\b|when\\b|default\\b|call\\b|check\\b|and\\b|or'
       '\\b|not\\b|async\\b|await\\b|scope\\b|spawn\\b|join\\b|true\\b|false\\b|success\\b'
       '|failure\\b|value\\b)[A-Za-z_][A-Za-z0-9_]*'), wsp__)
    INTEGER_LITERAL = Series(RegExp('-?[0-9]+'), wsp__)
    DOUBLE_LITERAL = Series(RegExp('-?(?:[0-9]+\\.[0-9]+)'), wsp__)
    NUMBER_LITERAL = Alternative(DOUBLE_LITERAL, INTEGER_LITERAL)
    BASE_TYPE = Alternative(Series(Text("Integer"), wsp__), Series(Text("Boolean"), wsp__), Series(Text("Double"), wsp__), Series(Text("String"), wsp__), Series(Text("BigInteger"), wsp__), Series(Text("BigFloat"), wsp__))
    array_literal = Series(Series(Text("["), wsp__), Option(arg_list), Series(Text("]"), wsp__))
    field_path = Synonym(FIELD_PATH)
    atom = Synonym(postfix_expr)
    primary = Alternative(STRING_LITERAL, DOUBLE_LITERAL, INTEGER_LITERAL, array_literal, Series(Series(Text("scope"), wsp__), Series(Text("("), wsp__), Option(arg_list), Series(Text(")"), wsp__)), Series(IDENT, type_arg_list, Series(Text("("), wsp__), Option(arg_list), Series(Text(")"), wsp__)), Series(IDENT, Series(Text("{"), wsp__), named_arg_list, Series(Text("}"), wsp__)), Series(type_ref, Series(Text("{"), wsp__), named_arg_list, Series(Text("}"), wsp__)), IDENT, Series(Series(Text("("), wsp__), expr, Series(Text(")"), wsp__)), Series(Text("true"), wsp__), Series(Text("false"), wsp__), Series(Text("success"), wsp__), Series(Text("failure"), wsp__), Series(Text("value"), wsp__), Series(Text("error"), wsp__))
    member_name = Alternative(IDENT, Series(Text("spawn"), wsp__), Series(Text("join"), wsp__), Series(Text("value"), wsp__), Series(Text("error"), wsp__))
    postfix = Alternative(Series(Option(type_arg_list), Series(Text("("), wsp__), Option(arg_list), Series(Text(")"), wsp__)), Series(Series(Text("["), wsp__), expr, Series(Text("]"), wsp__)), Series(Series(Text("."), wsp__), member_name))
    proto_field_id = Series(Series(Text("proto"), wsp__), INTEGER_LITERAL)
    array_type = Series(Series(Text("Array"), wsp__), Series(Text("<"), wsp__), type_ref, Series(Text(","), wsp__), INTEGER_LITERAL, Series(Text(">"), wsp__))
    product = Series(unary, ZeroOrMore(Series(Alternative(Series(Text("*"), wsp__), Series(Text("/"), wsp__)), unary)))
    sum = Series(product, ZeroOrMore(Series(Alternative(Series(Text("+"), wsp__), Series(Text("-"), wsp__)), product)))
    comparison = Series(sum, ZeroOrMore(Series(Alternative(Series(Text("<="), wsp__), Series(Text(">="), wsp__), Series(Text("<"), wsp__), Series(Text(">"), wsp__)), sum)))
    equality = Series(comparison, ZeroOrMore(Series(Alternative(Series(Text("!="), wsp__), Series(Text("="), wsp__)), comparison)))
    logic_and = Series(equality, ZeroOrMore(Series(Series(Text("and"), wsp__), equality)))
    logic_or = Series(logic_and, ZeroOrMore(Series(Series(Text("or"), wsp__), logic_and)))
    exposing_list = Series(IDENT, ZeroOrMore(Series(Series(Text(","), wsp__), IDENT)))
    named_arg = Series(IDENT, Series(Text(":"), wsp__), expr)
    exposing_clause = Series(Series(Text("exposing"), wsp__), exposing_list)
    expr_list = Series(expr, ZeroOrMore(Series(Series(Text(","), wsp__), expr)))
    call_arg = Alternative(named_arg, expr)
    qualified_name = Series(IDENT, ZeroOrMore(Series(wsp__, Series(Text("."), wsp__), wsp__, IDENT)))
    scope_result_block = Series(wsp__, Series(Text("result"), wsp__), ZeroOrMore(stmt))
    scope_join_block = Series(wsp__, Series(Text("join"), wsp__), ZeroOrMore(stmt))
    scope_spawn_block = Series(wsp__, Series(Text("spawn"), wsp__), ZeroOrMore(stmt))
    scope_stmt = Series(wsp__, Series(Text("scope"), wsp__), IDENT, Series(Text("do"), wsp__), scope_spawn_block, scope_join_block, scope_result_block, Series(Text("end"), wsp__), Series(Text("scope"), wsp__))
    case_block = ZeroOrMore(stmt)
    default_branch = Series(wsp__, Series(Text("default"), wsp__), Series(Text("=>"), wsp__), case_block)
    case_branch = Series(wsp__, Series(Text("when"), wsp__), expr, Series(Text("=>"), wsp__), case_block)
    case_stmt = Series(wsp__, Series(Text("case"), wsp__), expr, Series(Text("is"), wsp__), case_branch, ZeroOrMore(case_branch), default_branch, Series(Text("end"), wsp__), Series(Text("case"), wsp__))
    variant_clause = Series(wsp__, Series(Text("variant"), wsp__), expr)
    invariant_clause = Series(wsp__, Series(Text("invariant"), wsp__), expr)
    loop_block = ZeroOrMore(stmt)
    while_stmt = Series(wsp__, Series(Text("while"), wsp__), expr, invariant_clause, ZeroOrMore(invariant_clause), Option(variant_clause), Series(Text("do"), wsp__), loop_block, Series(Text("end"), wsp__), Series(Text("while"), wsp__))
    else_block = ZeroOrMore(stmt)
    then_block = ZeroOrMore(stmt)
    if_stmt = Series(wsp__, Series(Text("if"), wsp__), expr, Series(Text("then"), wsp__), then_block, Option(Series(Series(Text("else"), wsp__), else_block)), Series(Text("end"), wsp__), Series(Text("if"), wsp__))
    import_decl = Series(wsp__, Series(Text("import"), wsp__), qualified_name, Option(exposing_clause))
    check_stmt = Series(wsp__, Series(Text("check"), wsp__), expr)
    return_value = Alternative(Series(Series(Text("ok"), wsp__), expr), Series(Series(Text("error"), wsp__), IDENT), expr)
    abort_stmt = Series(wsp__, Series(Text("abort"), wsp__), IDENT)
    return_stmt = Series(wsp__, Series(Text("return"), wsp__), return_value)
    assign_stmt = Series(wsp__, IDENT, Series(Text(":="), wsp__), expr)
    field_assign_stmt = Series(wsp__, FIELD_PATH, Series(Text(":="), wsp__), expr)
    result_type = Series(Series(Text("Result"), wsp__), Series(Text("<"), wsp__), result_payload_type, Series(Text(","), wsp__), type_ref, Series(Text(">"), wsp__))
    call_stmt = Series(wsp__, Series(Text("call"), wsp__), qualified_name, Option(type_arg_list), Series(Text("("), wsp__), Option(arg_list), Series(Text(")"), wsp__))
    ensures_clause = Series(Series(Text("ensures"), wsp__), expr_list)
    aborts_clause = Series(Series(Text("aborts"), wsp__), IDENT, Option(Series(Series(Text("when"), wsp__), expr)))
    constraint = Alternative(Series(IDENT, Series(Text("is"), wsp__), IDENT), expr)
    constraint_list = Series(constraint, ZeroOrMore(Series(Series(Text(","), wsp__), constraint)))
    requires_clause = Series(Series(Text("requires"), wsp__), constraint_list)
    contract_block = Series(ZeroOrMore(requires_clause), ZeroOrMore(aborts_clause), ZeroOrMore(ensures_clause))
    param = Series(IDENT, Series(Text(":"), wsp__), type_ref)
    param_list = Series(param, ZeroOrMore(Series(Series(Text(","), wsp__), param)))
    rpc_decl = Series(wsp__, Series(Text("rpc"), wsp__), IDENT, Series(Text("("), wsp__), IDENT, Series(Text(":"), wsp__), type_ref, Series(Text(")"), wsp__), Series(Text(":"), wsp__), type_ref)
    service_decl = Series(wsp__, Series(Text("service"), wsp__), IDENT, Series(Text("is"), wsp__), rpc_decl, ZeroOrMore(rpc_decl), Series(Text("end"), wsp__), IDENT)
    type_param_list = Series(Series(Text("<"), wsp__), IDENT, ZeroOrMore(Series(Series(Text(","), wsp__), IDENT)), Series(Text(">"), wsp__))
    async_marker = Series(Text("async"), wsp__)
    procedure_decl = Series(wsp__, Series(Text("procedure"), wsp__), IDENT, Option(type_param_list), Series(Text("("), wsp__), Option(param_list), Series(Text(")"), wsp__), Option(contract_block), Series(Text("is"), wsp__), ZeroOrMore(stmt), Series(Text("end"), wsp__), IDENT)
    return_type = Alternative(array_type, result_type, type_ref)
    function_decl = Series(wsp__, Option(async_marker), Series(Text("function"), wsp__), IDENT, Option(type_param_list), Series(Text("("), wsp__), Option(param_list), Series(Text(")"), wsp__), Series(Text("returns"), wsp__), return_type, Option(contract_block), Series(Text("is"), wsp__), ZeroOrMore(stmt), Series(Text("end"), wsp__), IDENT)
    module_end = Series(wsp__, Series(Text("end"), wsp__), wsp__, qualified_name)
    let_stmt = Series(wsp__, Series(Text("let"), wsp__), IDENT, Series(Text(":"), wsp__), return_type, Series(Text("="), wsp__), expr)
    module_decl = Series(wsp__, Series(Text("module"), wsp__), wsp__, qualified_name)
    EOF = RegExp('$')
    base_type = Synonym(BASE_TYPE)
    error_decl = Series(wsp__, Series(Text("error"), wsp__), IDENT)
    range_decl = Series(Series(Text("range"), wsp__), NUMBER_LITERAL, Series(Text(".."), wsp__), NUMBER_LITERAL)
    type_decl = Series(wsp__, Series(Text("type"), wsp__), IDENT, Series(Text("is"), wsp__), base_type, Option(range_decl))
    record_field = Series(IDENT, Series(Text(":"), wsp__), type_ref, Option(proto_field_id))
    record_type_decl = Series(wsp__, Series(Text("type"), wsp__), IDENT, Option(type_param_list), Series(Text("is"), wsp__), Series(Text("record"), wsp__), record_field, ZeroOrMore(record_field), Series(Text("end"), wsp__), Series(Text("record"), wsp__))
    declaration = Alternative(record_type_decl, type_decl, error_decl, service_decl, function_decl, procedure_decl)
    postfix_expr.set(Series(primary, ZeroOrMore(postfix)))
    unary.set(Alternative(Series(Series(Text("await"), wsp__), unary), Series(Series(Text("-"), wsp__), unary), Series(Series(Text("not"), wsp__), unary), postfix_expr))
    expr.set(Series(wsp__, logic_or))
    named_arg_list.set(Series(named_arg, ZeroOrMore(Series(Series(Text(","), wsp__), named_arg))))
    arg_list.set(Series(call_arg, ZeroOrMore(Series(Series(Text(","), wsp__), call_arg))))
    stmt.set(Alternative(let_stmt, return_stmt, abort_stmt, if_stmt, while_stmt, case_stmt, scope_stmt, check_stmt, call_stmt, field_assign_stmt, assign_stmt))
    result_payload_type.set(Alternative(array_type, result_type, type_ref))
    type_ref.set(Series(Alternative(BASE_TYPE, IDENT), Option(type_arg_list)))
    start = Series(wsp__, module_decl, ZeroOrMore(import_decl), ZeroOrMore(declaration), module_end, EOF)
    root__ = start
    
parsing: PseudoJunction = create_parser_junction(FreeholdGrammar)
get_grammar = parsing.factory  # for backwards compatibility, only



try:
    assert RE_INCLUDE == NEVER_MATCH_PATTERN or \
        RE_COMMENT in (FreeholdGrammar.COMMENT__, NEVER_MATCH_PATTERN), \
        "Please adjust the pre-processor-variable RE_COMMENT in file FreeholdParser.py so that " \
        "it either is the NEVER_MATCH_PATTERN or has the same value as the COMMENT__-attribute " \
        "of the grammar class FreeholdGrammar! " \
        'Currently, RE_COMMENT reads "%s" while COMMENT__ is "%s". ' \
        % (RE_COMMENT, FreeholdGrammar.COMMENT__) + \
        "\n\nIf RE_COMMENT == NEVER_MATCH_PATTERN then includes will deliberately be " \
        "processed, otherwise RE_COMMENT==FreeholdGrammar.COMMENT__ allows the " \
        "preprocessor to ignore comments."
except (AttributeError, NameError):
    pass




#######################################################################
#
# AST SECTION - Can be edited. Changes will be preserved.
#
#######################################################################


Freehold_AST_transformation_table = {
    # AST Transformations for the Freehold-grammar
    # Special rules:
    # "<<<": [],  # called once before the tree-traversal starts
    # ">>>": [],  # called once after the tree-traversal has finished
    # "<": [],  # called for each node before calling its specific rules
    # "*": [],  # fallback for nodes that do not appear in this table
    # ">": [],   # called for each node after calling its specific rules
    "start": [],
    "EOF": [],
    "module_decl": [],
    "module_end": [],
    "qualified_name": [],
    "import_decl": [],
    "exposing_clause": [],
    "exposing_list": [],
    "declaration": [],
    "record_type_decl": [],
    "type_param_list": [],
    "record_field": [],
    "proto_field_id": [],
    "type_decl": [],
    "range_decl": [],
    "error_decl": [],
    "base_type": [],
    "type_ref": [],
    "type_arg_list": [],
    "return_type": [],
    "result_payload_type": [],
    "result_type": [],
    "array_type": [],
    "function_decl": [],
    "async_marker": [],
    "procedure_decl": [],
    "service_decl": [],
    "rpc_decl": [],
    "param_list": [],
    "param": [],
    "contract_block": [],
    "requires_clause": [],
    "constraint_list": [],
    "constraint": [],
    "aborts_clause": [],
    "ensures_clause": [],
    "stmt": [],
    "let_stmt": [],
    "field_assign_stmt": [],
    "assign_stmt": [],
    "return_stmt": [],
    "abort_stmt": [],
    "return_value": [],
    "check_stmt": [],
    "call_stmt": [],
    "if_stmt": [],
    "then_block": [],
    "else_block": [],
    "while_stmt": [],
    "loop_block": [],
    "invariant_clause": [],
    "variant_clause": [],
    "case_stmt": [],
    "case_branch": [],
    "default_branch": [],
    "case_block": [],
    "scope_stmt": [],
    "scope_spawn_block": [],
    "scope_join_block": [],
    "scope_result_block": [],
    "arg_list": [],
    "call_arg": [],
    "expr_list": [],
    "named_arg_list": [],
    "named_arg": [],
    "expr": [],
    "logic_or": [],
    "logic_and": [],
    "equality": [],
    "comparison": [],
    "sum": [],
    "product": [],
    "unary": [],
    "postfix_expr": [],
    "postfix": [],
    "member_name": [],
    "primary": [],
    "atom": [],
    "field_path": [],
    "array_literal": [],
    "BASE_TYPE": [],
    "DOUBLE_LITERAL": [],
    "NUMBER_LITERAL": [],
    "INTEGER_LITERAL": [],
    "IDENT": [],
    "FIELD_PATH": [],
    "STRING_LITERAL": [],
}


# DEPRECATED, because it requires pickling the transformation-table, which rules out lambdas!
# ASTTransformation: Junction = create_junction(
#     Freehold_AST_transformation_table, "CST", "AST", "transtable")

def FreeholdTransformer() -> TransformerFunc:
    return static(partial(
        transformer, 
        transformation_table=Freehold_AST_transformation_table.copy(),
        src_stage='CST', 
        dst_stage='AST'))

ASTTransformation: Junction = Junction(
    'CST', ThreadLocalSingletonFactory(FreeholdTransformer), 'AST')
get_transformer = ASTTransformation.factory  # for backwards compatibility, only



#######################################################################
#
# COMPILER SECTION - Can be edited. Changes will be preserved.
#
#######################################################################


class FreeholdCompiler(Compiler):
    """Compiler for the abstract-syntax-tree of a 
        Freehold source file.
    """

    def __init__(self):
        super(FreeholdCompiler, self).__init__()
        self.forbid_returning_None = True  # set to False if any compilation-method is allowed to return None

    def reset(self):
        super().reset()
        # initialize your variables here, not in the constructor!

    def prepare(self, root: RootNode) -> None:
        assert root.stage == "AST", f"Source stage `AST` expected, `but `{root.stage}` found."
        root.stage = "Freehold"
    def finalize(self, result: Any) -> Any:
        return result

    def on_start(self, node):
        return self.fallback_compiler(node)

    # def on_EOF(self, node):
    #     return node

    # def on_module_decl(self, node):
    #     return node

    # def on_module_end(self, node):
    #     return node

    # def on_qualified_name(self, node):
    #     return node

    # def on_import_decl(self, node):
    #     return node

    # def on_exposing_clause(self, node):
    #     return node

    # def on_exposing_list(self, node):
    #     return node

    # def on_declaration(self, node):
    #     return node

    # def on_record_type_decl(self, node):
    #     return node

    # def on_type_param_list(self, node):
    #     return node

    # def on_record_field(self, node):
    #     return node

    # def on_proto_field_id(self, node):
    #     return node

    # def on_type_decl(self, node):
    #     return node

    # def on_range_decl(self, node):
    #     return node

    # def on_error_decl(self, node):
    #     return node

    # def on_base_type(self, node):
    #     return node

    # def on_type_ref(self, node):
    #     return node

    # def on_type_arg_list(self, node):
    #     return node

    # def on_return_type(self, node):
    #     return node

    # def on_result_payload_type(self, node):
    #     return node

    # def on_result_type(self, node):
    #     return node

    # def on_array_type(self, node):
    #     return node

    # def on_function_decl(self, node):
    #     return node

    # def on_async_marker(self, node):
    #     return node

    # def on_procedure_decl(self, node):
    #     return node

    # def on_service_decl(self, node):
    #     return node

    # def on_rpc_decl(self, node):
    #     return node

    # def on_param_list(self, node):
    #     return node

    # def on_param(self, node):
    #     return node

    # def on_contract_block(self, node):
    #     return node

    # def on_requires_clause(self, node):
    #     return node

    # def on_constraint_list(self, node):
    #     return node

    # def on_constraint(self, node):
    #     return node

    # def on_aborts_clause(self, node):
    #     return node

    # def on_ensures_clause(self, node):
    #     return node

    # def on_stmt(self, node):
    #     return node

    # def on_let_stmt(self, node):
    #     return node

    # def on_field_assign_stmt(self, node):
    #     return node

    # def on_assign_stmt(self, node):
    #     return node

    # def on_return_stmt(self, node):
    #     return node

    # def on_abort_stmt(self, node):
    #     return node

    # def on_return_value(self, node):
    #     return node

    # def on_check_stmt(self, node):
    #     return node

    # def on_call_stmt(self, node):
    #     return node

    # def on_if_stmt(self, node):
    #     return node

    # def on_then_block(self, node):
    #     return node

    # def on_else_block(self, node):
    #     return node

    # def on_while_stmt(self, node):
    #     return node

    # def on_loop_block(self, node):
    #     return node

    # def on_invariant_clause(self, node):
    #     return node

    # def on_variant_clause(self, node):
    #     return node

    # def on_case_stmt(self, node):
    #     return node

    # def on_case_branch(self, node):
    #     return node

    # def on_default_branch(self, node):
    #     return node

    # def on_case_block(self, node):
    #     return node

    # def on_scope_stmt(self, node):
    #     return node

    # def on_scope_spawn_block(self, node):
    #     return node

    # def on_scope_join_block(self, node):
    #     return node

    # def on_scope_result_block(self, node):
    #     return node

    # def on_arg_list(self, node):
    #     return node

    # def on_call_arg(self, node):
    #     return node

    # def on_expr_list(self, node):
    #     return node

    # def on_named_arg_list(self, node):
    #     return node

    # def on_named_arg(self, node):
    #     return node

    # def on_expr(self, node):
    #     return node

    # def on_logic_or(self, node):
    #     return node

    # def on_logic_and(self, node):
    #     return node

    # def on_equality(self, node):
    #     return node

    # def on_comparison(self, node):
    #     return node

    # def on_sum(self, node):
    #     return node

    # def on_product(self, node):
    #     return node

    # def on_unary(self, node):
    #     return node

    # def on_postfix_expr(self, node):
    #     return node

    # def on_postfix(self, node):
    #     return node

    # def on_member_name(self, node):
    #     return node

    # def on_primary(self, node):
    #     return node

    # def on_atom(self, node):
    #     return node

    # def on_field_path(self, node):
    #     return node

    # def on_array_literal(self, node):
    #     return node

    # def on_BASE_TYPE(self, node):
    #     return node

    # def on_DOUBLE_LITERAL(self, node):
    #     return node

    # def on_NUMBER_LITERAL(self, node):
    #     return node

    # def on_INTEGER_LITERAL(self, node):
    #     return node

    # def on_IDENT(self, node):
    #     return node

    # def on_FIELD_PATH(self, node):
    #     return node

    # def on_STRING_LITERAL(self, node):
    #     return node



compiling: Junction = Junction(
    'AST', ThreadLocalSingletonFactory(FreeholdCompiler), 'Freehold')

get_compiler = compiling.factory  # for backwards compatibility, only



#######################################################################
#
# END OF DHPARSER-SECTIONS
#
#######################################################################


#######################################################################
#
# Post-Processing-Stages [add one or more postprocessing stages, here]
#
#######################################################################
from DHParser import ALLOWED_PRESET_VALUES

# class PostProcessing(Compiler):
#     ...

# # change the names of the source and destination stages. Source
# # ("Freehold") in this example must be the name of some earlier stage, though.
# postprocessing: Junction = Junction(
#     "Freehold", ThreadLocalSingletonFactory(PostProcessing), "refined")
#
# DON'T FORGET TO ADD ALL POSTPROCESSING-JUNCTIONS TO THE GLOBAL
# "junctions"-set IN SECTION "Processing-Pipeline" BELOW!

#######################################################################
#
# Processing-Pipeline
#
#######################################################################

# Add your own stages to the junctions and target-lists, below
# (See DHParser.compile for a description of junctions)

# ADD YOUR OWN POST-PROCESSING-JUNCTIONS HERE:
junctions = set([ASTTransformation, compiling])

# put your targets of interest, here. A target is the name of result (or stage)
# of any transformation, compilation or postprocessing step after parsing.
# Serializations of the stages listed here will be written to disk when
# calling process_file() or batch_process() and also appear in test-reports.
targets = end_points(junctions)
# alternative: targets = set([compiling.dst])

# provide a set of those stages for which you would like to see the output
# in the test-report files, here. (AST is always included)
test_targets = set(j.dst for j in junctions)
# alternative: test_targets = targets

# add one or more serializations for those targets that are node-trees
serializations = expand_table(dict([('*', [get_config_value('default_serialization')])]))


#######################################################################
#
# Main program
#
#######################################################################

def pipeline(source: str,
             target: Union[str, Set[str]] = "Freehold",
             start_parser: str = "root_parser__",
             *, cancel_query: Optional[CancelQuery] = None) -> PipelineResult:
    """Runs the source code through the processing pipeline. If
    the parameter target is not the empty string, only the stages required
    for the given target will be passed. See :py:func:`compile_src` for the
    explanation of the other parameters.
    """
    global targets
    if target:
        target_set = set([target]) if isinstance(target, str) else target
    else:
        target_set = targets
    return full_pipeline(
        source, preprocessing.factory, parsing.factory, junctions, target_set,
        start_parser, cancel_query = cancel_query)


def compile_src(source: str,
                target: str = "Freehold",
                start_parser: str = "root_parser__",
                *, cancel_query: Optional[CancelQuery] = None) -> Tuple[Any, List[Error]]:
    """Compiles the source to a single target and returns the result of the compilation
    as well as a (possibly empty) list or errors or warnings that have occurred in the
    process.

    :param source: Either a file name or a source text. Anything that is not a valid
        file name is assumed to be a source text. Add a byte-order mark ("\ufeff")
        at the beginning of short, i.e. one-line source texts, to avoid these being
        misinterpreted as filenames.
    :param target: the name of the target stage up to which the processing pipeline
        will be proceeded
    :param start_parser: the parser with which the parsing shall start. The default
        is the root-parser, but if only snippets of a full document shall be processed,
        it makes sense to pick another parser, here.

    :returns: a tuple (data, list of errors) of the data in the format of the
        target-stage selected by parameter "target" and of the potentially
        empty list of errors.
    """
    full_compilation_result = pipeline(source, target, start_parser)
    return full_compilation_result[target]


def compile_snippet(source_code: str,
                    target: str = "Freehold",
                    start_parser: str = "root_parser__",
                    *, cancel_query: Optional[CancelQuery] = None) -> Tuple[Any, List[Error]]:
    """Compiles a piece of source_code. In contrast to :py:func:`compile_src` the
    parameter source_code is always understood as a piece of source-code and never
    as a filename, not even if it is a one-liner that could also be a file-name.
    """
    if source_code[0:1] not in ('\ufeff', '\ufffe') and \
            source_code[0:3] not in ('\xef\xbb\xbf', '\x00\x00\ufeff', '\x00\x00\ufffe'):
        source_code = '\ufeff' + source_code  # add a byteorder-mark for disambiguation
    return compile_src(source_code, target, start_parser, cancel_query = cancel_query)


def process_file(source: str, out_dir: str = '', target_set: Set[str]=frozenset(),
                 *, cancel_query: CancelQuery = None) -> str:
    """Compiles the source and writes the serialized results back to disk,
    unless any fatal errors have occurred. Error and Warning messages are
    written to a file with the same name as `result_filename` with an
    appended "_ERRORS.txt" or "_WARNINGS.txt" in place of the name's
    extension. Returns the name of the error-messages file or an empty
    string, if no errors or warnings occurred.
    """
    global serializations, targets
    if not target_set:
        target_set = targets
    elif not target_set <= targets:
        raise AssertionError('Unknown compilation target(s): ' +
                             ', '.join(t for t in target_set - targets))
    # serializations = get_config_value('Freehold_serializations', serializations)
    return dsl.process_file(source, out_dir, preprocessing.factory, parsing.factory,
                            junctions, target_set, serializations, cancel_query)


def process_file_wrapper(args: Tuple[str, str, CancelQuery]) -> str:
    return process_file(args[0], args[1], cancel_query=args[2])


def batch_process(file_names: List[str], out_dir: str,
                  *, submit_func: Optional[Callable] = None,
                  log_func: Optional[Callable] = None,
                  cancel_func: Optional[Callable] = None) -> List[str]:
    """Compiles all files listed in file_names and writes the results and/or
    error messages to the directory `our_dir`. Returns a list of error
    messages files.
    """
    from FreeholdParser import process_file_wrapper
    return dsl.batch_process(file_names, out_dir, process_file_wrapper,
        submit_func=submit_func, log_func=log_func, cancel_func=cancel_func)


def main(called_from_app=False) -> bool:
    global targets, test_targets, serializations, junctions
    # recompile grammar if needed
    scriptpath = os.path.abspath(os.path.realpath(__file__))
    if scriptpath.endswith('Parser.py'):
        grammar_path = scriptpath.replace('Parser.py', '.ebnf')
    else:
        grammar_path = os.path.splitext(scriptpath)[0] + '.ebnf'
    parser_update = False

    def notify():
        nonlocal parser_update
        parser_update = True
        print('recompiling ' + grammar_path)

    if os.path.exists(grammar_path) and os.path.isfile(grammar_path):
        if not recompile_grammar(grammar_path, scriptpath, force=False, notify=notify):
            error_file = os.path.basename(__file__)\
                .replace('Parser.py', '_ebnf_MESSAGES.txt')
            with open(error_file, 'r', encoding="utf-8") as f:
                print(f.read())
            sys.exit(1)
        elif parser_update:
            if '--dontrerun' in sys.argv:
                print(os.path.basename(__file__) + ' has changed. '
                      'Please run again in order to apply updated compiler')
                sys.exit(0)
            else:
                import platform, subprocess
                call = [sys.executable, __file__, '--dontrerun'] + sys.argv[1:]
                result = subprocess.run(call, capture_output=True)
                print(result.stdout.decode('utf-8'))
                sys.exit(result.returncode)
    else:
        print('Could not check whether grammar requires recompiling, '
              'because grammar was not found at: ' + grammar_path)

    from argparse import ArgumentParser
    a = "an" if "Freehold"[0:1] in "AEIOUaeiou" else "a"
    parser = ArgumentParser(description="Parses " + a + " Freehold file and shows its syntax-tree."
                            " If several filenames are provided or an output directory is "
                            "specified with --out, the results will be written to the disk!"
                            " To directly process content, use a pipe | e.g. "
                            ' echo "..." | FreeholdParser.py.')
    parser.add_argument('files', nargs='*')
    parser.add_argument('-p', '--parse', nargs=1, default=[],
                        help='Processes the given snippet directly (instead of a file).')
    parser.add_argument('-d', '--debug', action='store_const', const='debug',
                        help='Write debug information to LOGS subdirectory')
    parser.add_argument('-o', '--out', nargs=1, default=['out'],
                        help='Output directory for batch processing')
    parser.add_argument('-v', '--verbose', action='store_const', const='verbose',
                        help='Verbose output')
    parser.add_argument('-f', '--force', action='store_const', const='force',
                        help='Write output file even if errors have occurred')
    parser.add_argument('--singlethread', action='store_const', const='singlethread',
                        help='Run batch jobs in a single thread (recommended only for debugging)')
    parser.add_argument('--dontrerun', action='store_const', const='dontrerun',
                        help='Do not automatically run again if the grammar has been recompiled.')
    parser.add_argument('-s', '--serialize', nargs=1, default=[],
                        help="Choose serialization format for tree structured data. Available: "
                             + ', '.join(ALLOWED_PRESET_VALUES['default_serialization']))
    parser.add_argument('-t', '--target', nargs='+', default=[],
                        help='Pick compilation target(s). Available targets: '
                             '%s; default: %s' % (', '.join(test_targets), ', '.join(targets)))

    args = parser.parse_args()
    file_names, out, log_dir = args.files, args.out[0], ''
    piped_data = get_piped_data()
    if piped_data: file_names.insert(0, '\ufeff' + piped_data)
    if args.parse: file_names.insert(0, '\ufeff' + args.parse[0])

    if not file_names and not called_from_app:
        print("missing argument: files")
        sys.exit(1)
    if len(file_names) > 1:
        if piped_data:
            print("Cannot process piped data and snippet or files at the same time!")
            sys.exit(1)
        if args.parse:
            print('Cannot process snippet and files at the same time! '
                  '(Snippets that contain blanks need to be enclosed in quotes "..."')
            sys.exit(1)

    read_local_config(os.path.join(scriptdir, 'FreeholdConfig.ini'))

    if args.serialize:
        if (args.serialize[0].lower() not in
                [sf.lower() for sf in ALLOWED_PRESET_VALUES['default_serialization']]):
            print('Unknown serialization format: ' + args.serialize[0] +
                  '! Available formats for tree-structures: '
                  + ', '.join(ALLOWED_PRESET_VALUES['default_serialization']))
            sys.exit(1)
        serializations['*'] = args.serialize
        access_presets()
        set_preset_value('Freehold_serializations', serializations, allow_new_key=True)
        finalize_presets()

    if args.debug is not None:
        log_dir = 'LOGS'
        access_presets()
        set_preset_value('history_tracking', True)
        set_preset_value('resume_notices', True)
        set_preset_value('log_syntax_trees', frozenset(['CST', 'AST']))  # don't use a set literal, here!
        start_logging(log_dir)
        finalize_presets()

    if args.singlethread:
        set_config_value('batch_processing_parallelization', False)

    if args.target:
        chosen = set(args.target)
        unknown = chosen - test_targets
        if unknown:
            print('Unknown targets: ' + ', '.join(unknown) + ' chosen!' +
                  '\nAvailable targets: ' + ', '.join(test_targets))
            sys.exit(1)
        targets = chosen

    def echo(message: str):
        if args.verbose:
            print(message)

    if called_from_app and not file_names:  return False

    batch_processing = True
    if len(file_names) <= 1:
        if os.path.isdir(file_names[0]):
            dir_name = file_names[0]
            echo('Processing all files in directory: ' + dir_name)
            file_names = [os.path.join(dir_name, fn) for fn in os.listdir(dir_name)
                          if fn[0:1] != '.' and os.path.isfile(os.path.join(dir_name, fn))]
        elif not ('-o' in sys.argv or '--out' in sys.argv):
            batch_processing = False

    if batch_processing:
        if not os.path.exists(out):
            os.mkdir(out)
        elif not os.path.isdir(out):
            print('Output directory "%s" exists and is not a directory!' % out)
            sys.exit(1)
        error_files = batch_process(file_names, out, log_func=print if args.verbose else None)
        if error_files:
            category = "ERRORS" if any(f.endswith('_ERRORS.txt') for f in error_files) \
                else "warnings"
            print("There have been %s! Please check files:" % category)
            print('\n'.join(error_files))
            if category == "ERRORS":
                sys.exit(1)
    else:
        if len(targets) == 1:
            result, errors = compile_src(file_names[0], target=next(iter(targets)))
        else:
            result, errors = compile_src(file_names[0])  # keep default_target

        if not errors or (not has_errors(errors, ERROR)) \
                or (not has_errors(errors, FATAL) and args.force):
            print(result.serialize(serializations['*'][0])
                  if isinstance(result, Node) else result)
            if errors:  print('\n---')

        for err_str in canonical_error_strings(errors):
            print(err_str)
        if has_errors(errors, ERROR):  sys.exit(1)

    return True


if __name__ == "__main__":
    main()
