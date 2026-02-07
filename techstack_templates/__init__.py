# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: TechStack-Templates Paket - Vordefinierte, getestete Konfigurationspakete
              fuer gaengige Tech-Stacks. Reduziert LLM-Variabilitaet bei Dependencies.
"""

from techstack_templates.template_loader import (
    load_all_templates,
    find_matching_templates,
    get_template_by_id,
    build_blueprint_from_template,
    copy_file_templates,
    get_coder_rules,
    get_template_summary_for_prompt,
)

__all__ = [
    "load_all_templates",
    "find_matching_templates",
    "get_template_by_id",
    "build_blueprint_from_template",
    "copy_file_templates",
    "get_coder_rules",
    "get_template_summary_for_prompt",
]
