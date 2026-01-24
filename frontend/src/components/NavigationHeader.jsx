/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: NavigationHeader Komponente - Gemeinsamer Header für alle Ansichten.
 *               Enthält Logo, Navigation-Tabs und Status-Anzeigen.
 */

import React from 'react';
import {
  Settings,
  Bell,
  Wifi,
  LayoutDashboard,
  Server,
  Users,
  DollarSign
} from 'lucide-react';

/**
 * NavigationHeader - Wiederverwendbarer Header mit Navigation.
 *
 * @param {string} currentRoom - Aktuelle Ansicht (für Tab-Highlighting)
 * @param {Function} setCurrentRoom - Navigation-Handler
 * @param {boolean} showConnectButton - "Connect Agent" Button anzeigen
 */
const NavigationHeader = ({ currentRoom, setCurrentRoom, showConnectButton = false }) => {
  return (
    <header className="flex-none flex items-center justify-between border-b border-border-dark px-6 py-3 bg-[#111418] z-20">
      <div className="flex items-center gap-6">
        {/* Logo und Projekt-Info */}
        <div className="flex items-center gap-4">
          <div className="p-2 rounded bg-primary/20 text-primary">
            <LayoutDashboard size={24} />
          </div>
          <div>
            <h2 className="text-lg font-bold leading-tight">Agent Office</h2>
            <div className="text-xs text-slate-400 font-medium">PROJECT: ALPHA-WEB-INTEGRATION</div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 ml-8 bg-[#1c2127] rounded-lg p-1 border border-[#283039]">
          <button
            onClick={() => setCurrentRoom('mission-control')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              currentRoom === 'mission-control'
                ? 'bg-primary/20 text-primary border border-primary/30'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Users size={16} />
            <span>Mission Control</span>
          </button>
          <button
            onClick={() => setCurrentRoom('mainframe')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              currentRoom === 'mainframe'
                ? 'bg-primary/20 text-primary border border-primary/30'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Server size={16} />
            <span>Mainframe Hub</span>
          </button>
          <button
            onClick={() => setCurrentRoom('budget-dashboard')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              currentRoom === 'budget-dashboard'
                ? 'bg-primary/20 text-primary border border-primary/30'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <DollarSign size={16} />
            <span>Budget</span>
          </button>
        </nav>
      </div>

      {/* Rechte Seite: Status und Aktionen */}
      <div className="flex gap-3 items-center">
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1c2127] border border-[#283039]">
          <Wifi size={14} className="text-green-500" />
          <span className="text-xs font-semibold text-white">System Online</span>
        </div>
        {showConnectButton && (
          <button className="h-9 px-4 bg-primary hover:bg-blue-600 text-white text-sm font-bold rounded-lg transition-colors">
            Connect Agent
          </button>
        )}
        <Settings size={20} className="text-slate-400 cursor-pointer hover:text-white" />
        <Bell size={20} className="text-slate-400 cursor-pointer hover:text-white" />
      </div>
    </header>
  );
};

export default NavigationHeader;
