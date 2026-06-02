package main

import (
	"flag"
	"fmt"
	"os"

	"freehold-go-frontend/internal/lexer"
	"freehold-go-frontend/internal/parser"
	"freehold-go-frontend/internal/token"
	"freehold-go-frontend/internal/whyml"
)

func main() {
	outFile := flag.String("out", "", "write WhyML output to this file")
	flag.Parse()

	if flag.NArg() != 1 {
		fmt.Println("usage: go-whyml [--out <file>] <input.fh>")
		os.Exit(2)
	}

	inputFile := flag.Arg(0)
	sourceBytes, err := os.ReadFile(inputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to read file: %v\n", err)
		os.Exit(1)
	}

	l := lexer.New(string(sourceBytes))
	var toks []token.Token
	for {
		tok := l.Next()
		toks = append(toks, tok)
		if tok.Kind == token.EOF {
			break
		}
	}

	p := parser.New(toks)
	mod, err := p.ParseModule()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to parse module: %v\n", err)
		if len(p.Diagnostics()) > 0 {
			for _, diag := range p.Diagnostics() {
				fmt.Fprintf(os.Stderr, "  %v\n", diag)
			}
		}
		os.Exit(1)
	}

	gen := whyml.NewGenerator(mod)
	output := gen.Generate()

	if *outFile != "" {
		err = os.WriteFile(*outFile, []byte(output), 0644)
		if err != nil {
			fmt.Fprintf(os.Stderr, "failed to write output: %v\n", err)
			os.Exit(1)
		}
	} else {
		fmt.Println(output)
	}
}
