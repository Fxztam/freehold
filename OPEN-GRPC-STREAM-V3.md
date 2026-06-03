# OPEN-GRPC-STREAM-V3: gRPC Streaming Integration Design & Roadmap

This document outlines the design, syntax, semantic rules, and Go codegen architecture required to implement gRPC streaming (Server-side, Client-side, and Bidirectional) in Freehold V3.

---

## 1. Syntax & Grammar Specifications

The Lark grammar will be extended to support the `stream` keyword modifier on request and/or response types within `service` declarations.

### Lark Grammar Modifications
```lark
// Extended service definition rule
rpc_decl: "rpc" NAME "(" rpc_param ")" ":" rpc_return_type
rpc_param: [ "stream" ] NAME ":" type_ref
rpc_return_type: [ "stream" ] type_ref
```

### Grammar Semantics
* `stream` indicates that the corresponding parameter or return value is treated as a continuous sequence of messages of the specified type rather than a single message.
* A streaming RPC can have:
  * Server Streaming: Unary request (`request: PriceRequest`) $\rightarrow$ streaming response (`stream PriceReply`).
  * Client Streaming: Streaming request (`request: stream PriceRequest`) $\rightarrow$ unary response (`PriceReply`).
  * Bidirectional Streaming: Streaming request (`request: stream PriceRequest`) $\rightarrow$ streaming response (`stream PriceReply`).

---

## 2. Type Checking & Semantic Verification

The Freehold Verifier (`verifier.py` and the V2/V3 resolver/type checker) must enforce the following rules for streaming services:

1. **Record-Only Enforce**: Any type marked as `stream` must resolve to a valid Freehold `record` type that has valid `proto` field IDs defined.
2. **Channel Mapping**: 
   * A service routine implementing a server stream must accept a `Sender<T>` parameter, where `T` is the streaming response record type.
   * A service routine implementing a client stream must accept a `Receiver<T>` parameter, where `T` is the streaming request record type.
   * A bidirectional stream routine must accept both `Receiver<Req>` and `Sender<Resp>`.
3. **No Mixed Returns**: If the RPC signature returns a `stream`, the corresponding Freehold implementation routine must return `Void` (or `Result<Void, Error>`), as all actual response values are published asynchronously via the `Sender<T>` channel.

---

## 3. Go Codegen Architecture & Runtime Adapter

Instead of introducing new streaming APIs inside the Freehold language, gRPC streams will map directly to Freehold's native structured concurrency primitives: **Channels** (`Sender<T>` and `Receiver<T>`).

```
┌─────────────────────────────────┐
│     Go gRPC Network Stream      │
└────────────────┬────────────────┘
                 │ (Adapter Goroutine)
                 ▼
┌─────────────────────────────────┐
│   Freehold Channel (Go chan)   │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Freehold Async Routine (Await) │
└─────────────────────────────────┘
```

### Go Code Generation Details

1. **gRPC Service Stream Descriptor**:
   Modify the generated `grpc.ServiceDesc` to register methods in the `Streams` slice:
   ```go
   Streams: []grpc.StreamDesc{
       {
           StreamName:    "StreamQuotes",
           Handler:       _PricingService_StreamQuotes_Handler,
           ServerStreams: true,
           ClientStreams: false,
       },
   },
   ```

2. **Stream Handler Adapter**:
   For a server stream `QuoteStream(PriceRequest) returns (stream PriceReply)`, generate a handler that bridges the gRPC stream to a Freehold `Sender`:
   ```go
   func _PricingService_StreamQuotes_Handler(srv interface{}, stream grpc.ServerStream) error {
       m := new(PriceRequest)
       if err := stream.RecvMsg(m); err != nil {
           return err
       }
       
       // 1. Create a Freehold-native channel wrapper for PriceReply
       ch := NewChannel[PriceReply](16)
       sender := ch.Sender()
       
       // 2. Start a background goroutine to read from the channel and send over gRPC
       go func() {
           for {
               reply, ok := <-ch.GoChan()
               if !ok {
                   break
               }
               if err := stream.SendMsg(&reply); err != nil {
                   break
               }
           }
       }()
       
       // 3. Call the Freehold implementation routine passing the request and sender channel
       err := srv.(PricingServiceServer).StreamQuotes(stream.Context(), m, sender)
       ch.Close() // Close channel when routine completes
       return err
   }
   ```

---

## 4. Implementation Status & Conformance (ERLEDIGT)

Alle Implementierungsphasen wurden erfolgreich abgeschlossen und in den Compiler sowie die Test-Suite integriert:

| Phase | Status | Beschreibung & Verifikation |
| :--- | :--- | :--- |
| **Phase 1: Grammar & Parser** | **ERLEDIGT** | Lark-Grammatik und AST-Strukturen erweitert, um `stream` für Request- und Response-Parameter in gRPC-Services zu unterstützen. |
| **Phase 2: Semantic Verification** | **ERLEDIGT** | Validierung im Typechecker implementiert: Prüfung auf Record-Typen mit `proto`-IDs, korrekte Typ-Abbildung zu Freehold-Channels (`Sender<T>` / `Receiver<T>`). |
| **Phase 3: Go Codegen** | **ERLEDIGT** | Generierung der gRPC-Streaming-Deskriptoren und asynchronen Adapter-Methoden in den Go-Bindings zur Weiterleitung von gRPC-Netzwerkströmen. |
| **Phase 4: Conformance Tests** | **ERLEDIGT** | Abgesichert über das Testmodul `24_grpc_idl` (inklusive `streaming_service.fh` und verifizierten Golden-Go-Bindings unter `expected_go_bindings/streaming_service.go`). |

Die vollständige Suite läuft unter `python tools/test_steps.py` stabil und fehlerfrei durch.

