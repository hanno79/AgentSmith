# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 28.01.2026
Version: 1.0
Beschreibung: EXA Search API Wrapper fuer Recherche.
              Integriert EXA als externen Intelligence-Specialist im External Bureau.
"""

import os
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_specialist import (
    BaseSpecialist,
    SpecialistResult,
    SpecialistFinding,
    SpecialistStatus,
    SpecialistCategory
)

logger = logging.getLogger(__name__)


class EXASpecialist(BaseSpecialist):
    """
    EXA Search API Integration fuer Recherche.

    EXA ist ein KI-gestuetzter Suchdienst fuer Entwickler-Recherche.
    Benoetigt: EXA_API_KEY Umgebungsvariable oder config.yaml Eintrag.

    Konfiguration in config.yaml:
        exa_search:
            enabled: true
            api_key: ${EXA_API_KEY}
            timeout_seconds: 60
            max_results: 10
    """

    @property
    def name(self) -> str:
        return "EXA Search"

    @property
    def category(self) -> SpecialistCategory:
        return SpecialistCategory.INTELLIGENCE

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "STR": 40,  # Keine direkte Code-Analyse
            "INT": 95,  # Sehr hohe Recherche-Intelligenz
            "AGI": 80   # Schnelle API-Antworten
        }

    @property
    def description(self) -> str:
        return "KI-gestuetzte Websuche fuer Entwickler-Dokumentation und Best Practices"

    @property
    def icon(self) -> str:
        return "travel_explore"  # Globus/Suche Icon

    def _get_api_key(self) -> Optional[str]:
        """Holt API Key aus Config oder Umgebungsvariable."""
        api_key = self.config.get("api_key", "")

        # Ersetze ${VAR} Platzhalter
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var, "")

        # Fallback auf direkte Umgebungsvariable
        if not api_key:
            api_key = os.getenv("EXA_API_KEY", "")

        return api_key if api_key else None

    def check_available(self) -> bool:
        """Prueft ob EXA API Key konfiguriert ist."""
        api_key = self._get_api_key()
        if api_key:
            logger.debug("EXA API Key gefunden")
            return True
        logger.debug("EXA API Key nicht konfiguriert")
        return False

    async def execute(self, context: Dict[str, Any]) -> SpecialistResult:
        """
        Fuehrt EXA Search aus.

        Args:
            context: Dict mit:
                - query: Suchanfrage (erforderlich)
                - num_results: Optional - Anzahl Ergebnisse (default: 10)
                - type: Optional - "neural" oder "keyword" (default: "neural")

        Returns:
            SpecialistResult mit Suchergebnissen als Findings
        """
        self.status = SpecialistStatus.COMPILING
        start_time = time.time()

        try:
            query = context.get("query", "")
            if not query:
                self.status = SpecialistStatus.ERROR
                return SpecialistResult(
                    success=False,
                    findings=[],
                    summary="Keine Suchanfrage angegeben",
                    error="Parameter 'query' ist erforderlich"
                )

            api_key = self._get_api_key()
            if not api_key:
                self.status = SpecialistStatus.ERROR
                return SpecialistResult(
                    success=False,
                    findings=[],
                    summary="API Key nicht konfiguriert",
                    error="EXA_API_KEY nicht gefunden"
                )

            timeout = self.config.get("timeout_seconds", 60)
            num_results = context.get("num_results", self.config.get("max_results", 10))
            search_type = context.get("type", "neural")

            logger.info(f"EXA Search: '{query[:50]}...'")

            # EXA API aufrufen
            results = await self._call_exa_api(
                api_key=api_key,
                query=query,
                num_results=num_results,
                search_type=search_type,
                timeout=timeout
            )

            duration_ms = int((time.time() - start_time) * 1000)
            self.last_run = datetime.now()
            self.run_count += 1

            if results is not None:
                findings = self._parse_results(results)
                self.status = SpecialistStatus.READY
                self.last_result = SpecialistResult(
                    success=True,
                    findings=findings,
                    summary=f"{len(findings)} Ergebnis(se) fuer: {query[:30]}...",
                    raw_output=str(results),
                    duration_ms=duration_ms
                )
                logger.info(f"EXA: {len(findings)} Ergebnisse in {duration_ms}ms")
                return self.last_result
            else:
                self.status = SpecialistStatus.ERROR
                self.error_count += 1
                self.last_result = SpecialistResult(
                    success=False,
                    findings=[],
                    summary="Keine Ergebnisse",
                    error="EXA API hat keine Ergebnisse geliefert",
                    duration_ms=duration_ms
                )
                return self.last_result

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = SpecialistStatus.ERROR
            self.error_count += 1
            timeout = self.config.get("timeout_seconds", 60)
            self.last_result = SpecialistResult(
                success=False,
                findings=[],
                summary=f"Timeout nach {timeout}s",
                error=f"EXA API hat nach {timeout} Sekunden nicht geantwortet",
                duration_ms=duration_ms
            )
            logger.warning(f"EXA Timeout nach {timeout}s")
            return self.last_result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = SpecialistStatus.ERROR
            self.error_count += 1
            self.last_result = SpecialistResult(
                success=False,
                findings=[],
                summary="Ausfuehrungsfehler",
                error=str(e),
                duration_ms=duration_ms
            )
            logger.error(f"EXA Exception: {e}")
            return self.last_result

    async def _call_exa_api(
        self,
        api_key: str,
        query: str,
        num_results: int,
        search_type: str,
        timeout: int
    ) -> Optional[Dict[str, Any]]:
        """
        Ruft die EXA API auf.

        Args:
            api_key: EXA API Key
            query: Suchanfrage
            num_results: Anzahl Ergebnisse
            search_type: "neural" oder "keyword"
            timeout: Timeout in Sekunden

        Returns:
            API Response als Dict oder None bei Fehler
        """
        try:
            import aiohttp
        except ImportError:
            logger.warning("aiohttp nicht installiert - verwende synchronen Fallback")
            return await self._call_exa_api_sync(api_key, query, num_results, search_type, timeout)

        url = "https://api.exa.ai/search"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "numResults": num_results,
            "type": search_type,
            "useAutoprompt": True,
            "contents": {
                "text": {"maxCharacters": 500}
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        # Rate Limit
                        cooldown = self.config.get("cooldown_seconds", 300)
                        self.set_cooldown(cooldown)
                        logger.warning(f"EXA Rate Limit - Cooldown {cooldown}s")
                        return None
                    else:
                        error_text = await response.text()
                        logger.error(f"EXA API Fehler {response.status}: {error_text[:200]}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"EXA HTTP Fehler: {e}")
            return None

    async def _call_exa_api_sync(
        self,
        api_key: str,
        query: str,
        num_results: int,
        search_type: str,
        timeout: int
    ) -> Optional[Dict[str, Any]]:
        """Synchroner Fallback wenn aiohttp nicht verfuegbar."""
        import urllib.request
        import json

        url = "https://api.exa.ai/search"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "numResults": num_results,
            "type": search_type,
            "useAutoprompt": True
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')

            def do_request():
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return json.loads(response.read().decode('utf-8'))

            result = await asyncio.to_thread(do_request)
            return result

        except Exception as e:
            logger.error(f"EXA Sync API Fehler: {e}")
            return None

    def _parse_results(self, api_response: Dict[str, Any]) -> List[SpecialistFinding]:
        """
        Parst EXA API Response in SpecialistFindings.

        Args:
            api_response: Raw API Response

        Returns:
            Liste von SpecialistFinding Objekten
        """
        findings = []
        results = api_response.get("results", [])

        for result in results:
            title = result.get("title", "Ohne Titel")
            url = result.get("url", "")
            text = result.get("text", "")
            score = result.get("score", 0)

            # Severity basierend auf Score
            if score > 0.8:
                severity = "HIGH"
            elif score > 0.5:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            description = f"**{title}**\n{url}\n\n{text[:300]}..."

            findings.append(SpecialistFinding(
                severity=severity,
                description=description,
                file=url,
                category="search-result",
                fix=f"Mehr Info: {url}"
            ))

        return findings
