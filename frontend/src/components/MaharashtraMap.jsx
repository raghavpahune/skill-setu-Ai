import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const MAHA_DISTRICTS = [
  {
    name: 'Pune',
    jobs: 144,
    cluster: 'Western Maharashtra',
    focus: 'IT/ITES, Automotive, EV Hub',
    x: 32,
    y: 58,
    color: '#0d9488',
    deficit: '32%',
    deficitStatus: 'High',
    topSkill: 'Generative AI & EV Tech',
    institutes: 8,
    enrolment: 480,
  },
  {
    name: 'Mumbai',
    jobs: 125,
    cluster: 'Konkan',
    focus: 'Fintech, IT, Healthcare, SCM',
    x: 18,
    y: 46,
    color: '#3b82f6',
    deficit: '28%',
    deficitStatus: 'Moderate',
    topSkill: 'Cloud & Cyber Infrastructure',
    institutes: 12,
    enrolment: 720,
  },
  {
    name: 'Thane',
    jobs: 64,
    cluster: 'Konkan',
    focus: 'Manufacturing, Chemicals, IT',
    x: 22,
    y: 42,
    color: '#3b82f6',
    deficit: '25%',
    deficitStatus: 'Moderate',
    topSkill: 'Chemical Plant Automation',
    institutes: 6,
    enrolment: 360,
  },
  {
    name: 'Nagpur',
    jobs: 69,
    cluster: 'Vidarbha',
    focus: 'Logistics, Aerospace, Power, IoT',
    x: 82,
    y: 24,
    color: '#8b5cf6',
    deficit: '36%',
    deficitStatus: 'Critical',
    topSkill: 'Drone Aviation & Logistics',
    institutes: 7,
    enrolment: 420,
  },
  {
    name: 'Nashik',
    jobs: 44,
    cluster: 'North Maharashtra',
    focus: 'Auto Ancillaries, Pharma, CAD',
    x: 30,
    y: 34,
    color: '#f59e0b',
    deficit: '29%',
    deficitStatus: 'Moderate',
    topSkill: '3D CAD/CAM Parametric Tooling',
    institutes: 5,
    enrolment: 300,
  },
  {
    name: 'Kolhapur',
    jobs: 31,
    cluster: 'Western Maharashtra',
    focus: 'Foundry, Precision Eng, Agri',
    x: 34,
    y: 82,
    color: '#0d9488',
    deficit: '34%',
    deficitStatus: 'High',
    topSkill: 'CNC Tooling & Foundry Metallurgy',
    institutes: 4,
    enrolment: 240,
  },
  {
    name: 'Chhatrapati Sambhajinagar',
    jobs: 29,
    cluster: 'Marathwada',
    focus: 'Auto, Pharma, Welding, Solar',
    x: 46,
    y: 44,
    color: '#ec4899',
    deficit: '38%',
    deficitStatus: 'Critical',
    topSkill: 'Solar Grid Inverters & MIG Welding',
    institutes: 5,
    enrolment: 280,
  },
  {
    name: 'Amravati',
    jobs: 18,
    cluster: 'Vidarbha',
    focus: 'Textiles, AgriTech, Drones',
    x: 68,
    y: 28,
    color: '#8b5cf6',
    deficit: '31%',
    deficitStatus: 'High',
    topSkill: 'AgriTech Drone Maintenance',
    institutes: 3,
    enrolment: 180,
  },
  {
    name: 'Solapur',
    jobs: 16,
    cluster: 'Western Maharashtra',
    focus: 'Solar Energy, Textiles, Machining',
    x: 48,
    y: 70,
    color: '#0d9488',
    deficit: '35%',
    deficitStatus: 'High',
    topSkill: 'PV Installation & Power Distribution',
    institutes: 3,
    enrolment: 160,
  },
  {
    name: 'Ratnagiri',
    jobs: 10,
    cluster: 'Konkan',
    focus: 'Marine, Processing, Tourism',
    x: 24,
    y: 72,
    color: '#3b82f6',
    deficit: '22%',
    deficitStatus: 'Low',
    topSkill: 'Marine Cold-Chain Processing',
    institutes: 2,
    enrolment: 110,
  },
];

