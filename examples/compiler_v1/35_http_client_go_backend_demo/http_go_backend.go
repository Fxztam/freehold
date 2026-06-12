package main

import (
	"encoding/json"
	"errors"
	"net/http"
)

type userDTO struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

type createUserRequest struct {
	Name  string `json:"name"`
	Email string `json:"email"`
}

type problemDetails struct {
	StatusCode int    `json:"statusCode"`
	Code       string `json:"code"`
	Message    string `json:"message"`
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/users/42", handleUser42)
	mux.HandleFunc("/users/missing", handleMissingUser)
	mux.HandleFunc("/users", handleUsers)
	server := &http.Server{Addr: "127.0.0.1:8104", Handler: mux}
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		panic(err)
	}
}

func handleUser42(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	writeJSON(w, http.StatusOK, userDTO{ID: "42", Name: "Ada", Email: "ada@example.test"})
}

func handleUsers(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req createUserRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, problemDetails{StatusCode: http.StatusBadRequest, Code: "INVALID_JSON", Message: "invalid JSON"})
		return
	}
	writeJSON(w, http.StatusCreated, userDTO{ID: "43", Name: req.Name, Email: req.Email})
}

func handleMissingUser(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	writeJSON(w, http.StatusNotFound, problemDetails{StatusCode: http.StatusNotFound, Code: "USER_NOT_FOUND", Message: "user resource was not found"})
}

func writeJSON(w http.ResponseWriter, statusCode int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(value)
}
