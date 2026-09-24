"""Instancias únicas del proceso para jobs y eventos (Spec-460).

Composition root: acá se cablean los servicios de aplicación con los repos de
infraestructura. Un solo proceso uvicorn (Spec-460 ASSUMPTIONS §1).
"""

from src.application.services.event_bus import EventBus
from src.application.services.job_manager import JobManager
from src.infrastructure.database.repositories import SQLJobRepository, SQLStoryRepository

event_bus = EventBus()
job_manager = JobManager(event_bus, SQLJobRepository(), SQLStoryRepository())
