package main

import (
	"context"
	app_main "freehold.local/app/main"
	_ "freehold.local/grpc/app/contract"
)

func main() {
	app_main.Main(context.Background())
}
