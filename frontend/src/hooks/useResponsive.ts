/**
 * Responsive layout hook.
 *
 * Tracks the current viewport width and classifies it into desktop / tablet
 * tiers so components can adapt their layout fluidly without horizontal
 * scrolling (Req 12.5, 12.6).
 */

import { useEffect, useState } from 'react';

import { BREAKPOINTS } from '../theme/tokens';

export type ViewportTier = 'tablet' | 'desktop';

export interface ResponsiveState {
  width: number;
  tier: ViewportTier;
  isTablet: boolean;
  isDesktop: boolean;
}

const getWidth = (): number =>
  typeof window === 'undefined' ? BREAKPOINTS.desktop : window.innerWidth;

const classify = (width: number): ViewportTier =>
  width >= BREAKPOINTS.desktop ? 'desktop' : 'tablet';

export const useResponsive = (): ResponsiveState => {
  const [width, setWidth] = useState<number>(getWidth);

  useEffect(() => {
    let frame = 0;
    const handleResize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setWidth(getWidth()));
    };
    window.addEventListener('resize', handleResize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const tier = classify(width);
  return {
    width,
    tier,
    isTablet: tier === 'tablet',
    isDesktop: tier === 'desktop',
  };
};
