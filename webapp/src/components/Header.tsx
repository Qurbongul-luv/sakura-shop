import React from 'react';
import { Search, Globe, Sparkles } from 'lucide-react';
import { PetalCanvas } from './PetalCanvas';
import { SakuraBranchTopRight } from './SakuraBranches';
import { Language, translations } from '../i18n';

interface HeaderProps {
  lang: Language;
  onLanguageChange: (lang: Language) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  petalsEnabled: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onLanguageChange,
  searchQuery,
  onSearchChange,
  petalsEnabled,
}) => {
  const t = translations[lang];

  const cycleLanguage = () => {
    const next: Record<Language, Language> = { uz: 'ru', ru: 'en', en: 'uz' };
    onLanguageChange(next[lang]);
  };

  return (
    <header className="relative bg-gradient-to-b from-sakura-blush via-sakura-blush/90 to-sakura-cream dark:from-sakura-darkcard dark:via-sakura-darkbg dark:to-sakura-darkbg pt-3 pb-4 px-4 shadow-sakura-sm overflow-hidden border-b border-sakura-pink/20">
      {/* Drifting Petals Canvas */}
      <PetalCanvas enabled={petalsEnabled} />

      {/* SVG Decorative Branch Top Right */}
      <SakuraBranchTopRight className="absolute -top-2 -right-4 w-44 h-24 opacity-80 z-0" />

      {/* Top row: Brand & Language Toggle */}
      <div className="relative z-20 flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-2xl filter drop-shadow-sm animate-pulse">🌸</span>
          <div>
            <h1 className="font-logo text-2xl sm:text-3xl font-normal text-sakura-darkrose dark:text-sakura-pink tracking-wide leading-none">
              {t.shopName}
            </h1>
            <p className="text-[11px] font-medium text-sakura-plum/80 dark:text-sakura-blush/80 mt-0.5 flex items-center gap-1">
              <span>{t.tagline}</span>
            </p>
          </div>
        </div>

        {/* Language Pill */}
        <button
          onClick={cycleLanguage}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-white/80 dark:bg-sakura-darkcardsoft/90 backdrop-blur-md border border-sakura-pink/40 text-xs font-bold text-sakura-plum dark:text-sakura-blush shadow-sm active:scale-95 transition-transform"
          title="Switch Language"
        >
          <Globe className="w-3.5 h-3.5 text-sakura-rose" />
          <span className="uppercase">{lang}</span>
        </button>
      </div>

      {/* Search Input Bar */}
      <div className="relative z-20">
        <div className="relative flex items-center">
          <Search className="absolute left-3.5 w-4 h-4 text-sakura-rose/70 dark:text-sakura-pink/70" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t.searchPlaceholder}
            className="w-full pl-10 pr-9 py-2.5 rounded-2xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 text-sm text-sakura-plum dark:text-white placeholder:text-sakura-plum/40 dark:placeholder:text-sakura-blush/40 focus:outline-none focus:ring-2 focus:ring-sakura-pink shadow-sm transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3 text-xs text-sakura-plum/50 hover:text-sakura-rose font-bold px-1"
            >
              ✕
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
