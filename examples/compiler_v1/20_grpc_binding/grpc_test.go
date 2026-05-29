package main_test

import (
	"context"
	"net"
	"testing"

	app_main_grpc "freehold.local/grpc/app/main"
	app_mainpb "freehold.local/grpc/app/mainpb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

type mockUserServiceHandler struct{}

func (m *mockUserServiceHandler) GetUser(ctx context.Context, request *app_mainpb.UserRequest) (*app_mainpb.UserResponse, error) {
	if request.Id == 42 {
		return &app_mainpb.UserResponse{Name: "Ada Lovelace"}, nil
	}
	return nil, status.Error(codes.NotFound, "user not found")
}

func TestUserServiceGRPC(t *testing.T) {
	// Start TCP listener on a random local port
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to listen: %v", err)
	}

	// Create and start the gRPC server
	s := grpc.NewServer()
	app_main_grpc.RegisterUserServiceServer(s, &mockUserServiceHandler{})

	go func() {
		if err := s.Serve(lis); err != nil {
			// Serve will return err on Stop, which is fine
		}
	}()
	defer s.Stop()

	// Connect a gRPC client to the server
	conn, err := grpc.NewClient(lis.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatalf("failed to connect to server: %v", err)
	}
	defer conn.Close()

	client := app_mainpb.NewUserServiceClient(conn)

	// Test case 1: Successful call
	resp, err := client.GetUser(context.Background(), &app_mainpb.UserRequest{Id: 42})
	if err != nil {
		t.Fatalf("GetUser failed: %v", err)
	}
	if resp.Name != "Ada Lovelace" {
		t.Errorf("expected Name to be 'Ada Lovelace', got %q", resp.Name)
	}

	// Test case 2: NotFound error
	_, err = client.GetUser(context.Background(), &app_mainpb.UserRequest{Id: 99})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected status error, got %v", err)
	}
	if st.Code() != codes.NotFound {
		t.Errorf("expected code NotFound, got %v", st.Code())
	}
	if st.Message() != "user not found" {
		t.Errorf("expected message 'user not found', got %q", st.Message())
	}
}
