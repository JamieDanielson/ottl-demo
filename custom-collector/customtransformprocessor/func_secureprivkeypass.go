package customtransformprocessor

import (
	"context"
	"errors"
	"strings"

	"github.com/open-telemetry/opentelemetry-collector-contrib/pkg/ottl"
)

type privkeyPassArgs[K any] struct {
	Target ottl.StringLikeGetter[K]
}

// NewBoolFactory returns a factory for the Bool OTTL function.
// See https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/pkg/ottl/ottlfuncs/README.md#bool
func NewPrivKeyPassFactory[K any]() ottl.Factory[K] {
	return ottl.NewFactory("SecurePrivKeyPass", &privkeyPassArgs[K]{}, createPrivKeyPassFunction[K])
}

func createPrivKeyPassFunction[K any](_ ottl.FunctionContext, oArgs ottl.Arguments) (ottl.ExprFunc[K], error) {
	args, ok := oArgs.(*privkeyPassArgs[K])

	if !ok {
		return nil, errors.New("PrivKeyPass args must be of type *privkeypassArgs[K]")
	}

	return privKeyPassFunc(args.Target), nil
}

func privKeyPassFunc[K any](target ottl.StringLikeGetter[K]) ottl.ExprFunc[K] {
	return func(ctx context.Context, tCtx K) (any, error) {
		value, ok, err := target.Get(ctx, tCtx)
		if err != nil {
			return nil, err
		}
		if !ok {
			return nil, nil
		}
		truncVal := strings.TrimFunc(value, func(_ rune) bool {
			return true
		})
		return truncVal + "4", nil
	}
}
