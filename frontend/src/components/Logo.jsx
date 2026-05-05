import React from 'react';

export const CADMationSymbol = ({ className = "w-8 h-8" }) => (
  <svg 
    viewBox="0 0 64 64" 
    className={className}
    fill="none" 
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Hexagon frame - Stroke only for precision feel */}
    <polygon
      points="32,4 56,18 56,46 32,60 8,46 8,18"
      fill="none"
      stroke="#2A2B2A"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    {/* Inner precision ring - Subtle fill */}
    <polygon
      points="32,14 48,23 48,41 32,50 16,41 16,23"
      fill="#2A2B2A"
      fillOpacity="0.08"
      stroke="#2A2B2A"
      strokeWidth="1"
      strokeLinejoin="round"
    />
    {/* Stylized C arc - CAD focus */}
    <path
      d="M 42,22 A 16,16 0 1,0 42,42"
      fill="none"
      stroke="#E63F26"
      strokeWidth="4"
      strokeLinecap="round"
    />
    {/* C apex dot - Center point */}
    <circle cx="43" cy="32" r="2.5" fill="#E63F26" />
    
    {/* Radial tick marks */}
    <line x1="32" y1="8" x2="32" y2="12" stroke="#2A2B2A" strokeWidth="2" strokeLinecap="round"/>
    <line x1="52" y1="20" x2="49" y2="22" stroke="#2A2B2A" strokeWidth="2" strokeLinecap="round"/>
    <line x1="52" y1="44" x2="49" y2="42" stroke="#2A2B2A" strokeWidth="2" strokeLinecap="round"/>
    <line x1="32" y1="56" x2="32" y2="52" stroke="#2A2B2A" strokeWidth="2" strokeLinecap="round"/>
    <line x1="12" y1="44" x2="15" y2="42" stroke="#2A2B2A" strokeWidth="2" strokeLinecap="round"/>
    <line x1="12" y1="20" x2="15" y2="22" stroke="#2A2B2A" strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

export const CADMationLogo = ({ className = "", version = "" }) => (
  <div className={`flex items-center gap-4 ${className}`}>
    <CADMationSymbol className="w-10 h-10" />
    <div className="flex flex-col justify-center">
      <div className="relative">
        <h1 className="text-xl font-black tracking-tight text-zen-primary leading-none uppercase">CAD</h1>
        <div className="absolute -bottom-1 left-0 w-8 h-1 bg-[#E63F26] rounded-full"></div>
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-[10px] font-medium text-zen-text-dim uppercase tracking-widest">MATION</span>
        {version && (
          <span className="text-[9px] font-mono text-zen-text-muted bg-zen-surface-alt px-1.5 py-0.5 rounded border border-zen-border">
            v{version}
          </span>
        )}
      </div>
    </div>
  </div>
);
