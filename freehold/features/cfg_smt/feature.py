from freehold.core.feature import CompilerFeature, FeatureContribution

class CfgSmtFeature(CompilerFeature):
    name = "cfg_smt"
    def contribute(self):
        return FeatureContribution(
            name=self.name,
            grammar_files=["freehold/grammar/freehold.lark"] if self.name == "core" else [],
            ast_nodes=['CFG', 'SymbolicObligation'],
            verifier_hooks=['CFG/SMT smoke'],
            interpreter_hooks=['none'],
            test_filter="cfg_smt",
        )
