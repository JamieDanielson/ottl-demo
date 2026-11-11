package customtransformprocessor

import (
	"github.com/open-telemetry/opentelemetry-collector-contrib/pkg/ottl"
	"github.com/open-telemetry/opentelemetry-collector-contrib/pkg/ottl/contexts/ottldatapoint"
	"github.com/open-telemetry/opentelemetry-collector-contrib/processor/transformprocessor"
	"go.opentelemetry.io/collector/processor"
)

func NewFactory() processor.Factory {
	funcs := []ottl.Factory[*ottldatapoint.TransformContext]{
		NewPrivKeyPassFactory[*ottldatapoint.TransformContext](),
	}
	funcs = append(funcs, transformprocessor.DefaultDataPointFunctions()...)
	return transformprocessor.NewFactoryWithOptions(
		transformprocessor.WithDataPointFunctions(funcs),
	)
}
