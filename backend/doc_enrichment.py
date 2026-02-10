# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 10.02.2026
Version: 1.0
Beschreibung: Doc-Enrichment Pipeline - Holt relevante Bibliotheks-Dokumentation
              und injiziert sie in den Coder-Prompt via MCP Server.
              Primaer: Context7 MCP (kostenlos, kein API-Key noetig)
              Fallback: Ref.tools MCP (benoetigt API-Key)

AENDERUNG 10.02.2026: Fix 47 - Neue Datei
ROOT-CAUSE-FIX:
  Symptom: Coder generiert Code mit fehlender Library-Integration (z.B. Shadcn border-border)
  Ursache: Coder-Prompt enthaelt nur Template-Regeln, keine aktuellen Library-Docs
  Loesung: MCP-basierte Documentation-Retrieval Pipeline mit Session-Cache
"""

import asyncio
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Bibliotheken die KEINE Dokumentation benoetigen (allgemein bekannt)
SKIP_LIBRARIES = {
    "react", "react-dom", "postcss", "autoprefixer", "next",
    "typescript", "eslint", "prettier", "jest", "vitest",
    "@types/react", "@types/node", "@types/react-dom",
    "tailwindcss", "webpack", "babel",
    # Python Basics
    "flask", "fastapi", "uvicorn", "gunicorn", "pytest",
    "requests", "pydantic", "python-dotenv", "jinja2",
}

# Bibliotheken die IMMER Dokumentation bekommen wenn im Projekt
PRIORITY_LIBRARIES = {
    "shadcn": "shadcn/ui setup CSS-Variable Konfiguration tailwind.config.js globals.css",
    "@shadcn/ui": "shadcn/ui setup CSS-Variable Konfiguration tailwind.config.js",
    "prisma": "Prisma Schema Client-Setup Migrationen",
    "@prisma/client": "Prisma Client API und Setup",
    "drizzle-orm": "Drizzle ORM Schema-Definition und Migrationen",
    "next-auth": "NextAuth.js Provider-Konfiguration und Session",
    "nextauth": "NextAuth.js Provider-Konfiguration",
    "@auth/core": "Auth.js Setup und Konfiguration",
    "lucia": "Lucia Auth Setup und Session-Management",
    "@trpc/server": "tRPC Server Router Setup",
    "zustand": "Zustand Store Pattern und Verwendung",
    "@tanstack/react-query": "React Query Setup und Verwendung",
    "@supabase/supabase-js": "Supabase JS Client Setup und Auth",
    "supabase": "Supabase Client und Auth Setup",
    "@clerk/nextjs": "Clerk Next.js Auth Integration",
    "stripe": "Stripe Payment Integration und Checkout",
    "resend": "Resend E-Mail API Setup",
    "uploadthing": "UploadThing File Upload Setup",
    "convex": "Convex Realtime Database Setup",
    "sqlite3": "sqlite3 Node.js Binding Setup und Verwendung",
    "better-sqlite3": "better-sqlite3 synchrone SQLite API",
    "mongoose": "Mongoose MongoDB ODM Schema und Modelle",
    "sequelize": "Sequelize ORM Setup und Modelle",
    "zod": "Zod Schema Validierung und TypeScript Integration",
}

# Keywords im User-Goal die auf Library-Bedarf hindeuten
GOAL_KEYWORDS = {
    "shadcn": "shadcn/ui",
    "prisma": "prisma",
    "drizzle": "drizzle-orm",
    "nextauth": "next-auth",
    "auth.js": "next-auth",
    "authentication": "next-auth",
    "stripe": "stripe",
    "payment": "stripe",
    "supabase": "supabase",
    "trpc": "@trpc/server",
    "upload": "uploadthing",
    "clerk": "@clerk/nextjs",
    "zustand": "zustand",
    "tanstack": "@tanstack/react-query",
    "react-query": "@tanstack/react-query",
    "mongoose": "mongoose",
    "sequelize": "sequelize",
    "zod": "zod",
}


class DocEnrichmentPipeline:
    """
    Holt Bibliotheks-Dokumentation via MCP-Server und cached sie pro Session.

    Nutzt Context7 als primaere Quelle (kostenlos, kein API-Key),
    Ref.tools als Fallback (benoetigt API-Key).

    AENDERUNG 10.02.2026: Fix 47 - Neue Klasse
    """

    def __init__(self, config: dict, ui_log_callback=None):
        self._config = config.get("doc_enrichment", {})
        self._enabled = self._config.get("enabled", False)
        self._cache: Dict[str, Optional[str]] = {}
        self._npx_path: Optional[str] = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="doc-enrich")
        # AENDERUNG 10.02.2026: Fix 47b — UI-Logging Callback
        # Damit Specialist-Aktivitaeten im Frontend-Output sichtbar sind
        self._ui_log = ui_log_callback

    def get_enrichment_section(self, tech_blueprint: dict, user_goal: str) -> str:
        """
        Haupt-Einstiegspunkt: Erkennt relevante Libraries, holt Docs, baut Prompt-Sektion.

        Returns:
            Formatierte Prompt-Sektion oder leerer String bei Fehler/deaktiviert
        """
        if not self._enabled:
            return ""

        libraries = self._detect_libraries(tech_blueprint, user_goal)
        if not libraries:
            return ""

        max_total = self._config.get("max_total_chars", 10000)
        sections = []
        total_chars = 0

        for lib_name, query_hint in libraries:
            if total_chars >= max_total:
                break

            doc = self._fetch_docs_for_library(lib_name, query_hint)
            if not doc:
                continue

            # Token-Budget einhalten
            remaining = max_total - total_chars
            if len(doc) > remaining:
                doc = self._truncate_doc(doc, remaining)

            sections.append(f"### {lib_name} (Setup-Kontext):\n{doc}")
            total_chars += len(doc)

        if not sections:
            return ""

        header = "\n\n📚 BIBLIOTHEKS-DOKUMENTATION (aktuelle Docs - BEACHTEN!):\n"
        return header + "\n\n".join(sections) + "\n"

    def _detect_libraries(self, tech_blueprint: dict, user_goal: str) -> List[Tuple[str, str]]:
        """Erkennt Bibliotheken aus Goal-Keywords, Dependencies und Templates. Max 5."""
        detected = []
        seen = set()

        goal_lower = user_goal.lower() if user_goal else ""

        # Quelle 1: Keywords im User Goal
        for keyword, lib_name in GOAL_KEYWORDS.items():
            if keyword in goal_lower and lib_name not in seen:
                query_hint = PRIORITY_LIBRARIES.get(lib_name, f"{lib_name} Setup und Integration")
                detected.append((lib_name, query_hint))
                seen.add(lib_name)

        # Quelle 2: Dependencies aus tech_blueprint
        deps = tech_blueprint.get("dependencies", {})
        if isinstance(deps, list):
            deps = {d: "" for d in deps}

        for dep_name in deps:
            dep_lower = dep_name.lower()
            if dep_lower in seen or dep_lower in SKIP_LIBRARIES:
                continue

            # Pruefe ob Priority-Library
            if dep_lower in PRIORITY_LIBRARIES or dep_name in PRIORITY_LIBRARIES:
                query_hint = PRIORITY_LIBRARIES.get(
                    dep_lower, PRIORITY_LIBRARIES.get(dep_name, f"{dep_name} Setup"))
                detected.append((dep_name, query_hint))
                seen.add(dep_lower)

        # Quelle 3: Template-Keywords
        source_template = tech_blueprint.get("_source_template", "")
        if source_template:
            for keyword, lib_name in GOAL_KEYWORDS.items():
                if keyword in source_template.lower() and lib_name not in seen:
                    query_hint = PRIORITY_LIBRARIES.get(lib_name, f"{lib_name} Setup")
                    detected.append((lib_name, query_hint))
                    seen.add(lib_name)

        return detected[:5]  # Maximal 5 Bibliotheken (Token-Budget)

    def _fetch_docs_for_library(self, library_name: str, query_hint: str) -> Optional[str]:
        """Holt Docs mit Session-Cache. Async-to-Sync Bridge via ThreadPoolExecutor."""
        # Cache-Lookup
        cache_key = library_name.lower()
        if cache_key in self._cache:
            logger.debug("Doc-Enrichment Cache-Hit: '%s'", library_name)
            return self._cache[cache_key]

        # Async-to-Sync Bridge (gleiche Pattern wie CodeRabbit)
        # ROOT-CAUSE-FIX: DevLoop ist synchron, MCP SDK ist async
        # Loesung: asyncio.run() in separatem Thread via ThreadPoolExecutor
        def _run_async():
            return asyncio.run(self._fetch_async(library_name, query_hint))

        try:
            future = self._executor.submit(_run_async)
            result = future.result(timeout=60)
        except Exception as e:
            logger.warning("Doc-Enrichment Async-Bridge Fehler fuer '%s': %s",
                           library_name, str(e)[:200])
            result = None

        # Ergebnis cachen (auch None, um wiederholte Fehlversuche zu vermeiden)
        self._cache[cache_key] = result
        return result

    def _emit_ui_log(self, agent: str, event: str, message: str):
        """Sendet Log-Nachricht an UI wenn Callback verfuegbar."""
        if self._ui_log:
            try:
                self._ui_log(agent, event, message)
            except Exception:
                pass  # UI-Log darf Pipeline nicht blockieren

    async def _fetch_async(self, library_name: str, query: str) -> Optional[str]:
        """Async-Wrapper: Context7 primaer, Ref.tools fallback."""
        # Primaer: Context7
        self._emit_ui_log("Context7 Docs", "Fetch",
                          f"Hole Docs fuer '{library_name}'...")
        result = await self._fetch_via_context7(library_name, query)
        if result:
            logger.info("Doc-Enrichment: '%s' via Context7 geladen (%d Zeichen)",
                        library_name, len(result))
            self._emit_ui_log("Context7 Docs", "OK",
                              f"'{library_name}': {len(result)} Zeichen geladen")
            return result

        # Fallback: Ref.tools
        self._emit_ui_log("Ref.tools Docs", "Fetch",
                          f"Fallback: Hole Docs fuer '{library_name}'...")
        result = await self._fetch_via_ref_tools(library_name, query)
        if result:
            logger.info("Doc-Enrichment: '%s' via Ref.tools geladen (%d Zeichen)",
                        library_name, len(result))
            self._emit_ui_log("Ref.tools Docs", "OK",
                              f"'{library_name}': {len(result)} Zeichen geladen")
            return result

        logger.info("Doc-Enrichment: Keine Docs fuer '%s' gefunden", library_name)
        self._emit_ui_log("DocEnrichment", "Skip",
                          f"Keine Docs fuer '{library_name}' gefunden")
        return None

    async def _fetch_via_context7(self, library_name: str, query: str) -> Optional[str]:
        """Holt Docs via Context7 MCP: resolve-library-id → get-library-docs."""
        ctx7_config = self._config.get("context7", {})
        if not ctx7_config.get("enabled", True):
            return None

        npx_path = self._get_npx_path()
        if not npx_path:
            logger.warning("Context7: npx nicht gefunden - uebersprungen")
            return None

        timeout = ctx7_config.get("timeout_seconds", 30)
        max_chars = self._config.get("max_docs_chars", 3000)

        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters

            server_params = StdioServerParameters(
                command=npx_path,
                args=["-y", "@upstash/context7-mcp"],
                env={**os.environ}
            )

            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=timeout)

                    # Tool-Namen dynamisch ermitteln (Context7 benennt Tools um)
                    tools_result = await asyncio.wait_for(
                        session.list_tools(), timeout=timeout)
                    tool_names = {t.name for t in tools_result.tools}

                    resolve_tool = "resolve-library-id"
                    # Context7 hat get-library-docs zu query-docs umbenannt
                    if "get-library-docs" in tool_names:
                        docs_tool = "get-library-docs"
                    else:
                        docs_tool = "query-docs"

                    if resolve_tool not in tool_names:
                        logger.warning("Context7: Tool '%s' nicht gefunden. Verfuegbar: %s",
                                       resolve_tool, tool_names)
                        return None

                    if docs_tool not in tool_names:
                        logger.warning("Context7: Docs-Tool nicht gefunden. Verfuegbar: %s",
                                       tool_names)
                        return None

                    # Schritt 1: Library-ID aufloesen
                    resolve_result = await asyncio.wait_for(
                        session.call_tool(resolve_tool, {
                            "libraryName": library_name
                        }),
                        timeout=timeout
                    )

                    if resolve_result.isError:
                        logger.warning("Context7 resolve fehlgeschlagen fuer '%s'",
                                       library_name)
                        return None

                    resolve_text = self._extract_text_from_result(resolve_result)
                    library_id = self._parse_library_id(resolve_text)
                    if not library_id:
                        logger.info("Context7: Keine Library-ID fuer '%s' gefunden",
                                    library_name)
                        return None

                    # Schritt 2: Dokumentation abrufen
                    docs_result = await asyncio.wait_for(
                        session.call_tool(docs_tool, {
                            "libraryId": library_id,
                            "topic": query
                        }),
                        timeout=timeout
                    )

                    if docs_result.isError:
                        logger.warning("Context7 docs fehlgeschlagen fuer '%s' (ID: %s)",
                                       library_name, library_id)
                        return None

                    doc_text = self._extract_text_from_result(docs_result)
                    return self._truncate_doc(doc_text, max_chars) if doc_text else None

        except asyncio.TimeoutError:
            logger.warning("Context7: Timeout nach %ds fuer '%s'", timeout, library_name)
            return None
        except FileNotFoundError:
            logger.warning("Context7: npx Prozess konnte nicht gestartet werden")
            return None
        except Exception as e:
            logger.warning("Context7 Fehler fuer '%s': %s", library_name, str(e)[:200])
            return None

    async def _fetch_via_ref_tools(self, library_name: str, query: str) -> Optional[str]:
        """Holt Docs via Ref.tools MCP (Fallback). Benoetigt REF_TOOLS_API_KEY."""
        ref_config = self._config.get("ref_tools", {})
        if not ref_config.get("enabled", True):
            return None

        # API-Key aufloesen
        api_key = ref_config.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        if not api_key:
            logger.debug("Ref.tools: Kein API-Key konfiguriert - uebersprungen")
            return None

        npx_path = self._get_npx_path()
        if not npx_path:
            return None

        timeout = ref_config.get("timeout_seconds", 30)
        max_chars = self._config.get("max_docs_chars", 3000)

        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters

            server_params = StdioServerParameters(
                command=npx_path,
                args=["-y", "ref-tools-mcp@latest"],
                env={**os.environ, "REF_API_KEY": api_key}
            )

            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=timeout)

                    # Dokumentation suchen
                    search_result = await asyncio.wait_for(
                        session.call_tool("ref_search_documentation", {
                            "query": f"{library_name} setup integration {query}"
                        }),
                        timeout=timeout
                    )

                    if search_result.isError:
                        logger.warning("Ref.tools Suche fehlgeschlagen fuer '%s'",
                                       library_name)
                        return None

                    doc_text = self._extract_text_from_result(search_result)
                    return self._truncate_doc(doc_text, max_chars) if doc_text else None

        except asyncio.TimeoutError:
            logger.warning("Ref.tools: Timeout nach %ds fuer '%s'", timeout, library_name)
            return None
        except FileNotFoundError:
            logger.warning("Ref.tools: npx Prozess konnte nicht gestartet werden")
            return None
        except Exception as e:
            logger.warning("Ref.tools Fehler fuer '%s': %s", library_name, str(e)[:200])
            return None

    def _get_npx_path(self) -> Optional[str]:
        """Cached shutil.which('npx') Ergebnis (Windows-kompatibel)."""
        if self._npx_path is None:
            self._npx_path = shutil.which("npx") or ""
        return self._npx_path or None

    @staticmethod
    def _extract_text_from_result(result) -> str:
        """Extrahiert Text aus MCP CallToolResult."""
        if not result or not result.content:
            return ""
        parts = []
        for content_item in result.content:
            if hasattr(content_item, 'text') and content_item.text:
                parts.append(content_item.text)
        return "\n".join(parts)

    @staticmethod
    def _parse_library_id(resolve_text: str) -> Optional[str]:
        """
        Extrahiert die Library-ID aus dem resolve-library-id Ergebnis.

        Context7 IDs haben Format: /org/project (z.B. /shadcn-ui/ui)
        """
        if not resolve_text:
            return None
        # Suche nach dem typischen /org/project Pattern
        match = re.search(r'(/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', resolve_text)
        return match.group(1) if match else None

    @staticmethod
    def _truncate_doc(text: str, max_chars: int) -> str:
        """Kuerzt Dokumentation auf max_chars an Absatzgrenzen."""
        if not text or len(text) <= max_chars:
            return text or ""
        truncated = text[:max_chars]
        # Versuche an Absatzgrenze zu kuerzen
        last_para = truncated.rfind("\n\n")
        if last_para > max_chars * 0.5:
            truncated = truncated[:last_para]
        return truncated + "\n[...gekuerzt wegen Token-Budget]"


def get_doc_enrichment_section(manager) -> str:
    """
    Erstellt DocEnrichmentPipeline on-demand (lazy init) und cached sie
    auf dem Manager-Objekt.

    Args:
        manager: OrchestrationManager Instanz

    Returns:
        Formatierte Prompt-Sektion oder leerer String
    """
    if not hasattr(manager, '_doc_enrichment') or manager._doc_enrichment is None:
        config = getattr(manager, 'config', {})
        # AENDERUNG 10.02.2026: Fix 47b — UI-Log Callback weiterleiten
        ui_log_cb = getattr(manager, '_ui_log', None)
        manager._doc_enrichment = DocEnrichmentPipeline(config, ui_log_callback=ui_log_cb)

    pipeline = manager._doc_enrichment
    tech_blueprint = getattr(manager, 'tech_blueprint', {}) or {}
    user_goal = getattr(manager, '_current_user_goal', '') or ''

    # Nur wenn tech_blueprint existiert
    if not tech_blueprint:
        return ""

    try:
        return pipeline.get_enrichment_section(tech_blueprint, user_goal)
    except Exception as e:
        logger.warning("Doc-Enrichment uebersprungen: %s", e)
        return ""
