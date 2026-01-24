import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Search,
  History,
  Settings,
  Rss,
  Globe,
  Database,
  Clock,
  Sparkles,
  Shield,
  Layers,
  PauseCircle,
  FileText,
  RefreshCw,
  Maximize2
} from 'lucide-react';

const ResearcherOffice = ({ agentName = "Researcher", status = "Idle", logs = [], onBack, color = "cyan" }) => {
  const insightLogRef = useRef(null);
  const knowledgeRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (insightLogRef.current) {
      insightLogRef.current.scrollTop = insightLogRef.current.scrollHeight;
    }
  }, [logs]);

  // Status badge styling
  const getStatusBadge = () => {
    const isActive = status !== 'Idle' && status !== 'Success' && status !== 'Failure';
    if (isActive) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/20 uppercase tracking-wide font-semibold shadow-[0_0_8px_rgba(6,182,212,0.2)]">
          Node Status: Online
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 border border-slate-500/20 uppercase tracking-wide">
        {status}
      </span>
    );
  };

  // Mock source feed data
  const sourceFeed = [
    { id: 1, type: 'scraping', title: '"Multi-Agent Reinforcement Learning in..."', source: 'arXiv.org', progress: 45 },
    { id: 2, type: 'indexed', title: 'TechCrunch: AI Funding Report Q3', source: 'url: .../2023/10/ai-funding-analysis', icon: 'globe' },
    { id: 3, type: 'indexed', title: 'Internal KB: Project Omega', source: 'id: doc-8821-omega-spec', icon: 'database' },
    { id: 4, type: 'pending', title: 'Google Scholar Query', source: '' },
  ];

  // Mock knowledge graph data
  const knowledgeTopics = [
    {
      title: 'Vector Databases',
      facts: [
        { text: 'Optimal chunk size for code snippets is', highlight: '512 tokens', suffix: ' with', highlight2: '50 token overlap', suffix2: '.' },
        { text: '', highlight: 'Pinecone', suffix: ' offers 20% faster retrieval for high-dimensional vectors compared to local solutions.' },
      ]
    },
    {
      title: 'Agent Orchestration',
      facts: [
        { text: '"Chain-of-Thought" prompting significantly reduces hallucinations in planning stages.' },
        { text: 'The', highlight: 'Reviewer Agent', suffix: ' pattern should act as a critic loop rather than a final gatekeeper to improve throughput.', citation: '[2]' },
      ]
    }
  ];

  // Mock reliability data
  const reliabilityScore = 88;
  const factDensity = [
    { id: 'S1', value: 80, count: 24 },
    { id: 'S2', value: 45, count: 12 },
    { id: 'S3', value: 95, count: 31 },
    { id: 'S4', value: 30, count: 8 },
  ];

  // Format timestamp
  const formatTime = (index) => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - (logs.length - index) * 3);
    return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-cyan-900/5">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-500/30 shadow-[0_0_10px_rgba(34,211,238,0.1)]">
              <Search size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName}
                {getStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-04-RES</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-cyan-500/30 transition-colors">
            <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
            </span>
            <Globe size={14} className="text-cyan-500" />
            <span className="text-xs font-semibold text-white">Deep Crawl #4402</span>
          </div>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#1e293b] hover:bg-[#334155] text-white transition-colors border border-[#334155]">
            <History size={18} />
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#1e293b] hover:bg-[#334155] text-white transition-colors border border-[#334155]">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden relative bg-[#0f172a]">
        {/* Grid Background */}
        <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.05] pointer-events-none"></div>

        {/* Left Sidebar - Source Feed */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Rss size={16} className="text-cyan-400" />
              Source Feed
            </h3>
            <span className="text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-900 px-1.5 py-0.5 rounded font-mono">12 Active</span>
          </div>

          <div className="flex-1 overflow-y-auto researcher-scrollbar p-4 space-y-4">
            {sourceFeed.map((source) => (
              <div key={source.id} className={source.type === 'scraping' ? 'relative group' : 'group cursor-pointer'}>
                {source.type === 'scraping' ? (
                  <>
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-teal-500 rounded-lg opacity-20 blur-sm group-hover:opacity-40 transition-opacity"></div>
                    <div className="relative bg-[#1e293b] p-3 rounded-lg border border-cyan-500/30 shadow-lg">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] font-bold text-cyan-400 bg-cyan-950/50 px-1.5 py-0.5 rounded border border-cyan-800">SCRAPING</span>
                        <span className="text-[10px] text-slate-400 font-mono">{source.source}</span>
                      </div>
                      <h4 className="text-sm font-semibold text-white mb-2 truncate">{source.title}</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <RefreshCw size={12} className="text-cyan-400 animate-spin" />
                            Extracting Abstract
                          </span>
                          <span className="font-mono text-cyan-200">{source.progress}%</span>
                        </div>
                        <div className="h-1 w-full bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-cyan-400 rounded-full animate-pulse" style={{ width: `${source.progress}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : source.type === 'indexed' ? (
                  <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-slate-500 transition-all">
                    <div className="flex justify-between items-start mb-1">
                      <span className="flex items-center gap-1 text-[10px] font-bold text-green-400 uppercase">
                        <span className="size-1.5 bg-green-500 rounded-full"></span>
                        Indexed
                      </span>
                      {source.icon === 'globe' ? <Globe size={14} className="text-slate-500" /> : <Database size={14} className="text-slate-500" />}
                    </div>
                    <h4 className="text-sm font-medium text-slate-300 group-hover:text-cyan-100 transition-colors">{source.title}</h4>
                    <p className="text-[11px] text-slate-500 mt-1 font-mono truncate">{source.source}</p>
                  </div>
                ) : (
                  <div className="bg-[#1e293b]/20 p-3 rounded-lg border border-[#334155] border-dashed opacity-70">
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-[10px] font-bold text-slate-500 uppercase">Pending</span>
                      <Clock size={14} className="text-slate-600" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-400">{source.title}</h4>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* API Usage Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Daily API Usage</span>
              <span>8,420 / 10,000</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              <div className="h-full w-[84%] bg-gradient-to-r from-cyan-600 to-cyan-400 rounded-full"></div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          {/* Insight Synthesis Panel */}
          <div className="h-[40%] border-b border-[#334155] bg-[#1e293b]/20 flex flex-col relative">
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <Sparkles size={180} />
            </div>
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/40 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                >
                  <Sparkles size={14} />
                </motion.div>
                Insight Synthesis
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">CONFIDENCE: 92.4%</span>
                <span className="size-2 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
              </div>
            </div>

            <div
              ref={insightLogRef}
              className="flex-1 p-5 overflow-y-auto researcher-scrollbar font-mono text-xs space-y-4"
            >
              {logs.length === 0 ? (
                <>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[14:02:10]</span>
                    <div className="flex-1">
                      <p className="text-slate-400 mb-1">Correlating data points from <span className="text-cyan-600">Source A</span> and <span className="text-cyan-600">Source C</span>...</p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[14:02:12]</span>
                    <div className="flex-1">
                      <p className="text-slate-300">Pattern Detected: Significant overlap in "Agentic Workflows" terminology across 4 recent papers.</p>
                    </div>
                  </div>
                  <div className="flex gap-4 group relative">
                    <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-cyan-900"></div>
                    <span className="text-cyan-700 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[14:02:15]</span>
                    <div className="flex-1 bg-cyan-950/20 p-2 rounded border-l-2 border-cyan-500">
                      <p className="text-cyan-300 font-semibold mb-1">Hypothesis Formulation:</p>
                      <p className="text-cyan-100/80 italic">The current implementation of the 'Coder' agent lacks context retention for long-running tasks, leading to repetitive queries. Proposed solution: Vector memory integration.</p>
                    </div>
                  </div>
                  <div className="flex gap-4 group animate-pulse">
                    <span className="text-cyan-500 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">...</span>
                    <p className="text-cyan-500/70 italic">Synthesizing final report...</p>
                  </div>
                </>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                    {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-cyan-900"></div>}
                    <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-cyan-700' : 'text-slate-600'}`}>
                      [{formatTime(i)}]
                    </span>
                    <div className={`flex-1 ${i === logs.length - 1 ? 'bg-cyan-950/20 p-2 rounded border-l-2 border-cyan-500' : ''}`}>
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-yellow-400' :
                        log.event === 'Success' ? 'text-green-400' :
                        i === logs.length - 1 ? 'text-cyan-100' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Knowledge Graph Panel */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Search size={14} className="text-teal-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Extracted Knowledge Graph</span>
              </div>
              <div className="flex gap-2">
                <button className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded hover:bg-slate-700 transition-colors">JSON View</button>
                <button className="text-[10px] bg-cyan-900/40 text-cyan-300 border border-cyan-700/50 px-2 py-0.5 rounded">List View</button>
              </div>
            </div>

            <div
              ref={knowledgeRef}
              className="flex-1 p-6 overflow-y-auto researcher-scrollbar font-mono text-sm leading-6"
            >
              <div className="space-y-6">
                {knowledgeTopics.map((topic, topicIndex) => (
                  <div key={topicIndex}>
                    <h5 className="text-slate-500 text-xs uppercase tracking-wider mb-2 border-b border-slate-800 pb-1">Topic: {topic.title}</h5>
                    <ul className="space-y-2">
                      {topic.facts.map((fact, factIndex) => (
                        <li key={factIndex} className="flex items-start text-slate-300">
                          <span className="text-teal-400 mr-2">●</span>
                          {fact.citation ? (
                            <div className="bg-slate-800/50 p-2 rounded w-full border border-slate-700/50">
                              <span className="text-xs text-slate-500 block mb-1">Citation {fact.citation}</span>
                              <span>{fact.text}<span className="text-teal-400">{fact.highlight}</span>{fact.suffix}</span>
                            </div>
                          ) : (
                            <span>
                              {fact.text}
                              {fact.highlight && <span className="text-cyan-200">{fact.highlight}</span>}
                              {fact.suffix}
                              {fact.highlight2 && <span className="text-cyan-200">{fact.highlight2}</span>}
                              {fact.suffix2}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div className="h-4 w-2 bg-cyan-400 animate-pulse mt-4"></div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <PauseCircle size={16} />
                Pause Research
              </button>
              <button className="flex-[2] bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(8,145,178,0.3)]">
                <FileText size={16} />
                Generate Final Report
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Reliability Metrics */}
        <aside className="w-[340px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Shield size={16} className="text-teal-400" />
              Source Reliability
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto researcher-scrollbar p-5 space-y-6">
            {/* Aggregate Credibility */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <Shield size={60} />
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Aggregate Credibility</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-white">High</span>
                <span className="text-sm text-green-400 font-medium font-mono">{reliabilityScore}/100</span>
              </div>
              <div className="mt-3 h-2 w-full bg-[#0f172a] rounded-full overflow-hidden flex gap-0.5">
                <div className="h-full w-[20%] bg-red-500/40"></div>
                <div className="h-full w-[30%] bg-yellow-500/40"></div>
                <div className="h-full w-[50%] bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]"></div>
              </div>
              <div className="flex justify-between mt-1 text-[9px] text-slate-500 uppercase font-bold">
                <span>Flagged</span>
                <span>Neutral</span>
                <span>Verified</span>
              </div>
            </div>

            {/* Search Depth Metrics */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Layers size={14} className="text-cyan-400" />
                Search Depth Metrics
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">Tree Depth</p>
                  <p className="text-lg font-bold text-white">4 <span className="text-[10px] text-slate-500 font-normal">levels</span></p>
                </div>
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">Breadth</p>
                  <p className="text-lg font-bold text-white">12 <span className="text-[10px] text-slate-500 font-normal">nodes</span></p>
                </div>
                <div className="col-span-2 bg-[#0f172a] p-2 rounded border border-slate-700/50 flex items-center justify-between">
                  <div>
                    <p className="text-[9px] text-slate-400 uppercase">Cross-Validation</p>
                    <p className="text-lg font-bold text-white">3x <span className="text-[10px] text-slate-500 font-normal">redundancy</span></p>
                  </div>
                  <div className="size-8 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin"></div>
                </div>
              </div>
            </div>

            {/* Fact Density */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] flex flex-col justify-between">
              <div className="flex justify-between items-center mb-2">
                <p className="text-xs text-slate-400 uppercase font-semibold">Fact Density</p>
                <span className="text-[10px] text-cyan-400 bg-cyan-950 px-1.5 rounded border border-cyan-900">Per Source</span>
              </div>
              <div className="space-y-2">
                {factDensity.map((fact, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px]">
                    <span className="w-8 text-slate-500 text-right">{fact.id}</span>
                    <div className="flex-1 h-2 bg-[#0f172a] rounded-sm overflow-hidden">
                      <div
                        className={`h-full rounded-sm ${i === 2 ? 'bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.4)]' : i === 0 ? 'bg-teal-400' : 'bg-teal-500/70'}`}
                        style={{ width: `${fact.value}%` }}
                      ></div>
                    </div>
                    <span className="w-6 text-slate-300 text-right">{fact.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Map Footer */}
          <div className="p-0 border-t border-[#334155] bg-[#0f172a] h-40 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-900/20 to-slate-900/80"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] to-transparent"></div>
            <div className="absolute bottom-3 right-3 flex flex-col items-end">
              <div className="flex gap-1 mb-1">
                <div className="size-2 bg-slate-600 rounded-full"></div>
                <div className="size-2 bg-slate-600 rounded-full"></div>
                <div className="size-2 bg-cyan-500 rounded-full animate-pulse shadow-[0_0_5px_cyan]"></div>
              </div>
              <span className="text-[9px] font-mono text-cyan-400 bg-black/50 px-1 rounded backdrop-blur-sm border border-cyan-900/50">MAP: SECTOR 4</span>
            </div>
            <button className="absolute top-2 right-2 text-white/50 hover:text-white transition-colors">
              <Maximize2 size={14} />
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default ResearcherOffice;
