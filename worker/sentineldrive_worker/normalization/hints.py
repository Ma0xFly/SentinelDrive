from __future__ import annotations

from sentineldrive_worker.normalization.dedup import normalize_text

VEHICLE_COMPONENTS = {
    "app": (" app", "mobile app", "application"),
    "tbox": ("t-box", "tbox", "telematics"),
    "ivi": ("ivi", "infotainment", "head unit"),
    "ota": ("ota", "over-the-air", "firmware update"),
    "v2x": ("v2x", "vehicle-to-everything"),
    "charging": ("charging", "charger", "evse"),
    "cloud_api": ("cloud api", "cloud", "api"),
    "bluetooth": ("bluetooth", "ble"),
    "wifi": ("wi-fi", "wifi", "wlan"),
    "cellular": ("cellular", "4g", "5g", "lte"),
    "can": (" can ", "can bus", "controller area network"),
    "usb": ("usb",),
}

ATTACK_SURFACES = {
    "bluetooth": ("bluetooth", "ble"),
    "wifi": ("wi-fi", "wifi", "wlan"),
    "cellular": ("cellular", "4g", "5g", "lte"),
    "cloud_api": ("cloud api", "cloud", "api"),
    "usb": ("usb",),
    "can": (" can ", "can bus", "controller area network"),
    "v2x": ("v2x", "vehicle-to-everything"),
    "charging": ("charging", "charger", "evse"),
    "ota": ("ota", "over-the-air", "firmware update"),
    "app": (" app", "mobile app", "application"),
    "tbox": ("t-box", "tbox", "telematics"),
    "ivi": ("ivi", "infotainment", "head unit"),
}


def infer_vehicle_component(*values: object) -> str | None:
    return infer_from_text(VEHICLE_COMPONENTS, *values)


def infer_attack_surface(*values: object) -> str | None:
    return infer_from_text(ATTACK_SURFACES, *values)


def infer_from_text(mapping: dict[str, tuple[str, ...]], *values: object) -> str | None:
    haystack = f" {normalize_text(' '.join(str(value or '') for value in values))} "
    for key, terms in mapping.items():
        if any(term in haystack for term in terms):
            return key
    return None
