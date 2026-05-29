package main_test

import (
	"context"
	"net"
	"testing"

	app_main_grpc "freehold.local/grpc/app/main"
	app_mainpb "freehold.local/grpc/app/mainpb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type mockPricingServiceHandler struct{}

func (m *mockPricingServiceHandler) Quote(ctx context.Context, request *app_mainpb.PriceRequest) (*app_mainpb.PriceReply, error) {
	return &app_mainpb.PriceReply{
		Total:    request.Quantity * 150,
		Accepted: true,
		Audit: app_mainpb.AuditEvent{
			TraceId: request.TraceId,
			Message: "mock pricing quote accepted",
		},
	}, nil
}

func TestPricingServiceGRPC(t *testing.T) {
	// Start TCP listener
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to listen: %v", err)
	}

	// Create and start gRPC server
	s := grpc.NewServer()
	app_main_grpc.RegisterPricingServiceServer(s, &mockPricingServiceHandler{})

	go func() {
		if err := s.Serve(lis); err != nil {
			// server stopped
		}
	}()
	defer s.Stop()

	// Connect gRPC client
	conn, err := grpc.NewClient(lis.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatalf("failed to connect: %v", err)
	}
	defer conn.Close()

	client := app_mainpb.NewPricingServiceClient(conn)

	// Call Quote
	resp, err := client.Quote(context.Background(), &app_mainpb.PriceRequest{
		Sku:      "widget-a",
		Quantity: 4,
		TraceId:  "trace-12345",
	})
	if err != nil {
		t.Fatalf("Quote failed: %v", err)
	}

	if resp.Total != 600 {
		t.Errorf("expected total 600, got %d", resp.Total)
	}
	if !resp.Accepted {
		t.Errorf("expected accepted to be true")
	}
	if resp.Audit.TraceId != "trace-12345" {
		t.Errorf("expected trace id 'trace-12345', got %q", resp.Audit.TraceId)
	}
	if resp.Audit.Message != "mock pricing quote accepted" {
		t.Errorf("expected message 'mock pricing quote accepted', got %q", resp.Audit.Message)
	}
}
