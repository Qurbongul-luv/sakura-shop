import React from 'react';
import { SakuraBranchEmptyState } from './SakuraBranches';

interface EmptyStateProps {
  title: string;
  subtitle?: string;
  actionButton?: {
    text: string;
    onClick: () => void;
  };
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, subtitle, actionButton }) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center my-8">
      <div className="w-48 h-36 mb-4 relative">
        <SakuraBranchEmptyState className="w-full h-full" />
      </div>
      <h3 className="text-xl font-bold text-sakura-plum dark:text-sakura-pink mb-1">{title}</h3>
      {subtitle && <p className="text-sm text-sakura-plum/70 dark:text-sakura-blush/70 max-w-xs mb-6">{subtitle}</p>}
      {actionButton && (
        <button
          onClick={actionButton.onClick}
          className="px-6 py-2.5 rounded-2xl bg-gradient-to-r from-sakura-pink to-sakura-rose text-white font-semibold text-sm shadow-sakura hover:opacity-95 transition-transform active:scale-95"
        >
          {actionButton.text}
        </button>
      )}
    </div>
  );
};
