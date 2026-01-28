/**
 * Author: rahn
 * Datum: 28.01.2026
 * Version: 1.1
 * Beschreibung: DependencyOffice - IT-Abteilung des Bueros.
 *               Verwaltet Software-Inventar, Installationen und Vulnerability-Checks.
 *               ÄNDERUNG 28.01.2026: Material Symbols durch Lucide-Icons ersetzt.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    ChevronDown,
    ChevronRight,
    ArrowLeft,
    Package,
    RefreshCw,
    Code,
    Terminal,
    Boxes,
    Activity,
    Shield,
    X,
    Sparkles,
    BarChart3,
    Circle
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

// Inventory Tree Item Komponente
function InventoryTreeItem({ label, version, children, icon: IconComponent, status }) {
    const [expanded, setExpanded] = useState(true);

    const statusColors = {
        installed: 'bg-green-500',
        updating: 'bg-orange-500 animate-pulse',
        error: 'bg-red-500'
    };

    return (
        <div className="mb-0.5">
            <div
                className="flex items-center gap-2 hover:bg-slate-800/50 px-2 py-1.5 rounded cursor-pointer group"
                onClick={() => children && setExpanded(!expanded)}
            >
                {/* Expand/Collapse oder Punkt für Blätter */}
                <span className="text-slate-500 group-hover:text-orange-400 w-4 flex-shrink-0">
                    {children ? (
                        expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
                    ) : (
                        <Circle size={6} className="ml-1" fill="currentColor" />
                    )}
                </span>

                {/* Icon falls vorhanden */}
                {IconComponent && (
                    <span className="text-amber-500 flex-shrink-0">
                        {typeof IconComponent === 'function' ? <IconComponent size={14} /> : IconComponent}
                    </span>
                )}

                {/* Label */}
                <span className="text-xs text-slate-300 truncate flex-1">{label}</span>

                {/* Version und Status */}
                {version && (
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                        {status && <span className={`w-1.5 h-1.5 rounded-full ${statusColors[status] || 'bg-green-500'}`}></span>}
                        <span className="text-[10px] text-green-400 font-mono">{version}</span>
                    </div>
                )}
            </div>
            {children && expanded && (
                <div className="pl-4 ml-2 border-l border-slate-700/50">
                    {children}
                </div>
            )}
        </div>
    );
}

// Terminal Log Line Komponente
function TerminalLine({ timestamp, content, type }) {
    const typeStyles = {
        info: 'text-slate-400',
        success: 'text-green-400',
        warning: 'text-amber-300/80',
        error: 'text-red-400',
        thought: 'border-l-2 border-orange-500 pl-3 bg-orange-500/5 py-2 rounded-r text-orange-100'
    };

    return (
        <div className={`flex gap-3 ${typeStyles[type] || 'text-slate-400'}`}>
            <span className="text-slate-600 w-20 shrink-0 border-r border-slate-700 pr-2">
                [{timestamp}]
            </span>
            <p dangerouslySetInnerHTML={{ __html: content }}></p>
        </div>
    );
}

// Metric Card Komponente
function MetricCard({ title, value, unit, icon: IconComponent, progress }) {
    return (
        <div className="glass-card rounded-xl p-4 relative overflow-hidden group hover:bg-[#1e293b]/80 transition-colors">
            {IconComponent && (
                <div className="absolute top-2 right-2 opacity-10">
                    <IconComponent size={48} className="text-orange-500" />
                </div>
            )}
            <p className="text-[10px] text-slate-400 uppercase font-bold mb-1 tracking-wider">{title}</p>
            <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-white" style={{ textShadow: '0 0 10px rgba(249,115,22,0.5)' }}>
                    {value}
                </span>
                {unit && <span className="text-sm text-orange-400 font-medium">{unit}</span>}
            </div>
            {progress !== undefined && (
                <div className="mt-3 h-1.5 w-full bg-[#0f172a] rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-orange-600 to-amber-300 rounded-full animate-pulse"
                        style={{ width: `${progress}%` }}
                    ></div>
                </div>
            )}
        </div>
    );
}

