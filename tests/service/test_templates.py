"""``GET /v1/templates`` and ``GET /v1/templates/{tid}`` before M10 (spec 3 "Endpoints";
AKS-110 acceptance: empty list until M10)."""

from starlette.testclient import TestClient

from service.service_support import assert_error


def test_there_are_no_templates_before_m10(client: TestClient) -> None:
    response = client.get("/v1/templates")
    assert response.status_code == 200
    assert response.json() == []


def test_every_template_id_is_404_with_e185(client: TestClient) -> None:
    response = client.get("/v1/templates/coffee_shop")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert "'coffee_shop'" in response.json()["error"]["message"]
