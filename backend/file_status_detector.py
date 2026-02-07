"""
Author: rahn
Datum: 05.02.2026
Version: 1.0
Beschreibung: Erkennt Dateistatus für gezielte Code-Generierung.
             Unterscheidet zwischen NEU, FEHLERHAFT und KORREKT.
             Ermöglicht gezielte Fixes statt vollständiger Regenerierung.
"""

import os
from typing import Dict, List, Optional


class FileStatusDetector:
    """
    Erkennt den Status von Dateien im Projekt.
    
    Status-Kategorien:
    - 'new': Datei existiert noch nicht, muss komplett generiert werden
    - 'error': Datei hat Fehler, muss gefixt werden
    - 'correct': Datei ist korrekt, sollte nicht überschrieben werden
    """
    
    def __init__(self, project_path: str):
        """
        Initialisiert den FileStatusDetector.
        
        Args:
            project_path: Pfad zum Projektverzeichnis
        """
        self.project_path = project_path
    
    def get_file_status(
        self, 
        filepath: str, 
        error_files: Optional[List[str]] = None
    ) -> str:
        """
        Ermittelt den Status einer einzelnen Datei.
        
        Args:
            filepath: Pfad zur Datei (relativ oder absolut)
            error_files: Liste von Dateien mit Fehlern
            
        Returns:
            Status: 'new', 'error', oder 'correct'
        """
        full_path = self._get_full_path(filepath)
        
        if not os.path.exists(full_path):
            return 'new'
        
        if error_files and filepath in error_files:
            return 'error'
        
        return 'correct'
    
    def get_files_to_patch(
        self, 
        current_code: Dict[str, str], 
        error_files: Optional[List[str]] = None,
        also_include_correct: bool = False
    ) -> List[str]:
        """
        Gibt die Dateien zurück, die tatsächlich bearbeitet werden müssen.
        
        Args:
            current_code: Dict mit {filepath: content}
            error_files: Liste von Dateien mit Fehlern
            also_include_correct: Wenn True, auch korrekte Dateien einbeziehen
            
        Returns:
            Liste von Dateipfaden die bearbeitet werden sollen
        """
        files_to_patch = []
        error_files = error_files or []
        
        for filepath in current_code:
            status = self.get_file_status(filepath, error_files)
            
            if status == 'new':
                # Neue Dateien müssen komplett generiert werden
                files_to_patch.append(filepath)
            elif status == 'error':
                # Fehlerhafte Dateien müssen gefixt werden
                files_to_patch.append(filepath)
            elif also_include_correct:
                # Korrekte Dateien nur wenn explizit gewünscht
                files_to_patch.append(filepath)
        
        return files_to_patch
    
    def get_status_summary(
        self, 
        current_code: Dict[str, str], 
        error_files: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Gibt eine Zusammenfassung aller Dateistatus zurück.
        
        Args:
            current_code: Dict mit {filepath: content}
            error_files: Liste von Dateien mit Fehlern
            
        Returns:
            Dict mit {status: [dateien]}
        """
        summary = {
            'new': [],
            'error': [],
            'correct': []
        }
        
        error_files = error_files or []
        
        for filepath in current_code:
            status = self.get_file_status(filepath, error_files)
            summary[status].append(filepath)
        
        return summary
    
    def _get_full_path(self, filepath: str) -> str:
        """
        Konvertiert relativen Pfad zu absolutem Pfad.
        
        Args:
            filepath: Relativer oder absoluter Pfad
            
        Returns:
            Absoluter Pfad
        """
        if os.path.isabs(filepath):
            return filepath
        
        return os.path.join(self.project_path, filepath)
    
    def filter_code_for_patch(
        self, 
        current_code: Dict[str, str], 
        files_to_patch: List[str]
    ) -> Dict[str, str]:
        """
        Filtert den Code auf nur die Dateien die gepatcht werden sollen.
        
        Args:
            current_code: Dict mit {filepath: content}
            files_to_patch: Liste von Dateipfaden die bearbeitet werden sollen
            
        Returns:
            Gefiltertes Dict mit nur den relevanten Dateien
        """
        filtered = {}
        
        for filepath, content in current_code.items():
            # Prüfe ob Datei in der Patch-Liste ist
            # Auch mit Pfad-Varianten prüfen
            for patch_file in files_to_patch:
                if (filepath == patch_file or 
                    filepath.endswith(f"/{patch_file}") or 
                    filepath.endswith(f"\\{patch_file}")):
                    filtered[filepath] = content
                    break
        
        return filtered
    
    def get_patch_ratio(
        self, 
        current_code: Dict[str, str], 
        error_files: Optional[List[str]] = None
    ) -> float:
        """
        Berechnet das Verhältnis von zu patchenden zu Gesamt-Dateien.
        
        Args:
            current_code: Dict mit {filepath: content}
            error_files: Liste von Dateien mit Fehlern
            
        Returns:
            Verhältnis (0.0 bis 1.0)
        """
        if not current_code:
            return 0.0
        
        files_to_patch = self.get_files_to_patch(current_code, error_files)
        return len(files_to_patch) / len(current_code)


def get_file_status_summary_for_log(
    project_path: str,
    current_code: Dict[str, str],
    error_files: Optional[List[str]] = None
) -> str:
    """
    Hilfsfunktion für Logging: Generiert Status-Zusammenfassung als String.
    
    Args:
        project_path: Pfad zum Projekt
        current_code: Dict mit {filepath: content}
        error_files: Liste von Dateien mit Fehlern
        
        Returns:
            Formatierter String für Logging
    """
    detector = FileStatusDetector(project_path)
    summary = detector.get_status_summary(current_code, error_files)
    
    parts = [
        f"New: {len(summary['new'])}",
        f"Error: {len(summary['error'])}",
        f"Correct: {len(summary['correct'])}",
        f"Patch-Ratio: {detector.get_patch_ratio(current_code, error_files):.1%}"
    ]
    
    return " | ".join(parts)
