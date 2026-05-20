from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from freehold.core.ast import *

@dataclass
class BasicBlock:
    id: int
    label: str
    stmts: list[Any] = field(default_factory=list)

@dataclass
class CFGEdge:
    source: int
    target: int
    label: str = ""

@dataclass
class CFG:
    routine_name: str
    blocks: dict[int, BasicBlock]
    edges: list[CFGEdge]
    entry: int

class CFGBuilder:
    def __init__(self):
        self.next_id = 0
        self.blocks: dict[int, BasicBlock] = {}
        self.edges: list[CFGEdge] = []

    def block(self, label: str) -> BasicBlock:
        b = BasicBlock(self.next_id, label)
        self.blocks[b.id] = b
        self.next_id += 1
        return b

    def edge(self, a: BasicBlock, b: BasicBlock, label: str = "") -> None:
        self.edges.append(CFGEdge(a.id, b.id, label))

    def build_routine(self, r: RoutineDecl) -> CFG:
        self.next_id = 0
        self.blocks = {}
        self.edges = {}
        self.edges = []
        entry = self.block(f"{r.name}.entry")
        self.stmts(r.body, [entry])
        return CFG(r.name, self.blocks, self.edges, entry.id)

    def stmts(self, body: list[Any], exits: list[BasicBlock]) -> list[BasicBlock]:
        current = exits
        for s in body:
            if isinstance(s, IfStmt):
                after = self.block("after_if")
                next_current = []
                for cur in current:
                    cur.stmts.append(("branch", s.condition))
                    t = self.block("then")
                    f = self.block("else")
                    self.edge(cur, t, "true")
                    self.edge(cur, f, "false")
                    for x in self.stmts(s.then_body, [t]): self.edge(x, after, "join")
                    for x in self.stmts(s.else_body, [f]): self.edge(x, after, "join")
                current = [after]
            elif isinstance(s, WhileStmt):
                after = self.block("after_while")
                for cur in current:
                    body_block = self.block("while_body")
                    cur.stmts.append(("while", s.condition))
                    self.edge(cur, body_block, "true")
                    self.edge(cur, after, "false")
                    for x in self.stmts(s.body, [body_block]): self.edge(x, cur, "loop")
                current = [after]
            elif isinstance(s, ReturnStmt):
                for cur in current:
                    cur.stmts.append(s)
                current = []
            else:
                for cur in current:
                    cur.stmts.append(s)
        return current

def build_cfgs(program: Program) -> dict[str, CFG]:
    b = CFGBuilder()
    return {d.name: b.build_routine(d) for d in program.declarations if isinstance(d, RoutineDecl)}

def cfg_summary(cfg: CFG) -> dict[str, int]:
    return {"blocks": len(cfg.blocks), "edges": len(cfg.edges)}
