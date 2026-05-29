@echo off
setlocal
go mod tidy
if errorlevel 1 exit /b %errorlevel%
go test ./...
