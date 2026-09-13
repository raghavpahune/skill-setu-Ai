import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useTour } from '../context/TourContext';

export default function DemoTour() {
  const location = useLocation();
  const {
    isTourOpen,
    currentStepIndex,
    currentStep,
    totalSteps,
    nextStep,
    prevStep,
    exitTour,
  } = useTour();

  const [targetRect, setTargetRect] = useState(null);
  const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0, placement: 'bottom' });
  const popoverRef = useRef(null);

  // Position calculation and scroll synchronization
  const updatePosition = useCallback(() => {
    if (!isTourOpen || !currentStep) return;

    if (!currentStep.targetSelector) {
      setTargetRect(null);
      return;
    }

    // Verify route synchronization before finding target
    const expectedRoute = currentStep.route ? currentStep.route.split('?')[0] : null;
    if (expectedRoute && location.pathname !== expectedRoute) {
      setTargetRect(null);
      return;
    }

    const el = document.querySelector(currentStep.targetSelector);
    if (el) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setTargetRect({
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
          bottom: rect.bottom,
          right: rect.right,
        });

        // Determine exact popover dimensions
        const measuredHeight = popoverRef.current ? popoverRef.current.offsetHeight : 240;
        const popoverWidth = Math.min(460, window.innerWidth - 32);
        const padding = 16;

        let left = Math.max(
          16,
          Math.min(
            rect.left + (rect.width / 2) - (popoverWidth / 2),
            window.innerWidth - popoverWidth - 16
          )
        );

        let top;
        let placement = 'bottom';

        const spaceBelow = window.innerHeight - rect.bottom;
        const spaceAbove = rect.top - 60; // 60px reserved for sticky navbar

        // 1. Check if fits cleanly below
        if (spaceBelow >= measuredHeight + padding) {
          top = rect.bottom + padding;
          placement = 'bottom';
        }
        // 2. Check if fits cleanly above
        else if (spaceAbove >= measuredHeight + padding) {
          top = rect.top - measuredHeight - padding;
          placement = 'top';
        }
        // 3. If element is very tall and spans most of the screen vertically:
        else {
          top = Math.max(16, window.innerHeight - measuredHeight - 16);
          // On desktop, dock to right side so center of element remains visible
          if (window.innerWidth >= 1024) {
            left = Math.min(window.innerWidth - popoverWidth - 24, Math.max(24, rect.right - popoverWidth));
          }
          placement = 'bottom';
        }

        // Final safety clamp: popover MUST NEVER overflow bottom of viewport
        top = Math.max(16, Math.min(top, window.innerHeight - measuredHeight - 16));

        setPopoverPos({ top, left, placement });
        return;
      }
    }
    setTargetRect(null);
  }, [isTourOpen, currentStep, location.pathname]);

  // Auto-scroll to element and continuously track position across layout shifts / smooth scrolls
  useEffect(() => {
    if (!isTourOpen || !currentStep) return;

    const expectedRoute = currentStep.route ? currentStep.route.split('?')[0] : null;
    let attempts = 0;
    const maxAttempts = 40; // 4s total search window for async rendered components

    const alignAndTrack = () => {
      attempts += 1;

      // Check route synchronization first
      if (expectedRoute && location.pathname !== expectedRoute) {
        setTargetRect(null);
        if (currentStepIndex === 4) {
          console.log('[Tour Step 5] Waiting for route transition:', {
            currentRoute: location.pathname,
            expectedRoute,
          });
        }
        return;
      }

      if (!currentStep.targetSelector) {
        setTargetRect(null);
        return;
      }

      const el = document.querySelector(currentStep.targetSelector);
      if (el) {
        const rect = el.getBoundingClientRect();

        // Step 5 Instrumentation / Logging
        if (currentStepIndex === 4) {
          console.log('=== TOUR STEP 5 DEBUG ===');
          console.log('TOUR STEP = 5');
          console.log('CURRENT ROUTE =', location.pathname);
          console.log('EXPECTED ROUTE =', expectedRoute);
          console.log('TARGET SELECTOR =', currentStep.targetSelector);
          console.log('TARGET FOUND =', true);
          console.log('TARGET RECT =', rect);
          console.log('TARGET HEIGHT =', rect.height);
          console.log('TARGET TOP =', rect.top);
          console.log('TARGET BOTTOM =', rect.bottom);
          console.log('SCROLL POSITION =', window.pageYOffset);
        }

        if (rect.width > 0 && rect.height > 0) {
          // Calculate optimal scroll target so that BOTH the element and the popover fit in the viewport
          let targetY;
          if (rect.height + 260 + 80 <= window.innerHeight) {
            // Align element top comfortably below sticky navbar (64px)
            targetY = el.getBoundingClientRect().top + window.pageYOffset - 64;
          } else if (rect.height > window.innerHeight * 0.45) {
            // Tall element: scroll top of element to 64px
            targetY = el.getBoundingClientRect().top + window.pageYOffset - 64;
          } else {
            targetY = el.getBoundingClientRect().top + window.pageYOffset - Math.max(64, (window.innerHeight - rect.height - 260) / 2);
          }

          // If the element's top is not in the desired position [50..90px], smoothly scroll
          const isMisaligned = rect.top < 50 || rect.top > 90;
          if (isMisaligned && Math.abs(window.pageYOffset - targetY) > 15) {
            window.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
          }

          updatePosition();
        }
      } else {
        if (currentStepIndex === 4) {
          console.log('=== TOUR STEP 5 DEBUG ===');
          console.log('TOUR STEP = 5');
          console.log('CURRENT ROUTE =', location.pathname);
          console.log('EXPECTED ROUTE =', expectedRoute);
          console.log('TARGET SELECTOR =', currentStep.targetSelector);
          console.log('TARGET FOUND =', false);
        }
        if (attempts >= maxAttempts) {
          setTargetRect(null);
        }
      }
    };

    // Run polling interval for smooth transition
    const interval = setInterval(alignAndTrack, 100);

    // Also observe DOM and body resize events to handle async data loading shifts
    const resizeObserver = new ResizeObserver(() => {
      updatePosition();
      const el = currentStep.targetSelector ? document.querySelector(currentStep.targetSelector) : null;
      if (el) {
        const rect = el.getBoundingClientRect();
        if (rect.top < 50 || rect.top > 90) {
          const targetY = el.getBoundingClientRect().top + window.pageYOffset - 64;
          window.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
        }
      }
    });

    resizeObserver.observe(document.body);

    return () => {
      clearInterval(interval);
      resizeObserver.disconnect();
    };
  }, [isTourOpen, currentStepIndex, currentStep, location.pathname, updatePosition]);

  // Handle window resize and all container scrolls (capture phase)
  useEffect(() => {
    if (!isTourOpen) return;
    const handleScrollOrResize = () => updatePosition();
    window.addEventListener('resize', handleScrollOrResize);
    window.addEventListener('scroll', handleScrollOrResize, { capture: true, passive: true });
    return () => {
      window.removeEventListener('resize', handleScrollOrResize);
      window.removeEventListener('scroll', handleScrollOrResize, { capture: true });
    };
  }, [isTourOpen, updatePosition]);

  if (!isTourOpen || !currentStep) return null;

  const isLastStep = currentStepIndex === totalSteps - 1;
  const progressPct = Math.round(((currentStepIndex + 1) / totalSteps) * 100);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto pointer-events-auto font-sans">
      {/* Semi-Transparent Dimmed Backdrop with Crisp Cutout (Zero Blur) */}
      <svg
        className="fixed inset-0 w-full h-full pointer-events-none z-40 transition-opacity duration-300"
        style={{ width: '100vw', height: '100vh' }}
        aria-hidden="true"
      >
        <defs>
          <mask id="tour-spotlight-cutout">
            {/* White reveals the dark overlay everywhere */}
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {/* Black cuts a hole out for the active element, leaving it 100% bright & crisp */}
            {targetRect && (
              <rect
                x={targetRect.left - 6}
                y={targetRect.top - 6}
                width={targetRect.width + 12}
                height={targetRect.height + 12}
                rx="12"
                ry="12"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(2, 6, 23, 0.55)"
          mask="url(#tour-spotlight-cutout)"
        />
      </svg>

      {/* Backdrop Click Handler to Exit Tour */}
      <div
        onClick={exitTour}
        className="fixed inset-0 z-30 cursor-default"
        aria-label="Click to exit tour"
      />

      {/* Target Element Spotlight (Border & Subtle Ambient Glow) */}
      {targetRect && (
        <div
          style={{
            position: 'fixed',
            top: targetRect.top - 6,
            left: targetRect.left - 6,
            width: targetRect.width + 12,
            height: targetRect.height + 12,
          }}
          className="rounded-xl ring-2 ring-teal-400 border border-teal-300/60 shadow-[0_0_25px_rgba(45,212,191,0.35)] pointer-events-none transition-all duration-300 z-40"
        />
      )}

      {/* Optional Full Ecosystem Summary Modal (Centered) */}
      {currentStep.isSummary ? (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-50">
          <div
            ref={popoverRef}
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full p-6 sm:p-8 animate-scale-in max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-teal-700 to-emerald-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
                  ✓
                </div>
                <div>
                  <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-teal-600 dark:text-teal-400">
                    Step {currentStep.step} of {totalSteps} • {currentStep.stage}
                  </span>
                  <h3 className="text-xl font-black text-slate-900 dark:text-white">
                    {currentStep.title}
                  </h3>
                </div>
              </div>
              <button
                onClick={exitTour}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                aria-label="Exit SIH Demo Tour"
              >
                ✕
              </button>
            </div>

            {/* Continuous Feedback Loop Infographic */}
            <div className="mt-5 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80">
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 text-center">
                The Complete SkillSetuAI Intelligence Feedback Loop
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-2xs">
                  <div className="text-base mb-1">📡</div>
                  <div className="font-bold text-slate-900 dark:text-white">1. Labour Demand</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Live Job Sensing</div>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-2xs">
                  <div className="text-base mb-1">⚡</div>
                  <div className="font-bold text-slate-900 dark:text-white">2. Skill Deficits</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Automated Gaps</div>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-2xs">
                  <div className="text-base mb-1">🎓</div>
                  <div className="font-bold text-slate-900 dark:text-white">3. Institutes</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Curriculum Update</div>
                </div>
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-2xs">
                  <div className="text-base mb-1">🏢</div>
                  <div className="font-bold text-slate-900 dark:text-white">4. Employers</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">Human Validation</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs mt-2">
                <div className="p-2.5 rounded-lg bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 shadow-2xs">
                  <div className="text-base mb-1">🎯</div>
                  <div className="font-bold text-teal-900 dark:text-teal-200">5. Student Action</div>
                  <div className="text-[10px] text-teal-700 dark:text-teal-400 mt-0.5">5D Explainability</div>
                </div>
                <div className="p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 shadow-2xs">
                  <div className="text-base mb-1">🧪</div>
                  <div className="font-bold text-indigo-900 dark:text-indigo-200">6. Policy Simulator</div>
                  <div className="text-[10px] text-indigo-700 dark:text-indigo-400 mt-0.5">What-If Models</div>
                </div>
                <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 shadow-2xs">
                  <div className="text-base mb-1">📈</div>
                  <div className="font-bold text-emerald-900 dark:text-emerald-200">7. Impact</div>
                  <div className="text-[10px] text-emerald-700 dark:text-emerald-400 mt-0.5">Higher Placement</div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <button
                onClick={prevStep}
                className="px-4 py-2 text-xs font-semibold rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
              >
                ← Previous Step
              </button>
              <button
                onClick={exitTour}
                className="px-6 py-2.5 text-xs font-bold rounded-lg bg-teal-600 hover:bg-teal-700 text-white shadow-md transition-colors"
              >
                Complete SIH Demo Tour 🎉
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Standard Floating Popover Attached to Target */
        <div
          ref={popoverRef}
          style={
            targetRect
              ? {
                  position: 'fixed',
                  top: popoverPos.top,
                  left: popoverPos.left,
                  transform: 'none',
                  width: 'min(460px, calc(100vw - 32px))',
                  maxHeight: 'calc(100vh - 32px)',
                }
              : {
                  position: 'fixed',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: 'min(460px, calc(100vw - 32px))',
                  maxHeight: 'calc(100vh - 32px)',
                }
          }
          className="z-50 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl p-4 sm:p-5 animate-fade-in transition-all duration-200 pointer-events-auto"
        >
          {/* Header (Fixed at top of card) */}
          <div className="shrink-0 flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-400 font-mono text-[10px] font-bold border border-teal-200 dark:border-teal-800">
                Step {currentStep.step} of {totalSteps}
              </span>
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 truncate max-w-[200px]">
                {currentStep.stage}
              </span>
            </div>
            <button
              onClick={exitTour}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs px-1.5 py-0.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              title="Exit Tour (Esc)"
            >
              ✕
            </button>
          </div>

          {/* Progress Bar (Fixed) */}
          <div className="shrink-0 w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden mb-3">
            <div
              className="bg-gradient-to-r from-teal-500 to-emerald-400 h-full rounded-full transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {/* Scrollable Content Body (Shrinks/scrolls gracefully on small viewports) */}
          <div className="flex-1 overflow-y-auto min-h-0 pr-1 mb-3 space-y-2.5">
            <h4 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white leading-tight">
              {currentStep.title}
            </h4>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              {currentStep.description}
            </p>
            <div className="p-2.5 rounded-lg bg-amber-50/80 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/40 text-[11px] text-amber-900 dark:text-amber-200 leading-snug">
              <span className="font-bold">Why it matters: </span>
              {currentStep.whyItMatters}
            </div>
          </div>

          {/* Fixed Footer Navigation Controls (ALWAYS 100% VISIBLE & CLICKABLE) */}
          <div className="shrink-0 pt-2.5 border-t border-slate-100 dark:border-slate-800 text-xs">
            <div className="flex items-center justify-between">
              <button
                onClick={exitTour}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-medium transition-colors cursor-pointer"
              >
                Skip Tour
              </button>

              <div className="flex items-center gap-2">
                {currentStepIndex > 0 && (
                  <button
                    onClick={prevStep}
                    className="px-3 py-1.5 font-semibold rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                  >
                    Back
                  </button>
                )}
                <button
                  onClick={isLastStep ? exitTour : nextStep}
                  className="px-4 py-1.5 font-bold rounded-lg bg-teal-600 hover:bg-teal-700 text-white shadow-xs transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <span>{isLastStep ? 'Finish Tour ✓' : 'Next'}</span>
                  {!isLastStep && <span>→</span>}
                </button>
              </div>
            </div>

            {/* Keyboard hint */}
            <div className="mt-2 text-[10px] text-slate-400 dark:text-slate-500 text-center font-mono flex items-center justify-center gap-3">
              <span>[← / →] Navigate</span>
              <span>•</span>
              <span>[Esc] Exit</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
