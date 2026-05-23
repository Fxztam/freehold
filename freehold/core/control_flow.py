from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from freehold.core.ast import *


@dataclass(frozen=True)
class RoutineFlowSummary:
    routine_name: str
    routine_kind: str
    normal_return_possible: bool
    guaranteed_exit: bool
    declared_aborts: frozenset[str]
    emitted_aborts: frozenset[str]
    called_routines: frozenset[str]
    propagated_aborts: frozenset[str]


@dataclass(frozen=True)
class _BlockFlow:
    normal_return_possible: bool
    guaranteed_exit: bool
    emitted_aborts: frozenset[str]
    called_routines: frozenset[str]


class ControlFlowAnalyzer:
    def __init__(self, routines: dict[str, RoutineDecl], module_name: str = ""):
        self.routines = routines
        self.module_name = module_name

    def analyze_program(self, program: Program) -> dict[str, RoutineFlowSummary]:
        analyzer = ControlFlowAnalyzer(
            {declaration.name: declaration for declaration in program.declarations if isinstance(declaration, RoutineDecl)},
            program.module_name,
        )
        return analyzer.analyze_routines()

    def analyze_routines(self) -> dict[str, RoutineFlowSummary]:
        return {name: self.analyze_routine(routine) for name, routine in self.routines.items()}

    def analyze_routine(self, routine: RoutineDecl) -> RoutineFlowSummary:
        body_flow = self._block(routine.body)
        declared_aborts = frozenset(clause.error_name for clause in routine.aborts)
        normal_return_possible = body_flow.normal_return_possible or (
            routine.kind == "procedure" and not body_flow.guaranteed_exit
        )
        return RoutineFlowSummary(
            routine_name=routine.name,
            routine_kind=routine.kind,
            normal_return_possible=normal_return_possible,
            guaranteed_exit=body_flow.guaranteed_exit,
            declared_aborts=declared_aborts,
            emitted_aborts=body_flow.emitted_aborts,
            called_routines=body_flow.called_routines,
            propagated_aborts=declared_aborts,
        )

    def _block(self, body: list[Any]) -> _BlockFlow:
        normal_return_possible = False
        emitted_aborts: set[str] = set()
        called_routines: set[str] = set()

        for statement in body:
            statement_flow = self._statement(statement)
            normal_return_possible = normal_return_possible or statement_flow.normal_return_possible
            emitted_aborts.update(statement_flow.emitted_aborts)
            called_routines.update(statement_flow.called_routines)
            if statement_flow.guaranteed_exit:
                return _BlockFlow(
                    normal_return_possible,
                    True,
                    frozenset(emitted_aborts),
                    frozenset(called_routines),
                )

        return _BlockFlow(normal_return_possible, False, frozenset(emitted_aborts), frozenset(called_routines))

    def _statement(self, statement: Any) -> _BlockFlow:
        if isinstance(statement, ReturnStmt):
            called_routines = self._calls_in_expr(statement.value)
            return _BlockFlow(True, True, frozenset(), frozenset(called_routines))
        if isinstance(statement, AbortStmt):
            return _BlockFlow(False, True, frozenset({statement.error_name}), frozenset())
        if isinstance(statement, CallStmt):
            called_routines = set(self._routine_call_name(statement.name))
            for argument in statement.args:
                called_routines.update(self._calls_in_expr(argument))
            return _BlockFlow(False, False, frozenset(), frozenset(called_routines))
        if isinstance(statement, LetStmt):
            return self._expression_statement_flow(statement.expr)
        if isinstance(statement, AssignStmt):
            return self._expression_statement_flow(statement.expr)
        if isinstance(statement, FieldAssignStmt):
            return self._expression_statement_flow(statement.expr)
        if isinstance(statement, CheckStmt):
            return self._expression_statement_flow(statement.expr)
        if isinstance(statement, IfStmt):
            condition_calls = self._calls_in_expr(statement.condition)
            then_flow = self._block(statement.then_body)
            else_flow = self._block(statement.else_body)
            return _BlockFlow(
                then_flow.normal_return_possible or else_flow.normal_return_possible,
                then_flow.guaranteed_exit and else_flow.guaranteed_exit,
                then_flow.emitted_aborts | else_flow.emitted_aborts,
                frozenset(set(condition_calls) | set(then_flow.called_routines) | set(else_flow.called_routines)),
            )
        if isinstance(statement, WhileStmt):
            body_flow = self._block(statement.body)
            called_routines = set(self._calls_in_expr(statement.condition)) | set(body_flow.called_routines)
            for invariant in statement.invariants:
                called_routines.update(self._calls_in_expr(invariant))
            if statement.variant is not None:
                called_routines.update(self._calls_in_expr(statement.variant))
            return _BlockFlow(False, False, body_flow.emitted_aborts, frozenset(called_routines))
        if isinstance(statement, CaseStmt):
            case_calls = set(self._calls_in_expr(statement.expr))
            branch_flows = [self._block(branch.body) for branch in statement.branches]
            default_flow = self._block(statement.default_body)
            all_flows = branch_flows + [default_flow]
            emitted_aborts: set[str] = set()
            called_routines: set[str] = set(case_calls)
            normal_return_possible = False
            guaranteed_exit = True
            for branch in statement.branches:
                called_routines.update(self._calls_in_expr(branch.value))
            for flow in all_flows:
                emitted_aborts.update(flow.emitted_aborts)
                called_routines.update(flow.called_routines)
                normal_return_possible = normal_return_possible or flow.normal_return_possible
                guaranteed_exit = guaranteed_exit and flow.guaranteed_exit
            return _BlockFlow(normal_return_possible, guaranteed_exit, frozenset(emitted_aborts), frozenset(called_routines))
        return _BlockFlow(False, False, frozenset(), frozenset())

    def _expression_statement_flow(self, expression: Any) -> _BlockFlow:
        return _BlockFlow(False, False, frozenset(), frozenset(self._calls_in_expr(expression)))

    def _calls_in_expr(self, expression: Any) -> set[str]:
        if expression is None:
            return set()
        if isinstance(expression, (ReturnPlain, ReturnOk)):
            return self._calls_in_expr(expression.expr)
        if isinstance(expression, ReturnError):
            return set()
        if isinstance(expression, CallExpr):
            called_routines = set(self._routine_call_name(expression.name))
            for argument in expression.args:
                called_routines.update(self._calls_in_expr(argument))
            return called_routines
        if isinstance(expression, NamedArg):
            return self._calls_in_expr(expression.expr)
        if isinstance(expression, RecordLiteralExpr):
            called_routines: set[str] = set()
            for argument in expression.args:
                called_routines.update(self._calls_in_expr(argument))
            return called_routines
        if isinstance(expression, ArrayLiteralExpr):
            called_routines: set[str] = set()
            for item in expression.items:
                called_routines.update(self._calls_in_expr(item))
            return called_routines
        if isinstance(expression, IndexExpr):
            return self._calls_in_expr(expression.index)
        if isinstance(expression, UnaryExpr):
            return self._calls_in_expr(expression.expr)
        if isinstance(expression, BinaryExpr):
            return self._calls_in_expr(expression.left) | self._calls_in_expr(expression.right)
        return set()

    def _routine_call_name(self, name: str) -> set[str]:
        local_name = self._local_routine_name(name)
        if local_name in self.routines:
            return {local_name}
        return set()

    def _local_routine_name(self, name: str) -> str:
        prefix = f"{self.module_name}."
        return name[len(prefix):] if self.module_name and name.startswith(prefix) else name