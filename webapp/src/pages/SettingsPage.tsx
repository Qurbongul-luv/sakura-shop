import React from 'react';
import { Globe, Sparkles, Send, ExternalLink, Shield, Package, Heart } from 'lucide-react';
import { ShopSettings } from '../types';
import { Language, Translations } from '../i18n';
import { openTelegramLink, haptic } from '../utils/telegram';
import { formatPrice } from '../utils/format';

interface SettingsPageProps {
  settings: ShopSettings;
  currentLang: Language;
  onLanguageChange: (lang: Language) => void;
  petalsEnabled: boolean;
  onTogglePetals: () => void;
  reducedMotion: boolean;
  onToggleReducedMotion: () => void;
  t: Translations;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
  settings,
  currentLang,
  onLanguageChange,
  petalsEnabled,
  onTogglePetals,
  reducedMotion,
  onToggleReducedMotion,
  t,
}) => {
  const languages: { code: Language; label: string; flag: string }[] = [
    { code: 'uz', label: "O'zbekcha", flag: '🇺🇿' },
    { code: 'ru', label: 'Русский', flag: '🇷🇺' },
    { code: 'en', label: 'English', flag: '🇬🇧' },
  ];

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      <div className="py-3">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white flex items-center gap-2">
          <span>⚙️</span>
          <span>{t.settings}</span>
        </h2>
      </div>

      {/* Language Selection Card */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
        <div className="flex items-center gap-2 mb-3 text-xs font-extrabold text-sakura-plum dark:text-white">
          <Globe className="w-4 h-4 text-sakura-rose" />
          <span>{t.languageSelect}</span>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {languages.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                haptic.selection();
                onLanguageChange(l.code);
              }}
              className={`py-2 px-3 rounded-2xl flex flex-col items-center justify-center gap-1 text-xs font-extrabold transition-all active:scale-95 ${
                currentLang === l.code
                  ? 'bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white shadow-sakura'
                  : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/30 text-sakura-plum dark:text-sakura-blush'
              }`}
            >
              <span className="text-base">{l.flag}</span>
              <span>{l.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Visual Effects Toggles */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
        <div className="flex items-center justify-between py-2 border-b border-sakura-pink/15">
          <div className="flex items-center gap-2">
            <span className="text-base">🌸</span>
            <span className="text-xs font-bold text-sakura-plum dark:text-white">{t.fallingPetals}</span>
          </div>
          <button
            onClick={() => {
              haptic.selection();
              onTogglePetals();
            }}
            className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ${
              petalsEnabled ? 'bg-sakura-rose' : 'bg-gray-300 dark:bg-gray-700'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-200 ${
                petalsEnabled ? 'translate-x-6' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        <div className="flex items-center justify-between py-2 mt-1">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-sakura-rose" />
            <span className="text-xs font-bold text-sakura-plum dark:text-white">{t.reducedMotion}</span>
          </div>
          <button
            onClick={() => {
              haptic.selection();
              onToggleReducedMotion();
            }}
            className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ${
              reducedMotion ? 'bg-sakura-rose' : 'bg-gray-300 dark:bg-gray-700'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-200 ${
                reducedMotion ? 'translate-x-6' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Official Links & Contact */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
        <h4 className="text-xs font-extrabold text-sakura-plum dark:text-white uppercase mb-2">
          Rasmiy kanallar 💌
        </h4>

        <div className="flex flex-col gap-2">
          <button
            onClick={() => openTelegramLink('https://t.me/sakuraaa_chinese_shop')}
            className="flex items-center justify-between p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft text-left hover:bg-sakura-blush/40 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-lg">📢</span>
              <div>
                <span className="text-xs font-extrabold block">Telegram Kanal</span>
                <span className="text-[11px] text-sakura-rose font-mono">@sakuraaa_chinese_shop</span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-sakura-rose/70" />
          </button>

          <button
            onClick={() => openTelegramLink(`https://t.me/${(settings.contact_username || 'fkhrdnvvvva').replace('@', '')}`)}
            className="flex items-center justify-between p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft text-left hover:bg-sakura-blush/40 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-lg">💌</span>
              <div>
                <span className="text-xs font-extrabold block">Do'kon egasi & Buyurtmalar</span>
                <span className="text-[11px] text-sakura-rose font-mono">@{settings.contact_username || 'fkhrdnvvvva'}</span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-sakura-rose/70" />
          </button>
        </div>
      </div>

      {/* Store Terms Info */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm text-xs text-sakura-plum/80 dark:text-sakura-blush/80 space-y-1.5">
        <div className="font-extrabold text-sakura-rose flex items-center gap-1.5 mb-1">
          <Heart className="w-3.5 h-3.5 fill-sakura-rose" />
          <span>Sakura shop haqida</span>
        </div>
        <p>📦 Kargo narxi: {formatPrice(settings.cargo_rate || 12000)} / 100g</p>
        <p>⏳ Yetkazib berish muddati: {settings.delivery_days || "10–15 kun"}</p>
        <p>🚚 Dastavka: {settings.delivery_scope || "O'zbekiston bo'ylab"}</p>
        <p>💳 To'lov: {settings.payment_terms || "100% oldindan to'lov"}</p>
        <p>📍 Joylashuv: {settings.location || "Toshkent"}</p>
      </div>

      <div className="text-center mt-6 text-[10px] text-sakura-plum/40 dark:text-sakura-blush/40">
        Sakura Shop Mini App v1.0.0 🌸
      </div>
    </div>
  );
};
