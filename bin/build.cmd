@echo off
setlocal
go mod tidy
if errorlevel 1 exit /b %errorlevel%
go test ./...
if errorlevel 1 exit /b %errorlevel%
go build -trimpath -o bin\demotaskcontrol.exe .\cmd\demotaskcontrol
