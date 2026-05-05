import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { CADMationLogo } from './Logo';

export default function LandingScreen({ onLoginSuccess }) {
  const [showLogin, setShowLogin] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post('/api/auth/login', {
        email,
        password
      });
      
      if (response.data.success) {
        onLoginSuccess(response.data.user);
      }
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('An unexpected error occurred during login.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-zen-bg text-zen-text-main font-sans min-h-screen flex flex-col antialiased">
      {/* Header */}
      <header className="w-full z-50 bg-zen-surface/90 backdrop-blur-md border-b border-zen-border transition-all">
        <nav className="flex justify-between items-center px-8 md:px-12 h-16 w-full">
          <CADMationLogo />
          {/* Real Status Indicator - No fake links */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zen-surface-alt border border-zen-border">
             <span className="w-1.5 h-1.5 rounded-full bg-zen-success animate-pulse"></span>
             <span className="text-[9px] font-bold text-zen-text-dim uppercase tracking-widest">Stratos Link Active</span>
          </div>
        </nav>
      </header>

      {/* Main Canvas */}
      <main className="flex-grow flex items-center justify-center p-6 relative overflow-hidden">
        {/* Architectural Background Pattern from Guidelines */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.03]" style={{ backgroundImage: 'radial-gradient(var(--color-zen-primary) 1.5px, transparent 1.5px)', backgroundSize: '32px 32px' }}></div>
        
        <div className={`w-full max-w-2xl transition-all duration-700 transform ${isVisible ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'} flex flex-col items-center`}>
          
          {!showLogin ? (
            <div className="text-center space-y-10 z-10 w-full">
              <div className="space-y-6">
                <h1 className="text-5xl md:text-6xl font-black text-zen-primary tracking-tight">
                  Stratos <span className="text-zen-text-muted font-light px-2">x</span> CADMation
                </h1>
                <p className="text-lg md:text-xl text-zen-text-dim max-w-xl mx-auto font-medium leading-relaxed">
                  The Intelligent Local Copilot for CATIA V5.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-3 text-xs font-bold text-zen-text-muted uppercase tracking-widest mt-4">
                  <span className="px-3 py-1 rounded-full border border-zen-border bg-zen-surface-alt">Precision without compromise</span>
                  <span className="px-3 py-1 rounded-full border border-zen-border bg-zen-surface-alt">Local without limitation</span>
                </div>
              </div>
              
              <div className="pt-8">
                <button 
                  onClick={() => setShowLogin(true)}
                  className="zen-pill px-10 py-4 text-sm tracking-widest shadow-xl shadow-zen-primary/10 hover:shadow-zen-primary/20 group"
                >
                  ACCESS WORKSPACE
                  <svg className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                </button>
              </div>
            </div>
          ) : (
            <div className="w-full max-w-md z-10">
              <button 
                onClick={() => setShowLogin(false)}
                className="mb-6 flex items-center gap-2 text-xs font-bold text-zen-text-muted hover:text-zen-primary transition-colors uppercase tracking-widest w-fit"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Return
              </button>
              
              <div className="zen-card p-10 md:p-12 w-full animate-[fadeIn_0.3s_ease-out]">
                <div className="mb-10 space-y-2">
                  <h2 className="text-2xl font-bold text-zen-primary">Welcome Back</h2>
                  <p className="text-sm text-zen-text-dim">Enter your Stratos engineering credentials to proceed.</p>
                </div>

                {error && (
                  <div className="mb-6 p-4 rounded-xl bg-zen-error/10 border border-zen-error/20 text-zen-error text-xs font-bold flex items-start gap-2">
                    <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                    <span>{error}</span>
                  </div>
                )}

                <form className="space-y-6" onSubmit={handleLogin}>
                  <div className="space-y-2">
                    <label className="zen-label">Email Address</label>
                    <input 
                      className="w-full bg-zen-surface-alt border border-zen-border rounded-xl px-4 py-3 text-sm text-zen-primary outline-none focus:border-zen-info focus:ring-1 focus:ring-zen-info transition-all" 
                      placeholder="engineer@stratos.engineering" 
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoFocus
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="zen-label">Password</label>
                    <input 
                      className="w-full bg-zen-surface-alt border border-zen-border rounded-xl px-4 py-3 text-sm text-zen-primary outline-none focus:border-zen-info focus:ring-1 focus:ring-zen-info transition-all" 
                      placeholder="••••••••••••" 
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                  <div className="pt-6">
                    <button 
                      disabled={loading}
                      className="w-full zen-pill py-3.5 text-xs disabled:opacity-50 flex items-center justify-center gap-2" 
                      type="submit"
                    >
                      {loading ? (
                        <>
                          <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                          AUTHENTICATING...
                        </>
                      ) : 'INITIALIZE SESSION'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full py-6 border-t border-zen-border bg-zen-surface/90 backdrop-blur-md relative z-10">
        <div className="flex justify-center items-center px-8">
          <div className="text-zen-text-muted text-[10px] font-bold uppercase tracking-widest text-center">
            © 2026 Stratos x CADMation. Engineered for Precision.
          </div>
        </div>
      </footer>
    </div>
  );
}
