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


COMPARE_IR_SCHEMA_V0 = "fh-compare-ir-v0"
COMPARE_IR_SCHEMA_V1 = "fh-compare-ir-v1"
FREEHOLD_LANGUAGE_VERSION = "freehold-v1"


def _schema_for_profile(profile: str) -> str:
    if profile == "v0":
        return COMPARE_IR_SCHEMA_V0
    if profile == "v1":
        return COMPARE_IR_SCHEMA_V1
    raise ValueError(f"unsupported compare-ir profile: {profile!r}")


def export_verified_program(verified: VerifiedProgram, profile: str = "v1") -> dict[str, Any]:
    return {
        "schema": _schema_for_profile(profile),
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


def export_compare_ir_json(verified: VerifiedProgram, profile: str = "v1") -> str:
    return json.dumps(export_verified_program(verified, profile=profile), indent=2, ensure_ascii=False) + "\n"