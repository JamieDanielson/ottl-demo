#!/usr/bin/env python3
"""Writes the demo's OTLP/JSON fixtures (data/*.json) with timestamps near "now".

The fixtures are committed, so this script is only needed to refresh timestamps
(for a trace UI such as Jaeger, whose search defaults to recent data) or to change
the story. Every value is fake: example.com addresses, the 4111 test card, FAKE tokens.

Usage: python3 data/make_fixtures.py
"""
import hashlib
import json
import pathlib
import time

OUT = pathlib.Path(__file__).resolve().parent
NOW = time.time_ns()
SERVER, CLIENT = 2, 3
UNSET, OK, ERROR = 0, 1, 2


def hexid(seed, nbytes):
    # Deterministic IDs keep the fixtures diff-friendly across regenerations.
    return hashlib.sha256(seed.encode()).hexdigest()[: nbytes * 2]


def val(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, list):
        return {"arrayValue": {"values": [val(x) for x in v]}}
    return {"stringValue": v}


def attrs(d):
    return [{"key": k, "value": val(v)} for k, v in d.items()]


def span(trace, sid, name, kind, start_ms, dur_ms, a, parent=None, status=UNSET, msg="", events=()):
    s = {
        "traceId": hexid(trace, 16),
        "spanId": hexid(trace + sid, 8),
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(NOW + start_ms * 1_000_000),
        "endTimeUnixNano": str(NOW + (start_ms + dur_ms) * 1_000_000),
        "attributes": attrs(a),
        "status": {"code": status, **({"message": msg} if msg else {})},
    }
    if parent:
        s["parentSpanId"] = hexid(trace + parent, 8)
    if events:
        s["events"] = [
            {"timeUnixNano": str(NOW + (start_ms + dur_ms) * 1_000_000), "name": n, "attributes": attrs(ea)}
            for n, ea in events
        ]
    return s


def resource_spans(service, spans):
    return {
        "resource": {"attributes": attrs({"service.name": service, "deployment.environment.name": "demo"})},
        "scopeSpans": [{"scope": {"name": "telescope-shop", "version": "1.0.0"}, "spans": spans}],
    }


def probe(path):
    return {
        "http.request.method": "GET",
        "url.path": path,
        "http.route": path,
        "user_agent.original": "kube-probe/1.31",
        "http.response.status_code": 200,
    }


# Scene 1: probe noise. The /readyz probe pings the database, so its child span
# carries no HTTP attributes. Filtering on HTTP attributes alone orphans it.
health = [
    resource_spans("frontend-proxy", [
        span(f"healthz-{i}", "root", "GET /healthz", SERVER, i * 1000, 1, probe("/healthz"))
        for i in range(4)
    ]),
    resource_spans("product-catalog", [
        s
        for i in range(3)
        for s in (
            span(f"readyz-{i}", "root", "GET /readyz", SERVER, i * 1000, 3, probe("/readyz")),
            span(f"readyz-{i}", "db", "SELECT", CLIENT, i * 1000 + 1, 1,
                 {"db.system.name": "postgresql", "db.operation.name": "SELECT", "db.query.text": "SELECT 1"},
                 parent="root"),
        )
    ]),
]

# Scene 2: real browsing. Product pages carry IDs in the span name (high
# cardinality). The blog post's path contains "health" and must survive the filter.
browse = [
    resource_spans("frontend", [
        span(f"product-{pid}", "root", f"GET /api/products/{pid}", SERVER, n * 400, 12, {
            "http.request.method": "GET",
            "url.path": f"/api/products/{pid}",
            "http.route": "/api/products/{productId}",
            "user_agent.original": "Mozilla/5.0",
            "http.response.status_code": 200,
        })
        for n, pid in enumerate(["OLJCESPC7Z", "66VCHSJNUP", "L9ECAV7KIM"])
    ] + [
        span("blog", "root", "GET /blog/healthy-stargazing", SERVER, 1500, 20, {
            "http.request.method": "GET",
            "url.path": "/blog/healthy-stargazing",
            "http.route": "/blog/{slug}",
            "user_agent.original": "Mozilla/5.0",
            "http.response.status_code": 200,
        }),
    ]),
]

