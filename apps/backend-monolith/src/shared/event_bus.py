from typing import Any, Callable, Dict, List
import logging

logger = logging.getLogger("catepass.event_bus")


class InProcessEventBus:
    """
    Bus de eventos en memoria para desacoplar los módulos del Monolito Modular
    (ej. notificar al futuro módulo de Telegram cuando se cierra la asistencia).
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)

    def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        logger.info(f"[EventBus] Evento emitido: {event_name} | Payload: {payload}")
        for handler in self._subscribers.get(event_name, []):
            try:
                handler(payload)
            except Exception as exc:
                logger.error(f"[EventBus] Error ejecutando suscriptor de {event_name}: {exc}")


event_bus = InProcessEventBus()