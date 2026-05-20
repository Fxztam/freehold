from freehold.core.feature import CompilerFeature, FeatureContribution

class RecordsFeature(CompilerFeature):
    name = "records"
    def contribute(self):
        return FeatureContribution(
            name=self.name,
            grammar_files=["freehold/grammar/freehold.lark"] if self.name == "core" else [],
            ast_nodes=['RecordTypeDecl', 'RecordLiteralExpr', 'FieldAccessExpr'],
            verifier_hooks=['record/nested/result.field'],
            interpreter_hooks=['RecordValue runtime'],
            test_filter="record",
        )
