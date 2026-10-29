"""Versioned logical column definitions from the existing validated input contract.
No physical sensor labels, units or components are inferred.
"""
from sentinel.data import SENSORS, SETTINGS


def catalog():
    def definitions(names, category):
        return [dict(id=name,category=category,input_index=index,name=None,unit=None,
                     component=None,metadata_status='unknown') for index,name in enumerate(names)]
    return dict(dataset='C-MAPSS',schema_version=1,
                sensor_channels=definitions(SENSORS,'sensor'),
                operating_settings=definitions(SETTINGS,'operating_setting'))
