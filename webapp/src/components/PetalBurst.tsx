import confetti from 'canvas-confetti';

export const triggerPetalBurst = (originX: number = 0.5, originY: number = 0.5) => {
  // Sakura petal colors: pinks, blush, white
  const colors = ['#FFB7C5', '#FFD1DC', '#FFE4EC', '#FFF0F5', '#E75480'];

  // Check prefers-reduced-motion
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  confetti({
    particleCount: 40,
    spread: 60,
    origin: { x: originX, y: originY },
    colors: colors,
    shapes: ['circle'],
    ticks: 160,
    gravity: 0.8,
    scalar: 1.1,
    drift: 0.2,
  });
};
