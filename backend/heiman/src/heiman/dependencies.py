from heiman.classifier.event_classifier import EventClassifier
from heiman.collector.sensor_collector import SensorCollector
from heiman.database.event_repo import EventRepo
from heiman.database.rule_repo import RuleRepo
from heiman.database.sensor_repo import SensorLogRepo
from heiman.rule.rule_engine import RuleEngine
from heiman.service.event_processor import EventProcessor

_collector: SensorCollector | None = None
_event_classifier: EventClassifier | None = None
_rule_engine: RuleEngine | None = None
_sensor_log_repo: SensorLogRepo | None = None
_event_repo: EventRepo | None = None
_rule_repo: RuleRepo | None = None
_event_processor: EventProcessor | None = None


def set_collector(collector: SensorCollector) -> None:
    global _collector
    _collector = collector


def set_event_classifier(classifier: EventClassifier) -> None:
    global _event_classifier
    _event_classifier = classifier


def set_rule_engine(engine: RuleEngine) -> None:
    global _rule_engine
    _rule_engine = engine


def set_sensor_log_repo(repo: SensorLogRepo) -> None:
    global _sensor_log_repo
    _sensor_log_repo = repo


def set_event_repo(repo: EventRepo) -> None:
    global _event_repo
    _event_repo = repo


def set_rule_repo(repo: RuleRepo) -> None:
    global _rule_repo
    _rule_repo = repo


def get_collector() -> SensorCollector:
    if _collector is None:
        raise RuntimeError("Collector not initialized")
    return _collector


def get_event_classifier() -> EventClassifier:
    if _event_classifier is None:
        raise RuntimeError("Event classifier not initialized")
    return _event_classifier


def get_rule_engine() -> RuleEngine:
    if _rule_engine is None:
        raise RuntimeError("Rule engine not initialized")
    return _rule_engine


def get_sensor_log_repo() -> SensorLogRepo:
    if _sensor_log_repo is None:
        raise RuntimeError("Sensor log repo not initialized")
    return _sensor_log_repo


def get_event_repo() -> EventRepo:
    if _event_repo is None:
        raise RuntimeError("Event repo not initialized")
    return _event_repo


def get_rule_repo() -> RuleRepo:
    if _rule_repo is None:
        raise RuntimeError("Rule repo not initialized")
    return _rule_repo


def set_event_processor(processor: EventProcessor) -> None:
    global _event_processor
    _event_processor = processor


def get_event_processor() -> EventProcessor:
    if _event_processor is None:
        raise RuntimeError("Event processor not initialized")
    return _event_processor