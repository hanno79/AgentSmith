# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: Manager fuer alle externen Specialists im External Bureau.
              Verwaltet Aktivierung, Ausfuehrung und Status aller externen Dienste.
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from external_specialists.base_specialist import (
    BaseSpecialist,
    SpecialistResult,
    SpecialistStatus,
    SpecialistCategory
)
from external_specialists.coderabbit_specialist import CodeRabbitSpecialist
from external_specialists.exa_specialist import EXASpecialist
from external_specialists.augment_specialist import AugmentSpecialist

logger = logging.getLogger(__name__)


class ExternalBureauManager:
    """
    Verwaltet alle externen Specialists im External Bureau.

    Verantwortlich fuer:
    - Initialisierung aller konfigurierten Specialists
    - Aktivierung/Deaktivierung einzelner Specialists
    - Ausfuehrung von Reviews und Suchen
    - Status-Abfragen fuer UI
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den External Bureau Manager.

        Args:
            config: Vollstaendige Konfiguration aus config.yaml
        """
        self.config = config.get("external_specialists", {})
        self.specialists: Dict[str, BaseSpecialist] = {}
        self.enabled = self.config.get("enabled", False)
        self.last_activity: Optional[datetime] = None
        self._init_specialists()

    def _init_specialists(self):
        """Initialisiert alle konfigurierten Specialists."""
        if not self.enabled:
            logger.info("External Bureau: Deaktiviert in config.yaml")
            return

        # CodeRabbit
        coderabbit_config = self.config.get("coderabbit", {})
        if coderabbit_config.get("enabled", False):
            try:
                self.specialists["coderabbit"] = CodeRabbitSpecialist(coderabbit_config)
                logger.info("External Bureau: CodeRabbit Specialist geladen")
            except Exception as e:
                logger.error(f"CodeRabbit Initialisierung fehlgeschlagen: {e}")

        # EXA Search
        exa_config = self.config.get("exa_search", {})
        if exa_config.get("enabled", False):
            try:
                self.specialists["exa"] = EXASpecialist(exa_config)
                logger.info("External Bureau: EXA Search Specialist geladen")
            except Exception as e:
                logger.error(f"EXA Search Initialisierung fehlgeschlagen: {e}")

        # Augment Context Engine
        augment_config = self.config.get("augment_context", {})
        if augment_config.get("enabled", False):
            try:
                # ÄNDERUNG 06.02.2026: Key muss mit to_dict()-ID uebereinstimmen
                # ROOT-CAUSE-FIX: Frontend sendet ID aus Klassenname (AugmentSpecialist -> "augment"),
                # aber Lookup schlug fehl weil Key "augment_context" war
                self.specialists["augment"] = AugmentSpecialist(augment_config)
                logger.info("External Bureau: Augment Context Specialist geladen")
            except Exception as e:
                logger.error(f"Augment Context Initialisierung fehlgeschlagen: {e}")

        logger.info(f"External Bureau: {len(self.specialists)} Specialist(s) initialisiert")

    def is_enabled(self) -> bool:
        """Prueft ob External Bureau aktiviert ist."""
        return self.enabled and len(self.specialists) > 0

    def get_all_specialists(self) -> List[Dict[str, Any]]:
        """
        Gibt Liste aller Specialists mit Status zurueck (fuer UI).

        Returns:
            Liste von Specialist-Dicts mit id, name, status, category, stats, available
        """
        return [spec.to_dict() for spec in self.specialists.values()]

    def get_specialists_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Filtert Specialists nach Kategorie.

        Args:
            category: "all", "combat", "intelligence", "creative"

        Returns:
            Gefilterte Liste von Specialist-Dicts
        """
        all_specs = self.get_all_specialists()
        if category == "all":
            return all_specs
        return [s for s in all_specs if s["category"] == category]

    def get_specialist(self, specialist_id: str) -> Optional[BaseSpecialist]:
        """
        Holt einen Specialist nach ID.

        Args:
            specialist_id: z.B. "coderabbit" oder "exa"

        Returns:
            BaseSpecialist Instanz oder None
        """
        return self.specialists.get(specialist_id)

    def activate_specialist(self, specialist_id: str) -> Dict[str, Any]:
        """
        Aktiviert einen Specialist.

        Args:
            specialist_id: ID des Specialists

        Returns:
            Dict mit success und message
        """
        spec = self.specialists.get(specialist_id)
        if not spec:
            return {"success": False, "message": f"Specialist '{specialist_id}' nicht gefunden"}

        if spec.is_in_cooldown():
            remaining = spec.get_cooldown_remaining()
            return {
                "success": False,
                "message": f"Specialist im Cooldown - noch {remaining}s"
            }

        if spec.activate():
            self.last_activity = datetime.now()
            return {"success": True, "message": f"{spec.name} aktiviert"}
        else:
            return {"success": False, "message": f"{spec.name} nicht verfuegbar"}

    def deactivate_specialist(self, specialist_id: str) -> Dict[str, Any]:
        """
        Deaktiviert einen Specialist.

        Args:
            specialist_id: ID des Specialists

        Returns:
            Dict mit success und message
        """
        spec = self.specialists.get(specialist_id)
        if not spec:
            return {"success": False, "message": f"Specialist '{specialist_id}' nicht gefunden"}

        spec.deactivate()
        self.last_activity = datetime.now()
        return {"success": True, "message": f"{spec.name} deaktiviert"}

    async def run_review_specialists(
        self,
        context: Dict[str, Any]
    ) -> List[SpecialistResult]:
        """
        Fuehrt alle aktiven Review-Specialists (COMBAT) parallel aus.

        Args:
            context: Dict mit project_path, code, files etc.

        Returns:
            Liste von SpecialistResults
        """
        tasks = []
        spec_names = []

        for key, spec in self.specialists.items():
            if (spec.category == SpecialistCategory.COMBAT and
                spec.status == SpecialistStatus.READY):
                tasks.append(spec.execute(context))
                spec_names.append(spec.name)

        if not tasks:
            logger.debug("External Bureau: Keine aktiven Review-Specialists")
            return []

        logger.info(f"External Bureau: Starte {len(tasks)} Review(s): {', '.join(spec_names)}")
        self.last_activity = datetime.now()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter exceptions und logge sie
        valid_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"{spec_names[i]} Exception: {r}")
            elif isinstance(r, SpecialistResult):
                valid_results.append(r)

        return valid_results

    async def run_search(self, query: str) -> Optional[SpecialistResult]:
        """
        Fuehrt eine Suche mit dem EXA Specialist aus.

        Args:
            query: Suchanfrage

        Returns:
            SpecialistResult oder None
        """
        exa = self.specialists.get("exa")
        if not exa:
            logger.debug("External Bureau: EXA Search nicht konfiguriert")
            return None

        if exa.status != SpecialistStatus.READY:
            logger.debug(f"External Bureau: EXA Status ist {exa.status.value}")
            return None

        self.last_activity = datetime.now()
        return await exa.execute({"query": query})

    async def run_specialist(
        self,
        specialist_id: str,
        context: Dict[str, Any]
    ) -> Optional[SpecialistResult]:
        """
        Fuehrt einen spezifischen Specialist aus.

        Args:
            specialist_id: ID des Specialists
            context: Ausfuehrungskontext

        Returns:
            SpecialistResult oder None
        """
        spec = self.specialists.get(specialist_id)
        if not spec:
            logger.warning(f"External Bureau: Specialist '{specialist_id}' nicht gefunden")
            return None

        if spec.status != SpecialistStatus.READY:
            logger.warning(f"External Bureau: {spec.name} ist nicht bereit ({spec.status.value})")
            return None

        self.last_activity = datetime.now()
        return await spec.execute(context)

    def get_combined_findings(self) -> List[Dict[str, Any]]:
        """
        Sammelt die letzten Findings aller Specialists.

        Returns:
            Liste aller Findings mit Specialist-Zuordnung
        """
        all_findings = []

        for spec in self.specialists.values():
            if spec.last_result and spec.last_result.findings:
                for finding in spec.last_result.findings:
                    all_findings.append({
                        "specialist": spec.name,
                        "category": spec.category.value,
                        "severity": finding.severity,
                        "description": finding.description,
                        "file": finding.file,
                        "line": finding.line,
                        "fix": finding.fix,
                        "timestamp": spec.last_result.timestamp
                    })

        # Nach Severity sortieren (HIGH > MEDIUM > LOW > INFO)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        all_findings.sort(key=lambda f: severity_order.get(f["severity"], 5))

        return all_findings

    def get_status(self) -> Dict[str, Any]:
        """
        Gibt den Gesamtstatus des External Bureau zurueck.

        Returns:
            Dict mit enabled, specialist_count, active_count, findings_count
        """
        active_count = sum(
            1 for s in self.specialists.values()
            if s.status == SpecialistStatus.READY
        )

        findings_count = sum(
            len(s.last_result.findings) if s.last_result else 0
            for s in self.specialists.values()
        )

        return {
            "enabled": self.enabled,
            "specialist_count": len(self.specialists),
            "active_count": active_count,
            "findings_count": findings_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "specialists": self.get_all_specialists()
        }

    def to_json(self) -> str:
        """Serialisiert den Status als JSON."""
        return json.dumps(self.get_status(), ensure_ascii=False, indent=2)