// Hauptkomponente
export default function DependencyOffice({ onBack }) {
    const [inventory, setInventory] = useState(null);
    const [logs, setLogs] = useState([]);
    const [vulnerabilities, setVulnerabilities] = useState({ counts: { critical: 0, moderate: 0 }, total: 0 });
    const [isLoading, setIsLoading] = useState(true);
    const [isInstalling, setIsInstalling] = useState(false);
    const [installCommand, setInstallCommand] = useState('');
    const [status, setStatus] = useState('Idle');

    // Inventar laden
    const loadInventory = useCallback(async (forceRefresh = false) => {
        try {
            const response = await fetch(`${API_BASE}/dependencies/inventory?force_refresh=${forceRefresh}`);
            const data = await response.json();
            if (data.status === 'ok') {
                setInventory(data.inventory);
                addLog('info', 'Inventar geladen');
            }
        } catch (error) {
            addLog('error', `Fehler beim Laden des Inventars: ${error.message}`);
        }
    }, []);

    // Vulnerabilities laden
    const loadVulnerabilities = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/dependencies/vulnerabilities`);
            const data = await response.json();
            if (data.status === 'ok') {
                setVulnerabilities(data.vulnerabilities);
            }
        } catch (error) {
            console.error('Fehler beim Laden der Vulnerabilities:', error);
        }
    }, []);

    // Log hinzufuegen
    const addLog = (type, message) => {
        const now = new Date();
        const timestamp = now.toTimeString().slice(0, 8);
        setLogs(prev => [...prev.slice(-50), { timestamp, content: message, type }]);
    };

    // Installation ausfuehren
    const runInstall = async () => {
        if (!installCommand.trim()) return;

        setIsInstalling(true);
        setStatus('Installing');
        addLog('info', `Starte Installation: <span class="text-slate-200">${installCommand}</span>`);

        try {
            const response = await fetch(`${API_BASE}/dependencies/install`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ install_command: installCommand })
            });
            const data = await response.json();

            if (data.status === 'OK') {
                addLog('success', 'Installation erfolgreich abgeschlossen');
                loadInventory(true);
            } else {
                addLog('error', `Installation fehlgeschlagen: ${data.output?.slice(0, 200) || 'Unbekannter Fehler'}`);
            }
        } catch (error) {
            addLog('error', `Fehler: ${error.message}`);
        } finally {
            setIsInstalling(false);
            setStatus('Idle');
            setInstallCommand('');
        }
    };

    // Vollstaendiger Scan
    const runFullScan = async () => {
        setStatus('Scanning');
        addLog('info', 'Starte vollstaendigen Dependency-Scan...');

        try {
            await loadInventory(true);
            await loadVulnerabilities();
            addLog('success', 'Scan abgeschlossen');
        } catch (error) {
            addLog('error', `Scan-Fehler: ${error.message}`);
        } finally {
            setStatus('Idle');
        }
    };

    // Initial laden
    useEffect(() => {
        const init = async () => {
            setIsLoading(true);
            await loadInventory();
            await loadVulnerabilities();
            setIsLoading(false);
            addLog('info', 'Dependency Agent Workstation bereit');
        };
        init();
    }, [loadInventory, loadVulnerabilities]);

    const healthScore = inventory?.health_score || 0;
    const pythonPackages = inventory?.python?.packages || [];
    const npmPackages = inventory?.npm?.packages || [];
    const systemTools = inventory?.system || {};

    return (
        <div className="h-screen flex flex-col bg-[#0f172a] text-white font-sans overflow-hidden">
            {/* Header */}
            <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-orange-900/5">
                <div className="flex items-center gap-4 text-white">
                    <button
                        onClick={onBack}
                        className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
                    >
                        <ArrowLeft size={18} />
                    </button>
                    <div className="h-6 w-px bg-slate-700"></div>
                    <div className="flex items-center gap-3">
                        <div className="size-8 flex items-center justify-center rounded bg-orange-500/20 text-orange-400 border border-orange-500/30 shadow-[0_0_10px_rgba(249,115,22,0.2)]">
                            <Package size={18} />
                        </div>
                        <div>
                            <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                                Dependency Agent
                                <span className={`px-1.5 py-0.5 rounded text-[10px] border uppercase tracking-wide flex items-center gap-1 ${
                                    status === 'Idle' ? 'bg-green-500/20 text-green-400 border-green-500/20' :
                                    status === 'Installing' ? 'bg-orange-500/20 text-orange-400 border-orange-500/20' :
                                    'bg-amber-500/20 text-amber-400 border-amber-500/20'
                                }`}>
                                    <span className={`w-1.5 h-1.5 rounded-full ${
                                        status === 'Idle' ? 'bg-green-400' : 'bg-amber-400 animate-pulse'
                                    }`}></span>
                                    {status}
                                </span>
                            </h2>
                            <div className="text-xs text-slate-400 font-medium tracking-wide">IT-ABTEILUNG</div>
                        </div>
                    </div>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={runFullScan}
                        className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] shadow-inner hover:bg-[#334155] transition-colors"
                    >
                        <RefreshCw size={14} className="text-orange-500" />
                        <span className="text-xs font-semibold text-white">Scan starten</span>
                    </button>
                </div>
            </header>

            {/* Main Content */}
            <div className="flex flex-1 overflow-hidden relative bg-[#0f172a]">
                {/* Grid Background */}
                <div className="absolute inset-0 opacity-[0.05] pointer-events-none"
                    style={{
                        backgroundImage: 'linear-gradient(to right, #1e293b 1px, transparent 1px), linear-gradient(to bottom, #1e293b 1px, transparent 1px)',
                        backgroundSize: '40px 40px',
                        maskImage: 'linear-gradient(to bottom, black 40%, transparent 100%)'
                    }}
                ></div>

                {/* Left Sidebar - Inventory Manager */}
                <aside className="w-[280px] border-r border-[#334155] bg-[#0f172a]/60 flex flex-col z-10 backdrop-blur-sm">
                    <div className="p-3 border-b border-[#334155] flex justify-between items-center bg-orange-500/5">
                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                            <Boxes size={14} className="text-orange-400" />
                            Inventory Manager
                        </h3>
                        <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">
                            v1.1
                        </span>
                    </div>

                    <div className="flex-1 overflow-y-auto p-3 space-y-1 text-sm">
                        {isLoading ? (
                            <div className="text-slate-500 text-xs p-2">Lade Inventar...</div>
                        ) : (
                            <>
                                {/* Python Runtime */}
                                <InventoryTreeItem
                                    label="Python Runtime"
                                    version={inventory?.python?.version}
                                    icon={Code}
                                >
                                    {pythonPackages.slice(0, 20).map((pkg, i) => (
                                        <InventoryTreeItem
                                            key={i}
                                            label={pkg.name}
                                            version={pkg.version}
                                            status={pkg.status}
                                        />
                                    ))}
                                    {pythonPackages.length > 20 && (
                                        <div className="text-[10px] text-slate-500 pl-6 py-1">
                                            +{pythonPackages.length - 20} weitere Pakete
                                        </div>
                                    )}
                                </InventoryTreeItem>

                                {/* NPM Packages */}
                                <InventoryTreeItem
                                    label="NPM Packages"
                                    version={inventory?.npm?.version}
                                    icon={Package}
                                >
                                    {npmPackages.map((pkg, i) => (
                                        <InventoryTreeItem
                                            key={i}
                                            label={pkg.name}
                                            version={pkg.version}
                                            status={pkg.status}
                                        />
                                    ))}
                                    {npmPackages.length === 0 && (
                                        <div className="text-[10px] text-slate-500 pl-6 py-1">Keine globalen Pakete</div>
                                    )}
                                </InventoryTreeItem>

                                {/* System Tools */}
                                <InventoryTreeItem
                                    label="System Tools"
                                    icon={Terminal}
                                >
                                    {Object.entries(systemTools).map(([name, version]) => (
                                        <InventoryTreeItem
                                            key={name}
                                            label={name}
                                            version={version}
                                            status="installed"
                                        />
                                    ))}
                                </InventoryTreeItem>
                            </>
                        )}
                    </div>

                    {/* Health Status */}
                    <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] text-slate-400 uppercase font-bold">Health Status</span>
                            <span className="text-[10px] text-orange-400">{healthScore}%</span>
                        </div>
                        <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-orange-600 to-amber-400 rounded-full transition-all duration-500"
                                style={{ width: `${healthScore}%` }}
                            ></div>
                        </div>
                    </div>
                </aside>

                {/* Main Panel */}
                <main className="flex-1 flex flex-col min-w-0 z-10">
                    {/* Activity Log */}
                    <div className="h-[40%] border-b border-[#334155] bg-[#1e293b]/30 flex flex-col">
                        <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/50 flex justify-between items-center backdrop-blur-md">
                            <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                                <Activity size={14} />
                                Activity Log
                            </h3>
                            <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                                <span className="size-2 rounded-full bg-green-500"></span> LIVE
                            </span>
                        </div>
                        <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-3">
                            {logs.map((log, i) => (
                                <TerminalLine key={i} {...log} />
                            ))}
                            {logs.length === 0 && (
                                <div className="text-slate-500 italic">Keine Aktivitaet...</div>
                            )}
                        </div>
                    </div>

                    {/* Installation Terminal */}
                    <div className="flex-1 bg-[#0d1117] flex flex-col relative overflow-hidden">
                        <div className="absolute bottom-0 right-0 p-8 opacity-[0.03] pointer-events-none">
                            <Terminal size={150} />
                        </div>

                        <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between shadow-md">
                            <div className="flex items-center gap-2">
                                <Terminal size={14} className="text-slate-500" />
                                <span className="text-xs font-mono text-slate-300">Installation Terminal</span>
                            </div>
                        </div>

                        <div className="flex-1 p-6 overflow-y-auto font-mono text-sm leading-6">
                            <div className="flex items-center gap-2 text-slate-400 mb-4">
                                <span className="text-green-500">➜</span>
                                <span className="text-blue-400">~</span>
                                <input
                                    type="text"
                                    value={installCommand}
                                    onChange={(e) => setInstallCommand(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && runInstall()}
                                    placeholder="pip install <package> oder npm install <package>"
                                    className="flex-1 bg-transparent border-none outline-none text-white placeholder-slate-600"
                                    disabled={isInstalling}
                                />
                                {isInstalling && <span className="animate-pulse text-orange-500">_</span>}
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3 z-10">
                            <button
                                onClick={() => setInstallCommand('')}
                                className="flex-1 bg-red-500/5 hover:bg-red-500/10 text-red-500 border border-red-500/20 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 group"
                                disabled={isInstalling}
                            >
                                <X size={16} className="group-hover:scale-110 transition-transform" />
                                Abbrechen
                            </button>
                            <button
                                onClick={runInstall}
                                disabled={isInstalling || !installCommand.trim()}
                                className="flex-[3] bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(249,115,22,0.3)] border border-orange-400/20 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <Sparkles size={16} />
                                {isInstalling ? 'Installiere...' : 'Installieren'}
                            </button>
                        </div>
                    </div>
                </main>

                {/* Right Sidebar - Metrics */}
                <aside className="w-[300px] border-l border-[#334155] bg-[#0f172a]/60 flex flex-col z-10 backdrop-blur-sm">
                    <div className="p-4 border-b border-[#334155]">
                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                            <BarChart3 size={14} className="text-amber-400" />
                            System Metrics
                        </h3>
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        <MetricCard
                            title="Python Packages"
                            value={pythonPackages.length}
                            unit="installed"
                            icon={Code}
                        />

                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155]">
                                <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">NPM Packages</p>
                                <div className="text-lg font-bold text-white">{npmPackages.length}</div>
                            </div>
                            <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155]">
                                <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">System Tools</p>
                                <div className="text-lg font-bold text-white">{Object.keys(systemTools).length}</div>
                            </div>
                        </div>

                        {/* Vulnerability Scanner */}
                        <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] relative">
                            <div className="flex justify-between items-center mb-4">
                                <span className="text-xs font-bold text-slate-300 uppercase">Vulnerability Scanner</span>
                                <Shield size={16} className="text-slate-500" />
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="relative size-16 flex items-center justify-center">
                                    <svg className="size-full -rotate-90" viewBox="0 0 36 36">
                                        <path
                                            className="text-slate-700"
                                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="3"
                                        />
                                        <path
                                            className="text-orange-500"
                                            style={{ filter: 'drop-shadow(0 0 5px rgba(249,115,22,0.8))' }}
                                            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeDasharray={`${100 - vulnerabilities.total * 5}, 100`}
                                            strokeWidth="3"
                                        />
                                    </svg>
                                    <span className="absolute text-xs font-bold text-white">
                                        {vulnerabilities.total === 0 ? 'Safe' : vulnerabilities.total}
                                    </span>
                                </div>
                                <div className="flex-1 space-y-1.5">
                                    <div className="flex justify-between text-[10px]">
                                        <span className="text-red-400 font-bold">Critical</span>
                                        <span className="text-white">{vulnerabilities.counts?.critical || 0}</span>
                                    </div>
                                    <div className="w-full h-1 bg-slate-700 rounded-full">
                                        <div
                                            className="h-full bg-red-500 rounded-full"
                                            style={{ width: `${(vulnerabilities.counts?.critical || 0) * 20}%` }}
                                        ></div>
                                    </div>
                                    <div className="flex justify-between text-[10px]">
                                        <span className="text-amber-400 font-bold">Moderate</span>
                                        <span className="text-white">{vulnerabilities.counts?.moderate || 0}</span>
                                    </div>
                                    <div className="w-full h-1 bg-slate-700 rounded-full">
                                        <div
                                            className="h-full bg-amber-400 rounded-full"
                                            style={{ width: `${(vulnerabilities.counts?.moderate || 0) * 10}%` }}
                                        ></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Last Updated */}
                        <div className="text-[10px] text-slate-500 text-center">
                            Letztes Update: {inventory?.last_updated ? new Date(inventory.last_updated).toLocaleString('de-DE') : '-'}
                        </div>
                    </div>
                </aside>
            </div>

            {/* Custom Styles */}
            <style>{`
                .glass-card {
                    background: rgba(30, 41, 59, 0.7);
                    backdrop-filter: blur(8px);
                    border: 1px solid rgba(249, 115, 22, 0.2);
                }
            `}</style>
        </div>
    );
}
