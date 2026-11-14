"""The interface's component tests read the service's component types from a fixture.

``ui/src/test/component-types.json`` must equal what ``GET /v1/schema`` serves under
``x-component-types`` (spec 3 "Endpoints"), so that the Canvas's tests (AKS-136) build its
forms from the same descriptions as the real service. Regenerate it with::

    python -c "import json; from ithax.engines.registry import installed_adapters; \\
    from ithax.service.engines import composed_schema; \\
    print(json.dumps(composed_schema(installed_adapters())['x-component-types'], indent=2))" \\
    > ui/src/test/component-types.json
"""

import json
from pathlib import Path

from ithax.engines.registry import installed_adapters
from ithax.service.engines import COMPONENT_TYPES_KEY, composed_schema

FIXTURE = Path(__file__).resolve().parents[1] / "ui" / "src" / "test" / "component-types.json"


def test_the_interface_fixture_equals_the_services_component_types() -> None:
    served = composed_schema(installed_adapters())[COMPONENT_TYPES_KEY]
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == served
