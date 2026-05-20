from dataclasses import dataclass, field

@dataclass
class FeatureContribution:
    name: str
    grammar_files: list[str] = field(default_factory=list)
    ast_nodes: list[str] = field(default_factory=list)
    verifier_hooks: list[str] = field(default_factory=list)
    interpreter_hooks: list[str] = field(default_factory=list)
    test_filter: str | None = None

class CompilerFeature:
    name = "abstract"
    def contribute(self) -> FeatureContribution:
        raise NotImplementedError
