import React from 'react';

export const SakuraBranchTopRight: React.FC<{ className?: string }> = ({ className = '' }) => (
  <svg
    viewBox="0 0 240 120"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={`pointer-events-none select-none ${className}`}
  >
    {/* Branch stem */}
    <path
      d="M240 0C210 20 180 25 150 40C120 55 90 45 60 70C40 85 20 90 0 110"
      stroke="#8B5A6B"
      strokeWidth="3.5"
      strokeLinecap="round"
      opacity="0.75"
    />
    <path
      d="M170 32C150 15 130 10 110 5"
      stroke="#8B5A6B"
      strokeWidth="2.5"
      strokeLinecap="round"
      opacity="0.7"
    />
    <path
      d="M100 52C85 65 70 75 50 85"
      stroke="#8B5A6B"
      strokeWidth="2"
      strokeLinecap="round"
      opacity="0.65"
    />

    {/* Sakura blossoms */}
    {/* Flower 1 */}
    <g transform="translate(145, 38)">
      <circle cx="-6" cy="0" r="7" fill="#FFB7C5" opacity="0.9" />
      <circle cx="6" cy="0" r="7" fill="#FFB7C5" opacity="0.9" />
      <circle cx="0" cy="-6" r="7" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="6" r="7" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="0" r="4.5" fill="#FFE4EC" />
      <circle cx="0" cy="0" r="2" fill="#E75480" />
    </g>

    {/* Flower 2 */}
    <g transform="translate(105, 8)">
      <circle cx="-5" cy="0" r="6" fill="#FFB7C5" opacity="0.9" />
      <circle cx="5" cy="0" r="6" fill="#FFB7C5" opacity="0.9" />
      <circle cx="0" cy="-5" r="6" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="5" r="6" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="0" r="3.5" fill="#FFE4EC" />
      <circle cx="0" cy="0" r="1.5" fill="#E75480" />
    </g>

    {/* Flower 3 */}
    <g transform="translate(65, 68)">
      <circle cx="-6" cy="0" r="7.5" fill="#FFB7C5" opacity="0.9" />
      <circle cx="6" cy="0" r="7.5" fill="#FFB7C5" opacity="0.9" />
      <circle cx="0" cy="-6" r="7.5" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="6" r="7.5" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="0" r="5" fill="#FFE4EC" />
      <circle cx="0" cy="0" r="2.2" fill="#E75480" />
    </g>

    {/* Bud */}
    <ellipse cx="25" cy="98" rx="4" ry="6" fill="#FFB7C5" transform="rotate(-20 25 98)" opacity="0.85" />
    <ellipse cx="185" cy="18" rx="3" ry="5" fill="#FFD1DC" transform="rotate(30 185 18)" opacity="0.85" />
  </svg>
);

export const SakuraBranchEmptyState: React.FC<{ className?: string }> = ({ className = '' }) => (
  <svg
    viewBox="0 0 200 160"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={`mx-auto select-none ${className}`}
  >
    <path
      d="M20 140C60 120 90 90 120 70C150 50 170 30 190 10"
      stroke="#8B5A6B"
      strokeWidth="4"
      strokeLinecap="round"
      opacity="0.6"
    />
    <path
      d="M90 95C110 110 130 115 155 125"
      stroke="#8B5A6B"
      strokeWidth="3"
      strokeLinecap="round"
      opacity="0.55"
    />
    {/* Big central blossom */}
    <g transform="translate(118, 70)">
      <circle cx="-10" cy="-3" r="11" fill="#FFB7C5" opacity="0.9" />
      <circle cx="10" cy="-3" r="11" fill="#FFB7C5" opacity="0.9" />
      <circle cx="-6" cy="10" r="11" fill="#FFD1DC" opacity="0.9" />
      <circle cx="6" cy="10" r="11" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="-12" r="11" fill="#FFD1DC" opacity="0.9" />
      <circle cx="0" cy="0" r="7" fill="#FFE4EC" />
      <circle cx="0" cy="0" r="3" fill="#E75480" />
    </g>
    {/* Small flower */}
    <g transform="translate(155, 125)">
      <circle cx="-6" cy="0" r="7" fill="#FFB7C5" opacity="0.85" />
      <circle cx="6" cy="0" r="7" fill="#FFB7C5" opacity="0.85" />
      <circle cx="0" cy="-6" r="7" fill="#FFD1DC" opacity="0.85" />
      <circle cx="0" cy="6" r="7" fill="#FFD1DC" opacity="0.85" />
      <circle cx="0" cy="0" r="4" fill="#FFE4EC" />
      <circle cx="0" cy="0" r="1.8" fill="#E75480" />
    </g>
    {/* Floating single petal */}
    <path
      d="M60 40C70 35 75 45 70 55C65 65 55 55 55 45C55 40 55 40 60 40Z"
      fill="#FFB7C5"
      opacity="0.8"
    />
  </svg>
);
