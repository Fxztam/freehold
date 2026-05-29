#!/bin/bash
set -e
go mod tidy
go test ./...
