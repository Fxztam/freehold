package main

import (
	"flag"
	"fmt"
	"os"

	"freehold-go-frontend/internal/semantic"
)

func main() {
	outFile := flag.String("out", "", "write compare IR JSON to this file")
	profile := flag.String("profile", "v1", "compare-ir export profile (v0 or v1)")
	flag.Parse()

	if flag.NArg() != 1 {
		fmt.Println("usage: go-compare-ir [--out <file>] <entry.fh>")
		os.Exit(2)
	}

	entryFile := flag.Arg(0)
	content, err := semantic.ExportCompareIRJSON(entryFile, *profile)
	if err != nil {
		fmt.Println("FAIL", entryFile, "=>", err)
		os.Exit(1)
	}

	if *outFile != "" {
		if err := os.WriteFile(*outFile, []byte(content), 0644); err != nil {
			fmt.Println("FAIL", entryFile, "=>", err)
			os.Exit(1)
		}
		fmt.Println("OK   ", entryFile)
		fmt.Println("[OK] Compare-IR JSON written:", *outFile)
		return
	}

	fmt.Print(content)
}
