package main

import (
	"bufio"
	"crypto/sha1"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
)

const wsMaxPayloadBytes int64 = 16 * 1024 * 1024

type wsFrame struct {
	opcode  byte
	payload []byte
	masked  bool
}

type wsConn struct {
	conn    net.Conn
	reader  *bufio.Reader
	writeMu sync.Mutex
}

func main() {
	state := &relayState{
		fromA:    make(chan string, 1),
		replyToA: make(chan string, 1),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/ws", state.handleWebSocket)
	server := &http.Server{Addr: "127.0.0.1:8102", Handler: mux}
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		panic(err)
	}
}

type relayState struct {
	mu       sync.Mutex
	count    int
	fromA    chan string
	replyToA chan string
}

func (s *relayState) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, reader, err := acceptWebSocket(w, r)
	if err != nil {
		return
	}
	ws := &wsConn{conn: conn, reader: reader}

	s.mu.Lock()
	s.count++
	index := s.count
	s.mu.Unlock()

	if index == 1 {
		s.handleClientA(ws)
		return
	}
	if index == 2 {
		s.handleClientB(ws)
		return
	}
	_ = ws.writeText("go backend: server already has two demo clients")
	_ = ws.close()
}

func (s *relayState) handleClientA(clientA *wsConn) {
	defer clientA.conn.Close()
	if err := clientA.writeText("go backend: welcome client A"); err != nil {
		return
	}
	msgA, err := clientA.readText()
	if err != nil {
		return
	}
	s.fromA <- msgA
	reply := <-s.replyToA
	_ = clientA.writeText(reply)
	_ = clientA.close()
}

func (s *relayState) handleClientB(clientB *wsConn) {
	defer clientB.conn.Close()
	if err := clientB.writeText("go backend: welcome client B"); err != nil {
		return
	}
	msgA := <-s.fromA
	if err := clientB.writeText("go backend relay to B: " + msgA); err != nil {
		return
	}
	msgB, err := clientB.readText()
	if err != nil {
		return
	}
	s.replyToA <- "go backend relay to A: " + msgB
	_ = clientB.close()
}

func acceptWebSocket(w http.ResponseWriter, r *http.Request) (net.Conn, *bufio.Reader, error) {
	if r.Method != http.MethodGet || !strings.EqualFold(r.Header.Get("Upgrade"), "websocket") || !strings.Contains(strings.ToLower(r.Header.Get("Connection")), "upgrade") {
		http.Error(w, "invalid websocket upgrade", http.StatusBadRequest)
		return nil, nil, errors.New("invalid websocket upgrade")
	}
	if r.Header.Get("Sec-WebSocket-Version") != "13" {
		http.Error(w, "unsupported websocket version", http.StatusBadRequest)
		return nil, nil, errors.New("unsupported websocket version")
	}
	key := r.Header.Get("Sec-WebSocket-Key")
	if key == "" {
		http.Error(w, "missing websocket key", http.StatusBadRequest)
		return nil, nil, errors.New("missing websocket key")
	}

	hijacker, ok := w.(http.Hijacker)
	if !ok {
		http.Error(w, "hijacking unsupported", http.StatusInternalServerError)
		return nil, nil, errors.New("hijacking unsupported")
	}
	conn, rw, err := hijacker.Hijack()
	if err != nil {
		return nil, nil, err
	}
	response := "HTTP/1.1 101 Switching Protocols\r\n" +
		"Upgrade: websocket\r\n" +
		"Connection: Upgrade\r\n" +
		"Sec-WebSocket-Accept: " + wsAcceptKey(key) + "\r\n\r\n"
	if _, err := rw.WriteString(response); err != nil {
		_ = conn.Close()
		return nil, nil, err
	}
	if err := rw.Flush(); err != nil {
		_ = conn.Close()
		return nil, nil, err
	}
	return conn, rw.Reader, nil
}

func wsAcceptKey(key string) string {
	h := sha1.New()
	_, _ = h.Write([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
	return base64.StdEncoding.EncodeToString(h.Sum(nil))
}

func (c *wsConn) readText() (string, error) {
	for {
		frame, err := readFrame(c.reader)
		if err != nil {
			return "", err
		}
		if !frame.masked {
			return "", errors.New("client frame must be masked")
		}
		switch frame.opcode {
		case 1:
			return string(frame.payload), nil
		case 8:
			return "", io.EOF
		case 9:
			if err := c.writeFrame(10, frame.payload); err != nil {
				return "", err
			}
		case 10:
		default:
			return "", fmt.Errorf("unsupported websocket opcode %d", frame.opcode)
		}
	}
}

func (c *wsConn) writeText(message string) error {
	return c.writeFrame(1, []byte(message))
}

func (c *wsConn) close() error {
	return c.writeFrame(8, nil)
}

func (c *wsConn) writeFrame(opcode byte, payload []byte) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	return writeFrame(c.conn, opcode, payload)
}

func readFrame(r io.Reader) (wsFrame, error) {
	header := make([]byte, 2)
	if _, err := io.ReadFull(r, header); err != nil {
		return wsFrame{}, err
	}
	if header[0]&0x80 == 0 {
		return wsFrame{}, errors.New("fragmented websocket frames are not supported")
	}
	opcode := header[0] & 0x0F
	masked := (header[1] & 0x80) != 0
	payloadLen := int64(header[1] & 0x7F)
	if payloadLen == 126 {
		lenBytes := make([]byte, 2)
		if _, err := io.ReadFull(r, lenBytes); err != nil {
			return wsFrame{}, err
		}
		payloadLen = int64(lenBytes[0])<<8 | int64(lenBytes[1])
	} else if payloadLen == 127 {
		lenBytes := make([]byte, 8)
		if _, err := io.ReadFull(r, lenBytes); err != nil {
			return wsFrame{}, err
		}
		payloadLen = 0
		for i := 0; i < 8; i++ {
			payloadLen = (payloadLen << 8) | int64(lenBytes[i])
		}
	}
	if payloadLen < 0 || payloadLen > wsMaxPayloadBytes {
		return wsFrame{}, errors.New("websocket payload too large")
	}
	if opcode >= 8 && payloadLen > 125 {
		return wsFrame{}, errors.New("websocket control frame too large")
	}
	maskKey := make([]byte, 4)
	if masked {
		if _, err := io.ReadFull(r, maskKey); err != nil {
			return wsFrame{}, err
		}
	}
	payload := make([]byte, payloadLen)
	if _, err := io.ReadFull(r, payload); err != nil {
		return wsFrame{}, err
	}
	if masked {
		for i := int64(0); i < payloadLen; i++ {
			payload[i] ^= maskKey[i%4]
		}
	}
	return wsFrame{opcode: opcode, payload: payload, masked: masked}, nil
}

func writeFrame(w io.Writer, opcode byte, payload []byte) error {
	var header []byte
	header = append(header, 0x80|opcode)
	length := len(payload)
	if length < 126 {
		header = append(header, byte(length))
	} else if length <= 65535 {
		header = append(header, 126, byte(length>>8), byte(length))
	} else {
		header = append(header, 127)
		for i := 7; i >= 0; i-- {
			header = append(header, byte(length>>(i*8)))
		}
	}
	if _, err := w.Write(header); err != nil {
		return err
	}
	if _, err := w.Write(payload); err != nil {
		return err
	}
	return nil
}
