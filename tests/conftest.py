import pytest

from controller.core import HOME, CellController


@pytest.fixture
def inputs():
    return {**HOME, "estop": False, "visible": True, "automatic": True,
            "communication_hold": False, "carrier_present": False, "material_present": False,
            "detect_carrier": False, "detect_material": False, "stop_carrier": False,
            "stop_material": False, "color_yellow": False, "direction_reverse": False,
            "holding": False, "bin1_count": 0, "bin2_count": 0, "ok_count": 0, "empty_count": 0}


@pytest.fixture
def cell(inputs):
    c = CellController()
    c.ingest(inputs, "epoch-a", 0)
    c.tick(0)
    return c
