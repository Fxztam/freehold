from __future__ import annotations

import re
from pathlib import Path

from freehold.core.ast import Program, RecordTypeDecl, ServiceDecl
from freehold.core.parser import parse_source
from freehold.core.verifier import TypeCheckError, VerifiedProgram, verify_program

PROTO_SCALARS = {
    "String": "string",
    "Boolean": "bool",
    "Integer": "int64",
    "Double": "double",
}


def proto_package_name(module_name: str) -> str:
    return ".".join(part.lower() for part in module_name.split("."))


def proto_field_type(type_name: str, record_names: set[str]) -> str:
    array_match = re.fullmatch(r"Array<\s*([^<>]+?)\s*>", type_name)
    if array_match:
        element_type = proto_field_type(array_match.group(1).strip(), record_names)
        return f"repeated {element_type}"
    if type_name in PROTO_SCALARS:
        return PROTO_SCALARS[type_name]
    if type_name in record_names:
        return type_name
    raise TypeCheckError(f"line ?:?: unsupported grpc proto field type: {type_name}")


def generate_proto(program: Program, verified: VerifiedProgram | None = None) -> str:
    if verified is None:
        verified = verify_program(program)

    record_decls = [declaration for declaration in program.declarations if isinstance(declaration, RecordTypeDecl)]
    service_decls = [declaration for declaration in program.declarations if isinstance(declaration, ServiceDecl)]
    grpc_record_names = {
        rpc.request_type
        for service in service_decls
        for rpc in service.rpcs
    } | {
        rpc.response_type
        for service in service_decls
        for rpc in service.rpcs
    }
    record_names = set(verified.records)

    lines: list[str] = [
        'syntax = "proto3";',
        "",
        f"package {proto_package_name(program.module_name)};",
        "",
    ]

    first_block = True
    for record in record_decls:
        if record.name not in grpc_record_names:
            continue
        if not first_block:
            lines.append("")
        first_block = False
        lines.append(f"message {record.name} {{")
        for field in record.fields:
            if field.proto_id is None:
                raise TypeCheckError(f"{field.pos.text()}: missing proto field id in grpc message: {record.name}.{field.name}")
            field_type = proto_field_type(field.type_name, record_names)
            lines.append(f"  {field_type} {field.name} = {field.proto_id};")
        lines.append("}")

    for service in service_decls:
        if not first_block:
            lines.append("")
        first_block = False
        lines.append(f"service {service.name} {{")
        for rpc in service.rpcs:
            lines.append(f"  rpc {rpc.name} ({rpc.request_type}) returns ({rpc.response_type});")
        lines.append("}")

    return "\n".join(lines).rstrip() + "\n"


def generate_proto_source(source: str) -> str:
    program = parse_source(source)
    verified = verify_program(program)
    return generate_proto(program, verified)


def generate_proto_file(path: str | Path) -> str:
    source = Path(path).read_text(encoding="utf-8")
    return generate_proto_source(source)
