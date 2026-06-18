#!/bin/bash
set -e
go mod tidy
go test ./...
go build -trimpath -o bin/demotaskcontrol ./cmd/demotaskcontrol
