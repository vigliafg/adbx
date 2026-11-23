"""I ventidue eventi di trigger di Alpha Four.

Un trigger si attiva assegnando a `%SYS_TRIG_<EVENTO>` il nome di uno script;
la stringa vuota lo disattiva. Il registro conserva la mappa, separata dalle
variabili, e il motore la consulta quando un evento occorre. I nomi sono
quelli del Reference Manual, capitolo 18, con alcuni alias tollerati per i
nomi che l'OCR del manuale rende in modo ambiguo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import normalize_name


@dataclass(frozen=True)
class TriggerEvent:
    code: str
    variable: str
    label: str


TRIGGER_EVENTS: tuple[TriggerEvent, ...] = (
    TriggerEvent("REC_ENTER", "%SYS_TRIG_REC_ENTER", "New record is entered"),
    TriggerEvent("REC_CHANGE", "%SYS_TRIG_REC_CHANGE",
                 "Existing record is changed"),
    TriggerEvent("REC_DEL", "%SYS_TRIG_REC_DEL", "Record is deleted"),
    TriggerEvent("REC_UNDEL", "%SYS_TRIG_REC_UNDEL", "Record is undeleted"),
    TriggerEvent("REC_SAVE", "%SYS_TRIG_REC_SAVE", "Record is saved"),
    TriggerEvent("REGION_ENTER", "%SYS_TRIG_REGION_ENTER",
                 "Region is entered"),
    TriggerEvent("REGION_EXIT", "%SYS_TRIG_REGION_EXIT", "Region is exited"),
    TriggerEvent("FIELD_ENTER", "%SYS_TRIG_FIELD_ENTER", "Field is entered"),
    TriggerEvent("FIELD_VALID", "%SYS_TRIG_FIELD_VALID",
                 "Field is validated"),
    TriggerEvent("FIELD_EXIT", "%SYS_TRIG_FIELD_EXIT", "Field is exited"),
    TriggerEvent("LETTER_START", "%SYS_TRIG_LETTER_START",
                 "Letter is started"),
    TriggerEvent("LETTER_PRINT", "%SYS_TRIG_LETTER_PRINT",
                 "Letter is printed"),
    TriggerEvent("LETTER_FINISH", "%SYS_TRIG_LETTER_FINISH",
                 "Letter is finished"),
    TriggerEvent("SEARCH_START", "%SYS_TRIG_SEARCH_START",
                 "Search/sort is started"),
    TriggerEvent("SEARCH_PERFORM", "%SYS_TRIG_SEARCH_PERFORM",
                 "Search/sort is performed"),
    TriggerEvent("SEARCH_SUCCESS", "%SYS_TRIG_SEARCH_SUCCESS",
                 "Search/sort is successful"),
    TriggerEvent("SEARCH_FINISH", "%SYS_TRIG_SEARCH_FINISH",
                 "Search/sort is finished"),
    TriggerEvent("UPDATE_START", "%SYS_TRIG_UPDATE_START",
                 "Update is started"),
    TriggerEvent("UPDATE_PERFORM", "%SYS_TRIG_UPDATE_PERFORM",
                 "Update is performed"),
    TriggerEvent("UPDATE_FINISH", "%SYS_TRIG_UPDATE_FINISH",
                 "Update is finished"),
    TriggerEvent("ZOOM", "%SYS_TRIG_ZOOM", "Zoom is performed"),
    TriggerEvent("UNZOOM", "%SYS_TRIG_UNZOOM", "UnZoom is performed"),
)

BY_CODE = {event.code: event for event in TRIGGER_EVENTS}
BY_VARIABLE = {event.variable: event for event in TRIGGER_EVENTS}

ALIASES = {
    "REC_INSERT": "REC_ENTER",
    "REC_CHANGED": "REC_CHANGE",
    "REC_DELETE": "REC_DEL",
    "REC_DELETED": "REC_DEL",
    "REC_UNDELETE": "REC_UNDEL",
    "REC_UNDELETED": "REC_UNDEL",
    "REC_SAVED": "REC_SAVE",
    "FIELD_VALIDATE": "FIELD_VALID",
    "FIELD_VALIDATED": "FIELD_VALID",
    "LETTER_END": "LETTER_FINISH",
    "LETTER_FINISHED": "LETTER_FINISH",
    "SEARCH_PERFORMED": "SEARCH_PERFORM",
    "SEARCH_FINISHED": "SEARCH_FINISH",
    "SEARCH_SUCCESSFUL": "SEARCH_SUCCESS",
    "UPDATE_PERFORMED": "UPDATE_PERFORM",
    "UPDATE_FINISHED": "UPDATE_FINISH",
    "UN_ZOOM": "UNZOOM",
}


def canonical_event(code: str) -> str:
    text = code.strip().upper()
    if text.startswith("%SYS_TRIG_"):
        text = text[len("%SYS_TRIG_"):]
    text = ALIASES.get(text, text)
    if text not in BY_CODE:
        raise ValueError(f"Unknown trigger event: {code}")
    return text


def event_by_variable(variable: str) -> TriggerEvent | None:
    text = variable.strip().upper()
    if not text.startswith("%"):
        text = "%" + text
    return BY_VARIABLE.get(text)


@dataclass
class TriggerRegistry:
    """Script attivi per evento, con le variabili di sistema corrispondenti."""

    scripts: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clean: dict[str, str] = {}
        for code, name in self.scripts.items():
            if not name:
                continue
            clean[canonical_event(code)] = normalize_name(name)
        self.scripts = clean

    def set(self, event: str, script: str) -> None:
        code = canonical_event(event)
        if not script.strip():
            self.scripts.pop(code, None)
            return
        self.scripts[code] = normalize_name(script)

    def set_from_variable(self, variable: str, value: str) -> bool:
        event = event_by_variable(variable)
        if event is None:
            return False
        self.set(event.code, value)
        return True

    def get(self, event: str) -> str:
        return self.scripts.get(canonical_event(event), "")

    def active(self) -> list[tuple[TriggerEvent, str]]:
        return [(BY_CODE[code], self.scripts[code])
                for code in sorted(self.scripts)]

    def variables(self) -> dict[str, str]:
        result = {event.variable: "" for event in TRIGGER_EVENTS}
        for code, script in self.scripts.items():
            result[BY_CODE[code].variable] = script
        return result

    def clear(self) -> None:
        self.scripts.clear()


__all__ = [
    "ALIASES", "BY_CODE", "BY_VARIABLE", "TRIGGER_EVENTS", "TriggerEvent",
    "TriggerRegistry", "canonical_event", "event_by_variable",
]