export default function MaharashtraMap({ selectedDistrict = 'Pune', onSelectDistrict }) {
  const [viewMode, setViewMode] = useState('both');
  const [hoveredDistrict, setHoveredDistrict] = useState(null);
  const [districtsData, setDistrictsData] = useState(MAHA_DISTRICTS);
  const [isLiveDynamic, setIsLiveDynamic] = useState(false);

  useEffect(() => {
    let activeSub = true;
    api.getDistricts()
      .then((res) => {
        if (!activeSub || !Array.isArray(res) || res.length === 0) return;
        const countMap = new Map(res.map((r) => [r.name?.toLowerCase(), r]));
        const updated = MAHA_DISTRICTS.map((d) => {
          const match = countMap.get(d.name.toLowerCase());
          if (match) {
            return {
              ...d,
              jobs: typeof match.job_count === 'number' ? match.job_count : d.jobs,
              institutes: typeof match.course_count === 'number' && match.course_count > 0 ? match.course_count : d.institutes,
            };
          }
          return d;
        });
        setDistrictsData(updated);
        setIsLiveDynamic(true);
      })
      .catch(() => {});
    return () => {
      activeSub = false;
    };
  }, []);

  const totalVacancies = districtsData.reduce((acc, d) => acc + (d.jobs || 0), 0);

  const active =
    districtsData.find(
      (d) => d.name.toLowerCase() === selectedDistrict?.toLowerCase()
    ) || districtsData[0];

  const displayed = hoveredDistrict || active;
  const demandShare = totalVacancies > 0 ? Math.round((displayed.jobs / totalVacancies) * 100) : null;

  return (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-slate-900 dark:text-white text-base tracking-tight">
              Maharashtra District Workforce Capacity & Demand Map
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 bg-teal-50 dark:bg-teal-950 text-teal-800 dark:text-teal-300 font-semibold rounded border border-teal-200 dark:border-teal-800">
              Regional Workforce Explorer
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Click any district node or card to inspect localized vacancy density, curriculum deficit levels, and seat quotas
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs border border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setViewMode('both')}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                viewMode === 'both'
                  ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white font-bold shadow-2xs'
                  : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white font-bold shadow-2xs'
                  : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
              }`}
            >
              Grid
            </button>
          </div>

          <Link
            to={`/government/district/${encodeURIComponent(active.name)}`}
            className="px-3 py-1.5 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white text-xs font-semibold rounded-lg shadow-2xs transition-colors whitespace-nowrap"
          >
            Inspect {active.name} Plan →
          </Link>
        </div>
      </div>

      {/* Main Container: Map Visual + Selected/Hovered Snapshot Panel */}
      {(viewMode === 'both' || viewMode === 'map') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
          {/* Interactive Geo Canvas */}
          <div className="lg:col-span-2 relative bg-slate-900 rounded-xl p-4 min-h-[300px] sm:min-h-[340px] flex flex-col justify-between border border-slate-800 overflow-hidden">
            {/* Background Map Grid Effect */}
            <div className="absolute inset-0 bg-[radial-gradient(#334155_1px,transparent_1px)] [background-size:16px_16px] opacity-40"></div>

            {/* State Outline Watermark */}
            <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-teal-400 font-semibold bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
                Geo-Cluster Canvas
              </span>
              <span className="text-[10px] text-slate-400 hidden sm:inline">
                Hover or click nodes to preview intelligence
              </span>
            </div>

            <div className="relative w-full h-[260px] sm:h-[300px] my-auto">
              {districtsData.map((d) => {
                const isSelected = selectedDistrict?.toLowerCase() === d.name.toLowerCase();
                const isHovered = hoveredDistrict?.name === d.name;

                return (
                  <button
                    key={d.name}
                    onClick={() => onSelectDistrict && onSelectDistrict(d.name)}
                    onMouseEnter={() => setHoveredDistrict(d)}
                    onMouseLeave={() => setHoveredDistrict(null)}
                    style={{ left: `${d.x}%`, top: `${d.y}%` }}
                    className="absolute -translate-x-1/2 -translate-y-1/2 group transition-all duration-300 focus:outline-none z-20"
                    title={`${d.name}: ${d.jobs} jobs (${d.cluster})`}
                  >
                    <div className="flex flex-col items-center relative">
                      <span
                        className={`w-3.5 h-3.5 rounded-full border-2 transition-transform duration-200 ${
                          isSelected
                            ? 'bg-teal-400 border-white scale-150 shadow-[0_0_12px_#2dd4bf]'
                            : isHovered
                            ? 'bg-amber-400 border-white scale-125 shadow-[0_0_8px_#f59e0b]'
                            : 'bg-slate-700 border-slate-400 group-hover:scale-125 group-hover:bg-teal-400'
                        }`}
                      />
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded mt-1 whitespace-nowrap transition-all shadow-md ${
                          isSelected
                            ? 'bg-teal-500 text-slate-950 font-extrabold'
                            : isHovered
                            ? 'bg-amber-500 text-slate-950 font-extrabold'
                            : 'bg-slate-800/90 text-slate-200 border border-slate-700 group-hover:bg-slate-700'
                        }`}
                      >
                        {d.name} ({d.jobs})
                      </span>

                      {/* Tooltip on Hover */}
                      {isHovered && (
                        <div className="absolute bottom-full mb-1.5 px-2.5 py-1 bg-slate-950 text-white text-[10px] rounded-lg shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-30 animate-fadeIn">
                          <p className="font-bold text-teal-300">{d.name} Hub</p>
                          <p className="text-slate-400">{d.jobs} jobs • {d.deficit} deficit</p>
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Map Cluster Legend */}
            <div className="relative z-10 flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800 text-[10px] text-slate-400">
              <span className="font-semibold text-slate-300">Cluster Zones:</span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-teal-500"></span> Western Maha
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-blue-500"></span> Konkan
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-purple-500"></span> Vidarbha
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span> North Maha
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-pink-500"></span> Marathwada
              </span>
            </div>
          </div>

          {/* Selected / Hovered District Snapshot Panel */}
          <div className="bg-slate-50 dark:bg-slate-800/60 p-5 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                  {displayed.cluster}
                </span>
                <span className="text-xs font-mono font-bold text-slate-600 dark:text-slate-300">
                  {displayed.jobs} Active Vacancies
                </span>
              </div>

              <div className="flex items-baseline justify-between mb-1">
                <h4 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                  {displayed.name} District
                </h4>
                {hoveredDistrict ? (
                  <span className="text-[10px] text-amber-600 dark:text-amber-400 font-semibold font-mono">
                    [Hover Preview]
                  </span>
                ) : !isLiveDynamic ? (
                  <span className="text-[10px] text-slate-500 font-semibold font-mono">
                    [Benchmark Baseline]
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
                Workforce Demographics & Capacity Status
              </p>

              <div className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 mb-3 text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Primary Hiring Clusters:
                </span>
                <p className="text-teal-800 dark:text-teal-300 font-medium">
                  {displayed.focus}
                </p>
              </div>

              <div className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
                <div className="flex justify-between py-1 border-b border-slate-200/60 dark:border-slate-700/60">
                  <span>Statewide Demand Share:</span>
                  <span className="font-bold text-slate-900 dark:text-white">
                    {demandShare != null ? `${demandShare}% of Maharashtra` : 'Calculating...'}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60 dark:border-slate-700/60">
                  <span>Curriculum Deficit Level:</span>
                  <span
                    className={`font-bold ${
                      displayed.deficitStatus === 'Critical'
                        ? 'text-rose-600 dark:text-rose-400'
                        : displayed.deficitStatus === 'High'
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-emerald-600 dark:text-emerald-400'
                    }`}
                  >
                    {displayed.deficit} ({displayed.deficitStatus})
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60 dark:border-slate-700/60">
                  <span>Registered Capacity (Est. ITI Baseline):</span>
                  <span className="font-bold text-slate-900 dark:text-white font-mono">
                    {displayed.institutes} ITIs ({displayed.enrolment} seats)
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60 dark:border-slate-700/60">
                  <span>Top High-Growth Skill:</span>
                  <span className="font-semibold text-teal-700 dark:text-teal-300 line-clamp-1">
                    {displayed.topSkill}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-3 border-t border-slate-200 dark:border-slate-700">
              <Link
                to={`/government/district/${encodeURIComponent(displayed.name)}`}
                className="w-full py-2 bg-slate-900 dark:bg-teal-600 hover:bg-slate-800 dark:hover:bg-teal-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-xs"
              >
                <span>Inspect Detailed {displayed.name} Plan</span>
                <span>→</span>
              </Link>
            </div>
          </div>
        </div>
      )}

      {(viewMode === 'both' || viewMode === 'grid') && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {districtsData.map((d) => {
            const isSelected = selectedDistrict?.toLowerCase() === d.name.toLowerCase();
            return (
              <div
                key={d.name}
                onClick={() => onSelectDistrict && onSelectDistrict(d.name)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer text-left ${
                  isSelected
                    ? 'bg-slate-900 dark:bg-teal-950 text-white border-slate-900 dark:border-teal-700 shadow-md ring-2 ring-teal-500/50 scale-[1.02]'
                    : 'bg-slate-50 dark:bg-slate-800/60 hover:bg-white dark:hover:bg-slate-800 text-slate-900 dark:text-white border-slate-200 dark:border-slate-700/80 hover:border-teal-400 dark:hover:border-teal-600 hover:shadow-xs'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm">{d.name}</span>
                  <span
                    className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded ${
                      isSelected
                        ? 'bg-teal-500 text-slate-950 font-bold'
                        : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {d.jobs} jobs
                  </span>
                </div>
                <div className="flex items-center justify-between mt-1 text-[11px]">
                  <span className={isSelected ? 'text-slate-300' : 'text-slate-500 dark:text-slate-400'}>
                    {d.cluster}
                  </span>
                  <span className={`font-mono font-semibold ${
                    d.deficitStatus === 'Critical'
                      ? 'text-rose-400'
                      : d.deficitStatus === 'High'
                      ? 'text-amber-400'
                      : 'text-emerald-400'
                  }`}>
                    {d.deficit}
                  </span>
                </div>
                <p
                  className={`text-[11px] mt-1.5 font-medium line-clamp-1 ${
                    isSelected ? 'text-teal-300' : 'text-teal-700 dark:text-teal-400'
                  }`}
                >
                  {d.focus}
                </p>

                <div className="mt-2.5 pt-2 border-t border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center text-[10px]">
                  <span className={isSelected ? 'text-slate-400' : 'text-slate-400 dark:text-slate-500'}>
                    {d.institutes} ITIs • {d.enrolment} seats
                  </span>
                  <Link
                    to={`/government/district/${encodeURIComponent(d.name)}`}
                    className={`font-semibold hover:underline flex items-center gap-0.5 ${
                      isSelected ? 'text-teal-300' : 'text-slate-900 dark:text-slate-300'
                    }`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    Plan →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
