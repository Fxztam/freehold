package semantic

import (
	"testing"
)

func TestControlFlowAnalyzerSimpleReturn(t *testing.T) {
	module := parseModule(t, `module SimpleReturn
function answer() returns Integer is
    return 42
end answer
end SimpleReturn`)

	analyzer := NewControlFlowAnalyzer(module)
	summaries := analyzer.AnalyzeRoutines()

	summary, ok := summaries["answer"]
	if !ok {
		t.Fatal("Expected summary for answer")
	}

	if !summary.NormalReturnPossible {
		t.Error("Expected normal return possible to be true")
	}
	if !summary.GuaranteedExit {
		t.Error("Expected guaranteed exit to be true")
	}
	if len(summary.EmittedAborts) != 0 {
		t.Errorf("Expected 0 emitted aborts, got %d", len(summary.EmittedAborts))
	}
}

func TestControlFlowAnalyzerAbort(t *testing.T) {
	module := parseModule(t, `module SimpleAbort
error NotFound
procedure fail() is
    abort NotFound
end fail
end SimpleAbort`)

	analyzer := NewControlFlowAnalyzer(module)
	summaries := analyzer.AnalyzeRoutines()

	summary, ok := summaries["fail"]
	if !ok {
		t.Fatal("Expected summary for fail")
	}

	if summary.NormalReturnPossible {
		t.Error("Expected normal return possible to be false")
	}
	if !summary.GuaranteedExit {
		t.Error("Expected guaranteed exit to be true")
	}
	if !summary.EmittedAborts["NotFound"] {
		t.Error("Expected EmittedAborts to contain NotFound")
	}
}

func TestControlFlowAnalyzerIfStmtSplit(t *testing.T) {
	module := parseModule(t, `module IfSplit
error NotFound
function check_flag(flag: Boolean) returns Integer is
    if flag then
        return 1
    else
        abort NotFound
    end if
end check_flag
end IfSplit`)

	analyzer := NewControlFlowAnalyzer(module)
	summaries := analyzer.AnalyzeRoutines()

	summary, ok := summaries["check_flag"]
	if !ok {
		t.Fatal("Expected summary for check_flag")
	}

	if !summary.NormalReturnPossible {
		t.Error("Expected normal return possible to be true")
	}
	if !summary.GuaranteedExit {
		t.Error("Expected guaranteed exit to be true")
	}
	if !summary.EmittedAborts["NotFound"] {
		t.Error("Expected EmittedAborts to contain NotFound")
	}
}

func TestControlFlowAnalyzerCalls(t *testing.T) {
	module := parseModule(t, `module Calls
function helper() returns Integer is
    return 1
end helper

procedure main() is
    let val: Integer = helper()
    call main()
end main
end Calls`)

	analyzer := NewControlFlowAnalyzer(module)
	summaries := analyzer.AnalyzeRoutines()

	mainSummary, ok := summaries["main"]
	if !ok {
		t.Fatal("Expected summary for main")
	}

	if !mainSummary.CalledRoutines["helper"] {
		t.Error("Expected CalledRoutines to contain helper")
	}
	if !mainSummary.CalledRoutines["main"] {
		t.Error("Expected CalledRoutines to contain main")
	}
}
