from __future__ import annotations

import json
from typing import Any

from freehold.core.fhir import (
    export_program,
    export_routine_decl,
    export_service_decl,
    export_type_def,
    export_record_def,
)
from freehold.core.verifier import VerifiedProgram


COMPARE_IR_SCHEMA = "fh-compare-ir-v0"
FREEHOLD_LANGUAGE_VERSION = "freehold-v1"


def export_verified_program(verified: VerifiedProgram) -> dict[str, Any]:
    return {
        "schema": COMPARE_IR_SCHEMA,
        "language_version": FREEHOLD_LANGUAGE_VERSION,
        "module": export_program(verified.ast),
        "analysis": {
            "types": [export_type_def(verified.types[name]) for name in sorted(verified.types)],
            "records": [export_record_def(verified.records[name]) for name in sorted(verified.records)],
            "errors": sorted(verified.errors),
            "routines": [export_routine_decl(verified.routines[name]) for name in sorted(verified.routines)],
            "services": [export_service_decl(verified.services[name]) for name in sorted(verified.services)],
        },
    }


def export_compare_ir_json(verified: VerifiedProgram) -> str:
    return json.dumps(export_verified_program(verified), indent=2, ensure_ascii=False) + "\n"