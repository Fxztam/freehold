from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program
from freehold.core.pipeline import read_source

source = read_source("tests/language_modules/05_records/invalid_semantics/unknown_record_literal_field.fh")
ast = parse_source(source)
verify_program(ast)
print("SUCCESS!")
