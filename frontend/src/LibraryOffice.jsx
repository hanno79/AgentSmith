/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.2
 * Beschreibung: Library Office - Archiv- und Protokollverwaltung für alle Projekte.
 *               Design: Warme Bibliotheks-Ästhetik mit Aktenschrank-Metapher.
 *               ÄNDERUNG 28.01.2026: Refaktoriert - ProtocolFeed und ProjectDetail extrahiert.
 *               ÄNDERUNG 29.01.2026: Resizable Panels - Trennlinie zwischen Projekt-Details und Protokoll verschiebbar.
 *               WICHTIG: Keine Dummy-Daten - nur echte Werte aus der Datenbank.
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { API_BASE } from './constants/config';
import {
  ArrowLeft,
  BookOpen,
  Archive,
  Search,
  Clock,
  Loader2,
  FolderOpen,
  Hash,
  Users,
  GripHorizontal
} from 'lucide-react';

// Extrahierte Komponenten
import ProtocolFeed from './components/ProtocolFeed';
import ProjectDetail, { renderStatusBadge, formatTime, formatCost } from './components/ProjectDetail';

// Farbpalette: Warme Bibliotheks-Ästhetik
const COLORS = {
  primary: '#ec9c13',
  backgroundDark: '#1a1612',
  woodDark: '#2c241b',
  woodLight: '#3e3226',
  glass: 'rgba(44, 36, 27, 0.7)',
  glassBorder: 'rgba(236, 156, 19, 0.2)'
};

