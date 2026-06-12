package main

import (
	"flag"
	"fmt"
	"os"

	"freehold-go-frontend/internal/semantic"
)

func main() {
	outFile := flag.String("out", "", "write source-map JSON to this file")
	flag.Parse()

	if flag.NArg() != 1 {
		fmt.Println("usage: go-source-map [--out <file>] <entry.fh>")
		os.Exit(2)
	}

	entryFile := flag.Arg(0)
	content, err := semantic.ExportSourceMapJSON(entryFile)
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
		fmt.Println("[OK] Source-map JSON written:", *outFile)
		return
	}

	fmt.Print(content)
}
