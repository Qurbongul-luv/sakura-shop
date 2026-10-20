import React from 'react';
import { Category } from '../types';
import { haptic } from '../utils/telegram';

interface CategoryChipsProps {
  categories: Category[];
  selectedCategory: string | null;
  onSelectCategory: (slug: string | null) => void;
  allLabel: string;
}

export const CategoryChips: React.FC<CategoryChipsProps> = ({
  categories,
  selectedCategory,
  onSelectCategory,
  allLabel,
}) => {
  const handleClick = (slug: string | null) => {
    haptic.selection();
    onSelectCategory(slug);
  };

  return (
    <div className="flex items-center space-x-2 overflow-x-auto py-2.5 px-4 no-scrollbar">
      {/* "All" chip */}
      <button
        onClick={() => handleClick(null)}
        className={`flex items-center space-x-1.5 px-4 py-2 rounded-2xl text-xs font-bold whitespace-nowrap transition-all duration-200 shadow-sm active:scale-95 ${
          selectedCategory === null
            ? 'bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white shadow-sakura scale-105'
            : 'bg-white/80 dark:bg-sakura-darkcard/80 text-sakura-plum/80 dark:text-sakura-blush/80 border border-sakura-pink/30 hover:border-sakura-rose'
        }`}
      >
        <span>🌸</span>
        <span>#{allLabel}</span>
      </button>

      {/* Category items */}
      {categories.map((cat) => {
        const isSelected = selectedCategory === cat.slug;
        return (
          <button
            key={cat.slug}
            onClick={() => handleClick(cat.slug)}
            className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-2xl text-xs font-bold whitespace-nowrap transition-all duration-200 shadow-sm active:scale-95 ${
              isSelected
                ? 'bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white shadow-sakura scale-105'
                : 'bg-white/80 dark:bg-sakura-darkcard/80 text-sakura-plum/80 dark:text-sakura-blush/80 border border-sakura-pink/30 hover:border-sakura-rose'
            }`}
          >
            <span>{cat.emoji || '🌸'}</span>
            <span>#{cat.slug}</span>
            {cat.product_count > 0 && (
              <span
                className={`ml-1 text-[10px] px-1.5 py-0.2 rounded-full ${
                  isSelected ? 'bg-white/30 text-white' : 'bg-sakura-blush dark:bg-sakura-darkcardsoft text-sakura-rose'
                }`}
              >
                {cat.product_count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
