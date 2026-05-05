import React, { useState, useEffect } from 'react';

export default function ScanLeaderboardPage({ currentUser }) {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confetti, setConfetti] = useState(false);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const res = await fetch('/api/stats/leaderboard');
        const data = await res.json();
        const sorted = (Array.isArray(data.leaderboard) ? data.leaderboard : [])
          .filter(u => u.role !== 'SUPER_ADMIN' && u.name !== 'SuperAdmin' && u.role !== 'Super Admin')
          .sort((a, b) => b.scans - a.scans);
        setLeaderboard(sorted);
        
        // Trigger confetti if current user is top 1
        if (sorted.length > 0 && sorted[0].userId === currentUser?.id) {
          setTimeout(() => setConfetti(true), 500);
        }
      } catch (err) {
        console.error('Failed to fetch leaderboard', err);
      } finally {
        setLoading(false);
      }
    };
    fetchLeaderboard();
  }, [currentUser]);

  const maxScans = leaderboard.length > 0 ? leaderboard[0].scans : 1;

  return (
    <div className="flex-1 overflow-y-auto p-10 bg-zen-bg relative">
      {confetti && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden z-50">
          {[...Array(50)].map((_, i) => (
            <div 
              key={i} 
              className="confetti-piece"
              style={{
                left: `${Math.random() * 100}%`,
                backgroundColor: i % 3 === 0 ? '#E63F26' : i % 3 === 1 ? '#2E75B6' : '#FFD700',
                animationDelay: `${Math.random() * 3}s`,
                animationDuration: `${2 + Math.random() * 2}s`
              }}
            />
          ))}
        </div>
      )}

      <div className="max-w-4xl mx-auto">
        <header className="mb-12 text-center">
          <div className="inline-block px-4 py-1 rounded-full bg-zen-primary/10 text-zen-primary text-[10px] font-bold uppercase tracking-widest mb-4">
            Stratos Enterprise Rewards
          </div>
          <h2 className="text-4xl font-bold text-zen-text-main mb-3">Scan Leaderboard</h2>
          <p className="text-zen-text-dim max-w-lg mx-auto">Celebrating our most active design engineers. Every scan pushes precision forward.</p>
        </header>

        {loading ? (
          <div className="text-center py-20 text-zen-text-dim">Loading rankings...</div>
        ) : (
          <div className="space-y-4">
            {leaderboard.map((user, index) => {
              const isCurrentUser = user.userId === currentUser?.id;
              const percentage = (user.scans / maxScans) * 100;
              
              return (
                <div 
                  key={user.userId} 
                  className={`zen-card p-6 flex items-center gap-6 transition-all duration-500 transform hover:scale-[1.02] ${
                    isCurrentUser ? 'border-zen-primary ring-1 ring-zen-primary/20 bg-zen-primary/[0.02]' : ''
                  }`}
                >
                  <div className="w-12 text-center">
                    {index === 0 ? <span className="text-3xl">🥇</span> :
                     index === 1 ? <span className="text-3xl">🥈</span> :
                     index === 2 ? <span className="text-3xl">🥉</span> :
                     <span className="text-xl font-bold text-zen-text-muted">#{index + 1}</span>}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-end mb-2">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm ${
                          isCurrentUser ? 'bg-zen-primary text-white' : 'bg-zen-surface-alt text-zen-text-muted'
                        }`}>
                          {user.name.charAt(0)}
                        </div>
                        <div className="truncate">
                          <h4 className={`font-bold text-zen-text-main truncate ${isCurrentUser ? 'text-lg' : ''}`}>
                            {user.name} {isCurrentUser && <span className="text-[10px] ml-1 bg-zen-primary/10 text-zen-primary px-2 py-0.5 rounded-full uppercase tracking-widest">You</span>}
                          </h4>
                          <p className="text-[10px] text-zen-text-dim uppercase tracking-widest">{user.role || 'Engineer'}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold text-zen-text-main leading-none">{user.scans}</div>
                        <div className="text-[9px] text-zen-text-muted uppercase tracking-widest">Total Scans</div>
                      </div>
                    </div>
                    
                    <div className="h-2 w-full bg-zen-surface-alt rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-1000 ease-out ${isCurrentUser ? 'bg-zen-primary' : 'bg-zen-text-muted/30'}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .confetti-piece {
          position: absolute;
          width: 8px;
          height: 16px;
          top: -20px;
          opacity: 0;
          animation: confetti-fall linear infinite;
        }
        @keyframes confetti-fall {
          0% { transform: translateY(0) rotate(0); opacity: 1; }
          100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
        }
      `}} />
    </div>
  );
}
