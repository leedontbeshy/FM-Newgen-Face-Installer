import pytest


def config_bytes(ids=("100", "200"), newline="\r\n", indent="        "):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<record>",
        "    <!-- Preserve this comment and all spacing. -->",
        '    <boolean id="preload" value="false"/>',
        '    <list id="maps">',
        *(f'{indent}<record from="{id_}" to="graphics/pictures/person/{id_}/portrait"/>' for id_ in ids),
        "    </list>",
        "</record>",
    ]
    return newline.join(lines).encode("utf-8")


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.xml"
    path.write_bytes(config_bytes())
    return path
