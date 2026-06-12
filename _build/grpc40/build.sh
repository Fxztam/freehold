#!/bin/bash
set -e
go mod tidy
go test ./...
go build -trimpath -o bin/grpc40 ./cmd/grpc40