const LibraryOffice = ({
  onBack,
  logs = []
}) => {
  // States für Daten vom Backend
  const [currentProject, setCurrentProject] = useState(null);
  const [archivedProjects, setArchivedProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('current');
  const [entries, setEntries] = useState([]);

  // ÄNDERUNG 29.01.2026: Resizable Panels für bessere Lesbarkeit
  const [topPanelHeight, setTopPanelHeight] = useState(40); // 40% für Projekt-Details
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  // Daten vom Backend laden
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  // ÄNDERUNG 29.01.2026: Resizer-Logik für Panel-Größenänderung
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newHeight = ((e.clientY - rect.top) / rect.height) * 100;
      // Min 15%, Max 85% für bessere Usability
      setTopPanelHeight(Math.min(Math.max(newHeight, 15), 85));
    };

    const handleMouseUp = () => setIsDragging(false);

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging]);

  const fetchData = async () => {
    try {
      const currentRes = await fetch(`${API_BASE}/library/current`);
      const currentData = await currentRes.json();
      setCurrentProject(currentData.project);

      if (currentData.project) {
        const entriesRes = await fetch(`${API_BASE}/library/entries?limit=100`);
        const entriesData = await entriesRes.json();
        setEntries(entriesData.entries || []);
      }

      const archiveRes = await fetch(`${API_BASE}/library/archive`);
      const archiveData = await archiveRes.json();
      setArchivedProjects(archiveData.projects || []);

      setIsLoading(false);
    } catch (error) {
      console.error('Fehler beim Laden der Library-Daten:', error);
      setIsLoading(false);
    }
  };

  const loadArchivedProject = async (projectId) => {
    try {
      const res = await fetch(`${API_BASE}/library/archive/${projectId}`);
      const data = await res.json();
      setSelectedProject(data.project);
      setEntries(data.project?.entries || []);
    } catch (error) {
      console.error('Fehler beim Laden des archivierten Projekts:', error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/library/search?q=${encodeURIComponent(searchQuery)}`);
      const data = await res.json();
      setSearchResults(data.results || []);
      setActiveTab('search');
    } catch (error) {
      console.error('Fehler bei der Suche:', error);
    }
  };

  // Aktives Projekt für Detail-Ansicht
  const activeProject = selectedProject || currentProject;

  return (
    <div
      className="text-white font-display overflow-hidden h-screen flex flex-col"
      style={{ backgroundColor: COLORS.backgroundDark }}
    >
      {/* Dust Motes Animation */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 rounded-full bg-amber-200/20"
            initial={{
              x: Math.random() * window.innerWidth,
              y: Math.random() * window.innerHeight
            }}
            animate={{
              y: [null, -20, 20, -10, 0],
              x: [null, 10, -10, 5, 0],
              opacity: [0.1, 0.3, 0.1, 0.2, 0.1]
            }}
            transition={{
              duration: 10 + Math.random() * 10,
              repeat: Infinity,
              delay: Math.random() * 5
            }}
          />
        ))}
      </div>

      {/* Header */}
      <header
        className="flex-none flex items-center justify-between whitespace-nowrap border-b px-6 py-3 z-20 shadow-lg"
        style={{ backgroundColor: COLORS.woodDark, borderColor: COLORS.glassBorder }}
      >
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded hover:bg-white/10 text-amber-200/70 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-amber-900/50" />
          <div className="flex items-center gap-3">
            <div
              className="size-9 flex items-center justify-center rounded-lg border shadow-lg"
              style={{ backgroundColor: COLORS.woodLight, borderColor: COLORS.primary + '40' }}
            >
              <BookOpen size={18} style={{ color: COLORS.primary }} />
            </div>
            <div>
              <h2 className="text-lg font-bold leading-tight tracking-[-0.015em]" style={{ color: COLORS.primary }}>
                Bibliothek
              </h2>
              <div className="text-xs text-amber-200/50 font-medium tracking-wide">ARCHIV & PROTOKOLL</div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
            style={{ backgroundColor: COLORS.glass, borderColor: COLORS.glassBorder }}
          >
            <Search size={14} className="text-amber-200/50" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Archive durchsuchen..."
              className="bg-transparent border-none outline-none text-sm text-amber-100 placeholder-amber-200/30 w-48"
            />
          </div>
          <button
            onClick={handleSearch}
            className="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            style={{ backgroundColor: COLORS.primary + '20', color: COLORS.primary }}
          >
            Suchen
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden relative">
        <div
          className="absolute inset-0 opacity-5 pointer-events-none"
          style={{
            backgroundImage: `linear-gradient(${COLORS.primary}20 1px, transparent 1px), linear-gradient(90deg, ${COLORS.primary}20 1px, transparent 1px)`,
            backgroundSize: '40px 40px'
          }}
        />

        {/* Left Sidebar - Cabinet Wall */}
        <aside
          className="w-[300px] border-r flex flex-col z-10"
          style={{ backgroundColor: COLORS.woodDark, borderColor: COLORS.glassBorder }}
        >
          {/* Tab Navigation */}
          <div className="p-3 border-b flex gap-2" style={{ borderColor: COLORS.glassBorder }}>
            <button
              onClick={() => { setActiveTab('current'); setSelectedProject(null); }}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'current' ? 'text-amber-900 shadow-lg' : 'text-amber-200/50 hover:text-amber-200'
              }`}
              style={{ backgroundColor: activeTab === 'current' ? COLORS.primary : 'transparent' }}
            >
              <Clock size={14} className="inline mr-1" />
              Aktuell
            </button>
            <button
              onClick={() => setActiveTab('archive')}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'archive' ? 'text-amber-900 shadow-lg' : 'text-amber-200/50 hover:text-amber-200'
              }`}
              style={{ backgroundColor: activeTab === 'archive' ? COLORS.primary : 'transparent' }}
            >
              <Archive size={14} className="inline mr-1" />
              Archiv
            </button>
          </div>

          {/* Sidebar Content */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ scrollbarColor: `${COLORS.primary} ${COLORS.woodDark}` }}>
            {isLoading ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-amber-200/50">
                <Loader2 size={24} className="animate-spin" style={{ color: COLORS.primary }} />
                <span className="text-sm">Lade Daten...</span>
              </div>
            ) : activeTab === 'current' ? (
              currentProject ? (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 rounded-lg border cursor-pointer transition-all hover:border-opacity-50"
                  style={{ backgroundColor: COLORS.woodLight, borderColor: COLORS.primary + '40', boxShadow: `0 4px 20px ${COLORS.primary}10` }}
                  onClick={() => setSelectedProject(null)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <FolderOpen size={16} style={{ color: COLORS.primary }} />
                      <span className="text-sm font-bold text-amber-100 truncate max-w-[180px]">{currentProject.name}</span>
                    </div>
                    {renderStatusBadge(currentProject.status)}
                  </div>
                  <p className="text-xs text-amber-200/50 mb-2 line-clamp-2">{currentProject.goal}</p>
                  <div className="flex items-center gap-4 text-xs text-amber-200/40">
                    <span className="flex items-center gap-1"><Hash size={10} />{currentProject.iterations || 0} Iter.</span>
                    <span className="flex items-center gap-1"><Users size={10} />{currentProject.agents_involved?.length || 0} Agents</span>
                  </div>
                </motion.div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-amber-200/30">
                  <BookOpen size={32} />
                  <span className="text-sm">Kein aktives Projekt</span>
                  <span className="text-xs">Starte ein neues Projekt um die Protokollierung zu beginnen</span>
                </div>
              )
            ) : activeTab === 'archive' ? (
              archivedProjects.length > 0 ? (
                archivedProjects.map((project, i) => (
                  <motion.div
                    key={project.project_id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={`p-3 rounded-lg border cursor-pointer transition-all hover:border-opacity-50 ${
                      selectedProject?.project_id === project.project_id ? 'ring-2' : ''
                    }`}
                    style={{
                      backgroundColor: COLORS.woodLight,
                      borderColor: selectedProject?.project_id === project.project_id ? COLORS.primary : COLORS.glassBorder
                    }}
                    onClick={() => loadArchivedProject(project.project_id)}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <span className="text-sm font-medium text-amber-100 truncate max-w-[160px]">{project.name}</span>
                      {renderStatusBadge(project.status)}
                    </div>
                    <p className="text-[10px] text-amber-200/40 mb-2">{formatTime(project.completed_at)}</p>
                    <div className="flex items-center gap-3 text-[10px] text-amber-200/30">
                      <span>{project.iterations} Iter.</span>
                      <span>{project.entry_count} Einträge</span>
                      <span>{formatCost(project.total_cost)}</span>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-amber-200/30">
                  <Archive size={32} />
                  <span className="text-sm">Keine archivierten Projekte</span>
                </div>
              )
            ) : (
              searchResults.length > 0 ? (
                searchResults.map((result, i) => (
                  <motion.div
                    key={`${result.project_id}-${i}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="p-3 rounded-lg border cursor-pointer transition-all hover:border-opacity-50"
                    style={{ backgroundColor: COLORS.woodLight, borderColor: COLORS.glassBorder }}
                    onClick={() => loadArchivedProject(result.project_id)}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Search size={12} style={{ color: COLORS.primary }} />
                      <span className="text-xs font-medium text-amber-100">{result.project_name}</span>
                    </div>
                    <p className="text-[10px] text-amber-200/50 line-clamp-2">{result.match_text}</p>
                    <span className="text-[9px] text-amber-200/30 mt-1 inline-block">Treffer in: {result.match_type}</span>
                  </motion.div>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-amber-200/30">
                  <Search size={32} />
                  <span className="text-sm">Keine Treffer für "{searchQuery}"</span>
                </div>
              )
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t text-xs text-amber-200/40" style={{ borderColor: COLORS.glassBorder }}>
            <div className="flex justify-between">
              <span>Archiviert: {archivedProjects.length}</span>
              <span style={{ color: COLORS.primary }}>SYS.VER.1.0</span>
            </div>
          </div>
        </aside>

        {/* Main Content - Reading Desk mit Resizable Panels */}
        <main
          ref={containerRef}
          className="flex-1 flex flex-col min-w-0 z-10"
          style={{ backgroundColor: COLORS.backgroundDark }}
        >
          {/* Top Panel: Projekt-Details */}
          <div
            className="overflow-auto"
            style={{ height: `${topPanelHeight}%` }}
          >
            <ProjectDetail project={activeProject} />
          </div>

          {/* Resizer Bar - ÄNDERUNG 29.01.2026 */}
          <div
            onMouseDown={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            className={`h-2 flex-shrink-0 flex items-center justify-center cursor-ns-resize transition-colors ${
              isDragging ? 'bg-amber-600' : 'bg-amber-900/30 hover:bg-amber-700/50'
            }`}
            style={{ borderTop: `1px solid ${COLORS.glassBorder}`, borderBottom: `1px solid ${COLORS.glassBorder}` }}
          >
            <GripHorizontal size={16} className={`${isDragging ? 'text-amber-200' : 'text-amber-700'}`} />
          </div>

          {/* Bottom Panel: Protokoll-Feed */}
          <div
            className="overflow-auto flex-1"
            style={{ height: `${100 - topPanelHeight}%` }}
          >
            <ProtocolFeed entries={entries} />
          </div>
        </main>
      </div>
    </div>
  );
};

export default LibraryOffice;