# Scene 3: one failing checkout that leaks PII at every hop. Two teams use two
# different keys for the customer's email (user.email vs app.customer.email).
T = "checkout-1"
checkout = [
    resource_spans("frontend", [
        span(T, "root", "POST /api/checkout", SERVER, 0, 180, {
            "http.request.method": "POST",
            "url.path": "/api/checkout",
            "url.query": "token=abc123&session=s-9981",
            "http.route": "/api/checkout",
            "http.request.header.authorization": ["Bearer FAKE-TOKEN-123"],
            "user.email": "jane.doe@example.com",
            "user.id": "u-7781",
            "user_agent.original": "Mozilla/5.0",
            "client.address": "203.0.113.42",
            "http.response.status_code": 500,
        }, status=ERROR),
    ]),
    resource_spans("checkout", [
        span(T, "place", "oteldemo.CheckoutService/PlaceOrder", SERVER, 5, 170, {
            "rpc.system.name": "grpc",
            "rpc.method": "oteldemo.CheckoutService/PlaceOrder",
            "app.customer.email": "jane.doe@example.com",
            "app.order.items.count": 2,
        }, parent="root", status=ERROR, msg="payment failed"),
        span(T, "cart", "oteldemo.CartService/GetCart", CLIENT, 10, 15, {
            "rpc.system.name": "grpc",
            "rpc.method": "oteldemo.CartService/GetCart",
            "user.id": "u-7781",
        }, parent="place"),
        span(T, "quote", "oteldemo.ShippingService/GetQuote", CLIENT, 30, 20, {
            "rpc.system.name": "grpc",
            "rpc.method": "oteldemo.ShippingService/GetQuote",
        }, parent="place"),
    ]),
    resource_spans("payment", [
        span(T, "charge", "oteldemo.PaymentService/Charge", SERVER, 60, 100, {
            "rpc.system.name": "grpc",
            "rpc.method": "oteldemo.PaymentService/Charge",
            "app.payment.card_type": "visa",
            "app.payment.card_number": "4111 1111 1111 1111",
            "app.payment.amount": 79.99,
        }, parent="place", status=ERROR, msg="card declined", events=[
            ("exception", {
                "exception.type": "CardDeclinedError",
                "exception.message": "Card 4111 1111 1111 1111 declined for jane.doe@example.com",
            }),
        ]),
    ]),
]

# Scene 4: the shop's AI assistant. GenAI semconv records prompts and responses as
# JSON strings in gen_ai.input.messages / gen_ai.output.messages, so PII typed by a
# customer ends up in span attributes. Provider and model names are fictional.
A = "assistant-1"
prompt = [{"role": "user", "parts": [{"type": "text",
           "content": "Which telescope is good for galaxies? Email the list to jane.doe@example.com"}]}]
answer = [{"role": "assistant", "parts": [{"type": "text",
           "content": "For galaxies you want aperture: the Lyra 8-inch Dobsonian is a good start."}]}]
assistant = [
    resource_spans("frontend", [
        span(A, "root", "POST /api/assistant", SERVER, 0, 1400, {
            "http.request.method": "POST",
            "url.path": "/api/assistant",
            "http.route": "/api/assistant",
            "user_agent.original": "Mozilla/5.0",
            "user.id": "u-7781",
            "http.response.status_code": 200,
        }),
    ]),
    resource_spans("astronomy-assistant", [
        span(A, "chat", "chat stargazer-1", CLIENT, 20, 1300, {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "example",
            "gen_ai.request.model": "stargazer-1",
            "gen_ai.usage.input_tokens": 412,
            "gen_ai.usage.output_tokens": 128,
            "gen_ai.input.messages": json.dumps(prompt),
            "gen_ai.output.messages": json.dumps(answer),
        }, parent="root"),
        span(A, "tool", "execute_tool search_products", CLIENT, 400, 150, {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "search_products",
        }, parent="chat"),
    ]),
    resource_spans("product-catalog", [
        span(A, "search", "oteldemo.ProductCatalogService/SearchProducts", SERVER, 410, 120, {
            "rpc.system.name": "grpc",
            "rpc.method": "oteldemo.ProductCatalogService/SearchProducts",
        }, parent="tool"),
    ]),
]

for name, payload in [
    ("1-health", {"resourceSpans": health}),
    ("2-browse", {"resourceSpans": browse}),
    ("3-checkout", {"resourceSpans": checkout}),
    ("4-assistant", {"resourceSpans": assistant}),
]:
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {path.relative_to(OUT.parent)}")
