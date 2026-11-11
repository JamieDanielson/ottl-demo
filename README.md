# OTTL demo: filter, transform, route

Companion repo for the live demo in *Filter, Transform, Route: Mastering OTTL in the OpenTelemetry
Collector* (KubeCon + CloudNativeCon North America 2026).

A small telescope shop has messy telemetry:

- Health probes drown out real traffic.
- The failing checkout trace leaks an email address, a card number and a bearer token.
- A new AI assistant records whatever customers type into it.

This repo fixes all of that in the OpenTelemetry Collector with OTTL, one stage at a time, without
touching the apps:

1. **Filter** the probe noise with the filter processor.
2. **Normalize** high-cardinality span names, then **redact** secrets and PII with the transform processor.
3. **Route** AI spans to their own backend with the routing connector, while Jaeger keeps whole traces.

Each stage includes a mistake we made along the way, so you can see what goes wrong as well as the fix.

## Try it in your browser

The hands-on scenarios from the end of the talk run in [ottl.run](https://ottl.run), so there's
nothing to install. Each link opens a telescope shop payload and a starter config. The comments at
the top of the config describe the situation, your goal, a stretch goal, and functions to reach
for. Replace `[]` with your statements, click Run, and compare the result with the input. If
you're stuck, set a breakpoint next to a statement to see the data before and after it runs.

| Scenario                        | Starter                                  | Solution                                           |
| ------------------------------- | ---------------------------------------- | -------------------------------------------------- |
| Rename legacy attributes        | [Open](https://is.gd/ottl_scenario_1)    | [Solution](https://is.gd/ottl_scenario_1_solution) |
| Drop health-check spans         | [Open](https://is.gd/ottl_scenario_2_v2) | [Solution](https://is.gd/ottl_scenario_2_solution) |
| Redact PII and secrets          | [Open](https://is.gd/ottl_scenario_3_v2) | [Solution](https://is.gd/ottl_scenario_3_solution) |
| Fix high-cardinality span names | [Open](https://is.gd/ottl_scenario_4_v2) | [Solution](https://is.gd/ottl_scenario_4_solution) |
| Parse messy logs                | [Open](https://is.gd/ottl_scenario_5_v2) | [Solution](https://is.gd/ottl_scenario_5_solution) |
| Mask emails with lambdas        | [Open](https://is.gd/ottl_scenario_7_v2) | [Solution](https://is.gd/ottl_scenario_7_solution) |
| Metric identity                 | [Open](https://is.gd/ottl_scenario_8)    | [Solution](https://is.gd/ottl_scenario_8_solution) |

### Debugging clinic

Each of these configs looks right and isn't. Read the goal, compare what you expect with what you
see, then find and fix the bug. Two of them don't even load, and reading the error is part of the
exercise. The result diff, breakpoints, and switching `error_mode` to `propagate` all help.

| Scenario                     | Starter                                | Solution                                            |
| ---------------------------- | -------------------------------------- | --------------------------------------------------- |
| `!=` on a missing attribute  | [Open](https://is.gd/ottl_scenario_6a) | [Solution](https://is.gd/ottl_scenario_6a_solution) |
| Int vs. string               | [Open](https://is.gd/ottl_scenario_6b) | [Solution](https://is.gd/ottl_scenario_6b_solution) |
| Unanchored regex             | [Open](https://is.gd/ottl_scenario_6c) | [Solution](https://is.gd/ottl_scenario_6c_solution) |
| Escaping                     | [Open](https://is.gd/ottl_scenario_6d) | [Solution](https://is.gd/ottl_scenario_6d_solution) |
| Statement order              | [Open](https://is.gd/ottl_scenario_6e) | [Solution](https://is.gd/ottl_scenario_6e_solution) |
| Metric vs. datapoint context | [Open](https://is.gd/ottl_scenario_6f) | [Solution](https://is.gd/ottl_scenario_6f_solution) |
| `error_mode: ignore`         | [Open](https://is.gd/ottl_scenario_6g) | [Solution](https://is.gd/ottl_scenario_6g_solution) |

## What you need

- Docker with Compose v2
- `curl`
- Python 3 (standard library only; it formats the output)

It runs on macOS and Linux; on Windows, use WSL. Once the images are pulled, everything runs offline.
All the data is fake: `example.com` addresses, the `4111 1111 1111 1111` test card, and tokens labelled FAKE.

## Quick start

```sh
git clone https://github.com/JamieDanielson/ottl-demo.git && cd ottl-demo
./demo pull                 # otel/opentelemetry-collector-contrib:0.164.0 and jaegertracing/jaeger:2.22.0
./demo stage 00-baseline    # start the Collector with no processing
./demo send                 # post the sample traces and show what came out
```

`./demo send` posts four scenes of OTLP/JSON from `data/` to the Collector on `localhost:4318`:
health probes, product browsing, a failing checkout, and an AI assistant chat. It then prints what
reached the Collector's debug exporter, condensed to one block per span:

- **red** values look like a leak (an email, a card number, a token)
- **green** values were redacted
- **⚠ parent not here** marks a span whose parent isn't in the same output, because it was dropped or routed elsewhere

`./demo raw` shows the debug exporter's output unformatted.

## Work through it

The Collector always runs `config/live.yaml`. You can edit it and run `./demo apply` (which
validates the config, then restarts), or jump to a finished stage with `./demo stage <name>`.
To try a stage yourself first, start from the previous one and compare afterwards with
`./demo diff <stage>`.

| Stage                     | What it adds                                                 | What to look for                                                                                                                                                                                                      |
| ------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `00-baseline`             | Debug exporter only                                          | 23 spans. Seven probe spans, and the email, token and card number in plain text, including inside an exception message and an AI prompt.                                                                              |
| `01-filter`               | `filter/health`                                              | The probes are gone and `/blog/healthy-stargazing` is still there. Try an unanchored `"health"` regex and watch the blog post vanish too. Three `SELECT` spans are now orphaned: the filter works one span at a time. |
| `02a-transform-first-try` | `transform/normalize` and a first try at `transform/redact`  | Span names like `GET /api/products/{productId}`. **But the checkout span still leaks.** Work out why before reading the comment at the top of the file.                                                               |
| `02b-transform`           | Redaction split into one statement group per context         | Everything is green: the hashed `user.hash`, the masked card, the scrubbed query string, and the email removed from the exception message and the AI prompt.                                                          |
| `03a-route-first-try`     | A routing connector that sends `gen_ai` spans to `traces/ai` | Open Jaeger with `./demo jaeger`: the assistant trace is incomplete. Why?                                                                                                                                             |
| `03b-route`               | `action: copy`                                               | Jaeger has the whole trace, without the prompt bodies, and the AI backend still gets its spans.                                                                                                                       |

The stage files are commented, and `snippets/` has each step's statements on their own, including
the wrong versions. Jaeger's UI is at <http://localhost:16686>; only the `03*` stages export to it.
Run `./demo jaeger-reset` between runs, because resending the same sample traces adds duplicate spans.

## Commands

```txt
./demo help                 every command
./demo stage <name>         copy config/<name>.yaml to config/live.yaml and restart
./demo apply                validate config/live.yaml, then restart
./demo check [file]         validate a config without restarting
./demo send                 post all scenes; ./demo checkout and ./demo assistant post one each
./demo show / names / raw   re-render the last send (full / names only / unformatted)
./demo diff <stage>         what a stage changes compared with config/live.yaml
./demo test                 run every stage and check the expected output (about 30 s)
./demo reset                stop everything
```

## How it's put together

```txt
demo                 the command wrapper
compose.yaml         the Collector (contrib 0.164.0) and Jaeger 2.22.0 with in-memory storage
config/              one complete, validated Collector config per stage
data/                OTLP/JSON sample traces, plus the script that generates them
bin/send             posts the samples and shows the result
bin/spans            condenses the debug exporter's output
bin/selftest         ./demo test
snippets/            each step's statements, including the deliberate mistakes
backup/replay/       the same stages, fed from files by the otlp_json_file receiver
```

- **No network path from your machine to the container?** `./demo replay <stage>` runs a stage with
  the `otlp_json_file` receiver, reading `backup/replay/data/` inside the container. It stops the
  Compose Collector while it runs; `./demo stage <name>` starts it again.
- **The sample data can be regenerated.** `./demo fixtures` rebuilds it with current timestamps;
  edit `data/make_fixtures.py` to change the story.
- **Lambdas need a feature gate.** The Collector starts with
  `--feature-gates=ottl.functions.enableLambda`, so `snippets/5-lambda.txt` works if you want to
  experiment with them. They're alpha, so leave the gate out if you copy the config.
- **These are teaching configs, not production ones.** A production Collector also needs a
  `memory_limiter` processor first in each pipeline. The redaction here is a denylist that only
  scrubs string attribute values, and `user.hash` is an unsalted hash, so it pseudonymizes rather
  than anonymizes. For allowlists, HMAC hashing and non-string values, see the redaction processor.

## Learn more

- [OTTL](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/pkg/ottl) and its
  [function reference](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/pkg/ottl/ottlfuncs/README.md)
- The [transform processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/transformprocessor),
  [filter processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/filterprocessor),
  [routing connector](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/connector/routingconnector) and
  [redaction processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/redactionprocessor)
- [ottl.run](https://ottl.run), the OTTL playground. Try the transform and filter statements there without a Collector.

## License

[Apache 2.0](LICENSE)
